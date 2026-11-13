import json

import pytest

from chartgame.api import battle


def recv_peers(ws):
    while True:
        m = json.loads(ws.receive_text())
        if m["t"] == "peers":
            return m


def test_room_shares_presence_and_cleans_up(client):
    with client.websocket_connect("/ws/room/cg-abcd") as a:
        me_a = recv_peers(a)["you"]
        a.send_text(json.dumps({"t": "presence", "p": {"nick": "철수", "role": "host"}}))
        assert recv_peers(a)["peers"][0]["presence"]["nick"] == "철수"
        with client.websocket_connect("/ws/room/cg-abcd") as b:
            first_b = recv_peers(b)
            assert {p["peer"] for p in first_b["peers"]} >= {me_a, first_b["you"]}
            b.send_text(json.dumps({"t": "presence", "p": {"nick": "영희", "ready": True}}))
            seen = recv_peers(b)
            nicks = {p["presence"].get("nick") for p in seen["peers"]}
            assert nicks == {"철수", "영희"}
            # a 도 영희를 본다
            for _ in range(5):
                m = recv_peers(a)
                if len(m["peers"]) == 2 and all(p["presence"].get("nick") for p in m["peers"]):
                    break
            assert {p["presence"]["nick"] for p in m["peers"]} == {"철수", "영희"}
            # null 은 필드를 지운다
            b.send_text(json.dumps({"t": "presence", "p": {"ready": None}}))
            assert "ready" not in [p for p in recv_peers(b)["peers"] if p["peer"] == first_b["you"]][0]["presence"]
        # b 가 나가면 a 혼자 남는다
        for _ in range(5):
            m = recv_peers(a)
            if len(m["peers"]) == 1:
                break
        assert [p["peer"] for p in m["peers"]] == [me_a]
    assert "cg-abcd" not in battle.ROOMS


def test_rejects_bad_room_name_and_oversized_presence(client):
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/room/BAD NAME") as ws:
            ws.receive_text()
    with client.websocket_connect("/ws/room/lobby") as ws:
        recv_peers(ws)
        ws.send_text(json.dumps({"t": "presence", "p": {"x": "a" * 5000}}))
        assert json.loads(ws.receive_text()) == {"t": "error", "code": "invalid_argument"}
        ws.send_text(json.dumps({"t": "presence", "p": {"bad key": 1}}))
        assert json.loads(ws.receive_text())["t"] == "error"


def test_merge_rules():
    assert battle.merge({"a": 1, "b": 2}, {"b": None, "c": 3}) == {"a": 1, "c": 3}
    with pytest.raises(ValueError):
        battle.merge({}, {"x": "y" * 5000})


def test_game_page_and_shim_are_served(client):
    r = client.get("/game")
    assert r.status_code == 200 and "/static/room_shim.js" in r.text and "const Q=" in r.text
    assert client.get("/static/room_shim.js").status_code == 200
    assert client.get("/static/nope.js").status_code == 404
    assert "DATA_DIR" not in client.get("/static/..%2Fconfig.py").text  # 상위 폴더 파일은 나가지 않는다
