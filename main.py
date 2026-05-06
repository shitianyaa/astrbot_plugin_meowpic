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
DEFAULT_CATEGORY = "meinv"
PIXIV_LOLICON_API_URL = "https://api.lolicon.app/setu/v2"
PIXIV_LEGACY_MOSSIA_API_URL = (
    "https://api.mossia.top/duckMo?num=1&r18Type=0&proxy=i.pixiv.re"
)
PIXIV_ALLOWED_SIZES = {"original", "regular", "small", "thumb", "mini"}
PIXIV_MAX_TAG_GROUPS = 3
FALSE_STRINGS = {"", "0", "false", "none", "null", "off", "no"}
IMAGE_CATEGORIES = {
    "meinv": {
        "label": "随机小姐姐",
        "config_key": "api_meinv_url",
        "default_url": "https://v2.xxapi.cn/api/meinvpic",
    },
    "baisi": {
        "label": "白丝",
        "config_key": "api_baisi_url",
        "default_url": "https://v2.xxapi.cn/api/baisi",
    },
    "heisi": {
        "label": "黑丝",
        "config_key": "api_heisi_url",
        "default_url": "https://v2.xxapi.cn/api/heisi",
    },
    "acg": {
        "label": "二次元",
        "config_key": "api_acg_url",
        "default_url": "https://v2.xxapi.cn/api/randomAcgPic?type=pc",
    },
    "jk": {
        "label": "JK",
        "config_key": "api_jk_url",
        "default_url": "https://v2.xxapi.cn/api/jk",
    },
    "pixiv": {
        "label": "Pixiv",
        "config_key": "api_pixiv_url",
        "default_url": PIXIV_LOLICON_API_URL,
    },
}
CATEGORY_ALIASES = {
    "meinv": "meinv",
    "mm": "meinv",
    "meizi": "meinv",
    "小姐姐": "meinv",
    "美女": "meinv",
    "随机小姐姐": "meinv",
    "baisi": "baisi",
    "bs": "baisi",
    "白丝": "baisi",
    "heisi": "heisi",
    "hs": "heisi",
    "黑丝": "heisi",
    "acg": "acg",
    "二次元": "acg",
    "动漫": "acg",
    "jk": "jk",
    "pixiv": "pixiv",
    "px": "pixiv",
    "p站": "pixiv",
    "p站图": "pixiv",
    "pixiv非r18": "pixiv",
}
DEFAULT_API_URL = IMAGE_CATEGORIES[DEFAULT_CATEGORY]["default_url"]
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
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
    "data",
    "imgurl",
    "image_url",
    "imageurl",
    "link",
    "result",
    "src",
    "download_url",
}
SECRET_QUERY_KEYS = {"key", "apikey", "api_key", "token", "access_token", "auth"}


class UserFacingError(Exception):
    """An error that can be shown directly to chat users."""


