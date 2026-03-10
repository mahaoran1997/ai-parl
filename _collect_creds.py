#!/usr/bin/env python3
"""Collect and resolve credentials for AI Parliament setup."""

import argparse
import json
import os
import sys

# Provider registry
# (pid, env_var, label, agent_name, emoji, model, builtin, auth_mode, custom_json)
PROVIDERS = [
    ("anthropic", "ANTHROPIC_API_KEY", "Anthropic (Claude)", "Member Claude", "🟣",
     "anthropic/claude-sonnet-4-5", True, "api_key", None),
    ("openai", "OPENAI_API_KEY", "OpenAI (GPT)", "Member GPT", "🟢",
     "openai/gpt-5.4", True, "api_key", None),
    ("openai-codex", None, "OpenAI Codex (ChatGPT OAuth)", "Member Codex", "🟢",
     "openai-codex/gpt-5.4", True, "oauth", None),
    ("deepseek", "DEEPSEEK_API_KEY", "DeepSeek", "Member DeepSeek", "🟡",
     "deepseek/deepseek-chat", False, "api_key",
     {"baseUrl": "https://api.deepseek.com/v1", "api": "openai-completions",
      "models": [{"id": "deepseek-chat", "name": "DeepSeek Chat",
                  "contextWindow": 65536, "maxTokens": 8192, "input": ["text"], "reasoning": False}]}),
    ("xai", "XAI_API_KEY", "xAI (Grok)", "Member Grok", "🔴",
     "xai/grok-3", True, "api_key", None),
    ("moonshot", "MOONSHOT_API_KEY", "Moonshot (Kimi)", "Member Kimi", "🌙",
     "moonshot/kimi-k2.5", False, "api_key",
     {"baseUrl": "https://api.moonshot.ai/v1", "api": "openai-completions",
      "models": [{"id": "kimi-k2.5", "name": "Kimi K2.5",
                  "contextWindow": 131072, "maxTokens": 8192, "input": ["text"], "reasoning": False}]}),
    ("qwen", "QWEN_API_KEY", "Qwen (Alibaba)", "Member Qwen", "🟠",
     "qwen/qwen3-coder", False, "api_key",
     {"baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api": "openai-completions",
      "models": [{"id": "qwen3-coder", "name": "Qwen3 Coder",
                  "contextWindow": 131072, "maxTokens": 8192, "input": ["text"], "reasoning": True}]}),
    ("zai", "ZAI_API_KEY", "Z.AI (GLM)", "Member GLM", "⚪",
     "zai/glm-5", True, "api_key", None),
    ("volcengine", "ARK_API_KEY", "Ark (Volcengine/Doubao)", "Member Doubao", "🔥",
     "volcengine/{endpoint}", False, "api_key", "__VOLCENGINE__"),
]

# Speaker priority (most capable first)
SPEAKER_PRIORITY = ["anthropic", "openai", "openai-codex", "xai", "zai",
                    "moonshot", "qwen", "volcengine", "deepseek"]


def load_json_safe(path):
    try:
        with open(os.path.expanduser(path)) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def get_existing_key(auth_data, pid):
    """Extract API key from auth-profiles.json."""
    if not auth_data:
        return None
    profiles = auth_data.get("profiles", {})
    p = profiles.get(f"{pid}:default", {})
    return p.get("key") or None


def has_oauth_token(auth_data, pid):
    """Check if OAuth token exists in auth-profiles.json."""
    if not auth_data:
        return False
    profiles = auth_data.get("profiles", {})
    p = profiles.get(f"{pid}:default", {})
    return p.get("type") == "oauth" and bool(p.get("access"))


def get_volcengine_endpoint(state_dir, profile):
    """Try to recover endpoint ID from existing config."""
    ep = os.environ.get("ARK_ENDPOINT_ID", "")
    if ep:
        return ep
    config_path = os.path.expanduser(f"~/.openclaw-{profile}/openclaw.json")
    config = load_json_safe(config_path)
    if config:
        models = (config.get("models", {}).get("providers", {})
                  .get("volcengine", {}).get("models", []))
        if models:
            return models[0].get("id", "")
    return ""


