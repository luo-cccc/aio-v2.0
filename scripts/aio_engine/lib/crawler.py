"""
异步页面抓取器 (aiohttp + html.parser.HTMLParser)
=================================================
抓取原始 HTML 并提取基础元数据，不依赖外部解析库。
"""

import asyncio
import ipaddress
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

import aiohttp


def validate_url(url: str) -> bool:
    """验证 URL 安全性：阻止 SSRF、内网地址、非 HTTP(S) scheme、@ 注入、非标准端口。"""
    try:
        parsed = urlparse(url)
    except (ValueError, TypeError):
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # 阻止 URL 中携带 credentials（@ 注入）
    if parsed.username is not None or parsed.password is not None:
        return False

    # 阻止非标准端口（只允许 80/443）
    if parsed.port is not None and parsed.port not in (80, 443):
        return False

    # 阻止纯 IP 内网/回环/链路本地地址
    try:
        ip = ipaddress.ip_address(hostname)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_link_local
        ):
            return False
    except ValueError:
        pass  # 是域名而非 IP，继续检查

    # 阻止常见内网主机名
    blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
    if hostname.lower() in blocked_hosts:
        return False

    return True


from .session_utils import NullContextManager

class _MetaParser(HTMLParser):
    """轻量级 HTML 元数据提取器。"""

    def __init__(self):
        super().__init__()
        self.title: Optional[str] = None
        self.description: Optional[str] = None
        self.canonical: Optional[str] = None
        self.og_type: Optional[str] = None
        self.json_ld_scripts: List[str] = []
        self.images: List[dict] = []
        self.videos: List[dict] = []
        self.links: List[str] = []
        self.headings: List[dict] = []  # {"level": int, "text": str}
        self._in_title = False
        self._title_buf: List[str] = []
        self._capture_json_ld = False
        self._json_ld_buf: List[str] = []
        self._current_heading_level: Optional[int] = None
        self._heading_buf: List[str] = []
        self._current_video: Optional[dict] = None

    def handle_starttag(self, tag: str, attrs: list):
        attr = dict(attrs)
        lower_tag = tag.lower()

        if lower_tag == "title":
            self._in_title = True
            return

        if lower_tag == "meta":
            name = attr.get("name", "").lower()
            prop = attr.get("property", "").lower()
            content = attr.get("content", "")
            if name == "description":
                self.description = content
            elif prop == "og:type":
                self.og_type = content
            return

        if lower_tag == "link":
            rel = attr.get("rel", "").lower()
            href = attr.get("href", "")
            if rel == "canonical":
                self.canonical = href
            return

        if lower_tag == "script":
            type_ = attr.get("type", "").lower()
            if type_ == "application/ld+json":
                self._capture_json_ld = True
                self._json_ld_buf: List[str] = []
            return

        if lower_tag == "img":
            src = attr.get("src", "")
            if src:
                self.images.append({"src": src, "alt": attr.get("alt", "")})
            return

        if lower_tag == "video":
            src = attr.get("src", "")
            self._current_video = {"type": "html5", "title": attr.get("title", "")}
            if src:
                self.videos.append({"src": src, "type": "html5", "title": attr.get("title", "")})
            return

        if lower_tag == "source":
            src = attr.get("src", "")
            if src:
                parent = getattr(self, "_current_video", None)
                vtype = "html5"
                title = ""
                if parent:
                    vtype = parent.get("type", "html5")
                    title = parent.get("title", "")
                self.videos.append({"src": src, "type": vtype, "title": title})
            return

        if lower_tag == "iframe":
            src = attr.get("src", "")
            if src:
                vtype = self._detect_iframe_video_type(src)
                self.videos.append({"src": src, "type": vtype, "title": attr.get("title", "")})
            return

        if lower_tag == "a":
            href = attr.get("href", "")
            if href:
                self.links.append(href)
            return

        # 提取 heading 标签
        if lower_tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            # 保存之前的 heading
            if self._current_heading_level is not None and self._heading_buf:
                self.headings.append({
                    "level": self._current_heading_level,
                    "text": "".join(self._heading_buf).strip(),
                })
            self._current_heading_level = int(lower_tag[1])
            self._heading_buf = []
            return

    def handle_endtag(self, tag: str):
        lower_tag = tag.lower()
        if lower_tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_buf).strip()

        if lower_tag == "script" and self._capture_json_ld:
            self._capture_json_ld = False
            self.json_ld_scripts.append("".join(self._json_ld_buf))

        if lower_tag == "video":
            self._current_video = None

        # 保存 heading
        if lower_tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            if self._current_heading_level is not None and self._heading_buf:
                self.headings.append({
                    "level": self._current_heading_level,
                    "text": "".join(self._heading_buf).strip(),
                })
            self._current_heading_level = None
            self._heading_buf = []

    def handle_data(self, data: str):
        if self._in_title:
            self._title_buf.append(data)
        if self._capture_json_ld:
            self._json_ld_buf.append(data)
        if self._current_heading_level is not None:
            self._heading_buf.append(data)

    @staticmethod
    def _detect_iframe_video_type(src: str) -> str:
        if "youtube.com" in src or "youtu.be" in src:
            return "youtube"
        if "bilibili.com" in src:
            return "bilibili"
        if "vimeo.com" in src:
            return "vimeo"
        return "iframe"


