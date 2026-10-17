"""Protocol and shared-state adapter checks; never calls a model provider."""

import json
import subprocess
import sys
from unittest.mock import patch
from urllib.error import URLError

import pytest

from campaign_mcp import CampaignClient, MCPServer


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path == "/api/status":
            return {"configured": True, "campaigns": [{"id": "abc"}], "write_token": "secret"}
        return {"id": "abc", "revision": 2, "presentation": {"title": "Wizard"},
                "character": {"name": "El"}, "media": {"image": "/portrait.png"}}


def ready(client=None):
    server = MCPServer(client or FakeClient())
    response = server.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                              "params": {"protocolVersion": "2025-11-25", "capabilities": {},
                                         "clientInfo": {"name": "test", "version": "1"}}})
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    return server


def call(server, name, arguments):
    return server.handle({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                          "params": {"name": name, "arguments": arguments}})


def test_read_only_tools_keep_payload_and_hide_token():
    client = FakeClient()
    server = ready(client)
    status = call(server, "dm_status", {})["result"]
    assert "secret" not in json.dumps(status)
    result = call(server, "dm_get_campaign", {"campaign_id": "abc"})["result"]
    assert result["structuredContent"]["presentation"]["title"] == "Wizard"
    assert result["structuredContent"]["character"]["name"] == "El"
    assert result["structuredContent"]["browserURL"].startswith("http://127.0.0.1:8766/")
    assert all(method == "GET" for method, _, _ in client.calls)


def test_action_forwards_revision_and_request_identity_exactly():
    client = FakeClient()
    server = ready(client)
    args = {"campaign_id": "abc", "revision": 1, "request_id": "same-request",
            "action": "Examine the bell", "intent": "act"}
    assert not call(server, "dm_act", args)["result"]["isError"]
    assert client.calls[-1] == ("POST", "/api/campaigns/abc/actions",
                              {key: value for key, value in args.items() if key != "campaign_id"})


@pytest.mark.parametrize("args", [{}, {"campaign_id": "../secret"},
                                  {"campaign_id": "abc", "extra": True}])
def test_invalid_tool_arguments_never_reach_http(args):
    client = FakeClient()
    result = call(ready(client), "dm_get_campaign", args)
    assert result["result"]["isError"]
    assert not client.calls


def test_protocol_errors_and_ping():
    server = ready()
    assert server.handle({"jsonrpc": "2.0", "id": 2, "method": "ping"})["result"] == {}
    assert server.handle([])["error"]["code"] == -32600
    assert server.handle({"jsonrpc": "2.0", "id": 4, "method": "missing"})["error"]["code"] == -32601
    assert server.handle({"jsonrpc": "2.0", "method": "notifications/cancelled"}) is None
    assert MCPServer(FakeClient()).handle({"jsonrpc": "2.0", "id": 1,
                                          "method": "tools/list"})["error"]["code"] == -32002


def test_transport_sanitizes_failure_and_rejects_remote_urls():
    with pytest.raises(ValueError):
        CampaignClient("https://example.com")
    with pytest.raises(ValueError):
        CampaignClient("http://user:password@127.0.0.1:8766")
    with patch("campaign_mcp.urllib.request.OpenerDirector.open",
               side_effect=URLError("secret provider credentials")):
        result = call(ready(CampaignClient()), "dm_status", {})["result"]
    assert result["isError"]
    assert "credentials" not in json.dumps(result)


def test_listed_create_and_reset_are_not_dispatched():
    """Both tools are advertised, but the dispatcher has no handler for them."""
    client = FakeClient()
    server = ready(client)
    for name, args in (("dm_create_campaign", {}), ("dm_reset", {"campaign_id": "abc"}),
                       ("dm_unknown", {})):
        result = call(server, name, args)["result"]
        assert result["isError"]
        assert name in result["content"][0]["text"]
    assert not client.calls


def test_tool_failures_stay_inside_the_result_envelope():
    class Broken(FakeClient):
        def request(self, method, path, body=None):
            raise RuntimeError("secret downstream detail")

    server = ready(Broken())
    for name, args in (
        ("dm_get_campaign", {"campaign_id": "abc"}),
        ("dm_status", {}),
        ("dm_act", {"campaign_id": "abc", "revision": 1, "request_id": "r",
                     "action": "look", "intent": "act"}),
    ):
        result = call(server, name, args)["result"]
        assert result["isError"]
        assert "secret" not in json.dumps(result)


def test_stdio_is_only_newline_json_and_notifications_are_silent():
    messages = ["{bad", json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                    "params": {"protocolVersion": "2025-11-25"}}),
                json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
                json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})]
    result = subprocess.run([sys.executable, "campaign_mcp.py"],
                            input="\n".join(messages) + "\n", capture_output=True, text=True,
                            check=False)
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 0
    assert len(replies) == 3
    assert replies[0]["error"]["code"] == -32700
    tools = replies[-1]["result"]["tools"]
    assert len(tools) == 5
    assert next(t for t in tools if t["name"] == "dm_get_campaign")["annotations"]["readOnlyHint"]
