import datetime as dt
import json

import pytest
from sqlalchemy import select

from chartgame import config
from chartgame.api import game
from chartgame.api.services import elo, scoring, selector, tokens
from chartgame.db.models import GameSession, Play, Question, User
from chartgame.db.session import make_session

SECRET_KEYS = {"reveal", "correct_choice", "answer", "answer_idx", "name", "code", "gap_start", "start_date",
               "public_id", "question_id", "id", "decoy_sources", "p_score", "elo"}


def _keys(obj) -> set[str]:
    if isinstance(obj, dict):
        return set(obj) | {k for v in obj.values() for k in _keys(v)}
    if isinstance(obj, list):
        return {k for v in obj for k in _keys(v)}
    return set()


def start(client, **kw):
    body = {"mode": "quick", "game_type": "choice4", "difficulty": "normal", "filters": {"interval": "day"}, **kw}
    r = client.post("/api/sessions", json=body)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def real_position(play_token: str) -> int:
    db = make_session()
    play = db.get(Play, tokens.read(play_token))
    db.close()
    return play.option_order.index(0)


def test_health_and_meta(client):
    h = client.get("/api/health").json()
    assert h["ok"] and h["questions"] > 100
    m = client.get("/api/meta/filters").json()
    day = m["by_interval"]["day"]
    assert day["total"] == h["questions"]
    assert sum(x["count"] for x in day["difficulties"]) == day["total"]
    assert {x["value"] for x in day["cap_tiers"]} == {"large", "mid", "small", "micro"}


def test_question_never_leaks_answer(client):
    sid = start(client)
    q = client.get(f"/api/sessions/{sid}/next").json()
    assert not (_keys(q) & SECRET_KEYS), _keys(q) & SECRET_KEYS
    assert len(q["options"]) == 4 and q["time_limit_ms"] == 20000
    L, G, R = q["layout"]["L"], q["layout"]["G"], q["layout"]["R"]
    assert len(q["candles"]) == L + R and all(len(o) == G for o in q["options"])
    assert "cg_uid" in client.cookies


def test_answer_flow_scores_and_reveals(client):
    sid = start(client)
    q = client.get(f"/api/sessions/{sid}/next").json()
    pos = real_position(q["play_token"])
    r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": pos}).json()
    assert r["correct"] and r["correct_choice"] == pos and r["score_delta"] >= 150
    assert r["state"]["streak"] == 1 and r["state"]["score"] == r["score_delta"]
    assert r["reveal"]["name"].startswith("테스트") and r["elo"]["after"] > r["elo"]["before"]
    assert r["decoy_sources"][pos] is None and sum(s is None for s in r["decoy_sources"]) == 1
    # 같은 문제에 두 번 답할 수 없다
    assert client.post("/api/answer", json={"play_token": q["play_token"], "choice": pos}).status_code == 409


def test_wrong_answer_resets_streak(client):
    sid = start(client)
    for want_correct in (True, False):
        q = client.get(f"/api/sessions/{sid}/next").json()
        pos = real_position(q["play_token"])
        r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": pos if want_correct else (pos + 1) % 4}).json()
        assert r["correct"] is want_correct
    assert r["state"]["streak"] == 0 and r["score_delta"] == 0


def test_bad_tokens_and_choices(client):
    sid = start(client)
    q = client.get(f"/api/sessions/{sid}/next").json()
    assert client.post("/api/answer", json={"play_token": "garbage", "choice": 0}).status_code == 400
    assert client.post("/api/answer", json={"play_token": q["play_token"], "choice": 7}).status_code == 422
    assert client.post("/api/answer", json={"play_token": q["play_token"], "choice": "O"}).status_code == 422
    assert tokens.read(q["play_token"], max_age=-1) is None  # 만료


def test_refresh_returns_same_pending_question(client):
    sid = start(client)
    a = client.get(f"/api/sessions/{sid}/next").json()
    b = client.get(f"/api/sessions/{sid}/next").json()
    assert a["candles"] == b["candles"] and a["options"] == b["options"] and b["index"] == 1
    assert b["remaining_ms"] <= a["remaining_ms"]


def test_timeout_counts_as_wrong(client, db_url):
    sid = start(client)
    q = client.get(f"/api/sessions/{sid}/next").json()
    db = make_session()
    play = db.get(Play, tokens.read(q["play_token"]))
    play.served_at -= dt.timedelta(seconds=60)
    db.commit()
    db.close()
    r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": real_position(q["play_token"])}).json()
    assert r["timed_out"] and not r["correct"] and r["score_delta"] == 0


def test_quick_session_finishes_after_ten(client):
    sid = start(client)
    seen = set()
    for i in range(config.QUICK_TOTAL):
        q = client.get(f"/api/sessions/{sid}/next").json()
        assert q["index"] == i + 1
        seen.add(json.dumps(q["candles"]))
        r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": 0}).json()
    assert len(seen) == config.QUICK_TOTAL and r["state"]["finished"]
    assert client.get(f"/api/sessions/{sid}/next").json()["finished"]
    s = client.get(f"/api/sessions/{sid}/summary").json()
    assert len(s["plays"]) == 10 and s["share_text"].count("🟩") + s["share_text"].count("🟥") == 10
    assert s["correct"] == sum(p["correct"] for p in s["plays"])


