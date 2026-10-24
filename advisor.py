from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any, Callable

AI_PRESETS = {
    "Локальный анализ": {
        "base_url": "",
        "model": "",
        "key_required": False,
    },
    "Ollama (локально)": {
        "base_url": "http://127.0.0.1:11434/v1",
        "model": "llama3.1:8b",
        "key_required": False,
    },
    "DeepSeek": {
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_required": True,
    },
    "OpenAI": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_required": True,
    },
    "OpenRouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
        "key_required": True,
    },
    "Свой OpenAI-совместимый API": {
        "base_url": "",
        "model": "",
        "key_required": True,
    },
}

MAP_GUIDE = {
    "Ancient": {
        "why": "Много утилиты, контроль мида и игра через узкие проходы.",
        "drills": [
            "Смоки/молотовы на мид и донат",
            "Выход через пещеру и контроль B",
            "Ретейки A с использованием утилиты",
        ],
        "tags": {"utility", "trade", "survival", "entry"},
    },
    "Anubis": {
        "why": "Быстрые выходы, вода и контроль мида наказывают пассивную игру.",
        "drills": [
            "Контроль мида и вода",
            "Быстрый выход через палас",
            "Флешки на выход и ретрейд",
        ],
        "tags": {"entry", "aim", "flashes", "trade"},
    },
    "Dust2": {
        "why": "Длинные дистанции, контроль лонга и ранние дуэли.",
        "drills": [
            "Контроль long: смоки и префайр",
            "Быстрый B через тоннели",
            "AWP-углы и пики на дальней дистанции",
        ],
        "tags": {"aim", "entry", "utility"},
    },
    "Inferno": {
        "why": "Банан, аппартаменты и утилита решают больше, чем чистый аим.",
        "drills": [
            "Контроль банана: молотов/дым",
            "Выход через аппартаменты",
            "Ретейки B и A с флешками",
        ],
        "tags": {"utility", "flashes", "clutch", "trade"},
    },
    "Mirage": {
        "why": "Контроль мида, смок окна и связка jungle/connector.",
        "drills": [
            "Смок окна и коннектора",
            "Контроль мида и выход на A",
            "Флешки на выход и ретрейд",
        ],
        "tags": {"utility", "aim", "entry", "flashes"},
    },
    "Nuke": {
        "why": "Вертикальная карта, где важны звук, тайминги и позиционная игра.",
        "drills": [
            "Выход через outside и ramp",
            "Контроль вентиляции",
            "Ретейки A/B через этажи",
        ],
        "tags": {"survival", "clutch", "trade", "utility"},
    },
    "Overpass": {
        "why": "Долгие раунды, контроль монстра и игра на удержание.",
        "drills": [
            "Контроль монстра и банк",
            "Выход через длинный A",
            "Ретейки B с утилитой",
        ],
        "tags": {"survival", "utility", "trade", "clutch"},
    },
    "Train": {
        "why": "Много укрытий, поездов и нестандартных пиков.",
        "drills": [
            "Контроль ivy",
            "Выход через pop dog",
            "Пики на A из-за поездов",
        ],
        "tags": {"aim", "entry", "utility"},
    },
    "Vertigo": {
        "why": "Тесные проходы, рампа и быстрые размены.",
        "drills": [
            "Контроль рампы",
            "Выход через середину",
            "Ретейки A/B с флешками",
        ],
        "tags": {"entry", "aim", "flashes", "clutch"},
    },
}

