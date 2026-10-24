from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_NAME = "Parsy"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demo_hash TEXT NOT NULL,
    player_sid TEXT NOT NULL,
    player_name TEXT NOT NULL DEFAULT '',
    file_name TEXT NOT NULL DEFAULT '',
    map_name TEXT NOT NULL DEFAULT '',
    played_at TEXT NOT NULL,
    rounds INTEGER NOT NULL DEFAULT 0,
    kills INTEGER NOT NULL DEFAULT 0,
    deaths INTEGER NOT NULL DEFAULT 0,
    assists INTEGER NOT NULL DEFAULT 0,
    kd REAL,
    adr REAL NOT NULL DEFAULT 0,
    kast REAL NOT NULL DEFAULT 0,
    hs_pct REAL NOT NULL DEFAULT 0,
    entry_kills INTEGER NOT NULL DEFAULT 0,
    entry_deaths INTEGER NOT NULL DEFAULT 0,
    utility_damage REAL NOT NULL DEFAULT 0,
    effective_flashes INTEGER NOT NULL DEFAULT 0,
    team_flashes INTEGER NOT NULL DEFAULT 0,
    clutches_won INTEGER NOT NULL DEFAULT 0,
    clutches_lost INTEGER NOT NULL DEFAULT 0,
    result TEXT NOT NULL DEFAULT '',
    team_score INTEGER NOT NULL DEFAULT 0,
    enemy_score INTEGER NOT NULL DEFAULT 0,
    source_label TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    UNIQUE(demo_hash, player_sid)
);
CREATE INDEX IF NOT EXISTS idx_matches_player ON matches(player_sid, played_at);
CREATE INDEX IF NOT EXISTS idx_matches_demo ON matches(demo_hash);
"""


def data_root() -> Path:
    override = os.environ.get("PARSY_DATA_DIR")
    if override:
        return Path(override).expanduser()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        return Path(local) / APP_NAME
    return Path.home() / ".parsy"


def db_path() -> Path:
    return data_root() / "history.db"


def _connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.executescript(SCHEMA)
    return connection


def _finite(value: Any, default: float | None = 0.0) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _integer(value: Any, default: int = 0) -> int:
    number = _finite(value, None)
    if number is None:
        return default
    return int(round(number))


def _safe_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def _clutch_totals(report: dict[str, Any]) -> tuple[int, int]:
    won = 0
    lost = 0
    clutches = report.get("clutches") or {}
    for size in (1, 2, 3):
        entry = clutches.get(size) or {}
        won += _integer(entry.get("won"))
        lost += _integer(entry.get("lost"))
    return won, lost


def _result(score: int, total_rounds: int) -> str:
    if total_rounds <= 0:
        return ""
    if score > total_rounds / 2:
        return "Победа"
    if score == total_rounds / 2:
        return "Ничья"
    return "Поражение"


def save_match(
    *,
    demo_hash: str,
    report: dict[str, Any],
    group: dict[str, Any] | None,
    total_rounds: int,
    file_name: str,
    map_name: str,
    source_label: str = "",
    played_at: str | None = None,
) -> None:
    if not demo_hash:
        return
    sid = str(report.get("sid") or "")
    if not sid:
        return
    score = _integer((group or {}).get("score"))
    total = max(_integer(total_rounds), 0)
    enemy_score = max(total - score, 0) if group else 0
    clutch_won, clutch_lost = _clutch_totals(report)
    stamp = played_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = _safe_json(
        {
            "rounds": report.get("rounds"),
            "kills": report.get("kills"),
            "deaths": report.get("deaths"),
            "assists": report.get("assists"),
            "kd": report.get("kd"),
            "adr": report.get("adr"),
            "kast": report.get("kast"),
            "hs_pct": report.get("hs_pct"),
            "entry_kills": report.get("entry_kills"),
            "entry_deaths": report.get("entry_deaths"),
            "utility_damage": report.get("utility_damage"),
            "effective_flashes": report.get("effective_flashes"),
            "team_flashes": report.get("team_flashes"),
            "clutches": report.get("clutches"),
            "plants": report.get("plants"),
            "defuses": report.get("defuses"),
            "weapon_stats": report.get("weapon_stats"),
        }
    )
    values = (
        demo_hash,
        sid,
        str(report.get("name") or sid),
        file_name,
        map_name,
        stamp,
        _integer(report.get("rounds")),
        _integer(report.get("kills")),
        _integer(report.get("deaths")),
        _integer(report.get("assists")),
        _finite(report.get("kd"), None),
        _finite(report.get("adr")) or 0.0,
        _finite(report.get("kast")) or 0.0,
        _finite(report.get("hs_pct")) or 0.0,
        _integer(report.get("entry_kills")),
        _integer(report.get("entry_deaths")),
        _finite(report.get("utility_damage")) or 0.0,
        _integer(report.get("effective_flashes")),
        _integer(report.get("team_flashes")),
        clutch_won,
        clutch_lost,
        _result(score, total),
        score,
        enemy_score,
        source_label,
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    connection = _connect()
    try:
        connection.execute(
            """
            INSERT INTO matches (
                demo_hash, player_sid, player_name, file_name, map_name, played_at,
                rounds, kills, deaths, assists, kd, adr, kast, hs_pct,
                entry_kills, entry_deaths, utility_damage, effective_flashes,
                team_flashes, clutches_won, clutches_lost, result, team_score,
                enemy_score, source_label, payload
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(demo_hash, player_sid) DO UPDATE SET
                player_name=excluded.player_name,
                file_name=excluded.file_name,
                map_name=excluded.map_name,
                played_at=excluded.played_at,
                rounds=excluded.rounds,
                kills=excluded.kills,
                deaths=excluded.deaths,
                assists=excluded.assists,
                kd=excluded.kd,
                adr=excluded.adr,
                kast=excluded.kast,
                hs_pct=excluded.hs_pct,
                entry_kills=excluded.entry_kills,
                entry_deaths=excluded.entry_deaths,
                utility_damage=excluded.utility_damage,
                effective_flashes=excluded.effective_flashes,
                team_flashes=excluded.team_flashes,
                clutches_won=excluded.clutches_won,
                clutches_lost=excluded.clutches_lost,
                result=excluded.result,
                team_score=excluded.team_score,
                enemy_score=excluded.enemy_score,
                source_label=excluded.source_label,
                payload=excluded.payload
            """,
            values,
        )
        connection.commit()
    finally:
        connection.close()


def player_history(sid: str, limit: int = 30) -> list[dict[str, Any]]:
    if not sid:
        return []
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT * FROM (
                SELECT * FROM matches
                WHERE player_sid = ?
                ORDER BY played_at DESC
                LIMIT ?
            )
            ORDER BY played_at ASC
            """,
            (sid, max(int(limit), 1)),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def recent_matches(limit: int = 8) -> list[dict[str, Any]]:
    connection = _connect()
    try:
        rows = connection.execute(
            """
            SELECT m.demo_hash, m.played_at, m.file_name, m.map_name,
                   m.team_score, m.enemy_score, m.result,
                   (
                       SELECT COUNT(*) FROM matches stats
                       WHERE stats.demo_hash = m.demo_hash
                   ) AS player_count
            FROM matches m
            JOIN (
                SELECT demo_hash, MIN(id) AS id
                FROM matches
                GROUP BY demo_hash
            ) first ON first.id = m.id
            ORDER BY m.played_at DESC
            LIMIT ?
            """,
            (max(int(limit), 1),),
        ).fetchall()
    finally:
        connection.close()
    return [dict(row) for row in rows]


def player_summary(sid: str) -> dict[str, Any]:
    connection = _connect()
    try:
        row = connection.execute(
            """
            SELECT COUNT(*) AS matches,
                   AVG(adr) AS adr,
                   AVG(kast) AS kast,
                   AVG(kd) AS kd,
                   AVG(hs_pct) AS hs_pct,
                   SUM(CASE WHEN result = 'Победа' THEN 1 ELSE 0 END) AS wins
            FROM matches
            WHERE player_sid = ?
            """,
            (sid,),
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return {"matches": 0, "adr": 0.0, "kast": 0.0, "kd": 0.0, "hs_pct": 0.0, "wins": 0}
    result = dict(row)
    result["matches"] = _integer(result.get("matches"))
    result["wins"] = _integer(result.get("wins"))
    for key in ("adr", "kast", "kd", "hs_pct"):
        result[key] = _finite(result.get(key)) or 0.0
    result["win_rate"] = (
        result["wins"] / result["matches"] * 100.0 if result["matches"] else 0.0
    )
    return result


def match_count() -> int:
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT COUNT(DISTINCT demo_hash) AS value FROM matches"
        ).fetchone()
    finally:
        connection.close()
    return _integer(row["value"] if row else 0)
