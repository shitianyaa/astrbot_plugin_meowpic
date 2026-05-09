from __future__ import annotations

import asyncio

import aiohttp

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

try:
    from .errors import UserFacingError
    from .image_service import ImageServiceMixin
    from .recall_service import MeowPicRecallService, extract_reply_info
    from .settings import (
        DEFAULT_LIMIT_MESSAGE,
        DEFAULT_RECALL_EXPIRED_MESSAGE,
        DEFAULT_RECALL_SUCCESS_MESSAGE,
        LOG_PREFIX,
    )
    from .user_config import UserConfigMixin
except ImportError:
    from errors import UserFacingError
    from image_service import ImageServiceMixin
    from recall_service import MeowPicRecallService, extract_reply_info
    from settings import (
        DEFAULT_LIMIT_MESSAGE,
        DEFAULT_RECALL_EXPIRED_MESSAGE,
        DEFAULT_RECALL_SUCCESS_MESSAGE,
        LOG_PREFIX,
    )
    from user_config import UserConfigMixin


@register(
    "astrbot_plugin_meowpic",
    "Sham1k0",
    "多分类随机图片插件，支持 Pixiv 标签、自定义 API、API Key 与图片撤回",
    "1.4.1",
)
class MeowPicPlugin(ImageServiceMixin, UserConfigMixin, Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.session: aiohttp.ClientSession | None = None
        self._request_log: dict[str, list[float]] = {}
        self._last_request_log_prune = 0.0
        self.recall_service = MeowPicRecallService(context)

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

    @filter.command("mm", alias={"小姐姐", "美女"})
    async def cmd_mm(self, event: AstrMessageEvent):
        """随机返回一张图片"""
        async for result in self._yield_random_image(event, "meinv"):
            yield result

    @filter.command("白丝", alias={"baisi"})
    async def cmd_baisi(self, event: AstrMessageEvent):
        """随机返回一张白丝图片"""
        async for result in self._yield_random_image(event, "baisi"):
            yield result

    @filter.command("黑丝", alias={"heisi"})
    async def cmd_heisi(self, event: AstrMessageEvent):
        """随机返回一张黑丝图片"""
        async for result in self._yield_random_image(event, "heisi"):
            yield result

    @filter.command("二次元", alias={"acg"})
    async def cmd_acg(self, event: AstrMessageEvent):
        """随机返回一张二次元图片"""
        async for result in self._yield_random_image(event, "acg"):
            yield result

    @filter.command("jk")
    async def cmd_jk(self, event: AstrMessageEvent):
        """随机返回一张 JK 图片"""
        async for result in self._yield_random_image(event, "jk"):
            yield result

    @filter.command("px", alias={"pixiv", "p站"})
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

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_hentai_recall(self, event: AstrMessageEvent):
        """监听 hentai 并撤回机器人发出的图片"""
        if not self._is_recall_trigger(event):
            return
        async for result in self._yield_recall_image(event):
            yield result

    @filter.command_group("meowpic")
    def meowpic(self):
        """喵图姬指令组"""
        pass

    @meowpic.command("help")
    async def cmd_help(self, event: AstrMessageEvent):
        """查看喵图姬指令"""
        yield event.plain_result(
            "喵图姬指令\n"
            "/mm                         随机小姐姐\n"
            "/小姐姐                     随机小姐姐\n"
            "/美女                       随机小姐姐\n"
            "/白丝                       白丝\n"
            "/黑丝                       黑丝\n"
            "/二次元                     二次元\n"
            "/jk                         JK\n"
            "/px [标签1] [标签2] [标签3] Pixiv 随机图，默认非 R18\n"
            "/pixiv [标签1] [标签2] [标签3] 同 /px\n"
            "/p站 [标签1] [标签2] [标签3]    同 /px\n"
            "/meowpic pixiv [标签...]     同 /px\n"
            "/meowpic get pixiv [标签...] 同 /px\n"
            "/meowpic help                查看指令\n"
            "hentai                      回复图片时撤回该图，否则撤回最近 2 分钟内机器人图片"
        )

    @meowpic.command("pixiv")
    async def cmd_meowpic_pixiv(
        self,
        event: AstrMessageEvent,
        tag1: str = "",
        tag2: str = "",
        tag3: str = "",
    ):
        """通过指令组返回 Pixiv 图片"""
        async for result in self._yield_random_image(
            event, "pixiv", self._normalize_pixiv_tags(tag1, tag2, tag3)
        ):
            yield result

    @meowpic.command("get")
    async def cmd_meowpic_get(
        self,
        event: AstrMessageEvent,
        category: str = "",
        tag1: str = "",
        tag2: str = "",
        tag3: str = "",
    ):
        """兼容 /meowpic get pixiv 标签"""
        if category.strip().lower() not in {"pixiv", "px", "p站"}:
            yield event.plain_result("用法：/meowpic get pixiv [标签1] [标签2] [标签3]")
            return

        async for result in self._yield_random_image(
            event, "pixiv", self._normalize_pixiv_tags(tag1, tag2, tag3)
        ):
            yield result

    async def _yield_recall_image(self, event: AstrMessageEvent):
        if self._safe_call(event, "get_platform_name") != "aiocqhttp":
            yield event.plain_result(
                "当前平台暂不支持撤回喵，仅支持 aiocqhttp/OneBot。"
            )
            return

        if not self._can_use_recall_image(event):
            yield event.plain_result("此指令仅管理员或喵图撤回白名单用户可用喵。")
            return

        recall_window_seconds = self._get_int("recall_window_seconds", 120, 1, 3600)
        history_limit = self._get_int("recall_history_limit", 30, 5, 100)

        reply = extract_reply_info(event)
        if reply.get("message_id"):
            ok, message = await self.recall_service.recall_replied_image(
                event, reply, recall_window_seconds
            )
        else:
            ok, message = await self.recall_service.recall_last_bot_image(
                event, history_limit, recall_window_seconds
            )

        if ok:
            success_message = self._get_str(
                "recall_success_message", DEFAULT_RECALL_SUCCESS_MESSAGE
            )
            if success_message:
                yield event.plain_result(success_message)
            return

        if message == "expired":
            message = self._get_str(
                "recall_expired_message", DEFAULT_RECALL_EXPIRED_MESSAGE
            )
        yield event.plain_result(message)

    def _can_use_recall_image(self, event: AstrMessageEvent) -> bool:
        if self._is_admin(event):
            return True
        sender_id = self._get_sender_id(event)
        if sender_id and sender_id in self._get_recall_whitelist_user_ids():
            return True
        return self._get_bool("recall_allow_anyone", False)

    def _get_recall_whitelist_user_ids(self) -> set[str]:
        value = self._get_str("recall_whitelist_user_ids", "")
        return set(self._split_list_value(value))

    def _is_recall_trigger(self, event: AstrMessageEvent) -> bool:
        trigger = self._get_str("recall_trigger_text", "hentai").lower()
        message = str(getattr(event, "message_str", "") or "").strip().lower()
        return bool(trigger and message == trigger)

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        direct = self._safe_call(event, "is_admin")
        if isinstance(direct, bool):
            return direct
        if direct is not None:
            return str(direct).strip().lower() in {"1", "true", "yes", "admin", "owner"}

        for value in self._possible_sender_roles(event):
            role = str(value).strip().lower()
            if role in {
                "admin",
                "administrator",
                "owner",
                "superuser",
                "管理员",
                "群主",
            }:
                return True
        return False

    def _possible_sender_roles(self, event: AstrMessageEvent):
        role = getattr(event, "role", None)
        if role:
            yield role

        message_obj = getattr(event, "message_obj", None)
        sender = getattr(message_obj, "sender", None)
        for attr in ("role", "permission"):
            value = getattr(sender, attr, None)
            if value:
                yield value

        raw = getattr(message_obj, "raw_message", None)
        if isinstance(raw, dict):
            raw_sender = raw.get("sender")
            if isinstance(raw_sender, dict):
                for key in ("role", "permission"):
                    value = raw_sender.get(key)
                    if value:
                        yield value

    async def _yield_random_image(
        self,
        event: AstrMessageEvent,
        category: str,
        pixiv_tags: list[str] | None = None,
    ):
        if not self._record_request(event):
            yield event.plain_result(
                self._get_str("rate_limit_message", DEFAULT_LIMIT_MESSAGE)
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
