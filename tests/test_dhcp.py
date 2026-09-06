"""Tests for DHCP reservation CRUD on OmadaSiteClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from tplink_omada_client.omadasiteclient import OmadaSiteClient


async def _async_gen(items):
    """Helper: turn an iterable into an async generator."""
    for item in items:
        yield item


@pytest.fixture
def site_client():
    api = MagicMock()
    api.format_openapi_url = MagicMock(side_effect=lambda path, site=None, version="v1": f"/openapi/v1/ctrl/sites/{site}/{path}")
    api.format_url = MagicMock(side_effect=lambda path, site=None: f"/api/v2/ctrl/sites/{site}/{path}")
    api.get_controller_version = AsyncMock(return_value=__import__("awesomeversion").AwesomeVersion("6.2.0.0"))
    return OmadaSiteClient("site-id", api)


@pytest.mark.asyncio
async def test_get_dhcp_reservations(site_client):
    """get_dhcp_reservations iterates paginated API and returns DhcpReservation objects."""
    mock_data = [
        {"id": "1", "mac": "AA-BB-CC-11-22-33", "ip": "192.168.1.100",
         "description": "web", "status": True, "netId": "net-1", "netName": "Main"},
        {"id": "2", "mac": "AA-BB-CC-44-55-66", "ip": "192.168.1.101",
         "description": "db", "status": True, "netId": "net-1", "netName": "Main"},
    ]
    site_client._api.iterate_pages_openapi_get = lambda url: _async_gen(mock_data)
    result = await site_client.get_dhcp_reservations()
    assert len(result) == 2
    assert result[0].mac == "AA-BB-CC-11-22-33"
    assert result[1].ip == "192.168.1.101"


@pytest.mark.asyncio
async def test_create_dhcp_reservation(site_client):
    """create_dhcp_reservation posts to the API and returns a DhcpReservation."""
    site_client._api.request = AsyncMock(return_value={
        "id": "3", "mac": "AA-BB-CC-77-88-99", "ip": "192.168.1.102",
        "description": "new-box", "status": True, "netId": "net-1",
    })
    r = await site_client.create_dhcp_reservation("AA-BB-CC-77-88-99", "192.168.1.102", "net-1", "new-box")
    assert r.mac == "AA-BB-CC-77-88-99"
    assert r.description == "new-box"


@pytest.mark.asyncio
async def test_create_dhcp_reservation_no_description(site_client):
    """create_dhcp_reservation works without optional description."""
    site_client._api.request = AsyncMock(return_value={
        "id": "4", "mac": "AA-BB-CC-00-00-01", "ip": "10.0.0.2",
        "status": True, "netId": "net-2",
    })
    r = await site_client.create_dhcp_reservation("AA-BB-CC-00-00-01", "10.0.0.2", "net-2")
    assert r.mac == "AA-BB-CC-00-00-01"
    assert r.description is None


@pytest.mark.asyncio
async def test_update_dhcp_reservation(site_client):
    """update_dhcp_reservation patches the API and returns the updated reservation."""
    site_client._api.request = AsyncMock(return_value={
        "id": "1", "mac": "AA-BB-CC-11-22-33", "ip": "192.168.1.200",
        "description": "updated", "status": False, "netId": "net-1",
    })
    r = await site_client.update_dhcp_reservation(
        "AA-BB-CC-11-22-33",
        ip="192.168.1.200",
        description="updated",
        enabled=False,
    )
    assert r.mac == "AA-BB-CC-11-22-33"
    assert r.ip == "192.168.1.200"
    assert r.description == "updated"
    assert r.status is False


@pytest.mark.asyncio
async def test_update_dhcp_reservation_partial(site_client):
    """update_dhcp_reservation only sends the fields that are provided."""
    site_client._api.request = AsyncMock(return_value={
        "id": "1", "mac": "AA-BB-CC-11-22-33", "ip": "10.0.0.99",
        "description": "just-ip", "status": True, "netId": "net-1",
    })
    r = await site_client.update_dhcp_reservation("AA-BB-CC-11-22-33", ip="10.0.0.99")
    assert r.ip == "10.0.0.99"


@pytest.mark.asyncio
async def test_delete_dhcp_reservation(site_client):
    """delete_dhcp_reservation sends a DELETE request and returns None."""
    site_client._api.request = AsyncMock(return_value={})
    result = await site_client.delete_dhcp_reservation("AA-BB-CC-11-22-33")
    assert result is None


@pytest.mark.asyncio
async def test_get_dhcp_reservations_url_format(site_client):
    """Verify the correct OpenAPI URL is constructed."""
    site_client._api.iterate_pages_openapi_get = lambda url: _async_gen([])
    await site_client.get_dhcp_reservations()
    site_client._api.format_openapi_url.assert_called_once_with(
        "setting/service/dhcp", site="site-id"
    )


@pytest.mark.asyncio
async def test_create_dhcp_reservation_url_and_body(site_client):
    """Verify the correct URL and body are sent on create."""
    site_client._api.request = AsyncMock(return_value={
        "id": "x", "mac": "aa-bb-cc", "ip": "1.2.3.4", "status": True, "netId": "n1",
    })
    await site_client.create_dhcp_reservation("aa-bb-cc", "1.2.3.4", "n1")
    site_client._api.request.assert_called_once()
    args, kwargs = site_client._api.request.call_args
    assert args[0] == "post"
    assert "setting/service/dhcp" in args[1]
    assert kwargs["json"]["mac"] == "aa-bb-cc"
    assert kwargs["json"]["status"] is True


@pytest.mark.asyncio
async def test_delete_dhcp_reservation_url(site_client):
    """Verify the correct URL is used for delete."""
    site_client._api.request = AsyncMock(return_value={})
    await site_client.delete_dhcp_reservation("AA-BB-CC-11-22-33")
    site_client._api.request.assert_called_once()
    args, _ = site_client._api.request.call_args
    assert args[0] == "delete"
    assert "setting/service/dhcp/aa-bb-cc-11-22-33" in args[1]


@pytest.mark.asyncio
async def test_update_dhcp_reservation_url_and_body(site_client):
    """Verify the correct URL and body are sent on update."""
    site_client._api.request = AsyncMock(return_value={
        "id": "x", "mac": "aa-bb", "ip": "1.2.3.5", "description": "new-desc",
        "status": False, "netId": "n1",
    })
    await site_client.update_dhcp_reservation("aa-bb", ip="1.2.3.5", description="new-desc", enabled=False)
    site_client._api.request.assert_called_once()
    args, kwargs = site_client._api.request.call_args
    assert args[0] == "patch"
    assert "setting/service/dhcp/aa-bb" in args[1]
    assert kwargs["json"]["ip"] == "1.2.3.5"
    assert kwargs["json"]["description"] == "new-desc"
    assert kwargs["json"]["status"] is False