def test_ox_mode(client):
    sid = start(client, game_type="ox")
    q = client.get(f"/api/sessions/{sid}/next").json()
    assert "options" not in q and len(q["candidate"]) == q["layout"]["G"] and q["time_limit_ms"] == 10000
    assert not (_keys(q) & SECRET_KEYS)
    r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": "O"}).json()
    assert r["correct"] == r["shown_was_real"] and len(r["real"]) == q["layout"]["G"]
    if r["correct"]:
        assert r["real"] == q["candidate"]


def test_survival_loses_lives_and_ends(client):
    sid = start(client, mode="survival", difficulty="easy")
    for i in range(config.SURVIVAL_LIVES):
        q = client.get(f"/api/sessions/{sid}/next").json()
        pos = real_position(q["play_token"])
        r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": (pos + 1) % 4}).json()
        assert r["state"]["lives"] == config.SURVIVAL_LIVES - i - 1
    assert r["state"]["finished"]


def test_survival_difficulty_rises_with_streak():
    assert selector.survival_level("easy", 0) == "easy"
    assert selector.survival_level("easy", 5) == "normal"
    assert selector.survival_level("easy", 10) == selector.survival_level("auto", 14) == "hard"
    assert selector.survival_level("normal", 30) == "hard"


def test_endless_has_no_timer_or_score(client):
    sid = start(client, mode="endless")
    q = client.get(f"/api/sessions/{sid}/next").json()
    assert q["time_limit_ms"] is None and q["total"] is None
    r = client.post("/api/answer", json={"play_token": q["play_token"], "choice": real_position(q["play_token"])}).json()
    assert r["correct"] and r["score_delta"] == 0 and not r["state"]["finished"]


def test_filters_are_respected(client, db_url):
    sid = start(client, difficulty="hard", filters={"interval": "day", "markets": ["KOSPI"], "cap_tiers": ["mid"]})
    db = make_session()
    for _ in range(4):
        q = client.get(f"/api/sessions/{sid}/next").json()
        assert q["difficulty"] == "hard" and q["context_hint"] == {"market": "KOSPI", "cap_tier": "mid", "interval": "day"}
        assert q["volume"] is None
        client.post("/api/answer", json={"play_token": q["play_token"], "choice": 0})
    db.close()


def test_no_repeats_and_stock_cooldown(client, db_url):
    sid = start(client, mode="endless")
    codes = []
    db = make_session()
    for _ in range(25):
        q = client.get(f"/api/sessions/{sid}/next").json()
        codes.append(db.get(Play, tokens.read(q["play_token"])).code)
        client.post("/api/answer", json={"play_token": q["play_token"], "choice": 0})
    qids = list(db.scalars(select(Play.question_id)))
    db.close()
    assert len(set(qids)) == len(qids)
    for i, c in enumerate(codes):
        assert c not in codes[max(0, i - config.STOCK_COOLDOWN):i]


def test_overlap_rule():
    d = dt.date
    f = selector.overlap_frac
    assert f(d(2020, 1, 1), d(2020, 1, 10), d(2020, 1, 9), d(2020, 1, 20)) == pytest.approx(0.2)
    assert f(d(2020, 1, 1), d(2020, 1, 10), d(2020, 1, 10), d(2020, 1, 20)) == pytest.approx(0.1)
    assert f(d(2020, 1, 1), d(2020, 1, 10), d(2020, 2, 1), d(2020, 2, 5)) == 0


def test_overlapping_window_of_seen_stock_is_excluded(db_url):
    db = make_session()
    user = User()
    db.add(user)
    db.commit()
    q = db.scalars(select(Question).limit(1)).one()
    sess = GameSession(user_id=user.id, mode="endless", game_type="choice4", filters={}, difficulty="auto")
    db.add(sess)
    db.commit()
    # 같은 종목에서 날짜가 절반 겹치는 문제를 이미 풀었다고 기록
    half = (q.end_date - q.start_date) // 2
    db.add(Play(session_id=sess.id, user_id=user.id, question_id=q.id, code=q.code, interval=q.interval,
                start_date=q.start_date + half, end_date=q.end_date + half, difficulty=q.difficulty, option_order=[0, 1, 2, 3]))
    db.commit()
    assert selector._unseen(db, user, [q], allow_repeat=False) == []
    other = db.scalars(select(Question).where(Question.code != q.code).limit(1)).one()
    assert selector._unseen(db, user, [other]) == [other]
    db.close()


def test_widen_goes_to_neighbors_then_everything():
    f = selector.normalize_filters({"interval": "week", "cap_tiers": ["large"], "eras": ["2020s"], "markets": ["KOSPI"]})
    assert selector.widen(f, 1)["cap_tiers"] == ["large", "mid"] and selector.widen(f, 1)["eras"] == ["2010s", "2020s"]
    assert selector.widen(f, 2)["cap_tiers"] == [] and selector.widen(f, 2)["markets"] == ["KOSPI"]
    assert selector.widen(f, 3)["markets"] == []
    assert selector.normalize_filters({"interval": "x", "markets": ["NYSE"]}) == {"interval": "day", "markets": [], "cap_tiers": [], "eras": []}


