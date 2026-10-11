
# Autonomous Finance Operations Agent

A Python-based AI finance worker that uses a local language model, PostgreSQL, and controlled tools to find, record, and verify invoices.

The project explores how an AI agent can execute real operations while maintaining an auditable history and refusing to claim success when verification fails.

## Features

- Local LLM inference using Ollama and Qwen3 8B.
- PostgreSQL-backed invoice search and recording.
- Tool calling through a registered set of Python functions.
- Execution guards that restrict recording to invoices discovered during the current run.
- Verification against authoritative source records.
- Duplicate prevention through database uniqueness and `ON CONFLICT DO NOTHING`.
- Per-tool execution logs stored in PostgreSQL.
- Agent run records containing status, final response, and timestamps.
- Up to three attempts for failed Ollama calls.
- A maximum of ten agent turns per run.
- Error handling for tool execution, logging, and unexpected failures.

## Architecture

1. The user submits a task.
2. The agent sends the request and available tool definitions to Ollama.
3. The model chooses a tool and supplies its arguments.
4. Python validates the tool request against execution guards.
5. The tool interacts with PostgreSQL and returns a structured result.
6. The agent records the tool result in the execution log and returns it to the model.
7. For invoice-processing tasks, the agent verifies the processed invoice against the source record.
8. The agent stores the final response and run status in PostgreSQL.

The LLM chooses actions, but Python tools and PostgreSQL perform the actual database operations. Invoice amounts, vendors, and due dates are retrieved from the source database rather than invented by the model.

## Technology Stack

- Python
- Ollama
- Qwen3 8B
- PostgreSQL
- psycopg
- Git

## Requirements

- Python 3
- PostgreSQL
- Ollama
- The Qwen3 8B model

## Setup

### 1. Clone the repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd <YOUR_REPOSITORY_DIRECTORY>
```

Replace the placeholders with your actual repository URL and directory.

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Start PostgreSQL

On systems using systemd:

```bash
sudo systemctl start postgresql
```

For a **fresh installation**, create the database and initialize its tables:

```bash
sudo -u postgres createdb centralign
sudo -u postgres psql -d centralign -f schema.sql
sudo -u postgres psql -d centralign -f seed.sql
```

The seed script inserts four demonstration invoices. It does not populate the full development dataset.

**Important:** Run the `createdb` command only when creating a new database. Do not run the seed script against your existing development database unless you intentionally want to add the demonstration invoices.

The project expects four tables:

- `invoices` — authoritative source invoices.
- `processed_invoices` — invoices recorded by the agent.
- `agent_runs` — overall status and response for each agent run.
- `agent_execution_logs` — arguments, results, and status for each tool execution.

The `schema.sql` script creates missing tables but does not migrate existing tables whose definitions differ.

### 5. Configure PostgreSQL access

The current `get_connection()` function in `agent.py` connects using:

- Database: `centralign`
- User: `postgres`
- Host: `localhost`
- Port: `5432`

Configure PostgreSQL authentication so the Python process can connect with these settings, or update `get_connection()` to match your local environment.

Do not commit database passwords, API keys, or other secrets.

### 6. Start Ollama

Ensure Ollama is running and the model is available:

```bash
ollama pull qwen3:8b
ollama serve
```

If Ollama is already running as a service, you do not need to start a second server.

### 7. Run the agent

In another terminal, activate the virtual environment and run:

```bash
python agent.py
```

Enter a task such as:

```text
Find the latest invoice from Acme Supplies, record it, and verify it.
```

## Example Workflow

For an invoice-processing request, the expected tool sequence is:

1. `find_latest_invoice`
2. `record_invoice`
3. `verify_invoice`

A successful verification compares the vendor, amount, and due date against the source record.

If the invoice already exists in the processed table, the agent avoids inserting a duplicate. If verification detects a mismatch, the run is marked `FAILED`.

In this prototype, "latest" means the invoice with the greatest due date because the source schema does not include an invoice creation date.

## Testing

The following scenarios have been exercised manually during development:

- Find, record, and verify an invoice.
- Handle an invoice that was already processed.
- Report a nonexistent vendor without inventing an invoice.
- Detect a deliberately altered processed invoice amount.
- Retry failed Ollama calls.
- Persist run records and individual tool execution results.
- Report failures when the model is unavailable or execution logging fails.

`test_ollama.py` is a basic connectivity test for the local model.

These are manual development tests, not a comprehensive automated test suite.

## Limitations

- The tool set focuses on invoice search, recording, and verification rather than general finance operations.
- The agent depends on a running local Ollama model and PostgreSQL.
- Task completion logic is tailored to the current invoice workflow.
- Natural-language intent classification and completion criteria need stronger structured planning.
- Database connection settings are currently defined in Python.
- Automated regression tests, formal evaluation metrics, and production deployment controls remain future work.
- The prototype is not designed for production financial use.

## Future Work

- Move database settings to environment variables.
- Add automated tests for tools, guards, retries, and verification.
- Improve task planning and completion criteria.
- Add structured error categories and recovery policies.
- Introduce human approval for sensitive finance operations.
- Evaluate reliability across a larger set of representative tasks.
- Improve database initialization and sample-data management.

## Project Status

**Functional prototype.** The project demonstrates local LLM tool calling, guarded database operations, verification, and persistent execution records.
