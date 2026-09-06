"""Tests for access point radio settings."""

import asyncio

import pytest

from tplink_omada_client.definitions import ChannelWidth, RadioId
from tplink_omada_client.devices import OmadaAccessPoint
from tplink_omada_client.exceptions import InvalidDevice
from tplink_omada_client.omadasiteclient import AccessPointRadioSettings, OmadaSiteClient

_5G_CHANNELS = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140]


def _ap_data() -> dict:
    return {
        "mac": "AA-BB-CC-DD-EE-FF",
        "name": "Test AP",
        "type": "ap",
        "radioSetting2g": {
            "radioEnable": True,
            "wirelessMode": -2,
            "channelWidth": "4",
            "channel": 0,
            "freq": 0,
            "txPower": 20,
            "txPowerLevel": 4,
        },
        "radioSetting5g": {
            "radioEnable": True,
            "wirelessMode": -2,
            "channelWidth": "2",
            "channel": 1,
            "freq": 5180,
            "txPower": 23,
            "txPowerLevel": 2,
        },
        "wp5g": {
            "actualChannel": "36  / 5180MHz",
            "bandWidth": "20MHz",
            "txPower": 23,
            "maxTxRate": 288,
            "rxUtil": 2,
            "txUtil": 1,
            "interUtil": 0,
            "rdMode": "a/n/ac mixed",
        },
    }


def _channel_info() -> dict:
    return {
        "data": [
            {
                "band": "2.4G",
                "channelList": [
                    {"value": c, "channelValue": c, "freq": 2407 + 5 * c, "channelName": f"{c}/{2407 + 5 * c}MHz"} for c in range(1, 14)
                ],
            },
            {
                "band": "5G",
                "channelList": [
                    {"value": i, "channelValue": c, "freq": 5000 + 5 * c, "channelName": f"{c}/{5000 + 5 * c}MHz"}
                    for i, c in enumerate(_5G_CHANNELS, start=1)
                ],
            },
        ]
    }


class FakeApi:
    """Stands in for the authenticated API connection."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict | None]] = []
        self.ap = _ap_data()

    def format_url(self, end_point: str, site: str | None = None) -> str:
        return f"api/{site}/{end_point}"

    async def request(self, method: str, url: str, params=None, json=None, data=None):
        self.requests.append((method, url, json))
        if method == "get" and url.endswith("/channelInfo"):
            return _channel_info()
        if method == "get" and "/eaps/" in url:
            return self.ap
        if method == "put" and url.endswith("/config/radios"):
            # Reflect the change so the read-back sees it, like the controller does
            for key, value in json.items():
                if key.startswith("radioSetting"):
                    self.ap[key] = value
            return {}
        raise AssertionError(f"Unexpected request: {method} {url}")

    @property
    def put_payload(self) -> dict:
        """The body of the last radio config PUT."""
        return next(body for method, url, body in reversed(self.requests) if method == "put" and body is not None)


def _set(api: FakeApi, band: RadioId, settings: AccessPointRadioSettings):
    client = OmadaSiteClient("site-1", api)
    return asyncio.run(client.set_access_point_radio_settings("AA-BB-CC-DD-EE-FF", band, settings))


def test_radio_settings_are_read_from_the_access_point():
    ap = OmadaAccessPoint(_ap_data())

    radio = ap.radio_settings(RadioId.FREQ_5_1)

    assert radio is not None
    assert radio.channel_width == ChannelWidth.WIDTH_20
    assert radio.channel_index == 1
    assert radio.frequency == 5180
    assert not radio.auto_channel


def test_auto_channel_is_reported_for_channel_zero():
    ap = OmadaAccessPoint(_ap_data())

    radio = ap.radio_settings(RadioId.FREQ_2_4)

    assert radio is not None
    assert radio.auto_channel
    assert radio.channel_width == ChannelWidth.AUTO_40_20


def test_missing_radio_returns_none():
    ap = OmadaAccessPoint(_ap_data())

    assert ap.radio_settings(RadioId.FREQ_6) is None
    assert ap.radio_bands == [RadioId.FREQ_2_4, RadioId.FREQ_5_1]


def test_unknown_channel_width_does_not_raise():
    ap = OmadaAccessPoint({"radioSetting5g": {"channelWidth": "99"}})

    radio = ap.radio_settings(RadioId.FREQ_5_1)

    assert radio is not None
    assert radio.channel_width == ChannelWidth.UNKNOWN


def test_radio_status_reports_live_state():
    ap = OmadaAccessPoint(_ap_data())

    status = ap.radio_status(RadioId.FREQ_5_1)

    assert status is not None
    assert status.band_width == "20MHz"
    assert status.max_tx_rate == 288


def test_setting_channel_width_puts_to_the_radios_endpoint():
    api = FakeApi()

    _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel_width=ChannelWidth.WIDTH_80))

    method, url, _ = next(r for r in api.requests if r[0] == "put")
    assert url == "api/site-1/eaps/AA-BB-CC-DD-EE-FF/config/radios"
    assert method == "put"


def test_channel_width_is_sent_as_a_string():
    api = FakeApi()

    _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel_width=ChannelWidth.WIDTH_80))

    assert api.put_payload["radioSetting5g"]["channelWidth"] == "5"


def test_unchanged_settings_are_preserved():
    api = FakeApi()

    _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel_width=ChannelWidth.WIDTH_40))

    radio = api.put_payload["radioSetting5g"]
    # The controller replaces the whole object, so everything we did not change
    # has to be sent back untouched
    assert radio["txPower"] == 23
    assert radio["txPowerLevel"] == 2
    assert radio["wirelessMode"] == -2
    assert radio["radioEnable"] is True


def test_channel_number_is_converted_to_index_and_frequency():
    api = FakeApi()

    _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel=108))

    radio = api.put_payload["radioSetting5g"]
    # 108 is the 11th entry of the 5GHz channel list
    assert radio["channel"] == 11
    assert radio["freq"] == 5540


def test_channel_zero_selects_automatic_and_clears_frequency():
    api = FakeApi()

    _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel=0))

    radio = api.put_payload["radioSetting5g"]
    assert radio["channel"] == 0
    assert radio["freq"] == 0


def test_channel_number_equals_index_on_2ghz():
    api = FakeApi()

    _set(api, RadioId.FREQ_2_4, AccessPointRadioSettings(channel=11))

    radio = api.put_payload["radioSetting2g"]
    assert radio["channel"] == 11
    assert radio["freq"] == 2462


def test_unavailable_channel_is_rejected():
    api = FakeApi()

    with pytest.raises(InvalidDevice, match="not available"):
        _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel=165))


def test_setting_a_radio_the_access_point_lacks_is_rejected():
    api = FakeApi()

    with pytest.raises(InvalidDevice, match="no FREQ_6 radio"):
        _set(api, RadioId.FREQ_6, AccessPointRadioSettings(channel_width=ChannelWidth.WIDTH_80))


def test_updated_settings_are_returned():
    api = FakeApi()

    updated = _set(api, RadioId.FREQ_5_1, AccessPointRadioSettings(channel_width=ChannelWidth.WIDTH_80))

    assert updated.channel_width == ChannelWidth.WIDTH_80
