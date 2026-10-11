# Autonomous Finance Agent

An AI-powered finance operations prototype built with Python, Ollama, and PostgreSQL. The agent interprets natural-language tasks, selects appropriate tools, performs controlled database operations, and verifies invoice records against authoritative source data.

The project explores reliable AI agent execution through tool calling, database constraints, verification, and persistent execution logs.

## Features

- **Local LLM:** Uses Ollama with Qwen3 8B for task interpretation and tool selection.
- **PostgreSQL integration:** Stores source invoices, processed records, and execution history.
- **Controlled tool calling:** Executes model-selected actions through registered Python functions.
- **Execution safeguards:** Enforces invoice discovery and explicit invoice targets.
- **Duplicate prevention:** Uses database uniqueness constraints and conflict handling.
- **Invoice verification:** Compares processed records against authoritative source data.
- **Execution logging:** Tracks tool arguments, results, and agent run statuses.
- **Failure handling:** Handles database errors, verification mismatches, model failures, and execution limits.
- **Automated testing:** Includes 16 unit tests for core functionality and safety checks.

## Architecture

1. The user submits a natural-language finance task.
2. Ollama selects a tool and provides its arguments.
3. Python validates the request against execution rules.
4. The selected tool performs the database operation.
5. The result is logged and returned to the model.
6. The agent verifies the invoice and reports the final task status.

The LLM proposes actions, while Python executes them and PostgreSQL stores the data. Successful completion depends on actual tool results and verification, not merely the model's claims.

## Technology Stack

- Python
- Ollama and Qwen3 8B
- PostgreSQL and psycopg
- python-dotenv
- unittest
- Git

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Initialize PostgreSQL

Start PostgreSQL:

```bash
sudo systemctl start postgresql
```

For a fresh database, initialize the schema and sample data:

```bash
sudo -u postgres createdb centralign
sudo -u postgres psql -d centralign -f schema.sql
sudo -u postgres psql -d centralign -f seed.sql
```

Configure database access using `.env.example` and your local PostgreSQL credentials. Only create and seed a new database when appropriate.

### 3. Start Ollama

```bash
ollama pull qwen3:8b
ollama serve
```

If Ollama is already running, do not start another instance.

### 4. Run the agent

```bash
python agent.py
```

Example request:

```text
Record invoice AC-1043 and verify it against the source record.
```

## Testing

Run the automated test suite:

```bash
python -m unittest -v test_agent.py
```

The 16 tests cover tool execution, invoice discovery, execution guards, duplicate handling, verification success and failure, model errors, and execution limits.

The live workflow has also been tested against PostgreSQL and Ollama. Invoice `AC-1043` was recognized as already recorded, was not inserted again, and was successfully verified against its source record.

## Limitations

- Focused on invoice processing rather than general finance operations.
- Requires PostgreSQL and a running local Ollama model.
- Automatic reconciliation of mismatched invoice fields is not implemented.
- Additional integration testing, security controls, and production-readiness work are needed.

## Future Improvements

- Add controlled invoice reconciliation with audit logging.
- Improve task planning and completion criteria.
- Expand integration testing and reliability evaluation.
- Introduce human approval for sensitive financial operations.
- Strengthen database migrations, access controls, and monitoring.

## Project Status

**Functional engineering prototype.**

Demonstrates local LLM tool calling, guarded database operations, invoice verification, duplicate prevention, and persistent execution logging. Not intended for production financial use in its current form.
