"""Regression tests: a reload before Home Assistant has started must not leave an orphaned control loop.

If the config entry was unloaded or reloaded while Home Assistant was still starting, the deferred
EVENT_HOMEASSISTANT_STARTED callbacks of the removed instance used to fire anyway. They started a
5-second control loop on the removed instance that was never cancelled and kept writing to the boiler.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.sat.const import DOMAIN
from tests.const import DEFAULT_USER_DATA


@pytest.fixture(autouse=True)
def no_dhcp_watchers():
    """The dhcp dependency opens sockets on EVENT_HOMEASSISTANT_STARTED, which these tests fire."""
    with patch("homeassistant.components.dhcp.async_setup", AsyncMock(return_value=True)):
        yield


@pytest.fixture(autouse=True)
def sensor_states(hass: HomeAssistant):
    hass.states.async_set("sensor.test_inside_sensor", "18.0")
    hass.states.async_set("sensor.test_outside_sensor", "0.0")


async def _setup_entry_while_starting(hass: HomeAssistant) -> MockConfigEntry:
    hass.set_state(CoreState.not_running)

    entry = MockConfigEntry(domain=DOMAIN, data=DEFAULT_USER_DATA.copy(), options={})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    return entry


def _count_control_loop_runs(monkeypatch, demand_control) -> list:
    runs = []
    original = demand_control._heating_control.update

    async def recording_update(demand):
        runs.append(demand)
        await original(demand)

    monkeypatch.setattr(demand_control._heating_control, "update", recording_update)
    return runs


async def test_reload_before_started_leaves_no_orphaned_control_loop(hass: HomeAssistant, monkeypatch):
    entry = await _setup_entry_while_starting(hass)
    old_demand_control = hass.data[DOMAIN][entry.entry_id].demand_control
    old_runs = _count_control_loop_runs(monkeypatch, old_demand_control)

    # Reload while Home Assistant is still starting.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    new_demand_control = hass.data[DOMAIN][entry.entry_id].demand_control
    assert new_demand_control is not old_demand_control

    # Now Home Assistant finishes starting, and time passes.
    await hass.async_start()
    await hass.async_block_till_done()

    for seconds in (5, 10, 15, 30, 60):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
        await hass.async_block_till_done()

    # The removed instance must stay completely inactive.
    assert old_demand_control._started is False
    assert old_demand_control._event_listeners_registered is False
    assert old_demand_control._unsubscribers == []
    assert old_runs == []

    # The new instance did start normally.
    assert new_demand_control._started is True
    assert new_demand_control._event_listeners_registered is True


async def test_unload_before_started_leaves_no_control_loop(hass: HomeAssistant, monkeypatch):
    entry = await _setup_entry_while_starting(hass)
    demand_control = hass.data[DOMAIN][entry.entry_id].demand_control
    runs = _count_control_loop_runs(monkeypatch, demand_control)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()

    for seconds in (5, 10, 30):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
        await hass.async_block_till_done()

    assert demand_control._started is False
    assert demand_control._event_listeners_registered is False
    assert runs == []


async def test_setup_while_starting_still_starts_after_started(hass: HomeAssistant):
    entry = await _setup_entry_while_starting(hass)
    demand_control = hass.data[DOMAIN][entry.entry_id].demand_control

    assert demand_control._event_listeners_registered is False

    await hass.async_start()
    await hass.async_block_till_done()

    assert demand_control._started is True
    assert demand_control._event_listeners_registered is True
