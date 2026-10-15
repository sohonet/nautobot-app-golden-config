"""Unit tests for nautobot_golden_config nornir compliance."""

import json
import unittest
from unittest.mock import MagicMock, Mock, patch

from nautobot_golden_config.choices import ComplianceRuleConfigTypeChoice
from nautobot_golden_config.nornir_plays.config_compliance import (
    batch_by_size,
    get_config_element,
    get_rules,
    send_compliance_webhook,
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
        mock_compliance_rule.objects.all.return_value = [mock_obj]
        features = get_rules()
        mock_compliance_rule.objects.all.assert_called_once()
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
