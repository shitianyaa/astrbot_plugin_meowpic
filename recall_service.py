from __future__ import annotations

import time
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context

try:
    from .settings import LOG_PREFIX
except ImportError:
    from settings import LOG_PREFIX


class MeowPicRecallService:
    def __init__(self, context: Context):
        self.context = context
        self._recalled_message_ids: set[str] = set()

    async def recall_replied_image(
        self,
        event: AstrMessageEvent,
        reply: dict[str, Any],
        recall_window_seconds: int,
    ) -> tuple[bool, str]:
        message_id = reply["message_id"]
        detail = await self.get_message_detail(event, message_id)

        self_id = get_self_id(event)
        sender_id = extract_sender_id(detail) or str_or_empty(reply.get("sender_id"))
        if not self_id or not sender_id:
            return False, "无法确认引用图片是否机器人发出的，已取消撤回喵。"
        if sender_id != self_id:
            return False, "只能撤回机器人发出的图片喵。"
        if not message_contains_image(detail):
            return False, "引用的不是机器人发出的图片消息喵。"

        sent_at = coerce_timestamp(
            pick_from_dict(detail, "time", "timestamp") or reply.get("time")
        )
        if is_over_recall_window(sent_at, recall_window_seconds):
            return False, "这张图已经超过撤回窗口，QQ 通常撤回不了了喵。"

        if await self.delete_message(event, message_id):
            self._remember_recalled(message_id)
            return True, ""
        return False, "撤回失败，可能已超过 2 分钟、消息已撤回，或机器人没有权限喵。"

    async def recall_last_bot_image(
        self,
        event: AstrMessageEvent,
        history_limit: int,
        recall_window_seconds: int,
    ) -> tuple[bool, str]:
        found, history_error = await self.find_last_bot_image(
            event, history_limit, recall_window_seconds
        )
        if not found:
            if history_error == "expired":
                return False, "expired"
            if history_error:
                return (
                    False,
                    f"没有从协议端历史里找到最近 {recall_window_seconds} 秒内机器人发出的图片喵。"
                    "当前 OneBot 实现可能不支持消息历史接口。",
                )
            return (
                False,
                f"最近 {recall_window_seconds} 秒内没有找到机器人发出的图片喵。",
            )

        message_id = found.get("message_id")
        if await self.delete_message(event, message_id):
            self._remember_recalled(message_id)
            return True, ""
        return False, "撤回失败，可能已超过 2 分钟、消息已撤回，或机器人没有权限喵。"

    async def find_last_bot_image(
        self,
        event: AstrMessageEvent,
        history_limit: int,
        recall_window_seconds: int,
    ) -> tuple[dict[str, Any] | None, bool | str]:
        messages, had_error = await self.fetch_history_messages(event, history_limit)
        if not messages:
            return None, had_error

        self_id = get_self_id(event)
        if not self_id:
            return None, had_error

        candidates: list[dict[str, Any]] = []
        had_expired_image = False
        for idx, msg in enumerate(messages):
            if not isinstance(msg, dict):
                continue
            if extract_sender_id(msg) != self_id:
                continue
            message_id = extract_message_id(msg)
            if not message_id or not message_contains_image(msg):
                continue
            if str(message_id) in self._recalled_message_ids:
                continue
            sent_at = coerce_timestamp(pick_from_dict(msg, "time", "timestamp"))
            if is_over_recall_window(sent_at, recall_window_seconds):
                had_expired_image = True
                continue
            candidates.append(
                {
                    "message_id": message_id,
                    "time": sent_at,
                    "_idx": idx,
                }
            )

        if not candidates:
            if had_expired_image:
                return None, "expired"
            return None, had_error

        with_time = [item for item in candidates if item.get("time")]
        if with_time:
            return max(with_time, key=lambda item: item["time"]), had_error
        return candidates[-1], had_error

    def _remember_recalled(self, message_id: Any):
        if message_id not in (None, ""):
            self._recalled_message_ids.add(str(message_id))
        if len(self._recalled_message_ids) > 500:
            self._recalled_message_ids = set(list(self._recalled_message_ids)[-250:])

    async def fetch_history_messages(
        self, event: AstrMessageEvent, limit: int
    ) -> tuple[list[dict[str, Any]], bool]:
        group_id = event.get_group_id()
        variants: list[tuple[str, dict[str, Any]]] = []

        if group_id:
            group_id_value = maybe_int(group_id)
            variants.extend(
                [
                    (
                        "get_group_msg_history",
                        {"group_id": group_id_value, "message_seq": 0},
                    ),
                    (
                        "get_group_msg_history",
                        {"group_id": group_id_value, "count": limit},
                    ),
                    ("get_group_msg_history", {"group_id": group_id_value}),
                ]
            )
        else:
            user_id = maybe_int(event.get_sender_id())
            variants.extend(
                [
                    (
                        "get_friend_msg_history",
                        {"user_id": user_id, "message_seq": 0},
                    ),
                    (
                        "get_friend_msg_history",
                        {"user_id": user_id, "count": limit},
                    ),
                    ("get_friend_msg_history", {"user_id": user_id}),
                    (
                        "get_private_msg_history",
                        {"user_id": user_id, "message_seq": 0},
                    ),
                    (
                        "get_private_msg_history",
                        {"user_id": user_id, "count": limit},
                    ),
                    ("get_private_msg_history", {"user_id": user_id}),
                ]
            )

        had_error = False
        for action, payload in variants:
            try:
                ret = await self.call_action(event, action, **payload)
            except Exception as e:
                had_error = True
                logger.debug(f"{LOG_PREFIX} {action} failed: {e}")
                continue
            messages = extract_messages_from_history(ret)
            if messages:
                return messages, had_error
        return [], had_error

    async def get_message_detail(
        self, event: AstrMessageEvent, message_id: Any
    ) -> dict[str, Any]:
        try:
            ret = await self.call_action(
                event, "get_msg", message_id=maybe_int(message_id)
            )
        except Exception as e:
            logger.debug(f"{LOG_PREFIX} get_msg {message_id} failed: {e}")
            return {}
        if isinstance(ret, dict) and isinstance(ret.get("data"), dict):
            return ret["data"]
        return ret if isinstance(ret, dict) else {}

    async def delete_message(self, event: AstrMessageEvent, message_id: Any) -> bool:
        if not message_id:
            return False
        try:
            await self.call_action(
                event, "delete_msg", message_id=maybe_int(message_id)
            )
            return True
        except Exception as e:
            logger.debug(f"{LOG_PREFIX} delete_msg {message_id} failed: {e}")
            return False

    async def call_action(self, event: AstrMessageEvent, action: str, **payload: Any):
        bot = getattr(event, "bot", None)
        if bot is not None:
            if callable(getattr(bot, "call_action", None)):
                return await bot.call_action(action, **payload)
            api = getattr(bot, "api", None)
            if api is not None and callable(getattr(api, "call_action", None)):
                return await api.call_action(action, **payload)

        platform = self.context.get_platform(filter.PlatformAdapterType.AIOCQHTTP)
        client = platform.get_client()
        api = getattr(client, "api", client)
        return await api.call_action(action, **payload)


