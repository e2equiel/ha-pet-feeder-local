"""Exercise full HA flows, identity checks, discovery and credential changes."""
from unittest.mock import patch

from aiohttp import ClientConnectionError
import pytest
from homeassistant import data_entry_flow
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
from custom_components.pet_feeder_local.api import InvalidAuth
from .conftest import DATA, INFO

@pytest.fixture(autouse=True)
def flow_client(client):
    with patch("custom_components.pet_feeder_local.config_flow.FeederClient",return_value=client),patch("custom_components.pet_feeder_local.async_setup_entry",return_value=True):
        yield client

async def test_user_and_duplicate(hass):
    form=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"user"})
    assert form["type"] is data_entry_flow.FlowResultType.FORM
    result=await hass.config_entries.flow.async_configure(form["flow_id"],DATA)
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id==INFO["id"]
    await hass.async_block_till_done()
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"user"},data=DATA)
    assert result["reason"]=="already_configured"

@pytest.mark.parametrize(('error','code'),[(InvalidAuth(),'invalid_auth'),(ClientConnectionError(),'cannot_connect'),(TimeoutError(),'cannot_connect'),(ValueError(),'invalid_response')])
async def test_errors_can_recover(hass,client,error,code):
    client.async_get_info.side_effect=error
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"user"},data=DATA)
    assert result["errors"]=={"base":code}
    client.async_get_info.side_effect=None
    result=await hass.config_entries.flow.async_configure(result["flow_id"],DATA)
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

async def test_invalid_stream_url(hass):
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"user"},data={**DATA,"stream_source":"https://invalid"})
    assert result["errors"]["base"]=="invalid_response"

@pytest.mark.parametrize('source',['reauth','reconfigure'])
async def test_update_credentials_without_changing_identity(hass,entry,source):
    with patch.object(hass.config_entries,"async_reload",return_value=True) as reload:
        result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":source,"entry_id":entry.entry_id})
        assert result["type"] is data_entry_flow.FlowResultType.FORM
        assert "synthetic-private-token" not in str(result["data_schema"].schema)
        result=await hass.config_entries.flow.async_configure(result["flow_id"],{**DATA,"token":"new-private-token"})
        assert result["type"] is data_entry_flow.FlowResultType.ABORT
        assert entry.data["token"]=="new-private-token"
        await hass.async_block_till_done()
        reload.assert_awaited_once_with(entry.entry_id)

async def test_reconfigure_rejects_other_feeder(hass,entry,client):
    client.async_get_info.return_value={**INFO,"id":"different-feeder"}
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"reconfigure","entry_id":entry.entry_id},data=DATA)
    assert result["errors"]["base"]=="wrong_device"
    assert entry.unique_id==INFO["id"]

def discovery(**changes):
    return SsdpServiceInfo(ssdp_usn="uuid:synthetic",ssdp_st="urn:pet-feeder-local:device:Feeder:1",upnp={"serialNumber":INFO["id"]},ssdp_location=changes.get('location',"http://192.168.1.124:8080/description.xml"))

async def test_discovery_asks_for_token_and_checks_identity(hass,client):
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"ssdp"},data=discovery())
    assert result["step_id"]=="user"
    client.async_get_info.return_value={**INFO,"id":"different-feeder"}
    result=await hass.config_entries.flow.async_configure(result["flow_id"],DATA)
    assert result["errors"]["base"]=="wrong_device"
    client.async_get_info.return_value=INFO
    result=await hass.config_entries.flow.async_configure(result["flow_id"],DATA)
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

async def test_discovery_updates_known_address(hass,entry):
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"ssdp"},data=discovery())
    assert result["reason"]=="already_configured"
    assert entry.data["address"]=="http://192.168.1.124:8080"

@pytest.mark.parametrize('location',["https://example.com/", "http://8.8.8.8:8080/description.xml", "http://192.168.1.124:wrong/description.xml", "http://192.168.1.124:80/description.xml", "http://192.168.1.124:8080/wrong"])
async def test_bad_discovery(hass,location):
    result=await hass.config_entries.flow.async_init("pet_feeder_local",context={"source":"ssdp"},data=discovery(location=location))
    assert result["reason"]=="invalid_discovery"
