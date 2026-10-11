
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from agent import execute_tool, verify_invoice, record_invoice, run_agent

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

    @patch("agent.get_connection")
    def test_verification_succeeds_when_all_fields_match(self, mock_connection):
        mock_cursor = mock_connection.return_value.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            "INV-1001", "Acme Supplies", 12500.00, "2026-11-15",
            "INV-1001", "Acme Supplies", 12500.00, "2026-11-15",
        )

        result = verify_invoice("INV-1001")

        self.assertTrue(result["verified"])
        self.assertEqual(result["invoice_number"], "INV-1001")
        self.assertEqual(result["vendor"], "Acme Supplies")
        self.assertEqual(result["amount"], "12500.0")
        self.assertEqual(result["due_date"], "2026-11-15")
        mock_connection.return_value.close.assert_called_once()

    @patch("agent.get_connection")
    def test_verification_fails_when_amount_mismatches(self, mock_connection):
        mock_cursor = mock_connection.return_value.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = (
            "INV-1001", "Acme Supplies", 12500.00, "2026-11-15",
            "INV-1001", "Acme Supplies", 12600.00, "2026-11-15",
        )

        result = verify_invoice("INV-1001")

        self.assertFalse(result["verified"])
        self.assertIn("amount", result["mismatches"])
        self.assertNotIn("vendor", result["mismatches"])
        self.assertNotIn("due_date", result["mismatches"])
        mock_connection.return_value.close.assert_called_once()

    @patch("agent.get_connection")
    def test_recording_nonexistent_source_invoice_fails(self, mock_connection):
        mock_conn = mock_connection.return_value
        mock_cursor = mock_conn.cursor.return_value.__enter__.return_value
        mock_cursor.fetchone.return_value = None

        result = record_invoice("INV-MISSING")

        self.assertFalse(result["success"])
        self.assertEqual(result["invoice_number"], "INV-MISSING")
        self.assertIn("does not exist", result["error"])
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_not_called()
        mock_conn.close.assert_called_once()

    @patch("agent.get_connection")
    def test_duplicate_invoice_is_not_inserted_again(self, mock_connection):
        mock_conn = mock_connection.return_value
        mock_cursor = mock_conn.cursor.return_value.__enter__.return_value

        mock_cursor.fetchone.return_value = (
            "INV-1001",
            "Acme Supplies",
            12500.00,
            "2026-11-15",
        )
        mock_cursor.rowcount = 0

        result = record_invoice("INV-1001")

        self.assertTrue(result["success"])
        self.assertFalse(result["inserted"])
        self.assertTrue(result["already_existed"])
        self.assertEqual(result["invoice_number"], "INV-1001")
        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_conn.commit.assert_called_once()
        mock_conn.close.assert_called_once()

    def model_response(self, tool_name=None, arguments=None, content=""):
        tool_calls = []

        if tool_name:
            tool_calls.append(
                SimpleNamespace(
                    function=SimpleNamespace(
                        name=tool_name,
                        arguments=arguments,
                    )
                )
            )

        return SimpleNamespace(
            message=SimpleNamespace(
                content=content,
                tool_calls=tool_calls,
            )
        )

    @patch("agent.chat")
    @patch("agent.save_execution_log")
    @patch("agent.finish_agent_run")
    @patch("agent.start_agent_run")
    @patch("agent.execute_tool")
    def test_failed_recording_makes_agent_run_fail(
        self,
        mock_execute,
        mock_start,
        mock_finish,
        mock_log,
        mock_chat,
    ):
        mock_execute.return_value = {
            "success": False,
            "invoice_number": "INV-1001",
            "error": "Database write failed",
        }

        mock_chat.side_effect = [
            self.model_response(
                "record_invoice",
                {"invoice_number": "INV-1001"},
            ),
            self.model_response(content="Finished."),
        ]

        run_agent("Find and record invoice INV-1001")

        self.assertEqual(mock_finish.call_args.args[1], "FAILED")

    @patch("agent.chat")
    @patch("agent.save_execution_log")
    @patch("agent.finish_agent_run")
    @patch("agent.start_agent_run")
    @patch("agent.execute_tool")
    def test_failed_verification_makes_agent_run_fail(
        self,
        mock_execute,
        mock_start,
        mock_finish,
        mock_log,
        mock_chat,
    ):
        mock_execute.side_effect = [
            {
                "success": True,
                "invoice_number": "INV-1001",
                "inserted": True,
            },
            {
                "verified": False,
                "invoice_number": "INV-1001",
                "mismatches": ["amount"],
                "error": "Invoice fields do not match the source record.",
            },
        ]

        mock_chat.side_effect = [
            self.model_response(
                "record_invoice",
                {"invoice_number": "INV-1001"},
            ),
            self.model_response(
                "verify_invoice",
                {"invoice_number": "INV-1001"},
            ),
            self.model_response(content="Finished."),
        ]

        run_agent("Find, record, and verify invoice INV-1001")

        self.assertEqual(mock_finish.call_args.args[1], "FAILED")


if __name__ == "__main__":
    unittest.main()
