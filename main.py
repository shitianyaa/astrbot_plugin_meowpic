from __future__ import annotations

import asyncio

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from .errors import UserFacingError
    from .image_service import ImageServiceMixin
    from .settings import (
        DEFAULT_CATEGORY,
        DEFAULT_LIMIT_MESSAGE,
        IMAGE_CATEGORIES,
        KV_USER_CONFIGS,
        LOG_PREFIX,
    )
    from .user_config import UserConfigMixin
except ImportError:
    from errors import UserFacingError
    from image_service import ImageServiceMixin
    from settings import (
        DEFAULT_CATEGORY,
        DEFAULT_LIMIT_MESSAGE,
        IMAGE_CATEGORIES,
        KV_USER_CONFIGS,
        LOG_PREFIX,
    )
    from user_config import UserConfigMixin


@register(
    "astrbot_plugin_meowpic",
    "Sham1k0",
    "多分类随机图片插件，支持 Pixiv 标签、自定义 API 与 API Key",
    "1.3.1",
)
class MeowPicPlugin(ImageServiceMixin, UserConfigMixin, Star):
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
        except asyncio.TimeoutError:
            yield event.plain_result("图片请求超时了喵，可以稍后再试或调大请求超时")
        except Exception as e:
            logger.error(f"{LOG_PREFIX} fetch image failed: {e}", exc_info=True)
            yield event.plain_result("图片获取失败了喵，请稍后再试")
        finally:
            if temp_path:
                self._cleanup_temp_file(temp_path)