def test_empty_filter_widens_instead_of_ending(client):
    sid = start(client, filters={"interval": "day", "eras": ["2000s"]})  # 합성 데이터에는 2000년대가 없다
    q = client.get(f"/api/sessions/{sid}/next").json()
    assert "candles" in q and q["widened"] is True


def test_pool_count_decreases(client):
    body = {"mode": "quick", "game_type": "choice4", "difficulty": "normal", "filters": {"interval": "day"}}
    before = client.post("/api/pool/count", json=body).json()
    sid = start(client)
    q = client.get(f"/api/sessions/{sid}/next").json()
    client.post("/api/answer", json={"play_token": q["play_token"], "choice": 0})
    after = client.post("/api/pool/count", json=body).json()
    assert after["total"] == before["total"] and after["remaining"] == before["remaining"] - 1


def test_daily_is_same_for_everyone_and_once_per_day(db_url):
    from fastapi.testclient import TestClient

    from chartgame.api.main import app

    runs = []
    for _ in range(2):
        with TestClient(app) as c:
            assert c.get("/api/daily").json()["session"] is None
            sid = c.post("/api/daily/start").json()["session_id"]
            assert c.post("/api/daily/start").json()["session_id"] == sid
            seq = []
            for _ in range(len(config.DAILY_MIX)):
                q = c.get(f"/api/sessions/{sid}/next").json()
                seq.append((json.dumps(q["candles"]), q["difficulty"]))
                r = c.post("/api/answer", json={"play_token": q["play_token"], "choice": real_position(q["play_token"])}).json()
            assert r["state"]["finished"]
            assert c.get("/api/daily").json()["session"]["finished"]
            lb = c.get("/api/daily/leaderboard").json()
            runs.append((seq, lb))
    assert runs[0][0] == runs[1][0]
    assert [d for _, d in runs[0][0]] == list(config.DAILY_MIX)
    lb = runs[1][1]
    assert lb["players"] == 2 and len(lb["top"]) == 2 and lb["my_rank"] in (1, 2)
    assert sum(t["me"] for t in lb["top"]) == 1 and lb["top"][0]["score"] >= lb["top"][1]["score"]


def test_nickname_and_stats(client):
    assert client.post("/api/me/nickname", json={"nickname": "차트왕"}).json() == {"nickname": "차트왕"}
    assert client.post("/api/me/nickname", json={"nickname": "관리자"}).status_code == 422
    assert client.post("/api/me/nickname", json={"nickname": "<b>x</b>"}).status_code == 422
    sid = start(client)
    q = client.get(f"/api/sessions/{sid}/next").json()
    client.post("/api/answer", json={"play_token": q["play_token"], "choice": real_position(q["play_token"])})
    s = client.get("/api/me/stats").json()
    assert s["nickname"] == "차트왕" and s["plays"] == 1 and s["correct"] == 1 and s["best_streak"] == 1
    assert s["by_difficulty"] == [{"key": "normal", "plays": 1, "correct": 1}]


def test_other_users_session_is_hidden(client, db_url):
    from fastapi.testclient import TestClient

    from chartgame.api.main import app

    sid = start(client)
    with TestClient(app) as other:
        assert other.get(f"/api/sessions/{sid}/next").status_code == 404


def test_scoring_formula():
    assert scoring.score(False, "hard", "choice4", 0, 5) == 0
    assert scoring.score(True, "easy", "choice4", 25000, 0) == 100  # 시간 다 씀
    assert scoring.score(True, "easy", "choice4", 0, 0) == 150  # 즉시
    assert scoring.score(True, "hard", "choice4", 0, 3) == round(375 * 1.3)
    assert scoring.score(True, "normal", "choice4", 10000, 20) == round((150 + 37.5) * 2.0)  # 콤보 상한
    assert scoring.score(True, "normal", "ox", 0, 0) == round(225 * 0.5)


def test_elo_math():
    assert elo.expected(1000, 1000, 0.25) == pytest.approx(0.625)
    assert elo.expected(1000, 1000, 0.5) == pytest.approx(0.75)
    assert elo.expected(3000, 1000, 0.25) == pytest.approx(1.0, abs=1e-3)
    assert elo.expected(0, 2000, 0.25) == pytest.approx(0.25, abs=1e-3)
    u, q = elo.update(1000, 1000, True, "choice4", 0, 0)
    assert u == pytest.approx(1000 + 48 * 0.375) and q == pytest.approx(1000 - 32 * 0.375)
    u2, q2 = elo.update(1000, 1000, False, "choice4", 100, 990)
    assert u2 == pytest.approx(1000 - 32 * 0.625) and q2 == pytest.approx(1000 + 8 * 0.625)


def test_kst_date():
    assert isinstance(game.kst_today(), dt.date)
