"""Fail-closed UniFi call policy; no controller access."""

import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parent


def load_policy():
    policy = json.loads((DIRECTORY / "policy.json").read_text())
    if (policy["schema"] != 1 or policy["approval"] != "explicit_user_approval"
            or policy["controller"] != "default" or policy["site_id"] != "default"):
        raise ValueError("Unsupported UniFi policy")
    for key in ("read_tools", "write_tools"):
        if not isinstance(policy[key], list) or not all(isinstance(x, str) for x in policy[key]):
            raise ValueError("Invalid UniFi tool allowlist")
    if set(policy["read_tools"]) & set(policy["write_tools"]):
        raise ValueError("Ambiguous UniFi tool policy")
    return policy


def guard(name, arguments, policy):
    args = dict(arguments or {})
    if name not in policy["read_tools"] + policy["write_tools"]:
        raise ValueError("Tool is outside repository UniFi policy")
    if args.get("controller") not in (None, policy["controller"]):
        raise ValueError("Controller is outside repository UniFi policy")
    if "site_id" in args and args["site_id"] != policy["site_id"]:
        raise ValueError("Site is outside repository UniFi policy")
    if name in policy["write_tools"]:
        args.setdefault("dry_run", True)
        args.setdefault("confirm", False)
        if type(args["dry_run"]) is not bool or type(args["confirm"]) is not bool:
            raise ValueError("Use JSON booleans for dry_run and confirm")
        if not args["dry_run"] and not args["confirm"]:
            raise ValueError("Explicit user approval is required before confirm=true")
        args["controller"] = policy["controller"]
        if args.get("site_id") != policy["site_id"]:
            raise ValueError("Writes require explicit site_id=default")
    return args
