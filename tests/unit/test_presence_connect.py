"""Unit tests for PypresencePublisher.connect (C-7a)."""

from __future__ import annotations

import pypresence.exceptions as pex
import pytest

from poe2_rpc.infrastructure.presence import PypresencePublisher
from poe2_rpc.infrastructure.settings import AppSettings


class FakeAioPresence:
    """Test double for pypresence.AioPresence."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.connect_call_count = 0
        self._side_effects: list[Exception | None] = []

    def set_side_effects(self, effects: list[Exception | None]) -> None:
        self._side_effects = list(effects)

    async def connect(self) -> None:
        self.connect_call_count += 1
        if self._side_effects:
            effect = self._side_effects.pop(0)
            if effect is not None:
                raise effect

    async def close(self) -> None:
        pass

    async def update(self, **kwargs: object) -> None:
        pass


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(discord_app_id="test-app-id", connect_retry_attempts=5)


@pytest.mark.asyncio
async def test_connect_calls_aiopresence_connect_once_on_success(settings: AppSettings) -> None:
    fake = FakeAioPresence("test-app-id")
    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]
    await publisher.connect()

    assert fake.connect_call_count == 1
    assert fake.client_id == "test-app-id"


@pytest.mark.asyncio
async def test_connect_retries_5_times_on_pipeclosed(settings: AppSettings, mocker: object) -> None:
    mocker.patch("asyncio.sleep")  # type: ignore[union-attr]

    fake = FakeAioPresence("test-app-id")
    # Fail 4 times, succeed on 5th
    fake.set_side_effects(
        [pex.PipeClosed(), pex.PipeClosed(), pex.PipeClosed(), pex.PipeClosed(), None]
    )

    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]
    await publisher.connect()

    assert fake.connect_call_count == 5


@pytest.mark.asyncio
async def test_connect_reraises_after_all_attempts_exhausted(
    settings: AppSettings, mocker: object
) -> None:
    mocker.patch("asyncio.sleep")  # type: ignore[union-attr]

    fake = FakeAioPresence("test-app-id")
    fake.set_side_effects([pex.PipeClosed()] * 5)

    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]

    with pytest.raises(pex.PipeClosed):
        await publisher.connect()

    assert fake.connect_call_count == 5


@pytest.mark.asyncio
async def test_connect_uses_settings_app_id(mocker: object) -> None:
    custom_settings = AppSettings(discord_app_id="custom-id-123", connect_retry_attempts=5)
    captured: list[str] = []

    def factory(cid: str) -> FakeAioPresence:
        captured.append(cid)
        return FakeAioPresence(cid)

    publisher = PypresencePublisher(custom_settings, presence_factory=factory)  # type: ignore[arg-type]
    await publisher.connect()

    assert captured == ["custom-id-123"]
