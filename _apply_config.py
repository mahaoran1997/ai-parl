#!/usr/bin/env python3
"""Apply provider config and write auth-profiles.json for all agents."""

import argparse
import json
import os
import subprocess
import sys


def oc_config_set(profile, path, value, strict_json=False):
    cmd = ["openclaw", "--profile", profile, "config", "set", path, value]
    if strict_json:
        cmd.append("--strict-json")
    subprocess.run(cmd, check=True, capture_output=True)


def write_auth_profiles(agent_dir, profiles_dict):
    """Write auth-profiles.json for an agent."""
    os.makedirs(agent_dir, exist_ok=True)
    path = os.path.join(agent_dir, "auth-profiles.json")
    with open(path, "w") as f:
        json.dump({"version": 1, "profiles": profiles_dict}, f, indent=2)


def load_json_safe(path):
    try:
        with open(os.path.expanduser(path)) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--creds-json", required=True)
    parser.add_argument("--state-dir", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--default-auth", required=True)
    args = parser.parse_args()

    creds = json.loads(args.creds_json)
    active = creds["active"]
    volcengine_endpoint = creds.get("volcengine_endpoint", "")

    default_auth_data = load_json_safe(args.default_auth)

    # Configure auth profiles and custom providers
    auth_order = {}

    for p in active:
        pid = p["pid"]
        mode = p["auth_mode"]

        # Built-in provider: set auth profile in config
        if p["builtin"]:
            oc_config_set(args.profile,
                          f"auth.profiles.{pid}:default",
                          json.dumps({"provider": pid, "mode": mode}),
                          strict_json=True)
            auth_order[pid] = [f"{pid}:default"]

        # Custom provider: set models.providers
        if not p["builtin"]:
            oc_config_set(args.profile, "models.mode", "merge")

            if p["volcengine"]:
                provider_json = {
                    "baseUrl": "https://ark.cn-beijing.volces.com/api/v3",
                    "api": "openai-completions",
                    "apiKey": p["key"],
                    "models": [{
                        "id": volcengine_endpoint,
                        "name": f"Doubao ({volcengine_endpoint})",
                        "contextWindow": 131072,
                        "maxTokens": 8192,
                        "input": ["text"],
                        "reasoning": False,
                    }]
                }
            else:
                provider_json = p["custom_json"]

            if provider_json:
                oc_config_set(args.profile,
                              f"models.providers.{pid}",
                              json.dumps(provider_json),
                              strict_json=True)

        print(f"  ✅ {p['label']} [{mode}]", file=sys.stderr)

    # Set auth.order
    if auth_order:
        oc_config_set(args.profile, "auth.order",
                      json.dumps(auth_order), strict_json=True)

    # Write auth-profiles.json for each agent (main + members)
    agent_ids = ["main"] + [f"member-{p['pid']}" for p in active]

    for agent_id in agent_ids:
        agent_dir = os.path.join(args.state_dir, "agents", agent_id, "agent")
        profiles = {}

        for p in active:
            pid = p["pid"]
            mode = p["auth_mode"]

            if mode == "api_key" and p["key"]:
                profiles[f"{pid}:default"] = {
                    "type": "api_key",
                    "provider": pid,
                    "key": p["key"],
                }
            elif mode == "oauth":
                # Try to copy from source
                oauth_profile = None
                if p["source"] == "default_profile" and default_auth_data:
                    oauth_profile = (default_auth_data.get("profiles", {})
                                     .get(f"{pid}:default"))
                elif p["source"] in ("existing", "oauth_flow"):
                    existing = load_json_safe(
                        os.path.join(agent_dir, "auth-profiles.json"))
                    if existing:
                        oauth_profile = (existing.get("profiles", {})
                                         .get(f"{pid}:default"))
                    # Also check main agent if this is a member
                    if not oauth_profile:
                        main_auth = load_json_safe(
                            os.path.join(args.state_dir,
                                         "agents/main/agent/auth-profiles.json"))
                        if main_auth:
                            oauth_profile = (main_auth.get("profiles", {})
                                             .get(f"{pid}:default"))
                    # Fall back to default profile
                    if not oauth_profile and default_auth_data:
                        oauth_profile = (default_auth_data.get("profiles", {})
                                         .get(f"{pid}:default"))

                if oauth_profile:
                    profiles[f"{pid}:default"] = oauth_profile

        if profiles:
            write_auth_profiles(agent_dir, profiles)

    print(f"  ✅ Auth profiles written for {len(agent_ids)} agents", file=sys.stderr)


if __name__ == "__main__":
    main()