WEAKNESS_LIBRARY = {
    "aim": {
        "title": "Стрельба и хедшоты",
        "detail": "Хедшотов мало, поэтому дуэли чаще затягиваются и заканчиваются разменом не в твою пользу.",
        "drill": "Aim Botz 20 минут: 100 тапов и 100 спреев, затем 15 минут DM с фокусом на первый выстрел.",
        "target": "Довести HS% до 40%+ и не терять темп в первых дуэлях.",
        "tags": {"aim", "entry"},
    },
    "impact": {
        "title": "Урон и влияние",
        "detail": "ADR ниже рабочего уровня: ты участвуешь в раундах, но наносишь мало урона до смерти.",
        "drill": "Retake-серверы 25 минут и 15 минут DM: цель — не меньше 75 урона за раунд.",
        "target": "ADR 70–75+ без потери KAST.",
        "tags": {"aim", "trade"},
    },
    "survival": {
        "title": "Выживаемость и KAST",
        "detail": "KAST низкий: часть раундов проходит без убийства, ассиста, выживания или трейда.",
        "drill": "20 минут ретейков и 15 минут игры на удержание: после действия не оставайся в открытом пространстве.",
        "target": "KAST 72%+ и меньше смертей в первых 20 секундах раунда.",
        "tags": {"survival", "trade", "clutch"},
    },
    "entry": {
        "title": "Первые дуэли",
        "detail": "Opening duels выигрываются реже половины: команда часто остаётся без пространства на входе.",
        "drill": "Prefire 15 минут + execute/retake 25 минут: отрабатывай первый контакт и выход с флешкой.",
        "target": "Entry success 50%+ на 5+ попытках.",
        "tags": {"entry", "aim", "flashes"},
    },
    "utility": {
        "title": "Урон утилитой",
        "detail": "Гранаты используются, но редко наносят урон или заставляют противника менять позицию.",
        "drill": "25 минут лайнапов на текущей карте: 3 смока, 2 молотова, 2 HE. Затем 15 минут executes.",
        "target": "6–8+ урона утилитой за раунд.",
        "tags": {"utility", "flashes"},
    },
    "flashes": {
        "title": "Эффективность флешек",
        "detail": "Флешки бросаются, но редко дают ослепление врагов дольше двух секунд.",
        "drill": "20 минут флешек на карте: отработай 5 связок под выход и 5 под ретрейк.",
        "target": "0.5+ эффективной флешки за раунд.",
        "tags": {"flashes", "utility", "entry"},
    },
    "teamflash": {
        "title": "Тимфлеши",
        "detail": "Свои флешки ослепляют союзников: это ломает тайминг выхода и ретрейка.",
        "drill": "20 минут командных флешек: проговаривай тайминг и не бросай флешку без команды «глаза».",
        "target": "0 тимфлешей за матч.",
        "tags": {"flashes", "trade"},
    },
    "trade": {
        "title": "Трейды и игра в паре",
        "detail": "Смерти редко размениваются: после потери игрока команда остаётся в меньшинстве.",
        "drill": "20 минут ретейков в паре и 15 минут DM: держи дистанцию размена и не отходи от партнёра.",
        "target": "Трейд-рейт 20%+ от своих смертей.",
        "tags": {"trade", "survival"},
    },
    "clutch": {
        "title": "Клатчи",
        "detail": "В ситуациях 1vX не хватает времени, утилиты или хладнокровия.",
        "drill": "20 минут 1vX-ретейков: сначала выходи на информацию, потом принимай бой. 10 минут разбора своих клатчей.",
        "target": "Clutch rate 40%+ на 4+ попытках.",
        "tags": {"clutch", "survival", "utility"},
    },
    "discipline": {
        "title": "Дисциплина и размены",
        "detail": "Смертей больше, чем убийств: ты часто входишь в бой без поддержки или утилиты.",
        "drill": "DM 15 минут + 25 минут командных выходов: не открывай дуэль без флешки или партнёра.",
        "target": "K/D 1.0+ и меньше одиночных смертей.",
        "tags": {"aim", "trade", "entry"},
    },
}

SESSION_PLANS = {
    "aim": {
        "title": "Аим и первый выстрел",
        "tasks": [
            "10 минут разогрев: тапы по головам",
            "20 минут Aim Botz: 100 тапов + 100 спреев",
            "20 минут DM: только первые дуэли",
        ],
        "minutes": 50,
    },
    "impact": {
        "title": "Урон и агрессия",
        "tasks": [
            "15 минут DM с фокусом на урон",
            "25 минут ретейков",
            "10 минут разбор своих смертей",
        ],
        "minutes": 50,
    },
    "survival": {
        "title": "Выживаемость и KAST",
        "tasks": [
            "10 минут разминка",
            "20 минут удержание позиций",
            "20 минут ретейков",
        ],
        "minutes": 50,
    },
    "entry": {
        "title": "Первые дуэли",
        "tasks": [
            "15 минут префайр",
            "25 минут execute/retake",
            "10 минут разбор opening duels",
        ],
        "minutes": 50,
    },
    "utility": {
        "title": "Утилита и лайнапы",
        "tasks": [
            "15 минут лайнапы смоков",
            "15 минут молотовы/HE",
            "20 минут executes",
        ],
        "minutes": 50,
    },
    "flashes": {
        "title": "Флешки",
        "tasks": [
            "20 минут лайнапы флешек",
            "20 минут связки под выход",
            "10 минут разбор тимфлешей",
        ],
        "minutes": 50,
    },
    "teamflash": {
        "title": "Командные флешки",
        "tasks": [
            "20 минут тайминги флешек",
            "20 минут выходы в паре",
            "10 минут разбор ошибок",
        ],
        "minutes": 50,
    },
    "trade": {
        "title": "Трейды",
        "tasks": [
            "20 минут ретейки в паре",
            "20 минут DM на размен",
            "10 минут разбор смертей",
        ],
        "minutes": 50,
    },
    "clutch": {
        "title": "Клатчи",
        "tasks": [
            "20 минут 1vX-ретейки",
            "15 минут сохранения/выходы",
            "15 минут разбор клатчей",
        ],
        "minutes": 50,
    },
    "discipline": {
        "title": "Дисциплина",
        "tasks": [
            "15 минут DM с фокусом на размен",
            "25 минут командные выходы",
            "10 минут разбор демки",
        ],
        "minutes": 50,
    },
}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def _rounds(report: dict[str, Any]) -> int:
    return max(int(_number(report.get("rounds"), 0.0)), 1)


