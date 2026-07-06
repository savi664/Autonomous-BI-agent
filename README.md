---
title: Insightflow Ai
emoji: 🚀
colorFrom: yellow
colorTo: gray
sdk: docker
pinned: false
---

# InsightFlow — Autonomous BI Agent

Upload a CSV. Get a full analysis report — automatically generated hypotheses, executable Python code, charts, and structured insights. No querying, no dashboard setup, no BI team required.

## Demo

![InsightFlow screenshot](https://raw.githubusercontent.com/savi664/Autonomous-BI-agent/5256882/screenshots/screenshot.png)

## Overview

Most companies have more data than they can use. The bottleneck isn't the data — it's getting a human to look at it, ask the right questions, and write something up.

InsightFlow automates the investigation. You give it a dataset. It profiles the data, generates hypotheses, writes and executes Python analysis code, and returns a structured report with visualizations — without being told what to look for.

Supports follow-up questions after the initial analysis. You can dig deeper into any finding via chat.

## Installation

```bash
git clone <repo-url>
cd BI_Intelligent_Agent
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```
GOOGLE_API_KEY=your_gemini_api_key
```

Optional (fallback LLM):

```
LLM7_IO_TOKEN=your_llm7_token
```

## Usage

```bash
python main.py
```

Open `http://localhost:8000` in your browser. Upload a CSV file and the agent will automatically:

1. Profile the dataset (column types, missing values, distributions)
2. Generate 7+ hypotheses about patterns in the data
3. Write and execute Python code to test each hypothesis
4. Return structured results with charts and discussion
5. Let you ask follow-up questions interactively

## Features

- **Autonomous hypothesis generation** — no manual querying required
- **Code generation & execution** — each hypothesis tested with real Python code in a sandboxed subprocess
- **Smart retry** — failed code is classified and retried with LLM feedback (max 2 retries)
- **Charts as images** — visualizations rendered as base64 PNG inline in results
- **Dataset validation** — detects non-business datasets and shows a warning
- **Follow-up chat** — ask questions about results after analysis completes
- **Parallel execution** — hypotheses generated and tested concurrently
- **LLM fault tolerance** — automatically retries LLM calls on failure, graceful degradation

## Tech Stack

| Component | Technology |
|---|---|
| LLM | Google Gemini 1.5 Flash Lite (primary), LLM7 (fallback) |
| Agent orchestration | LangGraph |
| API | FastAPI |
| Frontend | Vanilla HTML/CSS/JS |
| Code execution | `asyncio.create_subprocess_exec` (sandboxed) |
| Session memory | In-memory store with temp file cleanup |

## Project Structure

```
BI_Intelligent_Agent/
├── agent/
│   ├── graph.py          # LangGraph state graph
│   ├── nodes.py          # All agent node functions
│   └── state.py          # AgentState TypedDict
├── core/
│   ├── executor.py       # Subprocess code execution
│   ├── classifier.py     # Error classification
│   └── retry.py          # Retry logic with LLM feedback
├── api/
│   └── main.py           # FastAPI server
├── memory/
│   └── memory_store.py   # Session store
├── frontend/
│   ├── index.html        # App HTML
│   ├── style.css         # Styles
│   └── app.js            # Client logic
├── main.py               # Entry point
├── requirements.txt
└── .env
```

## License

MIT
