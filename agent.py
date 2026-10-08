import json
import psycopg
from ollama import chat


# DATABASE
def get_connection():
    return psycopg.connect(
        dbname="centralign",
        user="postgres",
        host="localhost",
        port=5432
    )


def find_latest_invoice(vendor):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT id, invoice_number, vendor, amount, due_date
        FROM invoices
        WHERE LOWER(vendor) = LOWER(%s)
        ORDER BY due_date DESC
        LIMIT 1;
    """, (vendor,))

    result = cursor.fetchone()

    cursor.close()
    connection.close()

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


def record_invoice(invoice_number):
    """
    Record an invoice using the authoritative invoice
    stored in the source database.

    The LLM only supplies the invoice number.
    It cannot invent the amount, vendor or due date.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # First retrieve the real invoice.
    cursor.execute("""
        SELECT invoice_number, vendor, amount, due_date
        FROM invoices
        WHERE invoice_number = %s;
    """, (invoice_number,))

    invoice = cursor.fetchone()

    if invoice is None:
        cursor.close()
        connection.close()

        return {
            "success": False,
            "error": "Invoice does not exist in the source system.",
            "invoice_number": invoice_number
        }

    # Insert into internal finance system.
    cursor.execute("""
        INSERT INTO processed_invoices
            (invoice_number, vendor, amount, due_date)
        VALUES
            (%s, %s, %s, %s)
        ON CONFLICT (invoice_number) DO NOTHING;
    """, (
        invoice[0],
        invoice[1],
        invoice[2],
        invoice[3]
    ))

    inserted = cursor.rowcount == 1

    connection.commit()

    cursor.close()
    connection.close()

    return {
        "success": True,
        "invoice_number": invoice[0],
        "inserted": inserted,
        "already_existed": not inserted
    }


def verify_invoice(invoice_number):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        SELECT invoice_number, vendor, amount, due_date
        FROM processed_invoices
        WHERE invoice_number = %s;
    """, (invoice_number,))

    result = cursor.fetchone()

    cursor.close()
    connection.close()

    if result is None:
        return {
            "verified": False,
            "invoice_number": invoice_number
        }

    return {
        "verified": True,
        "invoice_number": result[0],
        "vendor": result[1],
        "amount": float(result[2]),
        "due_date": str(result[3])
    }


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
def execute_tool(tool_name, arguments):

    if tool_name not in TOOLS:
        return {
            "error": f"Unknown tool: {tool_name}"
        }

    try:
        function = TOOLS[tool_name]
        return function(**arguments)

    except Exception as error:
        return {
            "error": str(error)
        }


# AGENT
def run_agent(user_request):

    messages = [
        {
            "role": "system",
            "content": """
You are an autonomous finance operations worker.

Your job is to complete the user's requested task using the
available tools.

Rules:

1. Do not invent invoice data.
2. Treat tool results as authoritative.
3. Use the output of one tool to decide the next action.
4. If the user asks you to record an invoice, use the invoice
   number returned by the invoice search tool.
5. After recording an invoice, verify that the operation succeeded
   before claiming success.
6. If a tool returns an error, do not pretend the task succeeded.
   Try to recover when possible.
7. When the task is complete, give the user a concise summary
   of what happened and include relevant evidence.
"""
        },

        {
            "role": "user",
            "content": user_request
        }
    ]

    while True:

        response = chat(
            model="qwen3:8b",
            messages=messages,
            tools=tools
        )

        # Add the assistant's response to the conversation.
        messages.append(response.message)

        # ----------------------------------------------------
        # No tool call = agent is finished
        # ----------------------------------------------------

        if not response.message.tool_calls:

            print("\n================ FINAL ANSWER ================\n")
            print(response.message.content)

            return response.message.content

        # ----------------------------------------------------
        # Execute requested tools
        # ----------------------------------------------------

        for tool_call in response.message.tool_calls:

            tool_name = tool_call.function.name
            arguments = tool_call.function.arguments

            print("\n--------------------------------------------")
            print("AI requested tool:", tool_name)
            print("Arguments:", arguments)

            result = execute_tool(
                tool_name,
                arguments
            )

            print("Tool result:", result)

            # Give the result back to the AI.
            messages.append({
                "role": "tool",
                "content": json.dumps(result),
                "tool_name": tool_name
            })


# MAIN
if __name__ == "__main__":

    request = input(
        "\nWhat should the finance worker do?\n> "
    )

    run_agent(request)