def _clutch_summary(report: dict[str, Any]) -> dict[str, float]:
    won = 0
    lost = 0
    clutches = report.get("clutches") or {}
    for size in (1, 2, 3):
        entry = clutches.get(size) or {}
        won += int(_number(entry.get("won"), 0.0))
        lost += int(_number(entry.get("lost"), 0.0))
    attempts = won + lost
    return {
        "won": float(won),
        "lost": float(lost),
        "attempts": float(attempts),
        "rate": won / attempts * 100.0 if attempts else 0.0,
    }


def _side_record(demo: Any, sid: str) -> dict[str, Any]:
    rounds = {"T": 0, "CT": 0}
    wins = {"T": 0, "CT": 0}
    frame = getattr(demo, "round_info", None)
    if frame is None or getattr(frame, "empty", True):
        return {"rounds": rounds, "wins": wins}
    for row in frame.itertuples(index=False):
        side = demo.side_at(sid, getattr(row, "start_tick", None))
        winner = str(getattr(row, "winner", "") or "")
        if side not in rounds:
            continue
        rounds[side] += 1
        if winner == side:
            wins[side] += 1
    return {"rounds": rounds, "wins": wins}


def _weakness(
    key: str,
    priority: int,
    extra: str = "",
) -> dict[str, Any]:
    item = dict(WEAKNESS_LIBRARY[key])
    item["key"] = key
    item["priority"] = priority
    if extra:
        item["detail"] = f"{item['detail']} {extra}"
    return item


