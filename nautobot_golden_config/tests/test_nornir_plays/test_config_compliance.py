"""Unit tests for nautobot_golden_config nornir compliance."""

import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from nautobot_golden_config.choices import ComplianceRuleConfigTypeChoice
from netutils.config.compliance import section_config as netutils_section_config

from nautobot_golden_config.nornir_plays import config_compliance
from nautobot_golden_config.nornir_plays.config_compliance import (
    batch_by_size,
    get_config_element,
    get_rules,
    rules_for_device,
    section_config,
    send_compliance_webhook,
    update_compliance,
)


class ConfigComplianceTest(unittest.TestCase):
    """Test Nornir Compliance Task."""

    @patch("nautobot_golden_config.nornir_plays.config_compliance.ComplianceRule", autospec=True)
    def test_get_rules(self, mock_compliance_rule):
        """Test proper return when Features are returned."""
        features = {"config_ordered": "test_ordered", "match_config": "aaa\nsnmp\n"}
        mock_obj = Mock(**features)
        mock_obj.name = "test_name"
        mock_obj.platform = Mock(network_driver="test_driver")
        mock_compliance_rule.objects.select_related.return_value = [mock_obj]
        features = get_rules()
        mock_compliance_rule.objects.select_related.assert_called_once()
        self.assertEqual(
            features, {"test_driver": [{"obj": mock_obj, "ordered": "test_ordered", "section": ["aaa", "snmp"]}]}
        )

    def test_get_config_element_match_config_present(self):
        """Test proper return when Config JSON is returned with match_config"""
        mock_config = json.dumps({"key1": "value1", "key2": "value2", "key3": "value3"})
        mock_obj = MagicMock(name="Device")
        mock_obj.platform = Mock(network_driver="test_driver")
        mock_rule = MagicMock(name="ComplianceRule")
        mock_rule["obj"].match_config = "key1"
        mock_rule["obj"].config_ordered = True
        mock_rule["obj"].config_type = ComplianceRuleConfigTypeChoice.TYPE_JSON
        return_config = json.dumps(get_config_element(mock_rule, mock_config, mock_obj, None))
        self.assertEqual(return_config, json.dumps({"key1": "value1"}))

    def test_get_config_element_match_config_absent(self):
        """Test proper return when Config JSON is returned without match_config"""
        mock_config = json.dumps({"key1": "value1", "key2": "value2", "key3": "value3"})
        mock_obj = MagicMock(name="Device")
        mock_obj.platform = Mock(network_driver="test_driver")
        mock_rule = MagicMock(name="ComplianceRule")
        mock_rule["obj"].match_config = ""
        mock_rule["obj"].config_ordered = True
        mock_rule["obj"].config_type = ComplianceRuleConfigTypeChoice.TYPE_JSON
        return_config = json.dumps(get_config_element(mock_rule, mock_config, mock_obj, None))
        self.assertEqual(return_config, mock_config)


def _host_result(name, failed=False, records=None):
    """Build a fake per-host Nornir MultiResult for one device."""
    device = Mock(serial="", primary_ip4=None, location=None, device_type=None, role=None, status=None)
    device.name = name
    device.platform = Mock(network_driver="arista_eos")
    result = Mock(result=None if failed else (records or []))
    result.host.data = {"obj": device}
    multi_result = MagicMock(failed=failed)
    multi_result.__getitem__.return_value = result
    return multi_result


@patch.dict("os.environ", {"CONFIG_WEBAPP_WEBHOOK_URL": "https://config-webapp/webhook/"})
@patch("nautobot_golden_config.nornir_plays.config_compliance.requests.post")
class SendComplianceWebhookTest(unittest.TestCase):
    """Test sending compliance results to config-webapp."""

    def test_failed_devices_do_not_block_the_rest(self, mock_post):
        """Devices that passed are sent; failed ones are skipped and logged."""
        mock_post.return_value = Mock(ok=True, status_code=202)
        results = {"sw1": _host_result("sw1"), "sw2": _host_result("sw2", failed=True), "sw3": _host_result("sw3")}
        logger = Mock()

        send_compliance_webhook(results, logger)

        mock_post.assert_called_once()
        sent = [device["name"] for device in mock_post.call_args.kwargs["json"]["devices"]]
        self.assertEqual(sent, ["sw1", "sw3"])
        self.assertIn("sw2", logger.warning.call_args.args[0])

    def test_non_2xx_response_is_logged_as_warning(self, mock_post):
        mock_post.return_value = Mock(ok=False, status_code=413)
        logger = Mock()

        send_compliance_webhook({"sw1": _host_result("sw1")}, logger)

        self.assertIn("HTTP 413", logger.warning.call_args.args[0])
        logger.info.assert_called_once()  # only the "Sending ..." line


