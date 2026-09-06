"""Implementation for 'dhcp' command group"""

import json
import re
from argparse import ArgumentError, _SubParsersAction

from .config import get_target_config, to_omada_connection
from .util import get_target_argument

MAC_RE = re.compile(r"^([0-9A-F]{2}[-:]){5}[0-9A-F]{2}$", re.IGNORECASE)


def _normalize_mac(mac: str) -> str:
    """Normalize MAC to API format: AA-BB-CC-11-22-33 (uppercase, hyphens)."""
    return mac.upper().replace(":", "-")


def _validate_mac(mac: str) -> str:
    """Normalize and validate MAC address, raise ArgumentError on failure."""
    mac = _normalize_mac(mac)
    if not MAC_RE.match(mac):
        raise ArgumentError(None, "Invalid MAC address (expected XX:XX:XX:XX:XX:XX or XX-XX-XX-XX-XX-XX)")
    return mac


async def command_dhcp_list(args) -> int:
    controller = get_target_argument(args)
    config = get_target_config(controller)
    async with to_omada_connection(config) as client:
        site_client = await client.get_site_client(config.site)
        reservations = await site_client.get_dhcp_reservations()
    if args.get("json"):
        print(json.dumps([r.raw_data for r in reservations], indent=2))
    else:
        print(f"{'MAC':<20} {'IP':<16} {'Name':<24} {'Network':<20} {'Status':<8}")
        print("-" * 88)
        for r in reservations:
            status = "enabled" if r.status else "disabled"
            print(f"{r.mac:<20} {r.ip:<16} {(r.description or '-'):<24} {(r.net_name or '-'):<20} {status:<8}")
    return 0


async def command_dhcp_create(args) -> int:
    mac = _validate_mac(args["mac"])
    controller = get_target_argument(args)
    config = get_target_config(controller)
    async with to_omada_connection(config) as client:
        site_client = await client.get_site_client(config.site)
        r = await site_client.create_dhcp_reservation(
            mac, args["ip"], args["net_id"], args.get("name"),
        )
    print(f"Created: {r.mac} \u2192 {r.ip}")
    return 0


async def command_dhcp_modify(args) -> int:
    mac = _validate_mac(args["mac"])
    controller = get_target_argument(args)
    config = get_target_config(controller)
    async with to_omada_connection(config) as client:
        site_client = await client.get_site_client(config.site)
        r = await site_client.update_dhcp_reservation(
            mac,
            ip=args.get("ip"),
            description=args.get("name"),
        )
    print(f"Updated: {r.mac} \u2192 {r.ip}")
    return 0


async def command_dhcp_delete(args) -> int:
    mac = _validate_mac(args["mac"])
    controller = get_target_argument(args)
    config = get_target_config(controller)
    async with to_omada_connection(config) as client:
        site_client = await client.get_site_client(config.site)
        await site_client.delete_dhcp_reservation(mac)
    print(f"Deleted reservation for {mac}")
    return 0


def arg_parser(subparsers: _SubParsersAction) -> None:
    dhcp_parser = subparsers.add_parser("dhcp", help="DHCP reservation management")
    dhcp_sub = dhcp_parser.add_subparsers(title="commands", metavar="command")

    list_p = dhcp_sub.add_parser("list", help="List DHCP reservations")
    list_p.add_argument("--json", action="store_true", help="JSON output")
    list_p.set_defaults(func=command_dhcp_list)

    create_p = dhcp_sub.add_parser("create", help="Create a DHCP reservation")
    create_p.add_argument("--mac", required=True, help="MAC address (XX:XX:XX:XX:XX:XX)")
    create_p.add_argument("--ip", required=True, help="IP address")
    create_p.add_argument("--net-id", required=True, help="LAN Network ID")
    create_p.add_argument("--name", help="Description/name for the reservation")
    create_p.set_defaults(func=command_dhcp_create)

    modify_p = dhcp_sub.add_parser("modify", help="Modify a DHCP reservation")
    modify_p.add_argument("--mac", required=True, help="MAC address")
    modify_p.add_argument("--ip", help="New IP address")
    modify_p.add_argument("--name", help="New description")
    modify_p.set_defaults(func=command_dhcp_modify)

    delete_p = dhcp_sub.add_parser("delete", help="Delete a DHCP reservation")
    delete_p.add_argument("--mac", required=True, help="MAC address")
    delete_p.set_defaults(func=command_dhcp_delete)
