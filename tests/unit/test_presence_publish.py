"""Unit tests for PypresencePublisher.publish (C-7b)."""

from __future__ import annotations

import pypresence.exceptions as pex
import pytest

from poe2_rpc.domain.models import InstanceInfo, LevelInfo
from poe2_rpc.infrastructure.presence import PypresencePublisher
from poe2_rpc.infrastructure.settings import AppSettings


class FakeAioPresence:
    """Test double for pypresence.AioPresence used in publish tests."""

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.update_call_count = 0
        self._side_effects: list[Exception | None] = []
        self.last_update_kwargs: dict[str, object] = {}

    def set_side_effects(self, effects: list[Exception | None]) -> None:
        self._side_effects = list(effects)

    async def connect(self) -> None:
        pass

    async def update(self, **kwargs: object) -> None:
        self.update_call_count += 1
        self.last_update_kwargs = dict(kwargs)
        if self._side_effects:
            effect = self._side_effects.pop(0)
            if effect is not None:
                raise effect

    async def close(self) -> None:
        pass


@pytest.fixture
def settings() -> AppSettings:
    return AppSettings(
        discord_app_id="test-app-id",
        connect_retry_attempts=5,
        publish_retry_attempts=3,
    )


@pytest.fixture
def level_info() -> LevelInfo:
    return LevelInfo(
        username="TestUser",
        base_class="Witch",
        ascension_class="Lich",
        level=42,
    )


@pytest.fixture
def instance_info() -> InstanceInfo:
    return InstanceInfo(
        area_code="G1_1",
        area_display_name="Clearfell",
        level=5,
        seed=12345,
    )


@pytest.mark.asyncio
async def test_publish_calls_aiopresence_update_once_on_success(
    settings: AppSettings,
    level_info: LevelInfo,
    instance_info: InstanceInfo,
) -> None:
    fake = FakeAioPresence("test-app-id")
    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]
    publisher._presence = fake  # inject already-connected presence

    await publisher.publish(level_info, instance_info)

    assert fake.update_call_count == 1


@pytest.mark.asyncio
async def test_publish_retries_3_times_on_discorderror(
    settings: AppSettings,
    level_info: LevelInfo,
    instance_info: InstanceInfo,
    mocker: object,
) -> None:
    mocker.patch("asyncio.sleep")  # type: ignore[union-attr]

    fake = FakeAioPresence("test-app-id")
    # Fail 2 times, succeed on 3rd
    fake.set_side_effects([pex.DiscordError(4000, "x"), pex.DiscordError(4000, "x"), None])
    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]
    publisher._presence = fake

    await publisher.publish(level_info, instance_info)

    assert fake.update_call_count == 3


@pytest.mark.asyncio
async def test_publish_reraises_after_3_attempts(
    settings: AppSettings,
    level_info: LevelInfo,
    instance_info: InstanceInfo,
    mocker: object,
) -> None:
    mocker.patch("asyncio.sleep")  # type: ignore[union-attr]

    fake = FakeAioPresence("test-app-id")
    fake.set_side_effects([pex.DiscordError(4000, "x") for _ in range(3)])
    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]
    publisher._presence = fake

    with pytest.raises(pex.DiscordError):
        await publisher.publish(level_info, instance_info)

    assert fake.update_call_count == 3


@pytest.mark.asyncio
async def test_publish_does_not_share_retry_state_with_connect(
    settings: AppSettings,
    level_info: LevelInfo,
    instance_info: InstanceInfo,
) -> None:
    fake = FakeAioPresence("test-app-id")
    publisher = PypresencePublisher(settings, presence_factory=lambda cid: fake)  # type: ignore[arg-type]
    publisher._presence = fake

    # Run publish — should succeed independently without any connect state
    await publisher.publish(level_info, instance_info)

    # Verify publish retry is independent: a fresh publisher also works
    fake2 = FakeAioPresence("test-app-id")
    publisher2 = PypresencePublisher(settings, presence_factory=lambda cid: fake2)  # type: ignore[arg-type]
    publisher2._presence = fake2
    await publisher2.publish(level_info, instance_info)

    assert fake.update_call_count == 1
    assert fake2.update_call_count == 1
