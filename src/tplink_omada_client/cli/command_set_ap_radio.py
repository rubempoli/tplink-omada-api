"""Implementation for 'set-ap-radio' command"""

from argparse import _SubParsersAction

from tplink_omada_client.definitions import ChannelWidth, RadioId
from tplink_omada_client.omadasiteclient import AccessPointRadioSettings

from .config import get_target_config, to_omada_connection
from .util import get_device_by_mac_or_name, get_target_argument

_BANDS = {
    "2g": RadioId.FREQ_2_4,
    "5g": RadioId.FREQ_5_1,
    "5g2": RadioId.FREQ_5_2,
    "6g": RadioId.FREQ_6,
}

_WIDTHS = {
    "20": ChannelWidth.WIDTH_20,
    "40": ChannelWidth.WIDTH_40,
    "80": ChannelWidth.WIDTH_80,
    "160": ChannelWidth.WIDTH_160,
    "240": ChannelWidth.WIDTH_240,
    "320": ChannelWidth.WIDTH_320,
}

# "Auto" is a different value on each band
_AUTO_WIDTHS = {
    RadioId.FREQ_2_4: ChannelWidth.AUTO_40_20,
    RadioId.FREQ_5_1: ChannelWidth.AUTO_80_40_20,
    RadioId.FREQ_5_2: ChannelWidth.AUTO_80_40_20,
    RadioId.FREQ_6: ChannelWidth.AUTO_160_80_40_20,
}


async def command_set_ap_radio(args) -> int:
    """Executes 'set-ap-radio' command"""
    controller = get_target_argument(args)
    config = get_target_config(controller)

    band = _BANDS[args["band"]]

    width = None
    if args["width"] is not None:
        width = _AUTO_WIDTHS[band] if args["width"] == "auto" else _WIDTHS[args["width"]]

    channel = None
    if args["channel"] is not None:
        channel = 0 if args["channel"] == "auto" else int(args["channel"])

    radio_enabled = None
    if args["enable"]:
        radio_enabled = True
    elif args["disable"]:
        radio_enabled = False

    settings = AccessPointRadioSettings(
        radio_enabled=radio_enabled,
        channel_width=width,
        channel=channel,
        tx_power=args["tx_power"],
    )

    async with to_omada_connection(config) as client:
        site_client = await client.get_site_client(config.site)
        device = await get_device_by_mac_or_name(site_client, args["mac"])
        updated = await site_client.set_access_point_radio_settings(device, band, settings)

        print(f"{device.name} {args['band']} radio:")
        print(f"  Enabled:       {updated.radio_enabled}")
        print(f"  Channel width: {updated.channel_width.name}")
        print(f"  Channel:       {'auto' if updated.auto_channel else f'{updated.frequency} MHz'}")
        print(f"  Tx power:      {updated.tx_power} dBm")
        print("The access point may take a minute to apply the change.")
    return 0


def arg_parser(subparsers: _SubParsersAction) -> None:
    """Configures arguments parser for 'set-ap-radio' command"""
    parser = subparsers.add_parser("set-ap-radio", help="Sets the radio settings of an access point")
    parser.add_argument(
        "mac",
        help="The MAC address or name of the access point",
    )
    parser.add_argument("band", choices=sorted(_BANDS), help="The radio band to configure")
    parser.add_argument(
        "-w",
        "--width",
        choices=[*sorted(_WIDTHS, key=int), "auto"],
        help="Channel width in MHz",
    )
    parser.add_argument(
        "-c",
        "--channel",
        help="The channel number to use, or 'auto' to let the access point choose",
    )
    parser.add_argument("-p", "--tx-power", type=int, help="Transmit power in dBm")
    parser.add_argument("--enable", action="store_true", help="Switch the radio on")
    parser.add_argument("--disable", action="store_true", help="Switch the radio off")

    parser.set_defaults(func=command_set_ap_radio)
