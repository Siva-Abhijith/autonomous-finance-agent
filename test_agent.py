
import unittest
from unittest.mock import Mock, patch

from agent import execute_tool


class TestExecuteTool(unittest.TestCase):

    def setUp(self):
        self.state = {
            "discovered_invoices": set(),
            "recorded_invoices": set(),
        }

    def test_unknown_tool_is_rejected(self):
        result = execute_tool(
            "delete_everything",
            {},
            self.state,
        )

        self.assertIn("error", result)
        self.assertIn("Unknown tool", result["error"])

    def test_recording_undiscovered_invoice_is_blocked(self):
        result = execute_tool(
            "record_invoice",
            {"invoice_number": "INV-UNKNOWN"},
            self.state,
        )

        self.assertFalse(result["success"])
        self.assertIn("not discovered", result["error"])

    def test_verification_before_recording_is_blocked(self):
        result = execute_tool(
            "verify_invoice",
            {"invoice_number": "INV-UNKNOWN"},
            self.state,
        )

        self.assertFalse(result["verified"])
        self.assertIn("not successfully recorded", result["error"])

    def test_discovered_invoice_can_be_recorded(self):
        self.state["discovered_invoices"].add("INV-1001")

        fake_record = Mock(return_value={
            "success": True,
            "invoice_number": "INV-1001",
            "inserted": True,
        })

        with patch.dict("agent.TOOLS", {"record_invoice": fake_record}):
            result = execute_tool(
                "record_invoice",
                {"invoice_number": "INV-1001"},
                self.state,
            )

        self.assertTrue(result["success"])
        self.assertIn("INV-1001", self.state["recorded_invoices"])
        fake_record.assert_called_once_with(invoice_number="INV-1001")

    def test_failed_recording_does_not_enable_verification(self):
        self.state["discovered_invoices"].add("INV-1001")

        fake_record = Mock(return_value={
            "success": False,
            "invoice_number": "INV-1001",
            "error": "Database write failed",
        })

        with patch.dict("agent.TOOLS", {"record_invoice": fake_record}):
            result = execute_tool(
                "record_invoice",
                {"invoice_number": "INV-1001"},
                self.state,
            )

        self.assertFalse(result["success"])
        self.assertNotIn("INV-1001", self.state["recorded_invoices"])

        verify_result = execute_tool(
            "verify_invoice",
            {"invoice_number": "INV-1001"},
            self.state,
        )

        self.assertFalse(verify_result["verified"])
        self.assertIn("not successfully recorded", verify_result["error"])


if __name__ == "__main__":
    unittest.main()
