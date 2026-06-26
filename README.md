# Autonomous BI Agent

Most companies have more data than they can actually use. The bottleneck is never the data — it's getting a human to look at it, ask the right questions, and write something up. A data team gets a request, queues it, runs a notebook, and sends back a chart three days later. By then the decision was already made on gut feel.

This project is an agent that handles the investigation part. You give it a dataset. It figures out what's interesting on its own, writes and runs its own analysis code, checks its own work, and returns a structured report — without being told what to look for.

It's not a chat interface over a database. You don't ask it questions. It asks its own.

---

## How it works

The agent builds a graph of hypotheses about the data. Each one gets tested with generated Python code, executed in an isolated sandbox, and either confirmed or ruled out. The graph branches based on results — if revenue looks fine but customer acquisition cost has been quietly climbing, it goes deeper on acquisition cost rather than continuing to poke at revenue.

```
Dataset → Data Profiler → Hypothesis Graph → Code Generator → Sandbox Executor → Insight Report
                                ↑                                      |
                                └──────── retry / replan ──────────────┘
```

The LLM handles reasoning and code generation. Everything else — the execution loop, retry logic, hypothesis state, memory, eval scoring — is built in Python. The LLM is one component. The system is the project.

---

## Architecture

### core/executor.py
Async Python code executor built on `asyncio.create_subprocess_exec`. Takes a code string, runs it in an isolated subprocess, enforces a timeout, kills the process cleanly on timeout, and returns a consistent structure every time:

```python
{"status": "success" | "error", "stdout": "...", "stderr": "..."}
```

### core/classifier.py
Reads the stderr from a failed execution and classifies the error: `syntax_error`, `import_error`, `name_error`, `timeout_error`, `runtime_error`, `unknown_error`. Pulls just the relevant line rather than dumping the full traceback.

### core/retry.py
Connects the executor and classifier. Runs code, classifies failures, decides what to do. Syntax errors bail immediately — no point retrying bad syntax. Everything else retries up to `max_retries`. Returns attempt count alongside the result.

### agent/graph.py
LangGraph state graph. Manages the hypothesis lifecycle — open, testing, confirmed, rejected. The graph branches based on what gets confirmed or ruled out, so investigation isn't linear.

### memory/
Persistent storage across sessions. The agent remembers what it found last time it saw this dataset, which hypotheses failed, which patterns tend to appear in which data types. Built on Redis and Qdrant.

### eval/harness.py
Scores agent output across four dimensions: relevance, correctness, coverage, and clarity. Produces a numeric score per run so you can actually measure whether changes improve or degrade output quality.

### api/main.py
FastAPI wrapper. Accepts file uploads, returns reports, supports webhooks for pushing findings to Slack or email.

---

## Tech stack

| Component | Technology |
|---|---|
| Agent orchestration | LangGraph |
| LLM | Claude via Anthropic API |
| Code execution | asyncio subprocess |
| Memory | Redis + Qdrant |
| API | FastAPI |
| Eval tracking | MLflow |
| Deployment | Railway |

---

## Project structure

```
bi_agent/
├── core/
│   ├── executor.py
│   ├── classifier.py
│   └── retry.py
├── agent/
│   ├── graph.py
│   ├── nodes.py
│   └── state.py
├── memory/
│   ├── store.py
│   └── retriever.py
├── eval/
│   └── harness.py
├── api/
│   └── main.py
├── tests/
│   ├── test_executor.py
│   ├── test_classifier.py
│   └── test_retry.py
└── main.py
```