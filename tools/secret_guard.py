#!/usr/bin/env python3
"""Offline upload gate: JSON on stdin; no secret values in diagnostics."""
import json
import math
import re
import sys
from collections import Counter
from pathlib import PurePosixPath

RULES = {
    "private-key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "known-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9_-]{20,})\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    "credential-url": re.compile(r"https?://[^\s/@:]+:[^\s/@]+@"),
    "credential-query": re.compile(r"[?&](?:token|api_key|access_token|password)=[^&\s\"'<>]+", re.I),
    "literal-credential": re.compile(r"""(?im)^[ \t]*["']?(?:[A-Z0-9_]*(?:TOKEN|PASSWORD|PASSWD|SECRET|API_KEY|APIKEY)[A-Z0-9_]*)["']?[ \t]*[:=][ \t]*["']?([^\s"'#,}]+)"""),
}

def inspect(path, text):
    findings = []
    parts = PurePosixPath(path).parts
    leaf = parts[-1] if parts else ""
    if (path.startswith("/") or "\\" in path or ".." in parts
            or leaf.startswith(".env") and leaf != ".env.example"
            or leaf.endswith((".pem", ".key", ".p12", ".pfx"))
            or any(part in {"secrets", "private", ".ssh"} for part in parts)):
        findings.append((path, 0, "forbidden-path"))
    for name, pattern in RULES.items():
        for match in pattern.finditer(text):
            findings.append((path, text.count("\n", 0, match.start()) + 1, name))
    # Conservative extra check for long, random-looking values, including
    # credentials without a recognizable prefix. No automatic allowlist.
    for match in re.finditer(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{32,}(?![A-Za-z0-9+/=_-])", text):
        value = match.group()
        counts = Counter(value)
        entropy = -sum((n / len(value)) * math.log2(n / len(value)) for n in counts.values())
        if entropy >= 4.5 and any(c.isupper() for c in value) and any(c.islower() for c in value) and any(c.isdigit() for c in value):
            findings.append((path, text.count("\n", 0, match.start()) + 1, "high-entropy"))
    return findings

def check(payload):
    if not isinstance(payload, dict) or set(payload) - {"files", "message"}:
        raise ValueError("Invalid payload")
    files = payload.get("files")
    if not isinstance(files, dict) or not files:
        raise ValueError("Missing complete outgoing file mapping")
    if not all(isinstance(p, str) and p and isinstance(t, str) for p, t in files.items()):
        raise ValueError("Files must map paths to complete UTF-8 text")
    message = payload.get("message", "")
    if not isinstance(message, str):
        raise ValueError("Message must be text")
    findings = [finding for path, text in files.items() for finding in inspect(path, text)]
    findings.extend(inspect("outgoing-message.txt", message))
    return findings

def main():
    try:
        findings = check(json.load(sys.stdin))
    except Exception:
        print("BLOCKED: scanner or input failure; no upload permitted.", file=sys.stderr)
        return 2
    if findings:
        for path, line, rule in sorted(set(findings)):
            print(f"BLOCKED: {path}:{line}: {rule}", file=sys.stderr)
        return 1
    print("PASS: no findings. Manual review is still required.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
