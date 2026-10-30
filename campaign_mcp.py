"""MCP (Model Context Protocol) Server and Client adapter for AI Dungeon Master."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class CampaignClient:
    """Client for local AI Dungeon Master campaign server."""

    def __init__(self, base_url: str = "http://127.0.0.1:8766") -> None:
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme != "http":
            raise ValueError(f"Only plain http allowed for local loopback; got {parsed.scheme!r}")
        if "@" in base_url or parsed.username or parsed.password:
            raise ValueError("Credentials not allowed in base_url")
        if parsed.hostname not in ("127.0.0.1", "localhost"):
            raise ValueError(f"Only loopback host allowed; got {parsed.hostname!r}")
        self.base_url = base_url.rstrip("/")
        self.opener = urllib.request.build_opener()

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with self.opener.open(req) as resp:
                raw = resp.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except (OSError, urllib.error.URLError, UnicodeError, json.JSONDecodeError):
            # Sanitize error to avoid leaking credentials or sensitive tokens
            raise RuntimeError("Campaign client communication error")


class MCPServer:
    """Stdio-compatible MCP JSON-RPC Server for AI Dungeon Master."""

    def __init__(self, client: Any = None) -> None:
        self.client = client or CampaignClient()
        self.initialized = False

    def handle(self, request: Any) -> dict[str, Any] | None:
        if not isinstance(request, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}}

        method = request.get("method")
        msg_id = request.get("id")

        if method == "notifications/initialized" or method == "notifications/cancelled":
            return None

        if method == "ping":
            return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

        if method == "initialize":
            self.initialized = True
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "ai-dungeon-master-mcp", "version": "1.0"},
                },
            }

        if method == "tools/list":
            if not self.initialized:
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32002, "message": "Server not initialized"}}
            tools = [
                {
                    "name": "dm_status",
                    "description": "Get status of active campaigns",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "dm_get_campaign",
                    "description": "Retrieve campaign state by ID",
                    "inputSchema": {"type": "object", "properties": {"campaign_id": {"type": "string"}}, "required": ["campaign_id"]},
                    "annotations": {"readOnlyHint": True},
                },
                {
                    "name": "dm_create_campaign",
                    "description": "Start a new campaign",
                    "inputSchema": {"type": "object", "properties": {}},
                },
                {
                    "name": "dm_act",
                    "description": "Dispatch player action in campaign",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "campaign_id": {"type": "string"},
                            "revision": {"type": "integer"},
                            "request_id": {"type": "string"},
                            "action": {"type": "string"},
                            "intent": {"type": "string"},
                        },
                        "required": ["campaign_id", "revision", "request_id", "action", "intent"],
                    },
                },
                {
                    "name": "dm_reset",
                    "description": "Reset campaign state",
                    "inputSchema": {"type": "object", "properties": {"campaign_id": {"type": "string"}}, "required": ["campaign_id"]},
                },
            ]
            return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}}

        if method == "tools/call":
            if not self.initialized:
                return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32002, "message": "Server not initialized"}}
            params = request.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})

            # Validate tool arguments
            if name == "dm_get_campaign":
                if set(args) != {"campaign_id"} or not isinstance(args.get("campaign_id"), str) or ".." in args["campaign_id"] or "/" in args["campaign_id"]:
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Invalid campaign_id"}]}}
                try:
                    res = self.client.request("GET", f"/api/campaigns/{args['campaign_id']}")
                    res["browserURL"] = f"http://127.0.0.1:8766/campaigns/{args['campaign_id']}"
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "isError": False,
                            "structuredContent": res,
                            "content": [{"type": "text", "text": json.dumps(res)}],
                        },
                    }
                except (OSError, RuntimeError, ValueError, TypeError, KeyError):
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Failed to get campaign"}]}}

            elif name == "dm_status":
                if set(args) != set():
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Invalid arguments"}]}}
                try:
                    res = self.client.request("GET", "/api/status")
                    # Hide write_token or sensitive fields from client output
                    sanitized = {k: v for k, v in res.items() if "token" not in k.lower()}
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "isError": False,
                            "structuredContent": sanitized,
                            "content": [{"type": "text", "text": json.dumps(sanitized)}],
                        },
                    }
                except (OSError, RuntimeError, ValueError, TypeError, KeyError, AttributeError):
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Failed to get status"}]}}

            elif name == "dm_act":
                expected = {"campaign_id", "revision", "request_id", "action", "intent"}
                if set(args) != expected or ".." in str(args.get("campaign_id")):
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Invalid act arguments"}]}}
                try:
                    cid = args["campaign_id"]
                    body = {k: v for k, v in args.items() if k != "campaign_id"}
                    res = self.client.request("POST", f"/api/campaigns/{cid}/actions", body)
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "isError": False,
                            "structuredContent": res,
                            "content": [{"type": "text", "text": json.dumps(res)}],
                        },
                    }
                except (OSError, RuntimeError, ValueError, TypeError, KeyError):
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Action failed"}]}}

            elif name == "dm_create_campaign":
                if set(args) != set():
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Invalid arguments"}]}}
                try:
                    res = self.client.request("POST", "/api/campaigns", {})
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "isError": False,
                            "structuredContent": res,
                            "content": [{"type": "text", "text": json.dumps(res)}],
                        },
                    }
                except (OSError, RuntimeError, ValueError, TypeError, KeyError):
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Failed to create campaign"}]}}

            elif name == "dm_reset":
                if set(args) != {"campaign_id"} or not isinstance(args.get("campaign_id"), str) or ".." in args["campaign_id"] or "/" in args["campaign_id"]:
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Invalid campaign_id"}]}}
                try:
                    res = self.client.request("POST", f"/api/campaigns/{args['campaign_id']}/reset", {})
                    return {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "isError": False,
                            "structuredContent": res,
                            "content": [{"type": "text", "text": json.dumps(res)}],
                        },
                    }
                except (OSError, RuntimeError, ValueError, TypeError, KeyError):
                    return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": "Failed to reset campaign"}]}}

            return {"jsonrpc": "2.0", "id": msg_id, "result": {"isError": True, "content": [{"type": "text", "text": f"Unsupported tool: {name}"}]}}

        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method {method!r} not found"}}


def main() -> None:
    client = CampaignClient()
    server = MCPServer(client)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
            continue

        res = server.handle(req)
        if res is not None:
            sys.stdout.write(json.dumps(res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
