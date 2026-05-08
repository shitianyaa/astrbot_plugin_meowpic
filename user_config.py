from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from astrbot.api.event import AstrMessageEvent

try:
    from .settings import (
        CATEGORY_ALIASES,
        DEFAULT_API_URL,
        DEFAULT_CATEGORY,
        FALSE_STRINGS,
        IMAGE_CATEGORIES,
        KV_USER_CONFIGS,
        PIXIV_ALLOWED_SIZES,
        PIXIV_LEGACY_MOSSIA_API_URL,
        PIXIV_MAX_TAG_GROUPS,
        SECRET_QUERY_KEYS,
    )
except ImportError:
    from settings import (
        CATEGORY_ALIASES,
        DEFAULT_API_URL,
        DEFAULT_CATEGORY,
        FALSE_STRINGS,
        IMAGE_CATEGORIES,
        KV_USER_CONFIGS,
        PIXIV_ALLOWED_SIZES,
        PIXIV_LEGACY_MOSSIA_API_URL,
        PIXIV_MAX_TAG_GROUPS,
        SECRET_QUERY_KEYS,
    )


class UserConfigMixin:
    def _record_request(self, event: AstrMessageEvent) -> bool:
        if not self.config.get("rate_limit_enabled", True):
            return True

        max_count = self._get_int("rate_limit_count", 3, 1, 100)
        window = self._get_float("rate_limit_window_seconds", 60.0, 1.0, 3600.0)
        now = time.monotonic()
        user_key = self._get_user_key(event)
        recent = [ts for ts in self._request_log.get(user_key, []) if now - ts < window]

        if len(recent) >= max_count:
            self._request_log[user_key] = recent
            return False

        recent.append(now)
        self._request_log[user_key] = recent
        return True

    async def _get_user_configs(self) -> dict[str, dict[str, Any]]:
        value = await self.get_kv_data(KV_USER_CONFIGS, {})
        if isinstance(value, dict):
            return value
        return {}

    async def _get_user_config(self, user_key: str) -> dict[str, Any]:
        configs = await self._get_user_configs()
        value = configs.get(user_key, {})
        if isinstance(value, dict):
            return value
        return {}

    async def _update_user_config(self, user_key: str, **updates: str | None):
        configs = await self._get_user_configs()
        current = configs.get(user_key, {})
        if not isinstance(current, dict):
            current = {}

        for key, value in updates.items():
            if value is None:
                current.pop(key, None)
            else:
                current[key] = value

        if current:
            configs[user_key] = current
        else:
            configs.pop(user_key, None)
        await self.put_kv_data(KV_USER_CONFIGS, configs)

    async def _update_user_category_config(
        self, user_key: str, field: str, category: str, value: str | None
    ):
        configs = await self._get_user_configs()
        current = configs.get(user_key, {})
        if not isinstance(current, dict):
            current = {}

        mapping = current.get(field, {})
        if not isinstance(mapping, dict):
            mapping = {}

        if value is None:
            mapping.pop(category, None)
        else:
            mapping[category] = value

        if mapping:
            current[field] = mapping
        else:
            current.pop(field, None)

        if current:
            configs[user_key] = current
        else:
            configs.pop(user_key, None)
        await self.put_kv_data(KV_USER_CONFIGS, configs)

    def _get_category_api_url(
        self, category: str, user_conf: dict[str, Any]
    ) -> tuple[str, str]:
        api_urls = user_conf.get("api_urls", {})
        if isinstance(api_urls, dict):
            user_url = (api_urls.get(category, "") or "").strip()
            if user_url:
                if category == "pixiv" and user_url == PIXIV_LEGACY_MOSSIA_API_URL:
                    return IMAGE_CATEGORIES[category]["default_url"], "内置默认"
                return user_url, "用户配置"

        # 兼容旧版个人配置：旧的 api_url 只作为“随机小姐姐”分类的覆盖。
        if category == DEFAULT_CATEGORY:
            legacy_user_url = (user_conf.get("api_url", "") or "").strip()
            if legacy_user_url:
                return legacy_user_url, "用户旧配置"

        meta = IMAGE_CATEGORIES[category]
        config_url = (self.config.get(meta["config_key"], "") or "").strip()
        if config_url:
            if category == "pixiv" and config_url == PIXIV_LEGACY_MOSSIA_API_URL:
                return meta["default_url"], "内置默认"
            return config_url, "插件配置"

        if category == DEFAULT_CATEGORY:
            legacy_config_url = (self.config.get("default_api_url", "") or "").strip()
            if legacy_config_url:
                return legacy_config_url, "旧配置"

        return meta["default_url"], "内置默认"

    def _get_category_api_key(self, category: str, user_conf: dict[str, Any]) -> str:
        api_keys = user_conf.get("api_keys", {})
        if isinstance(api_keys, dict):
            user_key = (api_keys.get(category, "") or "").strip()
            if user_key:
                return user_key

        user_common_key = (user_conf.get("api_key", "") or "").strip()
        if user_common_key:
            return user_common_key

        return self._get_default_api_key()

    @staticmethod
    def _resolve_category(value: str) -> str:
        value = (value or "").strip().lower()
        return CATEGORY_ALIASES.get(value, "")

    @staticmethod
    def _category_label(category: str) -> str:
        return IMAGE_CATEGORIES.get(category, {}).get("label", category)

    def _parse_category_value(
        self, first: str, second: str, allow_raw_default: bool = False
    ) -> tuple[str, str] | None:
        first = (first or "").strip()
        second = (second or "").strip()
        if not first:
            return None

        if second:
            category = self._resolve_category(first)
            if not category:
                return None
            return category, second

        if allow_raw_default or self._is_http_url(first):
            return DEFAULT_CATEGORY, first
        return None

    def _category_usage(self, prefix: str = "用法") -> str:
        categories = " / ".join(
            f"{key}({meta['label']})" for key, meta in IMAGE_CATEGORIES.items()
        )
        return f"{prefix}，可用分类: {categories}"

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
        name = self._safe_call(event, "get_sender_name") or "unknown"
        return f"{umo}:{name}"

    @staticmethod
    def _safe_call(obj: Any, method: str) -> Any:
        func = getattr(obj, method, None)
        if not callable(func):
            return None
        try:
            return func()
        except Exception:
            return None

    def _get_default_api_url(self) -> str:
        return (self.config.get("default_api_url", "") or DEFAULT_API_URL).strip()

    def _get_default_api_key(self) -> str:
        return (self.config.get("default_api_key", "") or "").strip()

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
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

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
        return path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))

    @staticmethod
    def _is_pixiv_direct_image_url(value: str) -> bool:
        hostname = urlparse(value).hostname or ""
        return hostname == "i.pximg.net" or hostname.endswith(".pximg.net")

    @staticmethod
    def _mask_url(value: str) -> str:
        if not value:
            return ""
        parsed = urlparse(value)
        query = []
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True):
            if key.lower() in SECRET_QUERY_KEYS:
                query.append((key, "***"))
            else:
                query.append((key, item_value))
        return urlunparse(parsed._replace(query=urlencode(query)))
