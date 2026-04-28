"""
监测与效果追踪模块
==================
连接 Google Search Console API，获取搜索分析数据，
通过本地历史缓存对比优化前后的变化趋势。

注意：此模块依赖 google-api-python-client，为可选依赖。
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..lib.llm_client import LLMClient

# 可选导入 google API
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    _HAS_GOOGLE = True
except ImportError:
    _HAS_GOOGLE = False

_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
_CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".monitor-cache.json")
_TOKEN_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".gsc-token.json")


class MonitorTracker:
    """
    Google Search Console 数据追踪器。
    """

    def __init__(self):
        self._client_secret_path = os.environ.get(
            "GSC_CLIENT_SECRET_PATH",
            os.path.join(os.path.dirname(__file__), "..", "..", "client_secret.json"),
        )

    async def track(self, url: str, days: int = 28) -> dict:
        """
        获取指定 URL 的 GSC 数据并与历史对比。

        返回标准模块结果格式:
            {"status": "success|error|unavailable", "score": int, "metrics": {...}, "trend": "...", "recommended_actions": [...]}
        """
        if not _HAS_GOOGLE:
            return {
                "status": "unavailable",
                "score": 0,
                "metrics": {},
                "trend": "unavailable",
                "recommended_actions": [
                    {"action": "Google API 客户端未安装，monitor 模块不可用", "priority": "low"}
                ],
            }

        if not os.path.exists(self._client_secret_path):
            return {
                "status": "unavailable",
                "score": 0,
                "metrics": {},
                "trend": "unavailable",
                "recommended_actions": [
                    {"action": f"找不到 GSC 凭证文件: {self._client_secret_path}", "priority": "low"}
                ],
            }

        # 计算日期范围
        end = datetime.now(timezone.utc) - timedelta(days=3)
        start = end - timedelta(days=days - 1)
        end_date = end.strftime("%Y-%m-%d")
        start_date = start.strftime("%Y-%m-%d")

        try:
            auth = self._authenticate()
            summary = self._query_summary(auth, url, start_date, end_date)
            queries = self._query_queries(auth, url, start_date, end_date)
        except (OSError, ValueError, RuntimeError) as e:
            return {
                "status": "error",
                "score": 0,
                "metrics": {},
                "trend": "unknown",
                "recommended_actions": [
                    {"action": f"GSC 数据获取失败: {e}", "priority": "medium"}
                ],
            }

        # 加载历史并对比
        cache = self._load_cache()
        cache_key = url
        prev = self._find_previous(cache, cache_key)

        trend = "stable"
        actions = []
        if prev:
            p_summary = prev.get("summary", {})
            clicks_change = summary.get("clicks", 0) - p_summary.get("clicks", 0)
            pos_change = summary.get("position", 0) - p_summary.get("position", 0)
            if clicks_change > 0:
                trend = "up"
            elif clicks_change < 0:
                trend = "down"
            if pos_change > 1:
                actions.append({
                    "action": f"平均排名下降 {pos_change:.1f} 位，建议检查页面优化",
                    "priority": "high",
                })

        # 保存当前数据
        entry = {
            "date": datetime.now(timezone.utc).isoformat(),
            "startDate": start_date,
            "endDate": end_date,
            "days": days,
            "summary": summary,
            "topQueries": queries,
        }
        self._save_cache(cache, cache_key, entry)

        # 自评分数：基于 CTR 和排名
        ctr = summary.get("ctr", 0)
        pos = summary.get("position", 100)
        score = min(100, int(ctr * 200 + max(0, 30 - pos) * 2))

        if ctr < 0.02:
            actions.append({
                "action": f"CTR 较低（{ctr:.2%}），建议优化标题和描述",
                "priority": "high",
            })

        return {
            "status": "success",
            "score": score,
            "metrics": {
                "clicks": summary.get("clicks", 0),
                "impressions": summary.get("impressions", 0),
                "ctr": ctr,
                "position": pos,
                "period": {"start": start_date, "end": end_date, "days": days},
            },
            "trend": trend,
            "topQueries": queries,
            "recommended_actions": actions,
        }

    def _authenticate(self):
        """OAuth2 认证，支持 token 缓存。"""
        if os.path.exists(_TOKEN_PATH):
            try:
                with open(_TOKEN_PATH, "r", encoding="utf-8") as f:
                    token_data = json.load(f)
                creds = Credentials.from_authorized_user_info(token_data, _SCOPES)
                if creds and creds.valid:
                    return creds
            except (OSError, ValueError):
                pass

        flow = InstalledAppFlow.from_client_secrets_file(
            self._client_secret_path, _SCOPES
        )
        creds = flow.run_local_server(port=0)

        # 缓存 token
        with open(_TOKEN_PATH, "w", encoding="utf-8") as f:
            json.dump(json.loads(creds.to_json()), f, indent=2)
        return creds

    def _query_summary(self, auth, site_url: str, start_date: str, end_date: str) -> dict:
        service = build("searchconsole", "v1", credentials=auth, cache_discovery=False)
        body = {"startDate": start_date, "endDate": end_date, "rowLimit": 1}
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = resp.get("rows", [])
        if rows:
            return {
                "clicks": rows[0].get("clicks", 0),
                "impressions": rows[0].get("impressions", 0),
                "ctr": rows[0].get("ctr", 0),
                "position": rows[0].get("position", 0),
            }
        return {"clicks": 0, "impressions": 0, "ctr": 0, "position": 0}

    def _query_queries(self, auth, site_url: str, start_date: str, end_date: str) -> List[dict]:
        service = build("searchconsole", "v1", credentials=auth, cache_discovery=False)
        body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["query"],
            "rowLimit": 20,
        }
        resp = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
        rows = resp.get("rows", [])
        return [
            {
                "query": r["keys"][0],
                "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "ctr": r.get("ctr", 0),
                "position": r.get("position", 0),
            }
            for r in rows
        ]

    @staticmethod
    def _load_cache() -> dict:
        if os.path.exists(_CACHE_PATH):
            try:
                with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    @staticmethod
    def _save_cache(cache: dict, key: str, data: dict) -> None:
        if key not in cache:
            cache[key] = []
        cache[key].append(data)
        if len(cache[key]) > 12:
            cache[key] = cache[key][-12:]
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)

    @staticmethod
    def _find_previous(cache: dict, key: str) -> Optional[dict]:
        entries = cache.get(key, [])
        if len(entries) < 2:
            return None
        return entries[-2]
