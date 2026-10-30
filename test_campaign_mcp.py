"""Protocol and shared-state adapter checks; never calls a model provider."""

import io
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
    """Unsupported tools return isError."""
    client = FakeClient()
    server = ready(client)
    result = call(server, "dm_unknown", {})["result"]
    assert result["isError"]
    assert "dm_unknown" in result["content"][0]["text"]
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
                            input="\n".join(messages) + "\n", capture_output=True, text=True, check=False)
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 0
    assert len(replies) == 3
    assert replies[0]["error"]["code"] == -32700
    tools = replies[-1]["result"]["tools"]
    assert len(tools) == 5
    assert next(t for t in tools if t["name"] == "dm_get_campaign")["annotations"]["readOnlyHint"]


def test_mcp_additional_tools_and_error_branches():
    client = FakeClient()
    server = ready(client)

    # 1. tools/list when initialized
    res = server.handle({"jsonrpc": "2.0", "id": 10, "method": "tools/list"})
    assert len(res["result"]["tools"]) == 5

    # 2. tools/call before initialized
    uninit_server = MCPServer(client)
    res_uninit = uninit_server.handle({"jsonrpc": "2.0", "id": 11, "method": "tools/call", "params": {"name": "dm_status", "arguments": {}}})
    assert res_uninit["error"]["code"] == -32002

    # 3. dm_create_campaign
    res_create = call(server, "dm_create_campaign", {})
    assert not res_create["result"]["isError"]
    assert call(server, "dm_create_campaign", {"invalid": 1})["result"]["isError"]

    # 4. dm_reset
    res_reset = call(server, "dm_reset", {"campaign_id": "abc"})
    assert not res_reset["result"]["isError"]
    assert call(server, "dm_reset", {"campaign_id": "../bad"})["result"]["isError"]
    assert call(server, "dm_reset", {"campaign_id": "a/b"})["result"]["isError"]
    assert call(server, "dm_reset", {})["result"]["isError"]

    # 5. dm_status with invalid arguments
    assert call(server, "dm_status", {"extra": 1})["result"]["isError"]

    # 6. dm_act with bad arguments
    assert call(server, "dm_act", {"campaign_id": "../evil"})["result"]["isError"]

    # 7. Unsupported tool
    assert call(server, "unknown_tool", {})["result"]["isError"]

    # 8. Client request exceptions
    class ErrorClient:
        def request(self, method, path, body=None):
            raise RuntimeError("Backend failure")

    err_server = ready(ErrorClient())
    assert call(err_server, "dm_status", {})["result"]["isError"]
    assert call(err_server, "dm_get_campaign", {"campaign_id": "abc"})["result"]["isError"]
    assert call(err_server, "dm_create_campaign", {})["result"]["isError"]
    assert call(err_server, "dm_reset", {"campaign_id": "abc"})["result"]["isError"]
    assert call(err_server, "dm_act", {"campaign_id": "abc", "revision": 1, "request_id": "r", "action": "a", "intent": "i"})["result"]["isError"]


def test_client_validation_and_request_success():
    # Loopback host rejection
    with pytest.raises(ValueError, match="Only loopback host allowed"):
        CampaignClient("http://8.8.8.8:8766")

    # Successful client request
    client = CampaignClient("http://127.0.0.1:8766")
    from unittest.mock import MagicMock
    mock_resp = MagicMock()
    mock_resp.read.return_value = b'{"status": "ok"}'
    mock_resp.__enter__.return_value = mock_resp

    with patch.object(client.opener, "open", return_value=mock_resp):
        res = client.request("GET", "/api/status")
        assert res == {"status": "ok"}


def test_main_in_process():
    import campaign_mcp
    input_data = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"}}) + "\n"
        + "{bad json\n"
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
    )
    with patch("sys.stdin", io.StringIO(input_data)), patch("sys.stdout", new_callable=io.StringIO) as mock_out:
        campaign_mcp.main()
        output = mock_out.getvalue()
        assert "serverInfo" in output
        assert "Parse error" in output
