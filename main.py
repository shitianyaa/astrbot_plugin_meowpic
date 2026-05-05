from __future__ import annotations

import json
import os
import random
import tempfile
import time
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register


KV_USER_CONFIGS = "user_configs"
LOG_PREFIX = "[MeowPic]"
DEFAULT_LIMIT_MESSAGE = "冲的太快了喵~"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_API_URL = "https://free.wqwlkj.cn/wqwlapi/ks_2cy.php?type=image"
IMAGE_SUFFIX_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
}
PREFERRED_IMAGE_KEYS = {
    "url",
    "urls",
    "img",
    "imgs",
    "image",
    "images",
    "pic",
    "pics",
    "picture",
    "pictures",
    "file",
    "files",
    "imgurl",
    "image_url",
    "imageurl",
    "download_url",
}
SECRET_QUERY_KEYS = {"key", "apikey", "api_key", "token", "access_token", "auth"}


class UserFacingError(Exception):
    """An error that can be shown directly to chat users."""


@register(
    "astrbot_plugin_meowpic",
    "Sham1k0",
    "随机小姐姐图片插件，支持用户自定义 API 与 API Key",
    "1.0.0",
)
class MeowPicPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self._request_log: dict[str, list[float]] = {}

    async def initialize(self):
        self._ensure_session()
        logger.info(f"{LOG_PREFIX} loaded")

    async def terminate(self):
        if self.session is not None and not self.session.closed:
            await self.session.close()
        logger.info(f"{LOG_PREFIX} stopped")

    def _ensure_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    @filter.command("mm", alias={"meizi", "小姐姐", "美女"})
    async def cmd_mm(self, event: AstrMessageEvent):
        """随机返回一张图片"""
        async for result in self._yield_random_image(event):
            yield result

    @filter.command_group("meowpic", alias={"喵图"})
    def meowpic(self):
        """喵图姬配置指令组"""
        pass

    @meowpic.command("get", alias={"pic", "来一张"})
    async def cmd_get(self, event: AstrMessageEvent):
        """随机返回一张图片"""
        async for result in self._yield_random_image(event):
            yield result

    @meowpic.command("setapi")
    async def cmd_setapi(self, event: AstrMessageEvent, api_url: str = ""):
        """设置当前用户的图片 API 地址"""
        api_url = (api_url or "").strip()
        if not api_url:
            yield event.plain_result("用法: /meowpic setapi <API地址>")
            return
        if not self._is_http_url(api_url):
            yield event.plain_result("API 地址只支持 http:// 或 https:// 开头")
            return

        user_key = self._get_user_key(event)
        await self._update_user_config(user_key, api_url=api_url)
        yield event.plain_result("已保存你的图片 API 地址喵")

    @meowpic.command("setkey")
    async def cmd_setkey(self, event: AstrMessageEvent, api_key: str = ""):
        """设置当前用户的 API Key"""
        api_key = (api_key or "").strip()
        if not api_key:
            yield event.plain_result("用法: /meowpic setkey <APIKey>")
            return

        user_key = self._get_user_key(event)
        await self._update_user_config(user_key, api_key=api_key)
        yield event.plain_result("已保存你的 API Key 喵")

    @meowpic.command("clearkey")
    async def cmd_clearkey(self, event: AstrMessageEvent):
        """清除当前用户的 API Key"""
        user_key = self._get_user_key(event)
        await self._update_user_config(user_key, api_key=None)
        yield event.plain_result("已清除你的 API Key")

    @meowpic.command("clear")
    async def cmd_clear(self, event: AstrMessageEvent):
        """清除当前用户的 API 地址与 API Key"""
        user_key = self._get_user_key(event)
        configs = await self._get_user_configs()
        configs.pop(user_key, None)
        await self.put_kv_data(KV_USER_CONFIGS, configs)
        yield event.plain_result("已清除你的喵图姬配置，将使用全局默认配置")

    @meowpic.command("status")
    async def cmd_status(self, event: AstrMessageEvent):
        """查看当前用户配置状态"""
        user_key = self._get_user_key(event)
        user_conf = await self._get_user_config(user_key)
        default_api = self._get_default_api_url()
        api_url = user_conf.get("api_url") or default_api
        api_key = user_conf.get("api_key") or self._get_default_api_key()
        source = "用户配置" if user_conf.get("api_url") else "全局默认"

        lines = [
            "喵图姬状态",
            f"API: {self._mask_url(api_url) if api_url else '未配置'}",
            f"来源: {source if api_url else '无'}",
            f"API Key: {'已配置' if api_key else '未配置'}",
            (
                "限流: "
                f"{self._get_int('rate_limit_count', 3, 1, 100)} 次 / "
                f"{self._get_float('rate_limit_window_seconds', 60.0, 1.0, 3600.0):g} 秒"
                if self.config.get("rate_limit_enabled", True)
                else "限流: 已关闭"
            ),
        ]
        yield event.plain_result("\n".join(lines))

    @meowpic.command("help")
    async def cmd_help(self, event: AstrMessageEvent):
        """查看喵图姬指令"""
        yield event.plain_result(
            "喵图姬指令\n"
            "/mm 或 /小姐姐              随机来一张\n"
            "/meowpic get               随机来一张\n"
            "/meowpic setapi <API地址>   设置你的图片 API\n"
            "/meowpic setkey <APIKey>    设置你的 API Key\n"
            "/meowpic clearkey           清除你的 API Key\n"
            "/meowpic clear              清除你的全部个人配置\n"
            "/meowpic status             查看当前配置"
        )

    async def _yield_random_image(self, event: AstrMessageEvent):
        if not self._record_request(event):
            yield event.plain_result(
                self.config.get("rate_limit_message", DEFAULT_LIMIT_MESSAGE)
                or DEFAULT_LIMIT_MESSAGE
            )
            return

        temp_path: str | None = None
        try:
            image_ref, temp_path = await self._fetch_image_for_event(event)
            yield event.image_result(image_ref)
        except UserFacingError as e:
            yield event.plain_result(str(e))
        except Exception as e:
            logger.error(f"{LOG_PREFIX} fetch image failed: {e}", exc_info=True)
            yield event.plain_result("图片获取失败了喵，请稍后再试")
        finally:
            if temp_path:
                self._cleanup_temp_file(temp_path)

    async def _fetch_image_for_event(
        self, event: AstrMessageEvent
    ) -> tuple[str, str | None]:
        user_conf = await self._get_user_config(self._get_user_key(event))
        api_url = (user_conf.get("api_url") or self._get_default_api_url()).strip()
        api_key = (user_conf.get("api_key") or self._get_default_api_key()).strip()

        request_url, headers = self._build_request(api_url, api_key)
        timeout = aiohttp.ClientTimeout(
            total=self._get_float(
                "request_timeout_seconds", DEFAULT_TIMEOUT_SECONDS, 3.0, 120.0
            )
        )

        session = self._ensure_session()
        async with session.get(
            request_url, headers=headers, timeout=timeout, allow_redirects=True
        ) as resp:
            if resp.status >= 400:
                raise UserFacingError(f"图片 API 返回了 {resp.status}，请检查配置")

            content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if content_type.startswith("image/"):
                image_bytes = await resp.read()
                if not image_bytes:
                    raise UserFacingError("图片 API 返回了空图片")
                temp_path = self._write_temp_image(
                    image_bytes, content_type, str(resp.url)
                )
                return temp_path, temp_path

            raw_text = await resp.text()

        image_url = self._extract_image_url(raw_text, request_url)
        if not image_url:
            raise UserFacingError("没有从 API 响应里找到图片地址")

        # 下载图片到本地，避免 QQ 客户端访问外网图床超时（如 retcode=1200）
        temp_path = await self._download_image(image_url, timeout)
        return temp_path, temp_path

    async def _download_image(
        self, image_url: str, timeout: aiohttp.ClientTimeout
    ) -> str:
        session = self._ensure_session()
        async with session.get(image_url, timeout=timeout, allow_redirects=True) as resp:
            if resp.status >= 400:
                raise UserFacingError(f"图片下载失败: HTTP {resp.status}")
            content_type = resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
            image_bytes = await resp.read()
        if not image_bytes:
            raise UserFacingError("图片下载到的内容为空")
        return self._write_temp_image(image_bytes, content_type, str(resp.url))

    def _build_request(self, api_url: str, api_key: str) -> tuple[str, dict[str, str]]:
        if api_key and "{api_key}" in api_url:
            return api_url.replace("{api_key}", quote(api_key, safe="")), {}
        return api_url, {}

    def _extract_image_url(self, raw_text: str, base_url: str) -> str | None:
        text = (raw_text or "").strip().strip('"').strip("'")
        if self._is_http_url(text):
            return text

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        candidates = self._collect_image_urls(payload, from_hint=False)
        if not candidates:
            return None
        return urljoin(base_url, random.choice(candidates))

    def _collect_image_urls(self, value: Any, from_hint: bool) -> list[str]:
        found: dict[str, None] = {}

        def add(url: str):
            if url not in found:
                found[url] = None

        def walk(node: Any, hinted: bool):
            if isinstance(node, str):
                s = node.strip()
                if self._is_http_url(s) and (hinted or self._looks_like_image_url(s)):
                    add(s)
                return

            if isinstance(node, list):
                for item in node:
                    walk(item, hinted)
                return

            if not isinstance(node, dict):
                return

            for key, child in node.items():
                if str(key).lower() in PREFERRED_IMAGE_KEYS:
                    walk(child, True)
            for key, child in node.items():
                if str(key).lower() not in PREFERRED_IMAGE_KEYS:
                    walk(child, hinted)

        walk(value, from_hint)
        return list(found.keys())

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

    async def _get_user_configs(self) -> dict[str, dict[str, str]]:
        value = await self.get_kv_data(KV_USER_CONFIGS, {})
        if isinstance(value, dict):
            return value
        return {}

    async def _get_user_config(self, user_key: str) -> dict[str, str]:
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

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    @staticmethod
    def _looks_like_image_url(value: str) -> bool:
        path = urlparse(value).path.lower()
        return path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"))

    @staticmethod
    def _write_temp_image(image_bytes: bytes, content_type: str, source_url: str) -> str:
        suffix = IMAGE_SUFFIX_BY_CONTENT_TYPE.get(content_type)
        if not suffix:
            source_path = urlparse(source_url).path.lower()
            for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
                if source_path.endswith(ext):
                    suffix = ext
                    break
        if not suffix:
            suffix = ".jpg"

        fd, temp_path = tempfile.mkstemp(prefix="meowpic_", suffix=suffix)
        with os.fdopen(fd, "wb") as file:
            file.write(image_bytes)
        return temp_path

    @staticmethod
    def _cleanup_temp_file(path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError as e:
            logger.debug(f"{LOG_PREFIX} cleanup temp file failed: {path}, {e}")

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
