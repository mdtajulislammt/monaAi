# JARVIS — Local Autonomous AI Desktop Assistant & System Controller

**JARVIS** is a production-grade, local autonomous AI Desktop Assistant and System Controller engineered with Clean Architecture, strict typing, and system safety guardrails. Powered by Google Gemini (`google-genai` SDK), persistent vector memory (`chromadb`), and an automated self-learning execution reflection loop, JARVIS accepts text and natural Bengali voice commands, supervises OS processes, conducts web research, and executes workstation automation.

JARVIS also exposes its entire tool suite via **FastMCP (Model Context Protocol)** so **Google Antigravity IDE** and **VS Code** can directly invoke its tools over `stdio`.

---

## 🏗️ Architecture & Core Components

```text
jarvis-core/
├── .env.example              # Configuration template
├── requirements.txt          # Production dependencies
├── config/
│   ├── __init__.py
│   ├── settings.py           # Pydantic Settings model with multi-tier env resolution
│   └── safety_rules.json     # Regex patterns and path protection rules
├── memory/
│   ├── __init__.py
│   ├── vector_store.py       # ChromaDB PersistentClient wrapper (episodic & semantic recall)
│   └── reflection_engine.py  # Error logging, dynamic fix storage, & self-learning reflection loop
├── tools/
│   ├── __init__.py
│   ├── system_tools.py       # Safe terminal executor, system telemetry, process monitor, IDE launcher
│   ├── file_tools.py         # Recursive directory tree, file read/write with atomic validation
│   └── browser_tools.py      # Headless Playwright script runner for external research
├── interfaces/
│   ├── __init__.py
│   └── voice_engine.py       # Async edge-tts stream player (bn-BD-PradeepNeural) & Bengali STT
├── core/
│   ├── __init__.py
│   └── agent.py              # Gemini client, tool registry, memory injector, & Bengali persona logic
├── mcp_server.py             # FastMCP server exposing tools to Antigravity IDE over stdio
├── main.py                   # Unified CLI & Voice entrypoint with graceful shutdown signals
└── tests/
    └── test_jarvis_core.py   # Comprehensive automated test suite (15/15 passing)
```

---

## ⚡ Quick Start

### 1. Environment & Setup
From the repository root:
```bash
cd jarvis-core

# Activate Python 3.11+ virtual environment
source ../venv/bin/activate

# Install dependencies (if not already installed)
pip install -r requirements.txt
```

### 2. Configure API Key
Create or update `.env` with your Gemini API key:
```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

---

## 🚀 Running JARVIS

### 1. One-Shot Command Execution
Ask JARVIS to execute a command, inspect files, or report telemetry:
```bash
python main.py --prompt "আমার পিসির CPU এবং RAM কত?"
```

### 2. Interactive CLI REPL Mode
Run an interactive session with Rich styling:
```bash
python main.py --text
```
Special commands in REPL:
- `telemetry` or `status`: View live CPU/RAM/Disk metrics table.
- `voice on` / `voice off`: Toggle Bengali speech synthesis.
- `reset` or `clear`: Reset active conversation session.
- `exit` or `quit`: Graceful shutdown.

### 3. Hands-Free Bengali Voice Loop
Start continuous natural Bengali voice interaction:
```bash
python main.py --voice
```
- **STT**: Transcribes Bengali (`bn-BD`) using Google Speech Recognition.
- **TTS**: Synthesizes male neural Bengali speech with Microsoft `edge-tts` (`bn-BD-PradeepNeural`).
- **Playback**: Non-blocking playback with immediate interruption when you speak.

### 4. FastMCP Server for Google Antigravity IDE & VS Code
Run as an MCP tool server over standard I/O:
```bash
python main.py --mcp
```

#### Google Antigravity IDE Integration
Add to your Antigravity IDE MCP configuration (e.g. `~/.gemini/antigravity-ide/mcp_config.json`):
```json
{
  "mcpServers": {
    "jarvis-core": {
      "command": "/home/mdtajulislam/Projects/monaAi/venv/bin/python",
      "args": [
        "/home/mdtajulislam/Projects/monaAi/jarvis-core/mcp_server.py"
      ],
      "env": {
        "PYTHONPATH": "/home/mdtajulislam/Projects/monaAi/jarvis-core"
      }
    }
  }
}
```

---

## 🧠 Self-Learning Execution Reflection Loop

When an action or terminal command fails:
1. `ExecutionReflectionEngine` intercepts the error and categorizes the root cause (e.g., `CommandNotFound`, `PermissionDenied`, `Timeout`, `FileNotFound`, `MissingDependency`).
2. Synthesizes a structured reflection:
   - **Action**: Command or tool invoked
   - **Diagnosis**: Why the execution failed
   - **Recommended Fix**: Concrete action to rectify the failure
3. Indexes the reflection vector into ChromaDB under `jarvis_reflections`.
4. Prior to subsequent actions, JARVIS performs semantic recall against past reflections, injecting learned lessons into the LLM system prompt to prevent repeating mistakes.

---

## 🧪 Testing

Run the automated test suite:
```bash
pytest tests/test_jarvis_core.py -v
```
All 15 unit and integration tests verify configuration, safety guardrails, ChromaDB memory CRUD, reflection loops, file atomic writes, telemetry, voice engine, agent tool registry, and FastMCP bindings.
