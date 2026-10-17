# OrgMind Setup & Installation Guide

This guide walks you through setting up **OrgMind** on **Windows** and **macOS/Linux** from scratch.

---

## 1. Prerequisites

1. **Docker Desktop**: Required to run the local FalkorDB graph engine.
   - [Download Docker Desktop](https://www.docker.com/products/docker-desktop/) and ensure Docker daemon is running.
2. **Python 3.10+**:
   - Check version: `python --version` (or `python3 --version`).
3. **An LLM API Key**:
   - OpenAI (`OPENAI_API_KEY`), Anthropic (`ANTHROPIC_API_KEY`), or Google Gemini (`GEMINI_API_KEY`).

---

## 2. Start FalkorDB Container

You can start FalkorDB using either `docker-compose` or a single `docker run` command.

### Option A: Using Docker Compose (Recommended)
```bash
docker compose up -d falkordb
```

### Option B: Using Direct Docker Run
```bash
docker run -d -p 6379:6379 -p 3000:3000 --name falkordb falkordb/falkordb:latest
```

* **Port 6379**: The Redis/FalkorDB database port used by the Python client.
* **Port 3000**: Optional FalkorDB Web Browser UI. Open [http://localhost:3000](http://localhost:3000) to inspect graph nodes visually.

---

## 3. Environment & Dependency Setup

### On Windows (PowerShell):
```powershell
# 1. Create a virtual environment
python -m venv venv

# 2. Activate virtual environment
.\venv\Scripts\Activate.ps1
# (If execution policy error occurs, run: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass)

# 3. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Create your .env file
Copy-Item .env.example .env
```

### On macOS / Linux (Bash or Zsh):
```bash
# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 4. Create your .env file
cp .env.example .env
```

---

## 4. Configure Environment Variables (`.env`)

Open `.env` in your text editor and specify your LLM credentials:

```dotenv
FALKORDB_HOST=localhost
FALKORDB_PORT=6379
FALKORDB_GRAPH_NAME=northwind_labs

# LLM Selection (LiteLLM supports any model name)
LLM_MODEL=gpt-4o

# Provide API key matching your model provider
OPENAI_API_KEY=sk-...
```

---

## 5. Step-by-Step Smoke Test & Verification

### Step 1: Database Smoke Test
Verify that Python can connect to FalkorDB, create a test node, and read it back:
```bash
python orgmind/db.py
```
**Expected output:**
```text
[OrgMind] Running smoke test against FalkorDB...
[OrgMind] Smoke test PASSED: successfully wrote and read from FalkorDB!
```

### Step 2: Ingest Structured Data
Initialize schema indexes and load people, teams, projects, and tickets:
```bash
python orgmind/ingest_structured.py
```
**Expected output:**
```text
=== Starting Structured Data Ingestion ===
[OrgMind] Initializing graph indexes...
[OrgMind] Schema & indexes successfully initialized.
[Ingest] Loaded 6 Person nodes.
[Ingest] Loaded 4 Team nodes.
[Ingest] Loaded 4 Project nodes.
[Ingest] Loaded 3 Ticket nodes.
=== Structured Ingestion Completed Successfully ===
```

### Step 3: Ingest Unstructured Documents & Chats
Extract decisions, link Source nodes, and resolve author handles:
```bash
python orgmind/ingest_unstructured.py
```

### Step 4: Run Evaluation Benchmark
Run the automated questions benchmark:
```bash
python tests/run_eval.py
```

### Step 5: Launch the Streamlit Dashboard
```bash
streamlit run app/streamlit_app.py
```
Open your browser to [http://localhost:8501](http://localhost:8501).

---

## 6. (Optional) Configuring Official FalkorDB MCP Server

If you wish to query the graph using Claude Desktop or an external MCP client:

1. **Install and run the FalkorDB MCP server in Read-Only Mode:**
   ```bash
   npx -y @falkordb/mcpserver@latest
   ```
2. **In your `claude_desktop_config.json`:**
   ```json
   {
     "mcpServers": {
       "falkordb": {
         "command": "npx",
         "args": ["-y", "@falkordb/mcpserver@latest"],
         "env": {
           "FALKORDB_HOST": "localhost",
           "FALKORDB_PORT": "6379",
           "FALKORDB_DEFAULT_READONLY": "true"
         }
       }
     }
   }
   ```

---

## 7. Troubleshooting

* **Error: `ConnectionRefusedError: [WinError 10061] No connection could be made because the target machine actively refused it`**
  - FalkorDB Docker container is not running. Check `docker ps`. Run `docker start falkordb` or `docker compose up -d falkordb`.
* **Port 6379 already in use**:
  - Another local Redis instance might be running. Either stop local Redis (`brew services stop redis` or stop Windows Redis service), or change port mapping in Docker to `-p 6380:6379` and set `FALKORDB_PORT=6380` in `.env`.
* **LLM Tool Call Errors**:
  - Ensure your API key is populated in `.env`.
  - LiteLLM uses standard model prefixes: `gpt-4o` for OpenAI, `anthropic/claude-3-5-sonnet-20240620` for Anthropic, `gemini/gemini-1.5-pro` for Google.