class Crawler:
    """
    异步抓取指定 URL 的 HTML，解析基础元数据。
    支持外部传入 aiohttp.ClientSession 以复用连接池。
    """

    def __init__(self, timeout: Optional[int] = None, session: Optional[aiohttp.ClientSession] = None):
        from .config import ConfigLoader
        cfg = ConfigLoader.get("crawler", default={})
        effective_timeout = timeout if timeout is not None else cfg.get("timeout", 30)
        self._timeout = aiohttp.ClientTimeout(total=effective_timeout)
        self._session = session

    def _session_ctx(self):
        """返回 session 上下文管理器：若已传入外部 session 则直接 yield，否则新建。"""
        if self._session is not None:
            return NullContextManager(self._session)
        return aiohttp.ClientSession(timeout=self._timeout)

    async def fetch(self, url: str) -> dict:
        """
        抓取页面并返回解析后的数据字典。

        返回字段:
            - url: 最终 URL（跟随重定向后）
            - html: 原始 HTML 文本
            - title: <title> 内容
            - description: meta description
            - canonical: canonical link
            - og_type: OpenGraph type
            - json_ld_scripts: List[str] 页面内所有 JSON-LD 脚本
            - images: List[dict] 图片（绝对 URL + alt）
            - videos: List[dict] 视频（绝对 URL + type）
            - links: List[str] 页面内链接（绝对 URL）
            - headings: List[dict] heading 结构 {"level": int, "text": str}
            - content_blocks: List[dict] 按 heading 分段的内容块
            - has_ssr: bool 是否有服务端渲染内容
        """
        if not validate_url(url):
            raise ValueError(f"URL 未通过安全验证: {url}")

        async with self._session_ctx() as session:
            async with session.get(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }) as resp:
                resp.raise_for_status()
                html = await resp.text()
                final_url = str(resp.url)
                resp_headers = dict(resp.headers)

        parser = _MetaParser()
        parser.feed(html)

        # 将相对 URL 转为绝对 URL
        def abs_url(u: str) -> str:
            joined = urljoin(final_url, u)
            scheme = urlparse(joined).scheme
            if scheme not in ("http", "https"):
                return u
            return joined

        # 提取内容块
        content_blocks = self.extract_content_blocks(html)

        # SSR 检测
        has_ssr = self._detect_ssr(html, content_blocks)

        return {
            "url": final_url,
            "html": html,
            "headers": resp_headers,
            "title": parser.title or "",
            "description": parser.description or "",
            "canonical": parser.canonical or "",
            "og_type": parser.og_type or "",
            "json_ld_scripts": parser.json_ld_scripts,
            "images": [{"src": abs_url(img["src"]), "alt": img["alt"]} for img in parser.images],
            "videos": [{**v, "src": abs_url(v["src"])} for v in parser.videos],
            "links": [abs_url(u) for u in parser.links],
            "headings": parser.headings,
            "content_blocks": content_blocks,
            "has_ssr": has_ssr,
        }

    @staticmethod
    def extract_content_blocks(html: str) -> List[dict]:
        """按 heading 分段提取内容块，供 citability 评分使用。"""
        # 移除 script/style/nav/footer/header/aside
        text = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", " ", html, flags=re.I)
        text = re.sub(r"<style\b[^>]*>[\s\S]*?</style>", " ", text, flags=re.I)
        text_no_tags = re.sub(r"<[^>]+>", " ", text)
        text_no_tags = re.sub(r"\s+", " ", text_no_tags).strip()
        total_words = len(text_no_tags.split())

        # 用简单正则按 heading 分段
        heading_pattern = re.compile(r"<(h[1-6])\b[^>]*>(.*?)</\1>", re.I | re.S)
        headings = list(heading_pattern.finditer(html))

        blocks = []
        if not headings:
            # 没有 heading，整页作为一个块
            if total_words >= 20:
                blocks.append({
                    "heading": None,
                    "content": text_no_tags,
                    "word_count": total_words,
                })
            return blocks

        for i, match in enumerate(headings):
            level = int(match.group(1)[1])
            heading_text = re.sub(r"<[^>]+>", "", match.group(2)).strip()

            # 提取该 heading 到下一个 heading 之间的内容
            start = match.end()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(html)
            segment = html[start:end]

            # 移除标签后提取文本
            segment_text = re.sub(r"<[^>]+>", " ", segment)
            segment_text = re.sub(r"\s+", " ", segment_text).strip()
            word_count = len(segment_text.split())

            if word_count >= 20:
                blocks.append({
                    "heading": heading_text,
                    "content": segment_text,
                    "word_count": word_count,
                })

        return blocks

    @staticmethod
    def _detect_ssr(html: str, content_blocks: List[dict]) -> bool:
        """检测页面是否有服务端渲染内容。"""
        # 检查是否有 JS 框架根节点
        js_roots = re.findall(r'<[^>]+\bid=["\'](?:app|root|__next|__nuxt)["\']', html, re.I)
        if not js_roots:
            # 没有 JS 框架根节点，认为是 SSR
            return True

        # 有 JS 框架根节点，检查内容块总字数
        total_words = sum(b["word_count"] for b in content_blocks)
        return total_words >= 200

    async def fetch_robots_txt(self, url: str) -> dict:
        """抓取并解析 robots.txt，返回 AI 爬虫状态。"""
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        ai_crawlers = [
            "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot",
            "anthropic-ai", "PerplexityBot", "CCBot", "Bytespider",
            "cohere-ai", "Google-Extended", "GoogleOther",
            "Applebot-Extended", "FacebookBot", "Amazonbot",
        ]

        result = {
            "url": robots_url,
            "exists": False,
            "content": "",
            "ai_crawler_status": {},
            "sitemaps": [],
            "errors": [],
        }

        try:
            async with self._session_ctx() as session:
                async with session.get(robots_url, headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                }) as resp:
                    if resp.status == 200:
                        result["exists"] = True
                        content = await resp.text()
                        result["content"] = content
                        result.update(self._parse_robots_txt(content, ai_crawlers))
                    elif resp.status == 404:
                        result["errors"].append("No robots.txt found (404)")
                        for crawler in ai_crawlers:
                            result["ai_crawler_status"][crawler] = "NO_ROBOTS_TXT"
                    else:
                        result["errors"].append(f"Unexpected status: {resp.status}")
        except aiohttp.ClientError as e:
            result["errors"].append(f"网络请求失败: {e}")
        except (OSError, ValueError) as e:
            result["errors"].append(str(e))

        return result

    @staticmethod
    def _parse_robots_txt(content: str, ai_crawlers: List[str]) -> dict:
        """解析 robots.txt 内容，返回 AI 爬虫状态。"""
        lines = content.split("\n")
        agent_rules: Dict[str, List[dict]] = {}
        current_agent = None
        sitemaps = []

        for line in lines:
            line = line.strip()
            if line.lower().startswith("user-agent:"):
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                current_agent = parts[1].strip()
                if current_agent not in agent_rules:
                    agent_rules[current_agent] = []
            elif line.lower().startswith("disallow:") and current_agent:
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                path = parts[1].strip()
                agent_rules[current_agent].append({"directive": "Disallow", "path": path})
            elif line.lower().startswith("allow:") and current_agent:
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                path = parts[1].strip()
                agent_rules[current_agent].append({"directive": "Allow", "path": path})
            elif line.lower().startswith("sitemap:"):
                parts = line.split(":", 1)
                if len(parts) < 2:
                    continue
                sitemap_url = parts[1].strip()
                if not sitemap_url.startswith(("http://", "https://")):
                    sitemap_url = "http://" + sitemap_url.lstrip("/:")
                sitemaps.append(sitemap_url)

        ai_crawler_status = {}
        for crawler in ai_crawlers:
            if crawler in agent_rules:
                rules = agent_rules[crawler]
                if any(r["directive"] == "Disallow" and r["path"] == "/" for r in rules):
                    ai_crawler_status[crawler] = "BLOCKED"
                elif any(r["directive"] == "Disallow" and r["path"] for r in rules):
                    ai_crawler_status[crawler] = "PARTIALLY_BLOCKED"
                else:
                    ai_crawler_status[crawler] = "ALLOWED"
            elif "*" in agent_rules:
                wildcard_rules = agent_rules["*"]
                if any(r["directive"] == "Disallow" and r["path"] == "/" for r in wildcard_rules):
                    ai_crawler_status[crawler] = "BLOCKED_BY_WILDCARD"
                else:
                    ai_crawler_status[crawler] = "ALLOWED_BY_DEFAULT"
            else:
                ai_crawler_status[crawler] = "NOT_MENTIONED"

        return {
            "ai_crawler_status": ai_crawler_status,
            "sitemaps": sitemaps,
        }

    async def fetch_llms_txt(self, url: str) -> dict:
        """检查 llms.txt 和 llms-full.txt 的存在性。"""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        llms_url = f"{base_url}/llms.txt"
        llms_full_url = f"{base_url}/llms-full.txt"

        result = {
            "llms_txt": {"url": llms_url, "exists": False, "content": ""},
            "llms_full_txt": {"url": llms_full_url, "exists": False, "content": ""},
            "errors": [],
        }

        for key, check_url in [("llms_txt", llms_url), ("llms_full_txt", llms_full_url)]:
            try:
                async with self._session_ctx() as session:
                    async with session.get(check_url, headers={
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/120.0.0.0 Safari/537.36"
                        )
                    }) as resp:
                        if resp.status == 200:
                            result[key]["exists"] = True
                            result[key]["content"] = await resp.text()
            except aiohttp.ClientError as e:
                result["errors"].append(f"网络请求失败: {e}")
            except (OSError, ValueError) as e:
                result["errors"].append(str(e))

        return result
