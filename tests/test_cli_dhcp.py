"""Tests for the DHCP CLI command."""

import asyncio
from argparse import ArgumentError

import pytest

from tplink_omada_client import cli
from tplink_omada_client.cli import command_dhcp
from tplink_omada_client.cli.config import ControllerConfig
from tplink_omada_client.networks import DhcpReservation


def _reservation(mac: str, ip: str, description: str | None = None, status: bool = True,
                 net_id: str = "net-1", net_name: str = "Main") -> DhcpReservation:
    return DhcpReservation({
        "id": f"id-{mac}",
        "mac": mac,
        "ip": ip,
        "description": description,
        "status": status,
        "netId": net_id,
        "netName": net_name,
    })


class FakeSiteClient:
    def __init__(self, reservations: list[DhcpReservation]) -> None:
        self.reservations = reservations
        self.created: list[dict] = []
        self.deleted: list[str] = []
        self.updated: list[dict] = []

    async def get_dhcp_reservations(self) -> list[DhcpReservation]:
        return self.reservations

    async def create_dhcp_reservation(
        self, mac: str, ip: str, net_id: str, description: str | None = None,
    ) -> DhcpReservation:
        r = _reservation(mac, ip, description, net_id=net_id)
        self.created.append({"mac": mac, "ip": ip, "net_id": net_id, "description": description})
        return r

    async def update_dhcp_reservation(
        self, mac: str, ip: str | None = None, description: str | None = None,
        enabled: bool | None = None,
    ) -> DhcpReservation:
        self.updated.append({"mac": mac, "ip": ip, "description": description, "enabled": enabled})
        return _reservation(mac, ip or "10.0.0.1", description)

    async def delete_dhcp_reservation(self, mac: str) -> None:
        self.deleted.append(mac)


class FakeConnection:
    def __init__(self, site_client: FakeSiteClient) -> None:
        self.site_client = site_client

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get_site_client(self, site: str) -> FakeSiteClient:
        return self.site_client


def _run_command(monkeypatch, site_client: FakeSiteClient, args: dict) -> int:
    config = ControllerConfig("url", "user", "pass", "Default", True)
    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: config)
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda target_config: FakeConnection(site_client))
    return 0  # We'll run commands via the main parser later


def test_normalize_mac_colon_to_hyphen():
    assert command_dhcp._normalize_mac("aa:bb:cc:11:22:33") == "AA-BB-CC-11-22-33"


def test_normalize_mac_hyphen_preserved():
    assert command_dhcp._normalize_mac("aa-bb-cc-11-22-33") == "AA-BB-CC-11-22-33"


def test_validate_mac_invalid():
    with pytest.raises(ArgumentError):
        command_dhcp._validate_mac("not-a-mac")


def test_validate_mac_short():
    with pytest.raises(ArgumentError):
        command_dhcp._validate_mac("AA:BB:CC:11:22")


def test_main_registers_dhcp_command(monkeypatch):
    seen = {}

    async def fake_command(args):
        seen.update(args)
        return 0

    monkeypatch.setattr(cli.command_dhcp, "command_dhcp_list", fake_command)

    assert cli.main(["dhcp", "list"]) == 0


def test_dhcp_list_command(monkeypatch, capsys):
    res = _reservation("AA-BB-CC-11-22-33", "192.168.1.100", "web-server", net_name="Main")
    site_client = FakeSiteClient([res])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_list({"target": "", "json": False}))
    assert result == 0

    output = capsys.readouterr().out
    assert "AA-BB-CC-11-22-33" in output
    assert "192.168.1.100" in output
    assert "web-server" in output
    assert "Main" in output
    assert "enabled" in output


def test_dhcp_list_json(monkeypatch, capsys):
    res = _reservation("AA-BB-CC-11-22-33", "192.168.1.100", "web-server")
    site_client = FakeSiteClient([res])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_list({"target": "", "json": True}))
    assert result == 0

    output = capsys.readouterr().out
    import json
    data = json.loads(output)
    assert data[0]["mac"] == "AA-BB-CC-11-22-33"


def test_dhcp_create_command(monkeypatch, capsys):
    site_client = FakeSiteClient([])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_create({
        "target": "", "mac": "aa:bb:cc:11:22:33", "ip": "10.0.0.5",
        "net_id": "net-1", "name": "test-device",
    }))
    assert result == 0
    assert len(site_client.created) == 1
    assert site_client.created[0]["mac"] == "AA-BB-CC-11-22-33"

    output = capsys.readouterr().out
    assert "Created" in output


def test_dhcp_create_no_name(monkeypatch, capsys):
    site_client = FakeSiteClient([])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_create({
        "target": "", "mac": "aa:bb:cc:11:22:33", "ip": "10.0.0.5",
        "net_id": "net-1",
    }))
    assert result == 0
    assert len(site_client.created) == 1
    assert site_client.created[0]["description"] is None


def test_dhcp_modify_command(monkeypatch, capsys):
    site_client = FakeSiteClient([])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_modify({
        "target": "", "mac": "aa:bb:cc:11:22:33", "ip": "10.0.0.99", "name": "renamed",
    }))
    assert result == 0
    assert len(site_client.updated) == 1
    assert site_client.updated[0]["mac"] == "AA-BB-CC-11-22-33"
    assert site_client.updated[0]["ip"] == "10.0.0.99"
    assert site_client.updated[0]["description"] == "renamed"

    output = capsys.readouterr().out
    assert "Updated" in output


def test_dhcp_modify_mac_only(monkeypatch, capsys):
    site_client = FakeSiteClient([])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_modify({
        "target": "", "mac": "aa:bb:cc:11:22:33",
    }))
    assert result == 0
    assert len(site_client.updated) == 1
    assert site_client.updated[0]["ip"] is None
    assert site_client.updated[0]["description"] is None


def test_dhcp_delete_command(monkeypatch, capsys):
    site_client = FakeSiteClient([])

    monkeypatch.setattr(command_dhcp, "get_target_config", lambda target: ControllerConfig("u", "u", "p", "Default", True))
    monkeypatch.setattr(command_dhcp, "to_omada_connection", lambda cfg: FakeConnection(site_client))

    result = asyncio.run(command_dhcp.command_dhcp_delete({
        "target": "", "mac": "aa:bb:cc:11:22:33",
    }))
    assert result == 0
    assert site_client.deleted == ["AA-BB-CC-11-22-33"]

    output = capsys.readouterr().out
    assert "Deleted" in output


def test_mac_validation_rejects_invalid():
    with pytest.raises(ArgumentError, match="Invalid MAC"):
        command_dhcp._validate_mac("AA:BB:CC:11:22:ZZ")


def test_mac_validation_normalizes_colons():
    assert command_dhcp._validate_mac("aa:bb:cc:11:22:33") == "AA-BB-CC-11-22-33"


def test_mac_validation_passes_hyphens():
    assert command_dhcp._validate_mac("AA-BB-CC-11-22-33") == "AA-BB-CC-11-22-33"
