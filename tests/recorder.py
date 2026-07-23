#!/usr/bin/env python3
"""Permission-prompt recorder for headless e2e runs. Stdlib-only stdio MCP server.

Registered via --mcp-config and --permission-prompt-tool mcp__recorder__approve.
Claude Code consults this tool only when the normal permission flow would have
shown an interactive prompt — calls pre-approved by allowed-tools never reach
it. Every request is appended to $PERM_LOG as JSONL and then allowed, so flows
run to completion while the log captures exactly what would have prompted.

Hand-rolled JSON-RPC instead of the mcp package: the permission-prompt
contract demands the tool result be a single {"type":"text"} content block
holding the {"behavior": ...} JSON as a string — FastMCP adds structured
output around return values and the harness rejects it (verified 2026-07).
"""

import json
import os
import sys

LOG = os.environ.get("PERM_LOG", "permission-requests.jsonl")

TOOL = {
    "name": "approve",
    "description": "Record a would-be permission prompt, then allow it.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "tool_name": {"type": "string"},
            "input": {"type": "object"},
            "tool_use_id": {"type": "string"},
        },
        "required": ["tool_name", "input"],
        "additionalProperties": True,
    },
}


def reply(mid, result):
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": mid, "result": result}) + "\n")
    sys.stdout.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    msg = json.loads(line)
    method, mid = msg.get("method"), msg.get("id")
    if method == "initialize":
        reply(mid, {
            "protocolVersion": msg.get("params", {}).get("protocolVersion", "2025-06-18"),
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "recorder", "version": "1.0.0"},
        })
    elif method == "tools/list":
        reply(mid, {"tools": [TOOL]})
    elif method == "tools/call":
        args = msg.get("params", {}).get("arguments", {})
        with open(LOG, "a") as f:
            f.write(json.dumps({"tool_name": args.get("tool_name"), "input": args.get("input")}) + "\n")
        payload = json.dumps({"behavior": "allow", "updatedInput": args.get("input") or {}})
        reply(mid, {"content": [{"type": "text", "text": payload}]})
    elif mid is not None:
        reply(mid, {})  # politely ack anything else; notifications need no reply
