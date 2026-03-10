#!/bin/bash
set -euo pipefail

# AI Parliament — Setup Script
# Sets up an OpenClaw profile with Speaker + Member agents
# Compatible with bash 3.2+ (macOS default)

PROFILE="parliament"
OC="openclaw --profile $PROFILE"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE="$SCRIPT_DIR/workspace"
STATE_DIR="$HOME/.openclaw-$PROFILE"

echo "🏛️  AI Parliament — Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1: Check OpenClaw ─────────────────────────────────────────────
if ! command -v openclaw &>/dev/null; then
  echo "❌ OpenClaw not found. Install it first:"
  echo "   npm install -g openclaw"
  exit 1
fi

echo "✅ OpenClaw $(openclaw --version 2>&1 | head -1)"
echo ""

# ── Step 2: Collect credentials via Python helper ─────────────────────
# Python handles all credential detection, prompting, and state tracking
# since macOS bash 3.2 lacks associative arrays.

CREDS_JSON="$(python3 "$SCRIPT_DIR/_collect_creds.py" \
  --state-dir "$STATE_DIR" \
  --default-auth "$HOME/.openclaw/agents/main/agent/auth-profiles.json" \
  --profile "$PROFILE"
)"

if [ $? -ne 0 ] || [ -z "$CREDS_JSON" ]; then
  echo "❌ Credential collection failed."
  exit 1
fi

# Extract values from JSON
MEMBER_COUNT="$(echo "$CREDS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['member_count'])")"
MEMBERS_STR="$(echo "$CREDS_JSON" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin)['members']))")"
SPEAKER_MODEL="$(echo "$CREDS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['speaker_model'])")"
VOLCENGINE_ENDPOINT="$(echo "$CREDS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin).get('volcengine_endpoint',''))")"

if [ "$MEMBER_COUNT" -lt 2 ]; then
  echo "❌ Need at least 2 providers for a parliament. Got $MEMBER_COUNT."
  exit 1
fi

echo "✅ $MEMBER_COUNT members will serve in parliament: $MEMBERS_STR"
echo ""

# ── Step 3: Initialize Profile ────────────────────────────────────────
echo "Setting up OpenClaw profile: $PROFILE"

# Default workspace points to main agent's copy (overridden per-agent below)
MAIN_WS="$STATE_DIR/workspaces/main"
$OC config set agents.defaults.workspace "$MAIN_WS"
$OC config set agents.defaults.maxConcurrent 4 --strict-json
$OC config set agents.defaults.subagents.maxConcurrent 4 --strict-json
# Speaker needs enough time for the full propose+vote cycle (default 600s is fine)
$OC config set agents.defaults.timeoutSeconds 600 --strict-json
# Each member spawn gets 2 minutes before being considered failed
$OC config set agents.defaults.subagents.runTimeoutSeconds 120 --strict-json
$OC config set gateway.port 18800 --strict-json
$OC config set gateway.mode local
$OC config set gateway.bind loopback
$OC config set tools.profile full

