from __future__ import annotations

import asyncio
import json
import os
import random
import tempfile
import time
from typing import Any
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent

try:
    from .errors import UserFacingError
    from .settings import (
        DEFAULT_TIMEOUT_SECONDS,
        DEFAULT_USER_AGENT,
        FALSE_STRINGS,
        IMAGE_SUFFIX_BY_CONTENT_TYPE,
        LOG_PREFIX,
        PREFERRED_IMAGE_KEYS,
    )
except ImportError:
    from errors import UserFacingError
    from settings import (
        DEFAULT_TIMEOUT_SECONDS,
        DEFAULT_USER_AGENT,
        FALSE_STRINGS,
        IMAGE_SUFFIX_BY_CONTENT_TYPE,
        LOG_PREFIX,
        PREFERRED_IMAGE_KEYS,
    )


class ImageServiceMixin:
    async def _fetch_image_for_event(
        self,
        event: AstrMessageEvent,
        category: str,
        pixiv_tags: list[str],
    ) -> tuple[str, str | None]:
        api_url, _ = self._get_category_api_url(category)
        api_key = self._get_api_key()

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
                if not self._looks_like_image_bytes(image_bytes):
                    raise UserFacingError("图片 API 返回的内容不是有效图片")
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

        timed_out = False
        client_error = ""
        invalid_image_response = False
        total_timeout = timeout.total
        if total_timeout is None:
            total_timeout = DEFAULT_TIMEOUT_SECONDS
        deadline = time.monotonic() + max(float(total_timeout), 0.1)

        for candidate_url in self._image_url_attempts(image_url):
            for headers in self._download_header_attempts(candidate_url, referer_url):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                try:
                    async with session.get(
                        candidate_url,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=remaining),
                        allow_redirects=True,
                    ) as resp:
                        if resp.status >= 400:
                            last_status = resp.status
                            if resp.status in (401, 403, 429):
                                continue
                            raise UserFacingError(f"图片下载失败: HTTP {resp.status}")

                        content_type = (
                            resp.headers.get("Content-Type", "")
                            .split(";", 1)[0]
                            .lower()
                        )
                        image_bytes = await resp.read()
                        last_content_type = content_type
                        if image_bytes and self._looks_like_image_bytes(image_bytes):
                            return self._write_temp_image(
                                image_bytes, content_type, str(resp.url)
                            )
                        if image_bytes:
                            invalid_image_response = True
                except asyncio.TimeoutError:
                    timed_out = True
                    continue
                except aiohttp.ClientError as e:
                    client_error = str(e)
                    continue
            if time.monotonic() >= deadline:
                break

        if last_status is not None:
            raise UserFacingError(f"图片下载失败: HTTP {last_status}")
        if invalid_image_response:
            detail = f" ({last_content_type})" if last_content_type else ""
            raise UserFacingError(f"图片下载失败: 返回内容不是有效图片{detail}")
        if last_content_type:
            raise UserFacingError(f"图片下载失败: 返回类型 {last_content_type}")
        if timed_out:
            raise UserFacingError(
                "图片下载超时了喵，可以调大请求超时或换一个 Pixiv 反代"
            )
        if client_error:
            raise UserFacingError(f"图片下载失败: {client_error}")
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

        proxy = self._get_str("pixiv_proxy", "i.pixiv.re")
        if "proxy" not in existing_keys and proxy.lower() not in FALSE_STRINGS:
            query.append(("proxy", proxy))
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
        configured = self._get_str("image_referer", "auto") or "auto"

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

    def _image_url_attempts(self, image_url: str) -> list[str]:
        attempts = [image_url]

        direct_url = self._pixiv_direct_image_url(image_url)
        if direct_url and direct_url not in attempts:
            attempts.append(direct_url)

        proxied_url = self._pixiv_proxy_image_url(image_url)
        if proxied_url and proxied_url not in attempts:
            attempts.append(proxied_url)

        return attempts

    @staticmethod
    def _pixiv_direct_image_url(value: str) -> str:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if hostname in {"", "i.pximg.net"} or hostname.endswith(".pximg.net"):
            return ""

        if parsed.path.startswith(("/img-original/", "/img-master/", "/c/")):
            return urlunparse(parsed._replace(netloc="i.pximg.net"))
        return ""

    def _pixiv_proxy_image_url(self, value: str) -> str:
        parsed = urlparse(value)
        hostname = (parsed.hostname or "").lower()
        if hostname != "i.pximg.net" and not hostname.endswith(".pximg.net"):
            return ""

        proxy = self._get_str("pixiv_proxy", "i.pixiv.re")
        if proxy.lower() in FALSE_STRINGS:
            return ""

        if "{{path}}" in proxy:
            image_path = parsed.path.lstrip("/")
            proxy = proxy.replace("{{path}}", image_path)
            proxy_parsed = urlparse(proxy if "://" in proxy else f"https://{proxy}")
            if proxy_parsed.scheme in {"http", "https"} and proxy_parsed.netloc:
                return urlunparse(proxy_parsed._replace(query=parsed.query))
            return ""

        proxy_parsed = urlparse(proxy if "://" in proxy else f"https://{proxy}")
        if proxy_parsed.scheme not in {"http", "https"} or not proxy_parsed.netloc:
            return ""

        proxy_path = proxy_parsed.path.rstrip("/")
        image_path = parsed.path
        path = f"{proxy_path}{image_path}" if proxy_path else image_path
        return urlunparse(
            parsed._replace(
                scheme=proxy_parsed.scheme,
                netloc=proxy_parsed.netloc,
                path=path,
            )
        )

    @staticmethod
    def _browser_headers(referer: str | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "image/jpeg,image/png,image/gif,image/webp,image/bmp,image/*;q=0.8,*/*;q=0.5",
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
            return urljoin(base_url, text)

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
        image_candidates = [
            url for url in candidates if self._looks_like_image_url(url)
        ]
        return urljoin(base_url, random.choice(image_candidates or candidates))

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

    @staticmethod
    def _looks_like_image_bytes(value: bytes) -> bool:
        head = value[:32]
        return (
            head.startswith(b"\xff\xd8\xff")
            or head.startswith(b"\x89PNG\r\n\x1a\n")
            or head.startswith((b"GIF87a", b"GIF89a"))
            or head.startswith(b"BM")
            or (head.startswith(b"RIFF") and head[8:12] == b"WEBP")
            or (head[4:8] == b"ftyp" and (b"avif" in head[8:] or b"avis" in head[8:]))
        )

    @staticmethod
    def _write_temp_image(
        image_bytes: bytes, content_type: str, source_url: str
    ) -> str:
        suffix = IMAGE_SUFFIX_BY_CONTENT_TYPE.get(content_type)
        if not suffix:
            source_path = urlparse(source_url).path.lower()
            for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".bmp"):
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
