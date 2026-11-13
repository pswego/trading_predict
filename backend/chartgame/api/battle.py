"""온라인 대전용 WebSocket 방.

게임 페이지는 claude.ai 의 room 기능과 같은 모양의 API(presence / onPeers / join)를 쓴다.
이 모듈은 그 API를 서버에서 흉내 낸다: 같은 방에 접속한 사람들의 presence 를 모아서 모두에게 다시 뿌린다.
저장하는 것은 없다. 서버를 재시작하면 방은 모두 사라진다.
"""
from __future__ import annotations

import asyncio
import json
import re
import secrets

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()
ROOM_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,47}$")
MAX_PRESENCE = 4096
MAX_PEERS = 64
MAX_ROOMS = 2000


class Room:
    def __init__(self, name: str):
        self.name = name
        self.peers: dict[str, tuple[WebSocket, dict]] = {}
        self.lock = asyncio.Lock()

    def snapshot(self) -> list[dict]:
        return [{"peer": k, "presence": p} for k, (_, p) in self.peers.items()]

    async def broadcast(self) -> None:
        snap = self.snapshot()
        dead = []
        for peer, (ws, _) in list(self.peers.items()):
            try:
                await ws.send_text(json.dumps({"t": "peers", "peers": snap, "you": peer}, ensure_ascii=False))
            except Exception:
                dead.append(peer)
        for peer in dead:
            self.peers.pop(peer, None)


ROOMS: dict[str, Room] = {}


def merge(cur: dict, patch: dict) -> dict:
    out = dict(cur)
    for k, v in patch.items():
        if not isinstance(k, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", k):
            raise ValueError("bad key")
        if v is None:
            out.pop(k, None)
        else:
            out[k] = v
    if len(json.dumps(out, ensure_ascii=False).encode()) > MAX_PRESENCE:
        raise ValueError("presence too large")
    return out


@router.websocket("/ws/room/{name}")
async def room_ws(ws: WebSocket, name: str):
    if not ROOM_RE.fullmatch(name):
        await ws.close(code=1008)
        return
    room = ROOMS.get(name)
    if room is None:
        if len(ROOMS) >= MAX_ROOMS:
            await ws.close(code=1013)
            return
        room = ROOMS.setdefault(name, Room(name))
    if len(room.peers) >= MAX_PEERS:
        await ws.close(code=1013)
        return
    await ws.accept()
    peer = secrets.token_hex(8)
    async with room.lock:
        room.peers[peer] = (ws, {})
        await room.broadcast()
    try:
        while True:
            raw = await ws.receive_text()
            if len(raw) > MAX_PRESENCE * 2:
                continue
            try:
                msg = json.loads(raw)
                if msg.get("t") != "presence" or not isinstance(msg.get("p"), dict):
                    continue
                async with room.lock:
                    cur = room.peers.get(peer, (ws, {}))[1]
                    room.peers[peer] = (ws, merge(cur, msg["p"]))
                    await room.broadcast()
            except (ValueError, json.JSONDecodeError):
                await ws.send_text(json.dumps({"t": "error", "code": "invalid_argument"}))
    except WebSocketDisconnect:
        pass
    finally:
        async with room.lock:
            room.peers.pop(peer, None)
            if room.peers:
                await room.broadcast()
            else:
                ROOMS.pop(name, None)