# ── Helper: Copy workspace template into an agent's own workspace ─────
# Each agent gets its own workspace copy so `agents delete` can't wipe shared files.
# Source of truth is the repo's workspace/ dir; setup always syncs from it.
sync_workspace() {
  local agent_id="$1"
  local dest="$STATE_DIR/workspaces/$agent_id"
  mkdir -p "$dest/memory"
  # Copy all .md files and skills from repo template
  for f in "$WORKSPACE"/*.md; do
    [ -f "$f" ] && cp "$f" "$dest/"
  done
  # Copy skills directory
  if [ -d "$SCRIPT_DIR/skills" ]; then
    cp -R "$SCRIPT_DIR/skills" "$dest/"
  fi
  echo "$dest"
}

echo "  ✅ Profile initialized at $STATE_DIR"

# ── Step 4: Configure Auth & Model Providers ──────────────────────────
echo "Configuring providers..."

python3 "$SCRIPT_DIR/_apply_config.py" \
  --creds-json "$CREDS_JSON" \
  --state-dir "$STATE_DIR" \
  --profile "$PROFILE" \
  --workspace "$WORKSPACE" \
  --default-auth "$HOME/.openclaw/agents/main/agent/auth-profiles.json"

echo "  ✅ Providers configured"

# ── Step 5: Set Speaker Model ─────────────────────────────────────────
$OC config set agents.defaults.model.primary "$SPEAKER_MODEL"
echo ""
echo "  Speaker will use: $SPEAKER_MODEL"

# ── Step 6: Set Speaker Identity ──────────────────────────────────────
echo "Configuring Speaker agent..."

SPEAKER_THEME="You are the Speaker of the AI Parliament. You coordinate debates by spawning tasks to member agents. ALWAYS read and follow skills/parliament/SKILL.md for every user request. Never propose solutions yourself — only orchestrate the propose-vote-execute cycle."

sync_workspace "main" >/dev/null

$OC agents set-identity --agent main \
  --name "Speaker" \
  --emoji "🏛️" \
  --theme "$SPEAKER_THEME"

echo "  ✅ Speaker identity set"

# ── Step 7: Add/update member agents ──────────────────────────────────
# Get existing agent IDs
EXISTING_AGENTS="$($OC agents list 2>&1 | grep -o '^- [a-z-]*' | sed 's/^- //' || true)"

echo "Adding parliament members..."

MEMBER_THEME="You are a parliament member. When asked for a PROPOSAL, provide your best solution in the exact format:

PROPOSAL:
[Your complete solution]

When asked to VOTE, respond with exactly:

VOTE: [letter]
REASON: [One sentence explaining why]

Be independent, thorough, and honest. You may vote for any proposal including your own."

ALLOW_LIST=()

# Read active providers from creds JSON
ACTIVE_PROVIDERS="$(echo "$CREDS_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d['active']:
    print(p['pid'] + '|' + p['label'] + '|' + p['agent_name'] + '|' + p['emoji'] + '|' + p['model'])
")"

while IFS='|' read -r pid label agent_name emoji model; do
  [ -z "$pid" ] && continue
  agent_id="member-$pid"

  # Sync workspace template into agent's own directory
  agent_ws="$(sync_workspace "$agent_id")"

  # Only add if agent doesn't exist yet (avoid duplicates)
  if ! echo "$EXISTING_AGENTS" | grep -qx "$agent_id"; then
    $OC agents add "$agent_id" \
      --model "$model" \
      --workspace "$agent_ws" \
      --non-interactive 2>/dev/null || true
  fi
  # Always update identity (handles re-runs)
  $OC agents set-identity --agent "$agent_id" \
    --name "$agent_name" \
    --emoji "$emoji" \
    --theme "$MEMBER_THEME"
  ALLOW_LIST+=("$agent_id")
  echo "  ✅ $agent_id ($label)"
done <<< "$ACTIVE_PROVIDERS"

# ── Step 8: Configure subagent permissions ────────────────────────────
ALLOW_JSON=$(printf '"%s",' "${ALLOW_LIST[@]}")
ALLOW_JSON="[${ALLOW_JSON%,}]"

$OC config set "agents.list.0.subagents.allowAgents" "$ALLOW_JSON" --strict-json

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🏛️  Parliament is ready!"
echo ""
echo "Members: $MEMBERS_STR"
echo "Speaker: $SPEAKER_MODEL"
echo "Profile: $PROFILE (state at $STATE_DIR)"
echo ""
echo "To start the gateway:"
echo "  openclaw --profile parliament gateway start"
echo ""
echo "To send a task:"
echo "  openclaw --profile parliament agent --message 'Your task here'"
echo ""
echo "To list agents:"
echo "  openclaw --profile parliament agents list"
echo ""
echo "To verify config:"
echo "  openclaw --profile parliament config validate"
