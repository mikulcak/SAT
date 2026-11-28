from homeassistant.core import is_callback

from custom_components.sat.area import Area, Areas
from custom_components.sat.demand_control import SatDemandControl


def test_pid_loops_run_on_the_event_loop():
    # Without @callback, async_track_time_interval runs these in executor threads,
    # where the room loop appends to the temperature history while the demand loop
    # iterates it: "RuntimeError: deque mutated during iteration" (28.11.2026).
    assert is_callback(Area.control_pid)
    assert is_callback(Areas.control_pid)
    assert is_callback(SatDemandControl.control_pid)
