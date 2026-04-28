#!/usr/bin/env python3
"""Check run manifests against Operator Local path allowlist policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def allowed_path(path: str, allowlist: list[str]) -> bool:
    return any(path.startswith(prefix) for prefix in allowlist)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Operator Local allowlist policy compliance.")
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--policy", default="build_control/operator_local/10_POLICY_ALLOWLIST.json")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    policy = json.loads(Path(args.policy).read_text(encoding="utf-8"))
    allowlist = policy.get("path_allowlist", [])

    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    trace = manifest.get("trace", {})

    violations: list[str] = []
    for key in ["inputs", "outputs"]:
        for value in trace.get(key, []):
            if value.startswith("/"):
                if not allowed_path(value, allowlist):
                    violations.append(f"{key} path outside allowlist: {value}")

    if violations:
        print(f"FAIL: {run_dir}")
        for v in violations:
            print(f"- {v}")
        return 1

    print(f"PASS: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
