"""Real HA setup, entities, actions, update failures, diagnostics and unload."""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util

from custom_components.pet_feeder_local.api import (FeederError, FeedOutcomeUnknown, InvalidAuth, Meal,
                                                   Schedule, ScheduleConflict, ScheduleVerificationError)
from custom_components.pet_feeder_local.diagnostics import async_get_config_entry_diagnostics
from .conftest import DATA, INFO, STATUS

pytestmark = pytest.mark.usefixtures("entity_registry_enabled_by_default")

async def setup(hass,entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry.runtime_data

async def test_setup_entities_card_and_unload(hass,entry,client):
    coordinator=await setup(hass,entry)
    registry=er.async_get(hass)
    entities=er.async_entries_for_config_entry(registry,entry.entry_id)
    assert {e.domain for e in entities}=={'number','button','sensor','binary_sensor','calendar','camera'}
    assert all(e.unique_id.startswith(INFO['id']) for e in entities)
    assert hass.services.has_service('pet_feeder_local','set_schedule')
    assert '/pet_feeder_local/frontend/pet-feeder-local-card.js?v=0.2.0' in hass.data['frontend_extra_module_url'].urls
    client.async_feed.assert_not_awaited()
    client.async_set_schedule.assert_not_awaited()
    assert coordinator.schedule_attributes()['integration']=='pet_feeder_local'
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not coordinator.async_update_listeners()

async def test_select_then_serve_and_schedule_action(hass,entry,client):
    coordinator=await setup(hass,entry)
    registry=er.async_get(hass)
    number=registry.async_get_entity_id('number','pet_feeder_local',INFO['id']+'_portions')
    button=registry.async_get_entity_id('button','pet_feeder_local',INFO['id']+'_serve')
    await hass.services.async_call('number','set_value',{'entity_id':number,'value':3},blocking=True)
    client.async_feed.assert_not_awaited()
    await hass.services.async_call('button','press',{'entity_id':button},blocking=True)
    client.async_feed.assert_awaited_once_with(3)
    await hass.services.async_call('pet_feeder_local','set_schedule',{'config_entry_id':entry.entry_id,'expected_revision':'12345678','meals':[]},blocking=True)
    client.async_set_schedule.assert_awaited_once_with((),'12345678')
    assert coordinator.schedule.revision=='87654321'

@pytest.mark.parametrize('entry_id,meals',[('missing',[]),('current',[{'invalid':'row'}])])
async def test_invalid_action_targets_and_rows(hass,entry,client,entry_id,meals):
    await setup(hass,entry)
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call('pet_feeder_local','set_schedule',{'config_entry_id':entry.entry_id if entry_id=='current' else entry_id,'expected_revision':'12345678','meals':meals},blocking=True)
    client.async_set_schedule.assert_not_awaited()

@pytest.mark.parametrize('error,key',[(FeedOutcomeUnknown(),'feed_unknown'),(FeederError(),'action_failed')])
async def test_uncertain_feed_is_never_retried(hass,entry,client,error,key):
    coordinator=await setup(hass,entry)
    client.async_feed.side_effect=error
    with pytest.raises(HomeAssistantError) as context:await coordinator.async_serve()
    assert context.value.translation_key==key
    client.async_feed.assert_awaited_once_with(1)

async def test_disabled_feed_never_sends(hass,entry,client):
    client.async_get_info.return_value={**INFO,'feeding_enabled':False}
    coordinator=await setup(hass,entry)
    with pytest.raises(HomeAssistantError) as context:await coordinator.async_serve()
    assert context.value.translation_key=='feeding_disabled'
    client.async_feed.assert_not_awaited()

@pytest.mark.parametrize('error,key',[(ScheduleConflict(),'schedule_conflict'),(ScheduleVerificationError(),'schedule_verification'),(FeederError(),'action_failed')])
async def test_schedule_errors_are_translated(hass,entry,client,error,key):
    coordinator=await setup(hass,entry)
    client.async_set_schedule.side_effect=error
    with pytest.raises(HomeAssistantError) as context:await coordinator.async_set_schedule((),'12345678')
    assert context.value.translation_key==key
    assert coordinator.schedule.revision=='12345678'

async def test_diagnostics_exclude_private_fields(hass,entry,client):
    coordinator=await setup(hass,entry)
    data=await async_get_config_entry_diagnostics(hass,entry)
    assert data['scheduled_rows']==0 and data['mcu_connected']
    for secret in (DATA['token'],DATA['address'],INFO['id'],'meals','revision'):
        assert secret not in str(data)

async def test_mcu_issue_and_recovery(hass,entry,client):
    coordinator=await setup(hass,entry)
    client.async_get_status.return_value={**STATUS,'mcu_connected':False}
    await coordinator.async_refresh()
    assert not coordinator.mcu_ready
    registry=ir.async_get(hass)
    assert ('pet_feeder_local',entry.entry_id+'_mcu') in registry.issues
    client.async_get_status.return_value=STATUS
    await coordinator.async_refresh()
    assert coordinator.mcu_ready
    assert ('pet_feeder_local',entry.entry_id+'_mcu') not in registry.issues

@pytest.mark.parametrize('error',[ClientConnectionError(),FeederError(),ValueError()])
async def test_poll_failure_logs_once_and_recovers(hass,entry,client,caplog,error):
    coordinator=await setup(hass,entry)
    client.async_get_status.side_effect=error
    await coordinator.async_refresh();await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert caplog.text.count('Error fetching pet_feeder_local data')==1
    client.async_get_status.side_effect=None
    await coordinator.async_refresh()
    assert coordinator.last_update_success

async def test_poll_auth_failure_starts_reauth(hass,entry,client):
    coordinator=await setup(hass,entry)
    client.async_get_status.side_effect=InvalidAuth()
    await coordinator.async_refresh();await hass.async_block_till_done()
    assert not coordinator.last_update_success
    assert any(flow['context']['source']=='reauth' for flow in hass.config_entries.flow.async_progress())

@pytest.mark.parametrize('info_error',[InvalidAuth(),ClientConnectionError(),ValueError()])
async def test_setup_errors_are_handled_by_ha(hass,entry,client,info_error):
    client.async_get_info.side_effect=info_error
    assert not await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state in (ConfigEntryState.SETUP_ERROR,ConfigEntryState.SETUP_RETRY)

async def test_wrong_device_does_not_load(hass,entry,client):
    client.async_get_info.return_value={**INFO,'id':'different-device'}
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY

async def test_camera_snapshot_and_calendar(hass,entry,client):
    client.async_get_schedule.return_value=Schedule('12345678',(Meal(127,8,0,2,True),Meal(127,9,0,1,False)))
    await setup(hass,entry)
    registry=er.async_get(hass)
    camera_id=registry.async_get_entity_id('camera','pet_feeder_local',INFO['id']+'_camera')
    camera=hass.data['camera'].get_entity(camera_id)
    assert camera.use_stream_for_stills
    with patch('custom_components.pet_feeder_local.camera.async_get_image',return_value=b'synthetic-jpeg') as image:
        assert await camera.async_camera_image(640,360)==b'synthetic-jpeg'
        image.assert_awaited_once()
    calendar_id=registry.async_get_entity_id('calendar','pet_feeder_local',INFO['id']+'_calendar')
    calendar=hass.data['calendar'].get_entity(calendar_id)
    assert calendar.event
    with pytest.raises(ValueError):await calendar.async_get_events(hass,datetime(2026,1,1,tzinfo=UTC),datetime(2028,1,1,tzinfo=UTC))

@pytest.mark.parametrize('state,value',[('4',4),('0',1),('unavailable',1),('2.5',1)])
async def test_restored_portions_never_feed(hass,entry,client,state,value):
    from homeassistant.core import State
    with patch('custom_components.pet_feeder_local.number.PortionNumber.async_get_last_state',return_value=State('number.saved',state)):
        coordinator=await setup(hass,entry)
    assert coordinator.selected_portions==value
    client.async_feed.assert_not_awaited()

async def test_removal_clears_only_this_feeders_repair(hass,entry,client):
    coordinator=await setup(hass,entry)
    client.async_get_status.return_value={**STATUS,'mcu_connected':False}
    await coordinator.async_refresh()
    registry=ir.async_get(hass)
    assert ('pet_feeder_local',entry.entry_id+'_mcu') in registry.issues
    assert await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert ('pet_feeder_local',entry.entry_id+'_mcu') not in registry.issues
    client.async_feed.assert_not_awaited()
