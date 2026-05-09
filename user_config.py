from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlparse

from astrbot.api.event import AstrMessageEvent

try:
    from .settings import (
        FALSE_STRINGS,
        IMAGE_CATEGORIES,
        PIXIV_ALLOWED_SIZES,
        PIXIV_MAX_TAG_GROUPS,
    )
except ImportError:
    from settings import (
        FALSE_STRINGS,
        IMAGE_CATEGORIES,
        PIXIV_ALLOWED_SIZES,
        PIXIV_MAX_TAG_GROUPS,
    )


class UserConfigMixin:
    def _record_request(self, event: AstrMessageEvent) -> bool:
        if not self._get_bool("rate_limit_enabled", True):
            return True

        max_count = self._get_int("rate_limit_count", 3, 1, 100)
        window = self._get_float("rate_limit_window_seconds", 60.0, 1.0, 3600.0)
        now = time.monotonic()
        self._prune_request_log(now, window)
        user_key = self._get_user_key(event)
        recent = [ts for ts in self._request_log.get(user_key, []) if now - ts < window]

        if len(recent) >= max_count:
            self._request_log[user_key] = recent
            return False

        recent.append(now)
        self._request_log[user_key] = recent
        return True

    def _prune_request_log(self, now: float, window: float) -> None:
        prune_interval = max(window, 60.0)
        if now - getattr(self, "_last_request_log_prune", 0.0) < prune_interval:
            return

        self._last_request_log_prune = now
        for user_key, timestamps in list(self._request_log.items()):
            recent = [ts for ts in timestamps if now - ts < window]
            if recent:
                self._request_log[user_key] = recent
            else:
                self._request_log.pop(user_key, None)

    def _get_category_api_url(self, category: str) -> tuple[str, str]:
        meta = IMAGE_CATEGORIES[category]
        config_url = self._get_str(meta["config_key"], "")
        if config_url:
            return config_url, "插件配置"

        return meta["default_url"], "内置默认"

    def _get_api_key(self) -> str:
        return self._get_str("default_api_key", "")

    def _get_user_key(self, event: AstrMessageEvent) -> str:
        platform = self._safe_call(event, "get_platform_name") or "unknown"
        sender_id = self._get_sender_id(event)
        return f"{platform}:{sender_id}"

    def _get_sender_id(self, event: AstrMessageEvent) -> str:
        direct = self._safe_call(event, "get_sender_id")
        if direct:
            return str(direct)

        message_obj = getattr(event, "message_obj", None)
        sender = getattr(message_obj, "sender", None)
        for attr in ("user_id", "id", "sender_id"):
            value = getattr(sender, attr, None)
            if value:
                return str(value)

        raw = getattr(message_obj, "raw_message", None)
        if isinstance(raw, dict):
            for key in ("user_id", "sender_id"):
                if raw.get(key):
                    return str(raw[key])
            raw_sender = raw.get("sender")
            if isinstance(raw_sender, dict):
                for key in ("user_id", "id"):
                    if raw_sender.get(key):
                        return str(raw_sender[key])

        umo = getattr(event, "unified_msg_origin", "")
        return umo or "unknown"

    @staticmethod
    def _safe_call(obj: Any, method: str) -> Any:
        func = getattr(obj, method, None)
        if not callable(func):
            return None
        try:
            return func()
        except Exception:
            return None

    def _get_int(self, key: str, default: int, lo: int, hi: int) -> int:
        try:
            value = int(self.config.get(key, default))
        except (TypeError, ValueError):
            return default
        return value if lo <= value <= hi else default

    def _get_float(self, key: str, default: float, lo: float, hi: float) -> float:
        try:
            value = float(self.config.get(key, default))
        except (TypeError, ValueError):
            return default
        return value if lo <= value <= hi else default

    def _get_bool(self, key: str, default: bool) -> bool:
        value = self.config.get(key, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() not in FALSE_STRINGS

    def _get_str(self, key: str, default: str = "") -> str:
        value = self.config.get(key, default)
        if value is None:
            return default
        return str(value).strip()

    def _get_pixiv_sizes(self) -> list[str]:
        sizes: list[str] = []
        for value in self._split_list_value(self._get_str("pixiv_size", "regular")):
            normalized = value.lower()
            if normalized in PIXIV_ALLOWED_SIZES and normalized not in sizes:
                sizes.append(normalized)
        return sizes or ["regular"]

    def _get_pixiv_default_tags(self) -> list[str]:
        return self._normalize_pixiv_tags(self._get_str("pixiv_default_tags", ""))

    def _normalize_pixiv_tags(self, *values: str) -> list[str]:
        tags: list[str] = []
        for value in values:
            for item in self._split_list_value(value):
                if item and item not in tags:
                    tags.append(item)
                if len(tags) >= PIXIV_MAX_TAG_GROUPS:
                    return tags
        return tags

    @staticmethod
    def _split_list_value(value: str) -> list[str]:
        text = (value or "").strip()
        if not text:
            return []
        for sep in ("\r\n", "\n", "，", "、", "；", ";", ","):
            text = text.replace(sep, " ")
        return [item.strip() for item in text.split() if item.strip()]

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed = urlparse(value)
        return (parsed.scheme in {"http", "https"} or not parsed.scheme) and bool(
            parsed.netloc
        )

    @staticmethod
    def _is_lolicon_v2_url(value: str) -> bool:
        parsed = urlparse(value)
        return (
            parsed.scheme in {"http", "https"}
            and (parsed.hostname or "").lower() == "api.lolicon.app"
            and parsed.path.rstrip("/") == "/setu/v2"
        )

    @staticmethod
    def _looks_like_image_url(value: str) -> bool:
        path = urlparse(value).path.lower()
        return path.endswith(
            (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp")
        )

    @staticmethod
    def _is_pixiv_direct_image_url(value: str) -> bool:
        hostname = urlparse(value).hostname or ""
        return hostname == "i.pximg.net" or hostname.endswith(".pximg.net")
