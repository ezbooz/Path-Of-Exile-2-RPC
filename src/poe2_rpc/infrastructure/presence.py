"""Discord Rich Presence publisher — infrastructure adapter for PresencePublisher port."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pypresence.exceptions as pex
import pypresence.presence as _pres
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from poe2_rpc.domain.models import InstanceInfo, LevelInfo
from poe2_rpc.infrastructure.settings import AppSettings

_CONNECT_RETRY_EXCEPTIONS = (
    pex.DiscordError,
    pex.PipeClosed,
    pex.InvalidPipe,
    pex.ConnectionTimeout,
    ConnectionError,
    OSError,
)

_PUBLISH_RETRY_EXCEPTIONS = (
    pex.DiscordError,
    pex.PipeClosed,
)


class PypresencePublisher:
    """Wraps pypresence.AioPresence with retry policies on connect and publish."""

    def __init__(
        self,
        settings: AppSettings,
        *,
        presence_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._settings = settings
        self._factory: Callable[[str], Any] = presence_factory or _pres.AioPresence
        self._presence: Any = None

    async def connect(self) -> None:
        """Connect to Discord IPC with exponential-backoff retry (5×, 2–32 s)."""
        presence = self._factory(self._settings.discord_app_id)

        @retry(
            retry=retry_if_exception_type(_CONNECT_RETRY_EXCEPTIONS),
            stop=stop_after_attempt(self._settings.connect_retry_attempts),
            wait=wait_exponential(multiplier=2, max=32),
            reraise=True,
        )
        async def _connect() -> None:
            await presence.connect()

        await _connect()
        self._presence = presence

    async def publish(
        self,
        level_info: LevelInfo | None,
        instance_info: InstanceInfo | None,
        *,
        afk_on: bool = False,
        small_image_override: str | None = None,
    ) -> None:
        """Publish a Rich Presence update with its own 3× retry (independent of connect)."""
        if self._presence is None:
            raise RuntimeError("publish() called before connect()")

        kwargs = self._build_update_kwargs(
            level_info,
            instance_info,
            afk_on=afk_on,
            small_image_override=small_image_override,
        )
        presence = self._presence

        @retry(
            retry=retry_if_exception_type(_PUBLISH_RETRY_EXCEPTIONS),
            stop=stop_after_attempt(self._settings.publish_retry_attempts),
            wait=wait_exponential(multiplier=1, max=8),
            reraise=True,
        )
        async def _publish() -> None:
            await presence.update(**kwargs)

        await _publish()

    @staticmethod
    def _build_update_kwargs(
        level_info: LevelInfo | None,
        instance_info: InstanceInfo | None,
        *,
        afk_on: bool = False,
        small_image_override: str | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "start": int(datetime.now(tz=UTC).timestamp()),
        }
        if level_info is not None:
            details = f"{level_info.username} ({level_info.base_class}"
            if level_info.ascension_class is not None:
                details += f" | {level_info.ascension_class}"
            details += f" - Lvl {level_info.level})"
            kwargs["details"] = details
            asc = level_info.ascension_class or level_info.base_class
            kwargs["small_image"] = asc.lower().replace(" ", "_")
        if small_image_override is not None:
            kwargs["small_image"] = small_image_override
        if instance_info is not None:
            state = f"In: {instance_info.area_display_name} (Lvl {instance_info.level})"
            if afk_on:
                state += " [AFK]"
            kwargs["state"] = state
        elif afk_on:
            kwargs["state"] = "[AFK]"
        return kwargs

    def close(self) -> None:
        """Close the Discord IPC connection."""
        if self._presence is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._presence.close())
                else:
                    loop.run_until_complete(self._presence.close())
            except Exception:
                pass
            self._presence = None
