# NIM Pi Research Agent

An autonomous web-searching and page-crawling research subagent that can be called from Claude Desktop, Antigravity, Cursor, Windsurf, or any MCP-compatible host via the **Model Context Protocol (MCP)**. Instead of the host agent spinning up its own browser processes, it delegates research to a dedicated [`@earendil-works/pi-coding-agent`](https://github.com/earendil-works/pi) subprocess powered by **NVIDIA NIM** inference APIs.

> **Why use this?** Subagents in harnesses such as Claude Code, Cursor, or Codex for simple research tasks consume a massive amount of tokens as they run. What if Pi agents with free NVIDIA NIM APIs can go ahead and handle that, come back, and give the feedback / research data and info that those subagents would normally give? That is exactly what this MCP server accomplishes.

---

## Architecture

```
Host Agent (Claude / Antigravity / Cursor)
  │
  ├─ MCP call: run_research(query, instructions, timeout_minutes)
  │
  ▼
FastMCP Server (research_agent/mcp_server.py)
  │
  ▼
ResearchAgent (research_agent/agent.py)
  │
  ├─ Creates ephemeral workspace with search_tool.py
  ├─ Configures NVIDIA NIM provider (models.json)
  ├─ Spawns pi coding agent subprocess
  │    │
  │    ├─ bash tool → search_tool.py --search "query"
  │    │              (Serper API → DuckDuckGo fallback)
  │    ├─ bash tool → search_tool.py --scrape "url"
  │    │              (BeautifulSoup → cleaned markdown text)
  │    └─ write tool → report.md
  │
  └─ Returns report.md contents to host agent
```

---

## Features

- **Autonomous research loop** — The pi agent plans searches, scrapes pages, and synthesizes findings autonomously
- **Dual search backends** — Serper API (Google results, 250 free/month) with zero-config DuckDuckGo fallback
- **Smart scraping** — Strips scripts/nav/footer, extracts headings/paragraphs/lists, truncates to 4000 words
- **Timeout protection** — Configurable timeout (default 5 min) prevents hung NVIDIA API calls from blocking indefinitely
- **MCP integration** — Exposes `run_research` tool via FastMCP for seamless integration with any MCP host
- **NVIDIA NIM powered** — Uses `meta/llama-3.3-70b-instruct` (default) or `deepseek-ai/deepseek-v4-pro` for reasoning

---

## Installation

```bash
# 1. Clone/navigate to the project
cd "/path/to/Free subagents skill"

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
pip install -e .

# 4. Install the pi coding agent (Node.js required)
npm install @earendil-works/pi-coding-agent
```

### Environment Variables

Create a `.env` file in the project root:

```env
NVIDIA_NIM_API_KEY=nvapi-your-key-here
NVIDIA_NIM_API_BASE=https://integrate.api.nvidia.com/v1
NVIDIA_MODEL=meta/llama-3.3-70b-instruct
NVIDIA_VISION_MODEL=meta/llama-3.2-90b-vision-instruct
SERPER_API_KEY=your-serper-key-optional
```

| Variable | Required | Description |
|----------|----------|-------------|
| `NVIDIA_NIM_API_KEY` | ✅ | NVIDIA NIM API key for LLM inference |
| `NVIDIA_NIM_API_BASE` | ✅ | NIM API base URL |
| `NVIDIA_MODEL` | ❌ | Text model (default: `meta/llama-3.3-70b-instruct`) |
| `NVIDIA_VISION_MODEL` | ❌ | Vision model (default: `meta/llama-3.2-90b-vision-instruct`) |
| `SERPER_API_KEY` | ❌ | Serper.dev API key for Google search (250 free/month) |

---

## Usage

### 1. MCP Server (recommended)

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "nim-research-agent": {
      "command": "/path/to/Free subagents skill/.venv/bin/research-agent-mcp",
      "env": {
        "NVIDIA_NIM_API_KEY": "nvapi-...",
        "NVIDIA_NIM_API_BASE": "https://integrate.api.nvidia.com/v1",
        "NVIDIA_MODEL": "meta/llama-3.3-70b-instruct",
        "SERPER_API_KEY": "your-key-here"
      }
    }
  }
}
```

The host agent can then call:
```
run_research(
  query="What are the latest advances in quantum computing?",
  instructions="Focus on error correction breakthroughs in 2025",
  timeout_minutes=5
)
```

### 2. Command-Line Interface

```bash
# Basic research
research-agent --query "Recent advances in nuclear fusion" --output report.md

# With additional instructions
research-agent -q "NVIDIA NIM 2025" -i "Focus on benchmarks" -o nim_report.md
```

**CLI Arguments:**
- `--query` / `-q` (required): Research topic or question
- `--instructions` / `-i` (optional): Focus areas or formatting constraints
- `--output` / `-o` (optional): Output file path (default: `research_report.md`)

### 3. Python API

```python
from research_agent.agent import ResearchAgent

agent = ResearchAgent(timeout_seconds=300)
report = agent.run(
    query="What is the state of AI regulation in the EU?",
    instructions="Include specific legislation and timelines"
)
print(report)
```

---

## How It Works

1. **Workspace setup** — Creates an ephemeral directory with `search_tool.py` and configures `models.json` for NVIDIA NIM
2. **Pi agent launch** — Spawns `@earendil-works/pi-coding-agent` in non-interactive mode with the research prompt
3. **Autonomous research** — The pi agent uses its `bash` and `write` tools to:
   - Run 3+ web searches with varied terms
   - Scrape 3-5 relevant pages
   - Synthesize findings into a structured report
4. **Report retrieval** — Reads `report.md` from the workspace and returns it to the caller
5. **Cleanup** — Removes the ephemeral workspace directory

---

## NVIDIA NIM Compatibility

The agent configures the following `compat` overrides for NVIDIA NIM's OpenAI-compatible API:

```json
{
  "supportsStrictMode": false,
  "supportsDeveloperRole": false,
  "supportsReasoningEffort": false
}
```

These are required because NVIDIA NIM doesn't support OpenAI's strict tool-calling schema features.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Pi coding agent not found` | Run `npm install @earendil-works/pi-coding-agent` |
| `403 Forbidden` from Serper | API key may be expired; DuckDuckGo will be used as fallback |
| Agent hangs indefinitely | Increase `timeout_minutes` or check NVIDIA API status |
| Short/low-quality reports | Try `deepseek-ai/deepseek-v4-pro` as `NVIDIA_MODEL` for better reasoning |
| `duckduckgo_search` deprecation warning | Run `pip install ddgs` (already handled in requirements) |
