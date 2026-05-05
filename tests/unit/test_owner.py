"""State-machine tests for OwnerTracker (PR-2 owner detection)."""

from __future__ import annotations

import pytest

from poe2_rpc.domain.owner import OwnerState, OwnerTracker


def test_initial_state_is_unknown() -> None:
    t = OwnerTracker.unknown()
    assert t.state == OwnerState.UNKNOWN
    assert t.pinned_name is None
    assert t.override_name is None


def test_local_area_entered_no_override_transitions_to_area_entered() -> None:
    t = OwnerTracker.unknown().on_local_area_entered()
    assert t.state == OwnerState.AREA_ENTERED
    assert t.pinned_name is None


def test_local_area_entered_with_override_pins_immediately() -> None:
    t = OwnerTracker.unknown(override_name="MyChar").on_local_area_entered()
    assert t.state == OwnerState.PINNED
    assert t.pinned_name == "MyChar"


def test_party_join_in_area_window_invalidates() -> None:
    t = OwnerTracker.unknown().on_local_area_entered().on_party_member_joined()
    assert t.state == OwnerState.INVALIDATED
    assert t.pinned_name is None


def test_first_level_in_clean_window_pins() -> None:
    t = OwnerTracker.unknown().on_local_area_entered().on_level_event("Alice")
    assert t.state == OwnerState.PINNED
    assert t.pinned_name == "Alice"


def test_should_emit_only_for_pinned_name() -> None:
    t = OwnerTracker(state=OwnerState.PINNED, pinned_name="Alice")
    assert t.should_emit("Alice") is True
    assert t.should_emit("Bob") is False


def test_invalidated_state_drops_all_emit() -> None:
    t = OwnerTracker(state=OwnerState.INVALIDATED)
    assert t.should_emit("Alice") is False
    assert t.should_emit("Bob") is False


def test_party_join_while_pinned_keeps_pin() -> None:
    pinned = OwnerTracker.unknown().on_local_area_entered().on_level_event("Alice")
    after_join = pinned.on_party_member_joined()
    assert after_join.state == OwnerState.PINNED
    assert after_join.pinned_name == "Alice"


def test_re_entering_area_resets_invalidated_state() -> None:
    t = OwnerTracker.unknown().on_local_area_entered().on_party_member_joined()
    assert t.state == OwnerState.INVALIDATED
    t = t.on_local_area_entered()
    assert t.state == OwnerState.AREA_ENTERED
    assert t.pinned_name is None


def test_unknown_state_emits_freely() -> None:
    """Pre-area-entered events shouldn't be filtered (caller has no owner signal yet)."""
    t = OwnerTracker.unknown()
    assert t.should_emit("Anyone") is True


def test_area_entered_state_emits_freely() -> None:
    """A pinned-but-not-yet-pinned window emits to let the orchestrator pin on first level."""
    t = OwnerTracker.unknown().on_local_area_entered()
    assert t.should_emit("Anyone") is True


def test_owner_tracker_is_frozen() -> None:
    """Domain VOs are immutable per the AST guard in tests/unit/test_no_mutable_state.py."""
    t = OwnerTracker.unknown()
    with pytest.raises((TypeError, ValueError)):
        t.state = OwnerState.PINNED  # type: ignore[misc]


@pytest.mark.parametrize(
    ("scenario", "expected_state", "expected_pinned"),
    [
        # Solo player enters, levels up — pins to local
        (
            [("area",), ("level", "Alice")],
            OwnerState.PINNED,
            "Alice",
        ),
        # Solo player enters, party member joins, then someone levels — invalidated, drops level
        (
            [("area",), ("party", "Bob"), ("level", "Alice")],
            OwnerState.INVALIDATED,
            None,
        ),
        # Override set: first area entry pins immediately regardless of party
        (
            [("area",), ("party", "Bob"), ("level", "Bob")],
            OwnerState.PINNED,
            "MyChar",
        ),
    ],
    ids=["solo-then-level", "party-then-level-drops", "override-pins-first"],
)
def test_party_scenarios(
    scenario: list[tuple[str, ...]],
    expected_state: OwnerState,
    expected_pinned: str | None,
) -> None:
    override = "MyChar" if expected_pinned == "MyChar" else None
    t = OwnerTracker.unknown(override_name=override)
    for step in scenario:
        if step[0] == "area":
            t = t.on_local_area_entered()
        elif step[0] == "party":
            t = t.on_party_member_joined()
        elif step[0] == "level":
            t = t.on_level_event(step[1])
    assert t.state == expected_state
    assert t.pinned_name == expected_pinned
