"""
多模态内容标签器
================
分析页面图片和视频，检测 alt 属性问题，生成 VideoObject Schema。
"""

import re
from typing import List

import aiohttp

from ..lib.llm_client import LLMClient
from ..lib.crawler import Crawler
from ..lib.json_utils import parse_json_object


class MultimodalLabeler:
    """
    分析页面中的图片和视频资源。
    """

    _SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

    def __init__(self, llm: LLMClient, crawler: Crawler):
        self._llm = llm
        self._crawler = crawler

    async def analyze(self, images: List[dict], videos: List[dict]) -> dict:
        """
        分析图片 alt 文本和视频 Schema。

        返回标准模块结果格式:
            {"status": "success", "score": int, "alt_texts": [...],
             "video_objects": [...], "score_details": {...}, "fallback": bool,
             "errors": [...], "recommended_actions": [...]}
        """
        alt_results = []
        actions = []
        missing_count = 0
        useless_count = 0
        errors = []

        # 分析图片（限制最多 5 张，避免过多视觉 API 调用）
        for img_info in images[:5]:
            alt_info = await self._analyze_image(img_info)
            alt_results.append(alt_info)
            if alt_info["status"] == "missing":
                missing_count += 1
                actions.append({
                    "action": f'图片缺少 alt 文本: {alt_info["url"][:60]}...',
                    "priority": "high",
                    "target_module": "multimodal_labeler",
                    "params": {"url": alt_info["url"], "issue": "missing_alt"},
                })
            elif alt_info["status"] == "useless":
                useless_count += 1
                actions.append({
                    "action": f'图片 alt 文本无意义: {alt_info["url"][:60]}...',
                    "priority": "medium",
                    "target_module": "multimodal_labeler",
                    "params": {"url": alt_info["url"], "issue": "useless_alt", "current_alt": alt_info.get("alt", "")},
                })
            if alt_info.get("error"):
                errors.append(alt_info["error"])

        # 生成 VideoObject Schema
        video_objects = []
        for video in videos[:5]:
            schema = self._generate_video_schema(video)
            video_objects.append(schema)

        # 自评分数
        total = len(alt_results)
        if total == 0:
            score = 100  # 无图片即满分
            ok_count = 0
        else:
            ok_count = total - missing_count - useless_count
            score = int(ok_count / total * 100)

        if videos and not video_objects:
            actions.append({
                "action": "页面包含视频但未生成 VideoObject Schema",
                "priority": "medium",
                "target_module": "multimodal_labeler",
                "params": {"video_count": len(videos)},
            })

        score_details = {
            "base_score": score,
            "image_count": total,
            "ok_count": ok_count,
            "missing_count": missing_count,
            "useless_count": useless_count,
            "video_count": len(videos),
            "video_schema_count": len(video_objects),
            "reason": f"{ok_count}/{total} 张图片 alt 合格，{missing_count} 缺失，{useless_count} 无意义",
        }

        return {
            "status": "success",
            "score": score,
            "alt_texts": alt_results,
            "video_objects": video_objects,
            "score_details": score_details,
            "fallback": False,
            "errors": errors,
            "recommended_actions": actions,
        }

    async def _analyze_image(self, img_info: dict) -> dict:
        """分析单张图片，检测 alt 并尝试生成替代文本。"""
        img_url = img_info.get("src", "") if isinstance(img_info, dict) else str(img_info)
        existing_alt = img_info.get("alt", "") if isinstance(img_info, dict) else ""

        result = {
            "url": img_url,
            "alt": existing_alt,
            "status": "ok",
            "ai_alt": "",
        }

        # 检测 alt 状态
        if not existing_alt:
            result["status"] = "missing"
        elif self._is_useless_alt(existing_alt):
            result["status"] = "useless"

        # 尝试下载图片并用视觉模型分析
        ext = self._get_ext(img_url)
        if ext not in self._SUPPORTED_IMAGE_EXTS:
            if result["status"] == "ok":
                result["status"] = "skipped"
            return result

        try:
            image_data = await self._fetch_image(img_url)
            mime = self._ext_to_mime(ext)
            prompt = (
                "你是一位电商视觉内容专家。请分析这张商品图片，"
                "生成一段场景化的 alt 文本（50-100字），描述图片内容且对 SEO 友好。"
                '仅返回 JSON：{"alt_text": "..."}'
            )
            text = await self._llm.chat_vision(prompt, image_data, mime)
            parsed = parse_json_object(text)
            ai_alt = parsed.get("alt_text", "")
            if ai_alt:
                result["ai_alt"] = ai_alt
                if result["status"] in ("missing", "useless"):
                    result["status"] = "enhanced"
        except (RuntimeError, OSError, ValueError):
            # 视觉模型不可用或下载失败，保持现有状态
            if result["status"] == "ok":
                result["status"] = "check_needed"

        return result

    @staticmethod
    def _is_useless_alt(alt: str) -> bool:
        """判断 alt 文本是否无 SEO 价值。"""
        if not alt:
            return True
        alt_lower = alt.strip().lower()
        useless_patterns = {
            "image", "img", "picture", "photo", "pic",
            "图片", "图像", "照片", "截图",
            "untitled", "placeholder", "loading", "spacer",
        }
        if alt_lower in useless_patterns:
            return True
        if alt_lower.startswith("http") or alt_lower.endswith(".jpg") or alt_lower.endswith(".png"):
            return True
        return False

    async def _fetch_image(self, url: str) -> bytes:
        """下载图片，复用 Crawler 的 session 以共享连接池。限制最大 10MB。"""
        session = self._crawler._session
        if session is not None:
            ctx = self._crawler._session_ctx()
        else:
            timeout = aiohttp.ClientTimeout(total=15)
            ctx = aiohttp.ClientSession(timeout=timeout)
        async with ctx as session:
            async with session.get(url, headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }) as resp:
                resp.raise_for_status()
                data = await resp.read()
                if len(data) > 10 * 1024 * 1024:
                    raise ValueError(f"图片过大: {len(data)} bytes (max 10MB)")
                return data

    @staticmethod
    def _generate_video_schema(video: dict) -> dict:
        schema = {
            "@context": "https://schema.org",
            "@type": "VideoObject",
            "name": video.get("title", ""),
            "description": "",
            "thumbnailUrl": video.get("thumbnailUrl", ""),
            "uploadDate": "",
            "duration": "",
        }
        src = video.get("src", "")
        vtype = video.get("type", "")
        if vtype == "html5":
            schema["contentUrl"] = src
        elif vtype in ("youtube", "bilibili", "vimeo", "iframe"):
            schema["embedUrl"] = src
        return schema

    @staticmethod
    def _get_ext(url: str) -> str:
        m = re.search(r"\.(\w+)(?:\?|$)", url)
        if m:
            return "." + m.group(1).lower()
        return ""

    @staticmethod
    def _ext_to_mime(ext: str) -> str:
        return {
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
        }.get(ext, "image/jpeg")