def extract_reply_info(event: AstrMessageEvent) -> dict[str, Any]:
    message_obj = getattr(event, "message_obj", None)
    for comp in getattr(message_obj, "message", []) or []:
        comp_type = str(getattr(comp, "type", "")).lower()
        if comp.__class__.__name__.lower() == "reply" or "reply" in comp_type:
            return {
                "message_id": str_or_empty(
                    getattr(comp, "id", "") or getattr(comp, "message_id", "")
                ),
                "sender_id": str_or_empty(getattr(comp, "sender_id", "")),
                "time": coerce_timestamp(getattr(comp, "time", None)),
            }

    raw = getattr(message_obj, "raw_message", None)
    raw_reply = extract_reply_from_raw(raw)
    if raw_reply:
        return raw_reply
    return {"message_id": "", "sender_id": "", "time": None}


def extract_reply_from_raw(raw: Any) -> dict[str, Any] | None:
    segments: list[Any] = []
    if isinstance(raw, dict):
        raw_message = raw.get("message")
        if isinstance(raw_message, list):
            segments = raw_message
    elif isinstance(raw, list):
        segments = raw

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        if str(seg.get("type", "")).lower() != "reply":
            continue
        data = seg.get("data", {})
        if not isinstance(data, dict):
            data = {}
        return {
            "message_id": str_or_empty(data.get("id") or seg.get("id")),
            "sender_id": str_or_empty(data.get("sender_id") or seg.get("sender_id")),
            "time": coerce_timestamp(data.get("time") or seg.get("time")),
        }
    return None


def extract_messages_from_history(ret: Any) -> list[dict[str, Any]]:
    if isinstance(ret, list):
        return [item for item in ret if isinstance(item, dict)]
    if not isinstance(ret, dict):
        return []

    candidates = [
        ret.get("messages"),
        ret.get("message"),
        ret.get("data", {}).get("messages")
        if isinstance(ret.get("data"), dict)
        else None,
    ]
    for value in candidates:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def get_self_id(event: AstrMessageEvent) -> str:
    direct = safe_call(event, "get_self_id")
    if direct:
        return str(direct)

    message_obj = getattr(event, "message_obj", None)
    value = getattr(message_obj, "self_id", None)
    if value:
        return str(value)

    raw = getattr(message_obj, "raw_message", None)
    if isinstance(raw, dict):
        for key in ("self_id", "bot_id", "login_uid"):
            value = raw.get(key)
            if value:
                return str(value)
    return ""


def extract_message_id(msg: dict[str, Any]) -> str:
    for key in ("message_id", "id"):
        value = msg.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def extract_sender_id(msg: dict[str, Any]) -> str:
    sender = msg.get("sender")
    if isinstance(sender, dict):
        for key in ("user_id", "id", "sender_id"):
            value = sender.get(key)
            if value not in (None, ""):
                return str(value)
    for key in ("user_id", "sender_id"):
        value = msg.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def message_contains_image(value: Any) -> bool:
    if isinstance(value, dict):
        if str(value.get("type", "")).strip().lower() == "image":
            return True
        return any(message_contains_image(item) for item in value.values())

    if isinstance(value, (list, tuple)):
        return any(message_contains_image(item) for item in value)

    if isinstance(value, str):
        return "[cq:image" in value.lower()

    return False


def pick_from_dict(data: dict[str, Any], *keys: str) -> Any:
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return None


def coerce_timestamp(value: Any) -> int | None:
    try:
        ts = int(float(value))
    except (TypeError, ValueError):
        return None
    if ts <= 0:
        return None
    if ts > 10_000_000_000:
        ts //= 1000
    return ts


def is_over_recall_window(sent_at: int | None, recall_window_seconds: int) -> bool:
    if not sent_at:
        return False
    return time.time() - sent_at > recall_window_seconds


def safe_call(obj: Any, method: str) -> Any:
    func = getattr(obj, method, None)
    if not callable(func):
        return None
    try:
        return func()
    except Exception:
        return None


def maybe_int(value: Any) -> int | str:
    text = str(value)
    return int(text) if text.isdigit() else text


def str_or_empty(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value)
