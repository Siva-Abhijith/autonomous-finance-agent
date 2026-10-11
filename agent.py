import json
import psycopg
from ollama import chat
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

# DATABASE

def get_connection():
    return psycopg.connect(
        dbname=os.getenv("DB_NAME", "centralign"),
        user=os.getenv("DB_USER", "postgres"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
    )



def save_execution_log(run_id, step, tool_name, arguments, status, result):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO agent_execution_logs
                    (run_id, step, tool_name, arguments, status, result)
                VALUES (%s, %s, %s, %s, %s, %s);
            """, (
                run_id,
                step,
                tool_name,
                json.dumps(arguments),
                status,
                json.dumps(result)
            ))

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def start_agent_run(run_id, user_request):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO agent_runs (run_id, user_request)
                VALUES (%s, %s);
            """, (run_id, user_request))
        connection.commit()
    finally:
        connection.close()


def finish_agent_run(run_id, final_status, final_response):
    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE agent_runs
                SET final_status = %s,
                    final_response = %s,
                    finished_at = CURRENT_TIMESTAMP
                WHERE run_id = %s;
            """, (final_status, final_response, run_id))
        connection.commit()
    finally:
        connection.close()



def find_latest_invoice(vendor):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, invoice_number, vendor, amount, due_date
                FROM invoices
                WHERE LOWER(vendor) = LOWER(%s)
                ORDER BY due_date DESC
                LIMIT 1;
            """, (vendor,))

            result = cursor.fetchone()

        if result is None:
            return {
                "found": False,
                "vendor": vendor
            }

        return {
            "found": True,
            "id": result[0],
            "invoice_number": result[1],
            "vendor": result[2],
            "amount": float(result[3]),
            "due_date": str(result[4])
        }

    finally:
        connection.close()



def record_invoice(invoice_number):
    """
    Record an invoice using the authoritative source database.
    The LLM supplies only the invoice number.
    """

    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            # Retrieve the authoritative invoice.
            cursor.execute("""
                SELECT invoice_number, vendor, amount, due_date
                FROM invoices
                WHERE invoice_number = %s;
            """, (invoice_number,))

            invoice = cursor.fetchone()

            if invoice is None:
                return {
                    "success": False,
                    "error": "Invoice does not exist in the source system.",
                    "invoice_number": invoice_number
                }

            # Insert it into the processed system.
            cursor.execute("""
                INSERT INTO processed_invoices
                    (invoice_number, vendor, amount, due_date)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (invoice_number) DO NOTHING;
            """, (
                invoice[0],
                invoice[1],
                invoice[2],
                invoice[3]
            ))

            inserted = cursor.rowcount == 1

        connection.commit()

        return {
            "success": True,
            "invoice_number": invoice[0],
            "inserted": inserted,
            "already_existed": not inserted
        }

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()



