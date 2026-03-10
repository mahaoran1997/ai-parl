# AI Parliament

A parliamentary voting system for AI agents, built on [OpenClaw](https://docs.openclaw.ai).

Multiple AI agents — each using a different LLM — deliberate on every task: they independently propose solutions, vote on the best one, and the winner gets executed.

## How It Works

```
User sends a task
       |
Speaker (orchestrator) fans out to all members via sessions_spawn
       |
+--------+--------+--------+--------+--------+
Claude   GPT     Grok    Kimi   DeepSeek  ...    <-- each proposes a solution
+--------+--------+--------+--------+--------+
       |
All proposals anonymized (A, B, C, D...) and shared with all members
       |
+--------+--------+--------+--------+--------+
Claude   GPT     Grok    Kimi   DeepSeek  ...    <-- each votes for the best
+--------+--------+--------+--------+--------+
       |
Speaker tallies votes --> winning proposal is executed or presented
```

## Supported Providers

| Provider | Model | Auth | Env Var |
|----------|-------|------|---------|
| Anthropic | Claude Sonnet 4.5 | API key | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-5.4 | API key | `OPENAI_API_KEY` |
| OpenAI Codex | GPT-5.4 (ChatGPT) | OAuth | _(auto-detected)_ |
| DeepSeek | DeepSeek Chat | API key | `DEEPSEEK_API_KEY` |
| xAI | Grok 3 | API key | `XAI_API_KEY` |
| Moonshot | Kimi K2.5 | API key | `MOONSHOT_API_KEY` |
| Qwen | Qwen3 Coder | API key | `QWEN_API_KEY` |
| Z.AI | GLM-5 | API key | `ZAI_API_KEY` |
| Volcengine/Ark | Doubao (endpoint) | API key + Endpoint ID | `ARK_API_KEY` + `ARK_ENDPOINT_ID` |

Minimum 2 providers required. Add more for richer debate.

## Prerequisites

- [OpenClaw](https://docs.openclaw.ai) (`npm install -g openclaw`)
- Python 3
- API keys for at least 2 providers

## Setup

```bash
./setup.sh
```

The setup script will:
1. Auto-detect existing credentials (env vars, previous setup, default profile OAuth)
2. Prompt only for missing providers
3. Create an isolated OpenClaw profile (`parliament`) at `~/.openclaw-parliament/`
4. Configure a Speaker agent + one member agent per provider
5. Copy workspace files into each agent's private directory

Re-running `setup.sh` is safe — it syncs workspace files, skips existing agents, and updates identities.

### Environment Variables

Pre-set API keys to skip interactive prompts:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
export DEEPSEEK_API_KEY="sk-..."
./setup.sh
```

For Volcengine/Ark, also set the endpoint ID:

```bash
export ARK_API_KEY="..."
export ARK_ENDPOINT_ID="ep-2024xxxx"
```

## Usage

Start the gateway:
```bash
openclaw --profile parliament gateway start
```

Send a task:
```bash
openclaw --profile parliament agent --message "Write a function to find the longest palindromic substring"
```

List agents:
```bash
openclaw --profile parliament agents list
```

Validate config:
```bash
openclaw --profile parliament config validate
```

## Design

- **Speaker orchestrates, never proposes** — ensures neutrality
- **Proposals are anonymized** (labeled A/B/C) during voting to prevent brand bias
- **Tie-breaking** — Speaker casts the deciding vote
- **Parallel execution** — both proposal and voting phases run all agents simultaneously via `sessions_spawn`
- **Execution** — code/commands are executed after voting; text answers are presented directly
- **Isolated workspaces** — each agent gets its own copy of workspace files under `~/.openclaw-parliament/workspaces/<agent-id>/`

## Project Structure

```
ai-parl/
├── setup.sh                  # Setup script (bash 3.2+ compatible)
├── _collect_creds.py         # Credential detection & prompting
├── _apply_config.py          # Provider config & auth-profiles writer
├── workspace/                # Workspace template (source of truth)
│   ├── SOUL.md               # Parliamentary behavior rules & response formats
│   ├── AGENTS.md             # Role definitions & coordination flow
│   └── USER.md               # User context
└── skills/
    └── parliament/
        └── SKILL.md           # Speaker's orchestration instructions
```

### Runtime State

```
~/.openclaw-parliament/
├── openclaw.json              # OpenClaw config (agents, models, auth)
├── workspaces/                # Per-agent workspace copies
│   ├── main/                  # Speaker
│   │   ├── SOUL.md, AGENTS.md, USER.md
│   │   ├── skills/parliament/SKILL.md
│   │   └── memory/
│   ├── member-anthropic/      # One per active provider
│   ├── member-openai/
│   └── ...
└── agents/                    # Per-agent state (sessions, auth)
    ├── main/agent/auth-profiles.json
    ├── member-anthropic/agent/auth-profiles.json
    └── ...
```

## Adding a New Provider

Edit `_collect_creds.py` and add a tuple to the `PROVIDERS` list:

```python
("provider-id", "ENV_VAR_NAME", "Display Label", "Member Name", "emoji",
 "provider-id/model-name", is_builtin, "api_key", custom_json_or_None),
```

- **Built-in** (`True`): Provider is in OpenClaw's catalog — only needs an auth profile
- **Custom** (`False`): Needs a `models.providers` entry — supply the JSON config as the last field