@register(
    "astrbot_plugin_meowpic",
    "Sham1k0",
    "多分类随机图片插件，支持 Pixiv 标签、自定义 API 与 API Key",
    "1.3.0",
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
        async for result in self._yield_random_image(event, "meinv"):
            yield result

    @filter.command("白丝", alias={"baisi", "bs"})
    async def cmd_baisi(self, event: AstrMessageEvent):
        """随机返回一张白丝图片"""
        async for result in self._yield_random_image(event, "baisi"):
            yield result

    @filter.command("黑丝", alias={"heisi", "hs"})
    async def cmd_heisi(self, event: AstrMessageEvent):
        """随机返回一张黑丝图片"""
        async for result in self._yield_random_image(event, "heisi"):
            yield result

    @filter.command("二次元", alias={"acg", "动漫"})
    async def cmd_acg(self, event: AstrMessageEvent):
        """随机返回一张二次元图片"""
        async for result in self._yield_random_image(event, "acg"):
            yield result

    @filter.command("jk", alias={"JK"})
    async def cmd_jk(self, event: AstrMessageEvent):
        """随机返回一张 JK 图片"""
        async for result in self._yield_random_image(event, "jk"):
            yield result

    @filter.command("pixiv", alias={"px", "p站", "p站图", "pixiv非r18"})
    async def cmd_pixiv(
        self,
        event: AstrMessageEvent,
        tag1: str = "",
        tag2: str = "",
        tag3: str = "",
    ):
        """随机返回一张 Pixiv 图片，可附加最多 3 组标签"""
        async for result in self._yield_random_image(
            event, "pixiv", self._normalize_pixiv_tags(tag1, tag2, tag3)
        ):
            yield result

    @filter.command_group("meowpic", alias={"喵图"})
    def meowpic(self):
        """喵图姬配置指令组"""
        pass

    @meowpic.command("get", alias={"pic", "来一张"})
    async def cmd_get(
        self,
        event: AstrMessageEvent,
        category: str = "",
        tag1: str = "",
        tag2: str = "",
        tag3: str = "",
    ):
        """随机返回一张图片"""
        category_key = self._resolve_category(category or DEFAULT_CATEGORY)
        if not category_key:
            yield event.plain_result(self._category_usage("未知分类"))
            return
        pixiv_tags = (
            self._normalize_pixiv_tags(tag1, tag2, tag3)
            if category_key == "pixiv"
            else []
        )
        async for result in self._yield_random_image(event, category_key, pixiv_tags):
            yield result

    @meowpic.command("baisi", alias={"白丝", "bs"})
    async def cmd_get_baisi(self, event: AstrMessageEvent):
        """随机返回一张白丝图片"""
        async for result in self._yield_random_image(event, "baisi"):
            yield result

    @meowpic.command("heisi", alias={"黑丝", "hs"})
    async def cmd_get_heisi(self, event: AstrMessageEvent):
        """随机返回一张黑丝图片"""
        async for result in self._yield_random_image(event, "heisi"):
            yield result

    @meowpic.command("acg", alias={"二次元", "动漫"})
    async def cmd_get_acg(self, event: AstrMessageEvent):
        """随机返回一张二次元图片"""
        async for result in self._yield_random_image(event, "acg"):
            yield result

    @meowpic.command("jk", alias={"JK"})
    async def cmd_get_jk(self, event: AstrMessageEvent):
        """随机返回一张 JK 图片"""
        async for result in self._yield_random_image(event, "jk"):
            yield result

    @meowpic.command("pixiv", alias={"px", "p站", "p站图", "pixiv非r18"})
    async def cmd_get_pixiv(
        self,
        event: AstrMessageEvent,
        tag1: str = "",
        tag2: str = "",
        tag3: str = "",
    ):
        """随机返回一张 Pixiv 图片，可附加最多 3 组标签"""
        async for result in self._yield_random_image(
            event, "pixiv", self._normalize_pixiv_tags(tag1, tag2, tag3)
        ):
            yield result

    @meowpic.command("setapi")
    async def cmd_setapi(
        self, event: AstrMessageEvent, first: str = "", second: str = ""
    ):
        """设置当前用户的图片 API 地址"""
        parsed = self._parse_category_value(first, second)
        if parsed is None:
            yield event.plain_result(
                "用法: /meowpic setapi [分类] <API地址>\n"
                "例: /meowpic setapi 白丝 https://example.com/api"
            )
            return
        category_key, api_url = parsed
        if not api_url:
            yield event.plain_result("用法: /meowpic setapi [分类] <API地址>")
            return
        if not self._is_http_url(api_url):
            yield event.plain_result("API 地址只支持 http:// 或 https:// 开头")
            return

        user_key = self._get_user_key(event)
        await self._update_user_category_config(
            user_key, "api_urls", category_key, api_url
        )
        yield event.plain_result(
            f"已保存你的{self._category_label(category_key)} API 地址喵"
        )

    @meowpic.command("setkey")
    async def cmd_setkey(
        self, event: AstrMessageEvent, first: str = "", second: str = ""
    ):
        """设置当前用户的 API Key"""
        parsed = self._parse_category_value(first, second, allow_raw_default=True)
        if parsed is None:
            yield event.plain_result("用法: /meowpic setkey [分类] <APIKey>")
            return
        category_key, api_key = parsed
        if not api_key:
            yield event.plain_result("用法: /meowpic setkey [分类] <APIKey>")
            return

        user_key = self._get_user_key(event)
        if second:
            await self._update_user_category_config(
                user_key, "api_keys", category_key, api_key
            )
            yield event.plain_result(
                f"已保存你的{self._category_label(category_key)} API Key 喵"
            )
        else:
            await self._update_user_config(user_key, api_key=api_key)
            yield event.plain_result("已保存你的通用 API Key 喵")

    @meowpic.command("clearkey")
    async def cmd_clearkey(self, event: AstrMessageEvent, category: str = ""):
        """清除当前用户的 API Key"""
        user_key = self._get_user_key(event)
        category_key = self._resolve_category(category) if category else ""
        if category and not category_key:
            yield event.plain_result(self._category_usage("未知分类"))
            return
        if category_key:
            await self._update_user_category_config(
                user_key, "api_keys", category_key, None
            )
            yield event.plain_result(
                f"已清除你的{self._category_label(category_key)} API Key"
            )
            return
        await self._update_user_config(user_key, api_key=None, api_keys=None)
        yield event.plain_result("已清除你的全部个人 API Key")

    @meowpic.command("clear")
    async def cmd_clear(self, event: AstrMessageEvent, category: str = ""):
        """清除当前用户的 API 地址与 API Key"""
        user_key = self._get_user_key(event)
        category_key = self._resolve_category(category) if category else ""
        if category and not category_key:
            yield event.plain_result(self._category_usage("未知分类"))
            return
        if category_key:
            await self._update_user_category_config(
                user_key, "api_urls", category_key, None
            )
            await self._update_user_category_config(
                user_key, "api_keys", category_key, None
            )
            yield event.plain_result(
                f"已清除你的{self._category_label(category_key)}个人配置"
            )
            return

        configs = await self._get_user_configs()
        configs.pop(user_key, None)
        await self.put_kv_data(KV_USER_CONFIGS, configs)
        yield event.plain_result("已清除你的喵图姬配置，将使用全局默认配置")

    @meowpic.command("status")
    async def cmd_status(self, event: AstrMessageEvent, category: str = ""):
        """查看当前用户配置状态"""
        user_key = self._get_user_key(event)
        user_conf = await self._get_user_config(user_key)
        category_key = self._resolve_category(category) if category else ""
        if category and not category_key:
            yield event.plain_result(self._category_usage("未知分类"))
            return

        lines = [
            "喵图姬状态",
            (
                "限流: "
                f"{self._get_int('rate_limit_count', 3, 1, 100)} 次 / "
                f"{self._get_float('rate_limit_window_seconds', 60.0, 1.0, 3600.0):g} 秒"
                if self.config.get("rate_limit_enabled", True)
                else "限流: 已关闭"
            ),
        ]
        categories = [category_key] if category_key else list(IMAGE_CATEGORIES)
        for key in categories:
            api_url, source = self._get_category_api_url(key, user_conf)
            api_key = self._get_category_api_key(key, user_conf)
            lines.append(
                f"{self._category_label(key)}: {self._mask_url(api_url)} "
                f"({source}, Key {'已配置' if api_key else '未配置'})"
            )
            if key == "pixiv" and self._is_lolicon_v2_url(api_url):
                default_tags = " ".join(self._get_pixiv_default_tags()) or "无"
                lines.append(
                    "Pixiv 参数: "
                    f"r18={self._get_int('pixiv_r18', 0, 0, 2)}, "
                    f"size={','.join(self._get_pixiv_sizes())}, "
                    f"proxy={self._get_str('pixiv_proxy', 'i.pixiv.re') or '无'}, "
                    f"excludeAI={self._get_bool('pixiv_exclude_ai', True)}, "
                    f"默认标签={default_tags}"
                )
        yield event.plain_result("\n".join(lines))

    @meowpic.command("help")
    async def cmd_help(self, event: AstrMessageEvent):
        """查看喵图姬指令"""
        yield event.plain_result(
            "喵图姬指令\n"
            "/mm /小姐姐 /美女           随机小姐姐\n"
            "/白丝 /黑丝 /二次元 /jk      指定分类来一张\n"
            "/pixiv /p站 /px [标签...]     Pixiv 随机图，默认非 R18\n"
            "/meowpic get [分类] [标签...] 随机来一张\n"
            "/meowpic pixiv [标签...]      Pixiv 按标签随机\n"
            "/meowpic setapi [分类] <URL> 设置个人分类 API\n"
            "/meowpic setkey [分类] <Key> 设置 API Key\n"
            "/meowpic clearkey [分类]     清除 API Key\n"
            "/meowpic clear [分类]        清除个人配置\n"
            "/meowpic status [分类]       查看当前配置"
        )

    async def _yield_random_image(
        self,
        event: AstrMessageEvent,
        category: str,
        pixiv_tags: list[str] | None = None,
    ):
        if not self._record_request(event):
            yield event.plain_result(
                self.config.get("rate_limit_message", DEFAULT_LIMIT_MESSAGE)
                or DEFAULT_LIMIT_MESSAGE
            )
            return

        temp_path: str | None = None
        try:
            image_ref, temp_path = await self._fetch_image_for_event(
                event, category, pixiv_tags or []
            )
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
        self,
        event: AstrMessageEvent,
        category: str,
        pixiv_tags: list[str],
    ) -> tuple[str, str | None]:
        user_conf = await self._get_user_config(self._get_user_key(event))
        api_url, _ = self._get_category_api_url(category, user_conf)
        api_key = self._get_category_api_key(category, user_conf)

        request_url, headers = self._build_request(
            api_url, api_key, category, pixiv_tags
        )
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
        temp_path = await self._download_image(image_url, timeout, request_url)
        return temp_path, temp_path

    async def _download_image(
        self, image_url: str, timeout: aiohttp.ClientTimeout, referer_url: str = ""
    ) -> str:
        session = self._ensure_session()
        last_status: int | None = None
        last_content_type = ""

        for headers in self._download_header_attempts(image_url, referer_url):
            async with session.get(
                image_url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
            ) as resp:
                if resp.status >= 400:
                    last_status = resp.status
                    if resp.status in (401, 403, 429):
                        continue
                    raise UserFacingError(f"图片下载失败: HTTP {resp.status}")

                content_type = (
                    resp.headers.get("Content-Type", "").split(";", 1)[0].lower()
                )
                image_bytes = await resp.read()
                last_content_type = content_type
                if image_bytes and (
                    content_type.startswith("image/")
                    or self._looks_like_image_url(str(resp.url))
                ):
                    return self._write_temp_image(
                        image_bytes, content_type, str(resp.url)
                    )

        if last_status is not None:
            raise UserFacingError(f"图片下载失败: HTTP {last_status}")
        if last_content_type:
            raise UserFacingError(f"图片下载失败: 返回类型 {last_content_type}")
        raise UserFacingError("图片下载失败")

    def _build_request(
        self,
        api_url: str,
        api_key: str,
        category: str = "",
        pixiv_tags: list[str] | None = None,
    ) -> tuple[str, dict[str, str]]:
        if api_key and "{api_key}" in api_url:
            api_url = api_url.replace("{api_key}", quote(api_key, safe=""))

        if category == "pixiv" and self._is_lolicon_v2_url(api_url):
            api_url = self._build_lolicon_v2_url(api_url, pixiv_tags or [])

        return api_url, self._browser_headers()

    def _build_lolicon_v2_url(self, api_url: str, pixiv_tags: list[str]) -> str:
        parsed = urlparse(api_url)
        query = parse_qsl(parsed.query, keep_blank_values=True)
        existing_keys = {key.lower() for key, _ in query}

        def add_if_missing(key: str, value: str):
            if key.lower() in existing_keys or value == "":
                return
            query.append((key, value))
            existing_keys.add(key.lower())

        add_if_missing("r18", str(self._get_int("pixiv_r18", 0, 0, 2)))
        add_if_missing("num", "1")

        if "size" not in existing_keys:
            for size in self._get_pixiv_sizes():
                query.append(("size", size))
            existing_keys.add("size")

        if "proxy" not in existing_keys:
            query.append(("proxy", self._get_str("pixiv_proxy", "i.pixiv.re")))
            existing_keys.add("proxy")
        add_if_missing(
            "excludeAI",
            "true" if self._get_bool("pixiv_exclude_ai", True) else "false",
        )
        add_if_missing("aspectRatio", self._get_str("pixiv_aspect_ratio", ""))

        tags = pixiv_tags or self._get_pixiv_default_tags()
        has_url_tags = any(key.lower() == "tag" for key, _ in query)
        if pixiv_tags or not has_url_tags:
            for tag in tags:
                query.append(("tag", tag))

        return urlunparse(parsed._replace(query=urlencode(query)))

    def _download_header_attempts(
        self, image_url: str, referer_url: str = ""
    ) -> list[dict[str, str]]:
        configured = (self.config.get("image_referer", "auto") or "auto").strip()

        if configured.lower() in {"none", "off", "false", "0"}:
            referers: list[str | None] = [None]
        elif configured and configured.lower() != "auto":
            referers = [configured]
        else:
            referers = [
                None,
                self._origin_url(image_url),
                self._origin_url(referer_url),
            ]
            if self._is_pixiv_direct_image_url(image_url):
                referers.append("https://www.pixiv.net/")

        seen: set[str] = set()
        attempts: list[dict[str, str]] = []
        for referer in referers:
            key = referer or ""
            if key in seen:
                continue
            seen.add(key)
            attempts.append(self._browser_headers(referer))
        return attempts

    @staticmethod
    def _browser_headers(referer: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        }
        if referer:
            headers["Referer"] = referer
        return headers

    @staticmethod
    def _origin_url(value: str) -> str:
        parsed = urlparse(value or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return f"{parsed.scheme}://{parsed.netloc}/"

    def _extract_image_url(self, raw_text: str, base_url: str) -> str | None:
        text = (raw_text or "").strip().strip('"').strip("'")
        if self._is_http_url(text):
            return text

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            return None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, str) and error.strip():
                raise UserFacingError(f"图片 API 返回错误: {error.strip()}")
            if isinstance(payload.get("data"), list) and not payload["data"]:
                raise UserFacingError("没有找到符合条件的图片，可以换个标签试试")

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
    def _write_temp_image(
        image_bytes: bytes, content_type: str, source_url: str
    ) -> str:
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
