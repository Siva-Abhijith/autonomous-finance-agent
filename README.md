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

### Prerequisites

- Python
- PostgreSQL
- Ollama
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Siva-Abhijith/autonomous-finance-agent.git
cd autonomous-finance-agent
```

### 2. Install dependencies

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure PostgreSQL

Start PostgreSQL:

```bash
sudo systemctl start postgresql
```

For a **fresh development database**, create the database and initialize its schema and sample data:

```bash
sudo -u postgres createdb centralign
sudo -u postgres psql -d centralign -f schema.sql
sudo -u postgres psql -d centralign -f seed.sql
```

Configure your local database credentials using `.env.example` as a reference. Create a `.env` file with the variables expected by the application and update the values for your environment.

**Important:** The commands above are for a fresh database only. If you already have a configured database with the required tables and data, do not recreate or reseed it.

### 4. Start Ollama

Download the model:

```bash
ollama pull qwen3:8b
```

Start the Ollama service if it is not already running:

```bash
ollama serve
```

Keep the service running while using the agent.

### 5. Run the agent

```bash
python agent.py
```

Example task:

```text
Record invoice AC-1043 and verify it against the source record.
```

The agent selects the appropriate tools, executes the requested operations, and reports the outcome.

## Testing

Run the automated unit tests:

```bash
python -m unittest -v test_agent.py
```

The test suite contains 16 tests covering tool execution, invoice discovery, execution guards, duplicate handling, verification success and failure, model errors, and execution limits.

The live workflow has also been tested against PostgreSQL and Ollama. Invoice `AC-1043` was recognized as already recorded, was not inserted again, and was successfully verified against its source record.

## Design Decisions

- **Local inference:** Ollama with Qwen3 8B avoids dependence on a paid LLM API and allows local model execution.
- **Controlled tool execution:** The model proposes actions, but Python validates tool requests and enforces execution rules before performing operations.
- **PostgreSQL persistence:** A relational database stores invoice data and execution history, while uniqueness constraints help prevent duplicate records.
- **Source-based verification:** The agent compares processed invoice fields with the source record instead of relying solely on the LLM's response.
- **Bounded execution:** Limits on model retries and agent turns help prevent indefinite execution when failures occur.
- **Automated testing:** Unit tests exercise core behavior, failure scenarios, and safeguards independently of a successful live run.

## Assumptions

- Source invoices are available in the configured PostgreSQL database before processing.
- The database schema and required tables have been initialized.
- PostgreSQL is accessible with the credentials configured in the local environment.
- Ollama is running and the configured Qwen3 8B model is available.
- Invoice verification checks the vendor, amount, and due date.
- The prototype runs in a controlled development environment and is not intended for production financial use.
- A successful tool result and verification are required to report successful invoice processing.

## Limitations

- Focused on invoice processing rather than general finance operations.
- Requires PostgreSQL and a running local Ollama model.
- Automatic reconciliation of mismatched invoice fields is not implemented.
- The current prototype has not undergone comprehensive production security or scalability testing.
- Model behavior and output quality may vary depending on the task and model response.

## Future Improvements

- Add controlled invoice reconciliation with audit logging.
- Improve task planning and completion criteria.
- Expand integration testing and reliability evaluation.
- Introduce human approval for sensitive financial operations.
- Strengthen database migrations, access controls, and monitoring.

## Project Status

**Functional engineering prototype.**

Demonstrates local LLM tool calling, guarded database operations, invoice verification, duplicate prevention, and persistent execution logging. It is a development prototype and is not intended for production financial use in its current form.