def _metric_findings(report: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rounds = _rounds(report)
    kills = _number(report.get("kills"))
    deaths = _number(report.get("deaths"))
    kd = _number(report.get("kd"), 0.0)
    adr = _number(report.get("adr"))
    kast = _number(report.get("kast"))
    hs = _number(report.get("hs_pct"))
    entry_kills = _number(report.get("entry_kills"))
    entry_deaths = _number(report.get("entry_deaths"))
    entry_attempts = entry_kills + entry_deaths
    entry_success = entry_kills / entry_attempts * 100.0 if entry_attempts else 0.0
    utility = _number(report.get("utility_damage")) / rounds
    flashes = _number(report.get("effective_flashes"))
    flash_attempts = _number(report.get("flash_throws"))
    flash_rate = flashes / flash_attempts if flash_attempts else 0.0
    team_flashes = _number(report.get("team_flashes"))
    team_flash_seconds = _number(report.get("team_flash_seconds"))
    traded = _number(report.get("traded"))
    trade_rate = traded / deaths if deaths else 0.0
    clutch = _clutch_summary(report)

    weaknesses: list[dict[str, Any]] = []
    strengths: list[str] = []

    if kd >= 1.15:
        strengths.append(f"Стабильный размен: K/D {kd:.2f}.")
    if adr >= 80:
        strengths.append(f"Высокий урон: ADR {adr:.1f}.")
    if kast >= 75:
        strengths.append(f"Хорошее участие в раундах: KAST {kast:.0f}%.")
    if hs >= 45:
        strengths.append(f"Сильная стрельба в голову: HS {hs:.0f}%.")
    if entry_attempts >= 4 and entry_success >= 55:
        strengths.append(f"Первые дуэли: {entry_success:.0f}% побед.")
    if utility >= 8:
        strengths.append(f"Утилита наносит {utility:.1f} урона за раунд.")
    if flash_attempts >= 5 and flash_rate >= 0.5:
        strengths.append(f"Флешки рабочие: {flash_rate:.2f} эффективной на бросок.")
    if clutch["attempts"] >= 3 and clutch["rate"] >= 50:
        strengths.append(f"Клатчи: {clutch['rate']:.0f}% побед.")
    if deaths >= 5 and trade_rate >= 0.25:
        strengths.append(f"Хорошие трейды: {trade_rate * 100:.0f}% смертей разменяны.")
    if flash_attempts >= 5 and team_flashes == 0 and team_flash_seconds < 1:
        strengths.append("Чистые флешки: союзники не слепли.")

    if hs < 35:
        weaknesses.append(
            _weakness(
                "aim",
                80 - hs,
                f"Сейчас HS {hs:.0f}% при цели 40%+.",
            )
        )
    if adr < 65:
        weaknesses.append(
            _weakness(
                "impact",
                70 - adr,
                f"ADR {adr:.1f} при рабочем уровне 70–75.",
            )
        )
    if kast < 70:
        weaknesses.append(
            _weakness(
                "survival",
                75 - kast,
                f"KAST {kast:.0f}% при цели 72%+.",
            )
        )
    if entry_attempts >= 4 and entry_success < 45:
        weaknesses.append(
            _weakness(
                "entry",
                50 - entry_success,
                f"Entry success {entry_success:.0f}% на {int(entry_attempts)} попытках.",
            )
        )
    if utility < 4:
        weaknesses.append(
            _weakness(
                "utility",
                50 - utility * 4,
                f"Урон утилитой {utility:.1f} за раунд.",
            )
        )
    if flash_attempts >= 5 and flash_rate < 0.35:
        weaknesses.append(
            _weakness(
                "flashes",
                50 - flash_rate * 50,
                f"Эффективных флешек {flashes:.0f} из {flash_attempts:.0f}.",
            )
        )
    if team_flashes >= 2 or team_flash_seconds >= 8:
        weaknesses.append(
            _weakness(
                "teamflash",
                60 + team_flashes * 4 + team_flash_seconds,
                f"Тимфлеши: {team_flashes:.0f} шт., {team_flash_seconds:.1f} сек.",
            )
        )
    if deaths >= 5 and trade_rate < 0.15:
        weaknesses.append(
            _weakness(
                "trade",
                30 - trade_rate * 50,
                f"Разменяно {trade_rate * 100:.0f}% смертей.",
            )
        )
    if clutch["attempts"] >= 4 and clutch["rate"] < 35:
        weaknesses.append(
            _weakness(
                "clutch",
                45 - clutch["rate"],
                f"Клатчи {int(clutch['won'])}W–{int(clutch['lost'])}L.",
            )
        )
    if deaths > kills and kd < 0.95:
        weaknesses.append(
            _weakness(
                "discipline",
                (deaths - kills) * 4 + 20,
                f"K/D {kd:.2f}: {int(kills)} убийств и {int(deaths)} смертей.",
            )
        )

    unique: dict[str, dict[str, Any]] = {}
    for item in sorted(weaknesses, key=lambda value: -value["priority"]):
        unique.setdefault(item["key"], item)
    return list(unique.values())[:4], strengths[:4]


def _find_group(groups: list[dict[str, Any]], sid: str) -> dict[str, Any] | None:
    for group in groups or []:
        if any(player.get("sid") == sid for player in group.get("players", [])):
            return group
    return None


def _canonical_map(map_name: str) -> str:
    lowered = (map_name or "").strip().lower().replace("de_", "")
    for name in MAP_GUIDE:
        if lowered == name.lower():
            return name
    return ""


def _map_plan(
    current_map: str,
    weaknesses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tags: list[str] = []
    for item in weaknesses:
        tags.extend(item.get("tags", set()))
    tag_weights = {tag: tags.count(tag) for tag in set(tags)}
    current = _canonical_map(current_map)
    chosen: list[dict[str, Any]] = []

    if current:
        guide = MAP_GUIDE[current]
        chosen.append(
            {
                "name": current,
                "why": f"Текущая карта. {guide['why']}",
                "drills": list(guide["drills"][:2]),
                "current": True,
            }
        )

    candidates = []
    for name, guide in MAP_GUIDE.items():
        if name == current:
            continue
        score = sum(tag_weights.get(tag, 0) for tag in guide["tags"])
        candidates.append((score, name, guide))
    candidates.sort(key=lambda value: (-value[0], value[1]))

    for score, name, guide in candidates:
        if len(chosen) >= 3:
            break
        if score <= 0 and current:
            continue
        reason = guide["why"]
        if score > 0:
            reason = f"{reason} Хорошо тренирует твои слабые места."
        chosen.append(
            {
                "name": name,
                "why": reason,
                "drills": list(guide["drills"][:2]),
                "current": False,
            }
        )

    if len(chosen) < 3:
        for name in ("Mirage", "Inferno", "Ancient", "Dust2", "Anubis"):
            if len(chosen) >= 3:
                break
            if any(item["name"] == name for item in chosen):
                continue
            guide = MAP_GUIDE[name]
            chosen.append(
                {
                    "name": name,
                    "why": guide["why"],
                    "drills": list(guide["drills"][:2]),
                    "current": False,
                }
            )
    return chosen[:3]


def _week_plan(weaknesses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys: list[str] = []
    for item in weaknesses:
        if item["key"] not in keys:
            keys.append(item["key"])
    if not keys:
        keys = ["aim", "utility", "trade"]
    base = ["aim", "utility", "entry", "trade", "clutch", "survival", "flashes"]
    for key in base:
        if len(keys) >= 4:
            break
        if key not in keys:
            keys.append(key)
    selected = keys[:3] + ["impact"] if "impact" not in keys[:3] else keys[:4]
    sessions = []
    for index, key in enumerate(selected[:4]):
        plan = SESSION_PLANS.get(key) or SESSION_PLANS["aim"]
        sessions.append(
            {
                "day": f"День {index + 1}",
                "title": plan["title"],
                "tasks": plan["tasks"],
                "minutes": plan["minutes"],
            }
        )
    sessions.append(
        {
            "day": f"День {len(sessions) + 1}",
            "title": "Разбор и закрепление",
            "tasks": [
                "20 минут разбор этой демки по раундам",
                "20 минут игра на текущей карте",
                "10 минут запись трёх ошибок на следующую неделю",
            ],
            "minutes": 50,
        }
    )
    return sessions[:5]


def build_local_plan(
    report: dict[str, Any],
    demo: Any,
    groups: list[dict[str, Any]],
    sid: str,
    map_name: str,
) -> dict[str, Any]:
    weaknesses, strengths = _metric_findings(report)
    group = _find_group(groups, sid) or {}
    score = int(_number(group.get("score"), 0.0))
    score_total = sum(
        int(_number(item.get("score"), 0.0))
        for item in (groups or [])[:2]
    )
    total_rounds = score_total or len(getattr(demo, "round_winners", {}) or {})
    if total_rounds <= 0:
        total_rounds = len(getattr(demo, "rounds", []) or [])
    side = _side_record(demo, sid)
    clutch = _clutch_summary(report)
    rounds = _rounds(report)
    kills = int(_number(report.get("kills")))
    deaths = int(_number(report.get("deaths")))
    adr = _number(report.get("adr"))
    kast = _number(report.get("kast"))

    side_parts = []
    for label in ("T", "CT"):
        count = side["rounds"][label]
        if count:
            side_parts.append(f"{label} {side['wins'][label]}/{count}")
    side_note = " · ".join(side_parts)

    if total_rounds:
        result = (
            "победа"
            if score > total_rounds / 2
            else "ничья"
            if score == total_rounds / 2
            else "поражение"
        )
        score_line = f"Счёт по раундам {score}:{total_rounds - score} ({result})."
    else:
        score_line = f"Раундов в демке: {rounds}."

    if weaknesses:
        focus_titles = ", ".join(item["title"].lower() for item in weaknesses[:3])
        summary = (
            f"{map_name or 'CS2'}: {score_line} K/D {_number(report.get('kd')):.2f}, "
            f"ADR {adr:.1f}, KAST {kast:.0f}%. "
            f"Главные зоны роста: {focus_titles}."
        )
    else:
        summary = (
            f"{map_name or 'CS2'}: {score_line} K/D {_number(report.get('kd')):.2f}, "
            f"ADR {adr:.1f}, KAST {kast:.0f}%. Явных провалов нет — "
            "закрепляй базу и повышай сложность тренировок."
        )

    if side_note:
        summary += f" По сторонам: {side_note}."

    if not strengths:
        strengths = [
            "Матч без выраженного пика: база ровная, следующий шаг — стабильность.",
            f"Сыграно {rounds} раундов, есть достаточно данных для плана.",
        ]

    if deaths and clutch["attempts"]:
        summary += f" Клатчи: {int(clutch['won'])}W–{int(clutch['lost'])}L."

    maps = _map_plan(map_name, weaknesses)
    week = _week_plan(weaknesses)
    return {
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "maps": maps,
        "week": week,
        "side_note": side_note,
        "score": score,
        "total_rounds": total_rounds,
    }


def build_prompt(
    report: dict[str, Any],
    local: dict[str, Any],
    map_name: str,
    player_name: str,
) -> list[dict[str, str]]:
    weakness_lines = "\n".join(
        f"- {item['title']}: {item['detail']} Цель: {item['target']}. Упражнение: {item['drill']}"
        for item in local["weaknesses"]
    ) or "- Явных провалов нет."
    strength_lines = "\n".join(f"- {item}" for item in local["strengths"])
    map_lines = "\n".join(
        f"- {item['name']}: {item['why']} Упражнения: {'; '.join(item['drills'])}"
        for item in local["maps"]
    )
    week_lines = "\n".join(
        f"- {item['day']}, {item['title']} ({item['minutes']} мин): {'; '.join(item['tasks'])}"
        for item in local["week"]
    )
    stats = (
        f"Карта: {map_name or 'неизвестна'}\n"
        f"Раунды: {report.get('rounds', 0)}\n"
        f"K/D: {_number(report.get('kd')):.2f} ({report.get('kills', 0)} K / {report.get('deaths', 0)} D)\n"
        f"ADR: {_number(report.get('adr')):.1f}\n"
        f"KAST: {_number(report.get('kast')):.1f}%\n"
        f"HS: {_number(report.get('hs_pct')):.1f}%\n"
        f"Entry: {report.get('entry_kills', 0)} kills / {report.get('entry_deaths', 0)} deaths\n"
        f"Урон утилитой: {_number(report.get('utility_damage')):.0f}\n"
        f"Эффективные флешки: {report.get('effective_flashes', 0)} из {report.get('flash_throws', 0)}\n"
        f"Тимфлеши: {report.get('team_flashes', 0)}\n"
        f"Трейды: {report.get('traded', 0)}\n"
        f"Клатчи: {int(round(_number(report.get('clutches', {}).get(1, {}).get('won', 0))))}W"
    )
    user = f"""Игрок: {player_name or 'игрок'}
{stats}

Сильные стороны:
{strength_lines}

Слабые стороны:
{weakness_lines}

Локальный план:
{map_lines}

Неделя:
{week_lines}

Составь разбор по структуре:
1. Главный вывод по матчу.
2. Три приоритета на ближайшую неделю.
3. Две карты для тренировки и почему именно они.
4. План на 5 дней с упражнениями и таймингом.

Требования: опирайся только на статистику выше, не выдумывай факты, пиши по-русски, конкретно и без воды. Не советуй читы и запрещённое ПО."""
    return [
        {
            "role": "system",
            "content": (
                "Ты опытный тренер по CS2. Ты помогаешь игрокам улучшать аим, "
                "утилиту, первые дуэли, трейды и клатчи. Ты пишешь структурированные, "
                "практичные советы на русском языке. Если данных мало, ты прямо говоришь об этом."
            ),
        },
        {"role": "user", "content": user},
    ]


def _api_key(settings: dict[str, Any]) -> str:
    return str(
        settings.get("api_key")
        or os.environ.get("PARSY_AI_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or ""
    ).strip()


def call_ai(
    settings: dict[str, Any],
    messages: list[dict[str, str]],
    timeout: float = 90.0,
) -> str:
    base_url = str(settings.get("base_url") or "").strip().rstrip("/")
    model = str(settings.get("model") or "").strip()
    if not base_url:
        raise RuntimeError("Не указан адрес AI API.")
    if not model:
        raise RuntimeError("Не указана модель AI.")
    key = _api_key(settings)
    if not key and "127.0.0.1" not in base_url and "localhost" not in base_url:
        raise RuntimeError("Не указан API-ключ.")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": 1100,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {key}" if key else "",
    }
    if "openrouter.ai" in base_url:
        headers["HTTP-Referer"] = "https://github.com/dponeNF/parsy"
        headers["X-Title"] = "Parsy"
    request = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")[:1200]
        try:
            message = json.loads(body).get("error", {}).get("message") or body
        except Exception:
            message = body
        raise RuntimeError(f"AI API вернул ошибку {error.code}: {message}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Не удалось подключиться к AI API: {error.reason}") from error
    except TimeoutError as error:
        raise RuntimeError("AI API не ответил вовремя.") from error

    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
        raise RuntimeError("AI API вернул неожиданный ответ.") from error
    if isinstance(content, list):
        content = "\n".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    text = str(content or "").strip()
    if not text:
        raise RuntimeError("AI API вернул пустой ответ.")
    return text


def generate_ai_advice(
    report: dict[str, Any],
    local: dict[str, Any],
    map_name: str,
    player_name: str,
    settings: dict[str, Any],
) -> str:
    return call_ai(settings, build_prompt(report, local, map_name, player_name))


def build_chat_context(
    report: dict[str, Any],
    local: dict[str, Any],
    map_name: str,
    player_name: str,
    rounds: list[dict[str, Any]] | None = None,
) -> str:
    stats = (
        f"Игрок: {player_name or 'игрок'}\n"
        f"Карта: {map_name or 'неизвестна'}\n"
        f"Счёт: {local.get('score', 0)}:{local.get('total_rounds', 0) - local.get('score', 0)}\n"
        f"Раунды: {report.get('rounds', 0)}\n"
        f"K/D: {_number(report.get('kd')):.2f} ({report.get('kills', 0)} K / {report.get('deaths', 0)} D)\n"
        f"ADR: {_number(report.get('adr')):.1f}\n"
        f"KAST: {_number(report.get('kast')):.1f}%\n"
        f"HS: {_number(report.get('hs_pct')):.1f}%\n"
        f"Entry: {report.get('entry_kills', 0)} / {report.get('entry_deaths', 0)}\n"
        f"Урон утилитой: {_number(report.get('utility_damage')):.0f}\n"
        f"Флешки: {report.get('effective_flashes', 0)} эффективных из {report.get('flash_throws', 0)}\n"
        f"Тимфлеши: {report.get('team_flashes', 0)}\n"
        f"Трейды: {report.get('traded', 0)}\n"
    )
    weaknesses = "\n".join(
        f"- {item['title']}: {item['detail']} Цель: {item['target']}."
        for item in local.get("weaknesses", [])
    ) or "- Явных провалов нет."
    plans = "\n".join(
        f"- {item['day']}, {item['title']}: {'; '.join(item['tasks'])}"
        for item in local.get("week", [])
    )
    round_lines = []
    for item in (rounds or [])[:24]:
        tags = ", ".join(item.get("tags", [])) or "без тегов"
        round_lines.append(
            f"R{item.get('round')}: {item.get('side')} {item.get('result')} "
            f"{item.get('score')}, {item.get('kills')}K/{item.get('deaths')}D, "
            f"{item.get('damage', 0):.0f} dmg, теги: {tags}, "
            f"первая дуэль: {item.get('first_duel') or '—'}."
        )
    return (
        f"Статистика:\n{stats}\n"
        f"Слабые стороны:\n{weaknesses}\n"
        f"План:\n{plans}\n"
        f"Раунды:\n" + "\n".join(round_lines)
    )


def local_chat_answer(
    question: str,
    report: dict[str, Any],
    local: dict[str, Any],
    map_name: str,
    player_name: str,
    rounds: list[dict[str, Any]] | None = None,
) -> str:
    text = (question or "").strip()
    lowered = text.lower()
    round_match = re.search(r"(?:раунд|round|r)\s*#?\s*(\d{1,2})", lowered)
    if round_match:
        number = int(round_match.group(1))
        item = next((row for row in (rounds or []) if int(row.get("round", 0)) == number), None)
        if not item:
            return f"Раунда {number} нет в разобранной демке или он не был сыгран игроком."
        tags = ", ".join(item.get("tags", [])) or "без тегов"
        clutch = item.get("clutch") or {}
        clutch_text = ""
        if clutch:
            clutch_text = (
                f" Клатч 1v{clutch.get('enemies')}: "
                f"{'выигран' if clutch.get('won') else 'проигран'}."
            )
        return (
            f"Раунд {number}: {item.get('side')} · {item.get('result')} "
            f"({item.get('score')}).\n"
            f"K/D/A: {item.get('kills')}/{item.get('deaths')}/{item.get('assists')}, "
            f"урон {item.get('damage', 0):.0f}.\n"
            f"Первая дуэль: {item.get('first_duel') or 'не зафиксирована'}.\n"
            f"Теги: {tags}.{clutch_text}\n"
            f"Ключевой вывод: {local.get('summary', '')}"
        )
    if any(word in lowered for word in ("почему", "проигр", "результат", "счет", "счёт")):
        weaknesses = local.get("weaknesses", [])
        focus = "; ".join(item["title"].lower() for item in weaknesses[:3])
        return (
            f"{local.get('summary', '')}\n\n"
            f"Главные причины: {focus or 'выраженных провалов нет'}. "
            f"Смотри раунды с тегами entry loss, no plant/no defuse, teamflash и low damage."
        )
    if any(word in lowered for word in ("тренир", "план", "что делать", "улучш", "недел")):
        lines = [
            f"{item['day']}: {item['title']} ({item['minutes']} мин) — {'; '.join(item['tasks'])}"
            for item in local.get("week", [])
        ]
        return "План на неделю:\n" + "\n".join(lines)
    if any(word in lowered for word in ("карта", "карты", "map")):
        lines = [
            f"{item['name']}: {item['why']} Упражнения: {'; '.join(item['drills'])}"
            for item in local.get("maps", [])
        ]
        return f"Текущая карта: {map_name}.\n" + "\n".join(lines)
    if any(word in lowered for word in ("клатч", "1v")):
        clutches = report.get("clutches") or {}
        won = sum(int(_number((clutches.get(size) or {}).get("won"))) for size in (1, 2, 3))
        lost = sum(int(_number((clutches.get(size) or {}).get("lost"))) for size in (1, 2, 3))
        return (
            f"Клатчи: {won}W–{lost}L. "
            f"В раундах с клатчем смотри теги clutch win/clutch loss: "
            f"важнее не количество, а решение перед первым контактом."
        )
    if any(word in lowered for word in ("аим", "стрель", "hs", "хедшот", "aim")):
        return (
            f"HS%: {_number(report.get('hs_pct')):.1f}%, K/D {_number(report.get('kd')):.2f}. "
            "Фокус: 20 минут Aim Botz на тапы и спреи, затем 15 минут DM с первой пулей в голову. "
            "Не тренируй аим отдельно от выхода: цель — выигрывать первый контакт."
        )
    if any(word in lowered for word in ("утилит", "флеш", "гранат", "смок")):
        return (
            f"Урон утилитой: {_number(report.get('utility_damage')):.0f}, "
            f"эффективных флешек: {report.get('effective_flashes', 0)}, "
            f"тимфлешей: {report.get('team_flashes', 0)}. "
            "Сначала убери тимфлеши, затем добавь 3 смока и 2 молотова под текущую карту."
        )
    if any(word in lowered for word in ("смерт", "умира", "позиц")):
        return (
            f"Смертей: {report.get('deaths', 0)} за {report.get('rounds', 0)} раундов. "
            f"В истории раундов ищи теги entry loss, no defuse и low damage. "
            f"Смотри карту активности: красные крестики — твои смерти."
        )
    if any(word in lowered for word in ("сильн", "хорош", "плюс")):
        return "Сильные стороны: " + "; ".join(local.get("strengths", []))
    if any(word in lowered for word in ("раунд", "демк", "разбор")):
        return (
            f"{local.get('summary', '')}\n\n"
            "Можно спросить конкретнее: «разбери раунд 5», «почему проиграли», "
            "«что тренировать», «где я умираю»."
        )
    return (
        f"{local.get('summary', '')}\n\n"
        f"Приоритеты: {'; '.join(item['title'] for item in local.get('weaknesses', [])[:3]) or 'стабильность'}. "
        "Спроси про конкретный раунд, карту или метрику — отвечу по данным этой демки."
    )


def chat_with_ai(
    question: str,
    report: dict[str, Any],
    local: dict[str, Any],
    map_name: str,
    player_name: str,
    rounds: list[dict[str, Any]] | None,
    history: list[dict[str, str]] | None,
    settings: dict[str, Any],
) -> str:
    context = build_chat_context(report, local, map_name, player_name, rounds)
    messages = [
        {
            "role": "system",
            "content": (
                "Ты тренер по CS2 и аналитик демок. Отвечай по-русски, кратко и конкретно. "
                "Опирайся только на переданный контекст. Если данных нет, скажи об этом. "
                "Не выдумывай раунды, цифры и факты. Не советуй читы и запрещённое ПО."
            ),
        }
    ]
    for item in (history or [])[-6:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": str(content)[:2500]})
    messages.append(
        {
            "role": "user",
            "content": f"Контекст демки:\n{context}\n\nВопрос игрока: {question}",
        }
    )
    return call_ai(settings, messages, timeout=60.0)
