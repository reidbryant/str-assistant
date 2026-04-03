# STR Assistant

AI agent for Short-Term Rental (STR) investment analysis. Given a ZIP code and price range, the
orchestrator coordinates three subagents to find properties, research rental revenue, and calculate
cap rates.

## Architecture

```
User → Orchestrator (str-assistant)
              ├── ① search-agent     → search_zillow (MCP tool)
              ├── ② synthesis-agent  → calc_return   (MCP tool)
              └── ③ return-results   → cap_rate      (MCP tool)
```

## Quick Start

**Prerequisites**: [str-mcp-server](https://github.com/reidbryant/str-mcp-server) must be running first.

```bash
# Terminal 1 — start the MCP server
cd str-mcp-server
cp .env.example .env   # add your TAVILY_API_KEY
make local

# Terminal 2 — start the agent
git clone https://github.com/reidbryant/str-assistant
cd str-assistant
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
cp .env.example .env   # add your OPENAI_API_KEY
uv run str-assistant
```

Health check: `curl http://localhost:8081/health`

## API

```bash
curl -X POST http://localhost:8081/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze STR opportunities in ZIP 78701 between $300,000 and $600,000",
    "thread_id": "thread-1",
    "user_id": "user-1",
    "stream_tokens": true
  }'
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Get at [platform.openai.com](https://platform.openai.com/api-keys) |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` |
| `MCP_SERVER_URL` | No | Default: `http://localhost:5001/mcp/` |
| `USE_INMEMORY_SAVER` | No | Default: `true` (no database needed) |
| `AGENT_PORT` | No | Default: `8081` |

## Part of STR Assistant System

- **str-mcp-server** — MCP tools (search_zillow, calc_return, cap_rate)
- **str-assistant** — This agent (orchestrator + 3 subagents) ← you are here
- **str-ui** — Web UI with intake form