class BatchBySizeTest(unittest.TestCase):
    """Test splitting webhook payloads by size."""

    def test_batches_stay_under_the_cap(self):
        devices = [{"name": f"sw{i}", "config": "x" * 100} for i in range(10)]
        device_bytes = len(json.dumps(devices[0]))

        batches = batch_by_size(devices, max_bytes=device_bytes * 3)

        self.assertEqual([len(batch) for batch in batches], [3, 3, 3, 1])
        self.assertEqual([device for batch in batches for device in batch], devices)

    def test_oversized_device_is_sent_alone(self):
        devices = [{"name": "small"}, {"name": "big", "config": "x" * 1000}, {"name": "small2"}]

        batches = batch_by_size(devices, max_bytes=100)

        self.assertEqual([[device["name"] for device in batch] for batch in batches], [["small"], ["big"], ["small2"]])


AOSCX_CONFIG = """hostname sw1
!
snmp-server vrf default
snmp-server community public
aaa authentication login default local
aaa accounting all-mgmt default start-stop
interface 1/1/1
    description uplink
    no shutdown
interface 1/1/2
    shutdown
ssh server vrf mgmt
banner motd !
welcome
!
"""


EOS_CONFIG = """hostname sw2
!
snmp-server community public ro
aaa authentication login default local
interface Ethernet1
   description uplink
   no shutdown
interface Ethernet2
   shutdown
banner motd
welcome
EOF
!
"""

CONFIGS = {"aruba_aoscx": AOSCX_CONFIG, "arista_eos": EOS_CONFIG}


class SectionConfigTest(unittest.TestCase):
    """section_config must match netutils' and parse each config only once."""

    RULES = (
        {"section": ["snmp-server"]},
        {"section": ["aaa "]},
        {"section": ["interface "]},
        {"section": ["ssh server", "banner"]},
        {"section": ["no-such-section"]},
        {"section": []},
    )

    def setUp(self):
        config_compliance._parse_config.cache_clear()

    def test_matches_netutils(self):
        for network_os, config in CONFIGS.items():
            for rule in self.RULES:
                with self.subTest(network_os=network_os, rule=rule):
                    self.assertEqual(
                        section_config(rule, config, network_os),
                        netutils_section_config(rule, config, network_os),
                    )

    def test_parses_each_config_once(self):
        real_parser = config_compliance.parser_map["aruba_aoscx"]
        counting_parser = Mock(side_effect=real_parser)
        with patch.dict(config_compliance.parser_map, {"aruba_aoscx": counting_parser}):
            for rule in self.RULES:
                section_config(rule, AOSCX_CONFIG, "aruba_aoscx")
                section_config(rule, AOSCX_CONFIG + "\n", "aruba_aoscx")
        self.assertEqual(counting_parser.call_count, 2)


class RulesForDeviceTest(unittest.TestCase):
    """Rules are matched on Platform, not just network_driver."""

    def test_only_this_platforms_rules(self):
        eos, eos_rr = Mock(platform_id="eos"), Mock(platform_id="eos-rr")
        rules = {"arista_eos": [{"obj": eos}, {"obj": eos_rr}]}
        device = Mock(platform_id="eos")
        device.platform.network_driver = "arista_eos"
        self.assertEqual(rules_for_device(rules, device), [{"obj": eos}])


class FakeCompliance:  # pylint: disable=too-few-public-methods
    """Stands in for a stored ConfigCompliance row; compliance = actual == intended."""

    def __init__(self, actual, intended):
        self.device = self.rule = None
        self.actual, self.intended, self.missing, self.extra = actual, intended, "", ""
        self.compliance_on_save()
        self.remediation_on_save()

    def compliance_on_save(self):
        self.compliance = self.actual == self.intended
        self.compliance_int = int(self.compliance)
        self.ordered = True
        self.missing = "" if self.compliance else self.intended
        self.extra = "" if self.compliance else self.actual

    def remediation_on_save(self):
        self.remediation = "" if self.compliance else f"fix: {self.intended}"


@patch("nautobot_golden_config.nornir_plays.config_compliance.ConfigCompliance")
class UpdateComplianceTest(unittest.TestCase):
    """update_compliance only writes when the stored result would change."""

    def test_creates_missing_row(self, mock_cc):
        mock_cc.objects.filter.return_value.first.return_value = None
        self.assertTrue(update_compliance("dev", "rule", "a", "a"))
        mock_cc.objects.update_or_create.assert_called_once_with(
            device="dev", rule="rule", defaults={"actual": "a", "intended": "a", "missing": "", "extra": ""}
        )

    def test_skips_unchanged_row(self, mock_cc):
        mock_cc.objects.filter.return_value.first.return_value = FakeCompliance("a", "b")
        self.assertFalse(update_compliance("dev", "rule", "a", "b"))
        mock_cc.objects.update_or_create.assert_not_called()

    def test_saves_changed_row(self, mock_cc):
        for actual, intended in (("a", "c"), ("b", "b"), ("x", "b")):
            with self.subTest(actual=actual, intended=intended):
                mock_cc.reset_mock()
                stored = FakeCompliance("a", "b")
                mock_cc.objects.filter.return_value.first.return_value = stored
                self.assertTrue(update_compliance("dev", "rule", actual, intended))
                mock_cc.objects.update_or_create.assert_called_once()
                self.assertEqual((stored.actual, stored.intended), ("a", "b"))  # stored row not mutated