def prompt(msg):
    """Print prompt to stderr and read from stdin (stdout is captured by shell)."""
    sys.stderr.write(msg)
    sys.stderr.flush()
    return sys.stdin.readline().strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--default-auth", required=True)
    parser.add_argument("--profile", required=True)
    args = parser.parse_args()

    # Load existing auth files
    parliament_auth = load_json_safe(
        os.path.join(args.state_dir, "agents/main/agent/auth-profiles.json"))
    default_auth = load_json_safe(args.default_auth)

    # Credential store: pid -> {"key": str|None, "mode": "api_key"|"oauth", "source": str}
    creds = {}

    # Phase 1: Check environment variables
    for pid, env_var, label, *_ in PROVIDERS:
        if env_var and env_var in os.environ and os.environ[env_var]:
            creds[pid] = {"key": os.environ[env_var], "mode": "api_key", "source": "env"}

    # Phase 2: Check existing parliament profile auth
    for pid, _, label, _, _, _, _, auth_mode, _ in PROVIDERS:
        if pid in creds:
            continue
        if auth_mode == "api_key":
            key = get_existing_key(parliament_auth, pid)
            if key:
                creds[pid] = {"key": key, "mode": "api_key", "source": "existing"}
        if auth_mode == "oauth":
            if has_oauth_token(parliament_auth, pid):
                creds[pid] = {"key": None, "mode": "oauth", "source": "existing"}

    # Phase 3: Check default profile for OAuth tokens
    for pid, _, label, _, _, _, _, auth_mode, _ in PROVIDERS:
        if pid in creds:
            continue
        if auth_mode == "oauth" and has_oauth_token(default_auth, pid):
            creds[pid] = {"key": None, "mode": "oauth", "source": "default_profile"}

    # Report found credentials
    found = [(pid, label, creds[pid]) for pid, _, label, *_ in PROVIDERS if pid in creds]
    if found:
        print("Found existing credentials:", file=sys.stderr)
        for pid, label, c in found:
            print(f"  ✓ {label} [{c['mode']}]", file=sys.stderr)
        print("", file=sys.stderr)

    # Volcengine endpoint — try to recover early
    volcengine_endpoint = get_volcengine_endpoint(args.state_dir, args.profile)

    # Phase 4: Prompt for missing credentials
    missing = [(pid, env_var, label, auth_mode)
               for pid, env_var, label, _, _, _, _, auth_mode, _ in PROVIDERS
               if pid not in creds]

    if missing:
        print("Enter credentials for additional providers (press Enter to skip):",
              file=sys.stderr)
        print("", file=sys.stderr)
        for pid, env_var, label, auth_mode in missing:
            if auth_mode == "oauth":
                answer = prompt(f"  {label} — run OAuth flow? [y/N]: ")
                if answer.lower().startswith("y"):
                    creds[pid] = {"key": None, "mode": "oauth", "source": "oauth_flow"}
            else:
                key = prompt(f"  {label} API key: ")
                if key:
                    creds[pid] = {"key": key, "mode": "api_key", "source": "input"}
                    # Volcengine needs endpoint ID
                    if pid == "volcengine" and not volcengine_endpoint:
                        volcengine_endpoint = prompt("  Ark (Volcengine) Endpoint ID (e.g. ep-2024xxxx): ")
                        if not volcengine_endpoint:
                            print("  ⚠️  Endpoint ID required for Volcengine, skipping",
                                  file=sys.stderr)
                            del creds[pid]
        print("", file=sys.stderr)

    # Resolve Volcengine endpoint if key exists but endpoint still missing
    if "volcengine" in creds and not volcengine_endpoint:
        volcengine_endpoint = prompt("  Ark (Volcengine) Endpoint ID (e.g. ep-2024xxxx): ")
        if not volcengine_endpoint:
            print("  ⚠️  Endpoint ID required for Volcengine, skipping", file=sys.stderr)
            del creds["volcengine"]

    # Build active providers list
    active = []
    for pid, env_var, label, agent_name, emoji, model, builtin, auth_mode, custom_json in PROVIDERS:
        if pid not in creds:
            continue
        resolved_model = model.replace("{endpoint}", volcengine_endpoint) if volcengine_endpoint else model
        active.append({
            "pid": pid,
            "label": label,
            "agent_name": agent_name,
            "emoji": emoji,
            "model": resolved_model,
            "builtin": builtin,
            "auth_mode": creds[pid]["mode"],
            "key": creds[pid].get("key"),
            "source": creds[pid]["source"],
            "custom_json": custom_json if custom_json != "__VOLCENGINE__" else None,
            "volcengine": custom_json == "__VOLCENGINE__",
        })

    # Determine speaker model
    speaker_model = ""
    for pid in SPEAKER_PRIORITY:
        if pid in creds:
            for a in active:
                if a["pid"] == pid:
                    speaker_model = a["model"]
                    break
            if speaker_model:
                break

    result = {
        "member_count": len(active),
        "members": [a["pid"] for a in active],
        "speaker_model": speaker_model,
        "volcengine_endpoint": volcengine_endpoint,
        "active": active,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
