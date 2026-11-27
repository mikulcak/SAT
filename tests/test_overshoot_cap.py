from types import SimpleNamespace

from custom_components.sat.area import Areas
from custom_components.sat.const import COLD_SETPOINT


def _area(entity_id: str, error: float, requires_heat: bool = True):
    return SimpleNamespace(
        id=entity_id,
        pid=SimpleNamespace(available=True),
        requires_heat=requires_heat,
        temperature_state=SimpleNamespace(error=error),
    )


def _cap(*areas) -> float | None:
    return Areas._PIDs(list(areas)).overshoot_cap


def test_overshoot_cap_applies_when_no_room_is_cold():
    # Kitchen 0.5 °C too warm, study at target: cap = 22 + 10 - 4 * 0.5
    assert _cap(_area("climate.kitchen", -0.5), _area("climate.study", 0.0)) == 30.0


def test_overshoot_cap_skipped_when_another_room_is_clearly_cold():
    # 27.11.2026: the kitchen 0.5 °C over target capped the whole house to 30 °C
    # while the study was 4 °C below its target.
    assert _cap(_area("climate.kitchen", -0.5), _area("climate.study", 4.0)) is None


def test_overshoot_cap_still_applies_when_cold_room_is_within_margin():
    assert _cap(_area("climate.kitchen", -0.5), _area("climate.study", 0.5)) == 30.0


def test_overshoot_cap_ignores_cold_rooms_that_do_not_call_for_heat():
    cold_closed = _area("climate.study", 4.0, requires_heat=False)
    assert _cap(_area("climate.kitchen", -0.5), cold_closed) == 30.0


def test_overshoot_cap_never_below_cold_setpoint():
    assert _cap(_area("climate.kitchen", -6.0)) == COLD_SETPOINT