def verify_invoice(invoice_number):
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    s.invoice_number,
                    s.vendor,
                    s.amount,
                    s.due_date,
                    p.invoice_number,
                    p.vendor,
                    p.amount,
                    p.due_date
                FROM invoices AS s
                LEFT JOIN processed_invoices AS p
                    ON p.invoice_number = s.invoice_number
                WHERE s.invoice_number = %s;
            """, (invoice_number,))

            result = cursor.fetchone()

        if result is None:
            return {
                "verified": False,
                "invoice_number": invoice_number,
                "error": "Invoice does not exist in the source system."
            }

        source_number, source_vendor, source_amount, source_date = result[:4]
        processed_number, processed_vendor, processed_amount, processed_date = result[4:]

        if processed_number is None:
            return {
                "verified": False,
                "invoice_number": invoice_number,
                "error": "Invoice is missing from the processed system."
            }

        mismatches = []

        if source_vendor != processed_vendor:
            mismatches.append("vendor")

        if source_amount != processed_amount:
            mismatches.append("amount")

        if source_date != processed_date:
            mismatches.append("due_date")

        if mismatches:
            return {
                "verified": False,
                "invoice_number": invoice_number,
                "error": "Invoice fields do not match the source record.",
                "mismatches": mismatches
            }

        return {
            "verified": True,
            "invoice_number": source_number,
            "vendor": source_vendor,
            "amount": str(source_amount),
            "due_date": str(source_date),
            "comparison": "All fields match the source record."
        }

    finally:
        connection.close()



# TOOL REGISTRY
TOOLS = {
    "find_latest_invoice": find_latest_invoice,
    "record_invoice": record_invoice,
    "verify_invoice": verify_invoice,
}


# TOOL DEFINITIONS GIVEN TO THE LLM
tools = [
    {
        "type": "function",
        "function": {
            "name": "find_latest_invoice",
            "description": (
                "Find the latest invoice for a vendor. "
                "Use this when the user asks to find an invoice."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "vendor": {
                        "type": "string",
                        "description": "The vendor name."
                    }
                },
                "required": ["vendor"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "record_invoice",
            "description": (
                "Record an existing invoice in the internal finance system. "
                "Only provide an invoice number returned by another tool. "
                "Do not invent invoice numbers."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": "string",
                        "description": (
                            "The invoice number returned by "
                            "find_latest_invoice."
                        )
                    }
                },
                "required": ["invoice_number"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "verify_invoice",
            "description": (
                "Verify that an invoice exists in the internal "
                "finance system."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": "string",
                        "description": "The invoice number to verify."
                    }
                },
                "required": ["invoice_number"]
            }
        }
    }
]


# TOOL EXECUTOR
def execute_tool(tool_name, arguments, state):

    if tool_name not in TOOLS:
        return {"error": f"Unknown tool: {tool_name}"}

    # Block recording invoices not discovered in this run.
    if tool_name == "record_invoice":
        invoice_number = arguments.get("invoice_number")

        if invoice_number not in state["discovered_invoices"]:
            return {
                "success": False,
                "invoice_number": invoice_number,
                "error": "Recording blocked: this invoice was not discovered during the current agent run."
            }

    # Block verification unless recording succeeded.
    if tool_name == "verify_invoice":
        invoice_number = arguments.get("invoice_number")

        if invoice_number not in state["recorded_invoices"]:
            return {
                "verified": False,
                "invoice_number": invoice_number,
                "error": "Verification blocked: this agent run has not successfully recorded this invoice."
            }

    try:
        function = TOOLS[tool_name]
        result = function(**arguments)

        # Track invoices found by the search tool.
        if (
            tool_name == "find_latest_invoice"
            and result.get("found") is True
        ):
            state["discovered_invoices"].add(
                result["invoice_number"]
            )

        # Track successful recordings.
        if (
            tool_name == "record_invoice"
            and result.get("success") is True
        ):
            state["recorded_invoices"].add(
                result["invoice_number"]
            )

        return result

    except Exception as error:
        return {"error": str(error)}

# AGENT

def run_agent(user_request):
    state = {
        "discovered_invoices": set(),
        "recorded_invoices": set()
    }

    if not user_request or not user_request.strip():
        print("Please enter a non-empty task.")
        return "Empty task rejected."

    run_id = str(uuid.uuid4())
    print(f"\nRun ID: {run_id}")

    try:
        start_agent_run(run_id, user_request)
    except Exception as error:
        print(f"Could not start agent run: {error}")
        return f"Agent could not start: {error}"

    execution_log = []

    messages = [
        {
            "role": "system",
            "content": """
            You are an autonomous finance operations worker.

            Your job is to complete the user's requested task using
            the available tools.

            Rules:
            1. Never invent invoice data.
            2. Treat tool results as authoritative.
            3. Use tool results to decide the next action.
            4. When recording an invoice, use an invoice number
               returned by the search tool.
            5. Verify a recorded invoice before claiming success.
            6. Never claim success when a tool fails.
            7. Give a concise summary with relevant evidence.
            8. If the requested vendor has no invoice, report that
               honestly.
            """
        },
        {
            "role": "user",
            "content": user_request
        }
    ]

    max_turns = 10

    try:
        for turn in range(max_turns):

            # Ask Ollama, retrying temporary failures.
            max_attempts = 3
            response = None

            for attempt in range(1, max_attempts + 1):
                try:
                    response = chat(
                        model="qwen3:8b",
                        messages=messages,
                        tools=tools
                    )
                    break

                except Exception as error:
                    print(
                        f"Ollama call failed "
                        f"(attempt {attempt}/{max_attempts}): "
                        f"{error}"
                    )

                    if attempt == max_attempts:
                        final_response = (
                            f"Agent execution failed after "
                            f"{max_attempts} attempts: {error}"
                        )

                        finish_agent_run(
                            run_id, "FAILED", final_response
                        )
                        print(final_response)
                        print("Final task status: FAILED")
                        return final_response

            messages.append(response.message)

            # No tool calls means the model has finished.
            if not response.message.tool_calls:

                verified_invoice = next(
                    (
                        entry["result"]
                        for entry in reversed(execution_log)
                        if entry["tool"] == "verify_invoice"
                        and entry["result"].get("verified") is True
                    ),
                    None
                )

                # Determine whether the requested task succeeded.
                search_results = [
                    entry["result"]
                    for entry in execution_log
                    if entry["tool"] == "find_latest_invoice"
                ]

                record_results = [
                    entry["result"]
                    for entry in execution_log
                    if entry["tool"] == "record_invoice"
                ]

                verification_results = [
                    entry["result"]
                    for entry in execution_log
                    if entry["tool"] == "verify_invoice"
                ]

                has_failed_verification = any(
                    result.get("verified") is False
                    for result in verification_results
                )

                has_failed_recording = any(
                    result.get("success") is False
                    for result in record_results
                )

                has_failed_search = any(
                    result.get("found") is False
                    for result in search_results
                )

                if verified_invoice:
                    final_response = (
                        "Invoice verified successfully.\n\n"
                        f"Invoice number: "
                        f"{verified_invoice['invoice_number']}\n"
                        f"Vendor: {verified_invoice['vendor']}\n"
                        f"Amount: {verified_invoice['amount']} "
                        "(currency not specified in the database)\n"
                        f"Due date: {verified_invoice['due_date']}\n\n"
                        "Verification: all checked fields match "
                        "the source record."
                    )
                    final_status = "COMPLETED"

                elif has_failed_verification:
                    final_response = (
                        "Invoice verification failed. "
                        "The invoice could not be confirmed "
                        "against the source record."
                    )
                    final_status = "FAILED"

                elif has_failed_recording:
                    final_response = (
                        "Invoice recording failed. "
                        "Check the execution log for details."
                    )
                    final_status = "FAILED"

                elif has_failed_search:
                    final_response = (
                        "No matching invoice was found. "
                        "No invoice was recorded."
                    )
                    final_status = "FAILED"

                elif search_results and not record_results:
                    requested_recording = "record" in user_request.lower()
                    requested_verification = "verif" in user_request.lower()

                    if requested_recording or requested_verification:
                        final_response = (
                            "The invoice was found, but the requested "
                            "recording or verification was not completed."
                        )
                        final_status = "FAILED"
                    else:
                        final_response = (
                            "Invoice search completed successfully.\n\n"
                            + (
                                response.message.content
                                or "The search result is available "
                                "in the execution log."
                            )
                        )
                        final_status = "COMPLETED"

                else:
                    final_response = (
                        response.message.content
                        or "The agent finished without a final response."
                    )
                    final_status = "FAILED"

                finish_agent_run(
                    run_id, final_status, final_response
                )

                print("\n================ FINAL ANSWER ================\n")
                print(final_response)
                print("\nFinal task status:", final_status)

                print("\n================ EXECUTION LOG ================\n")
                print(json.dumps(execution_log, indent=2))

                return final_response

            # Execute each requested tool.
            for tool_call in response.message.tool_calls:
                tool_name = tool_call.function.name
                arguments = tool_call.function.arguments

                print("\n--------------------------------------------")
                print("AI requested tool:", tool_name)
                print("Arguments:", arguments)

                result = execute_tool(
                    tool_name, arguments, state
                )

                # Classify the tool result.
                if result.get("verified") is False:
                    status = "NOT_VERIFIED"
                elif result.get("found") is False:
                    status = "NOT_FOUND"
                elif result.get("success") is False:
                    status = (
                        "BLOCKED_OR_ERROR"
                        if result.get("error")
                        else "FAILED"
                    )
                elif result.get("error"):
                    status = "BLOCKED_OR_ERROR"
                elif result.get("already_existed") is True:
                    status = "ALREADY_EXISTS"
                elif result.get("verified") is True:
                    status = "VERIFIED"
                else:
                    status = "SUCCESS"

                step = len(execution_log) + 1

                execution_log.append({
                    "step": step,
                    "tool": tool_name,
                    "arguments": arguments,
                    "status": status,
                    "result": result
                })

                # Persist the tool execution.
                try:
                    save_execution_log(
                        run_id=run_id,
                        step=step,
                        tool_name=tool_name,
                        arguments=arguments,
                        status=status,
                        result=result
                    )

                except Exception as error:
                    final_response = (
                        f"Execution logging failed at step "
                        f"{step}: {error}"
                    )

                    print(final_response)

                    try:
                        finish_agent_run(
                            run_id, "FAILED", final_response
                        )
                    except Exception as status_error:
                        print(
                            "Could not update run status: "
                            f"{status_error}"
                        )

                    print("Final task status: FAILED")
                    return final_response

                print("Tool result:", result)
                print("Step status:", status)

                messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_name": tool_name
                })

        # The agent exhausted its allowed turns.
        final_response = (
            f"Agent stopped after reaching the "
            f"{max_turns}-turn limit."
        )

        finish_agent_run(
            run_id, "FAILED", final_response
        )

        print(final_response)
        print("Final task status: FAILED")
        return final_response

    except Exception as error:
        # Catch unexpected errors not handled above.
        final_response = (
            f"Unexpected agent error: {type(error).__name__}: {error}"
        )

        print(final_response)

        try:
            finish_agent_run(
                run_id, "FAILED", final_response
            )
        except Exception as status_error:
            print(
                "Could not update run status: "
                f"{status_error}"
            )

        print("Final task status: FAILED")
        return final_response



# MAIN
if __name__ == "__main__":

    request = input(
        "\nWhat should the finance worker do?\n> "
    )

    run_agent(request)
