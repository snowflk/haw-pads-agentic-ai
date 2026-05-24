from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

from shared.schemas import DomainRecord

OPENLIGADB_BASE_URL = "https://api.openligadb.de"


class DomainApiError(RuntimeError):
    pass


def find_team_matches(
    team_name: str,
    season: int = 2025,
    league_shortcut: str = "bl1",
    limit: int = 5,
) -> list[DomainRecord]:
    """Find matches for one team in a league season."""
    payload = _get_json(f"/getmatchdata/{league_shortcut}/{season}/{team_name}")
    if not isinstance(payload, list):
        return []

    rows: list[DomainRecord] = []
    now = datetime.utcnow()
    enriched: list[tuple[float, dict[str, Any]]] = []
    for match in payload:
        if not isinstance(match, dict):
            continue
        match_time = _parse_match_time(match)
        # Sort by "closest to now" so users get practical results quickly.
        delta = abs((match_time - now).total_seconds()) if match_time else float("inf")
        enriched.append((delta, match))

    enriched.sort(key=lambda item: item[0])
    for _, match in enriched[: max(1, min(limit, 20))]:
        home_name = _nested_str(match, "team1", "teamName") or "Unknown Team"
        away_name = _nested_str(match, "team2", "teamName") or "Unknown Team"
        score = _score_text(match)
        status = "finished" if bool(match.get("matchIsFinished")) else "scheduled"
        kickoff = _nested_str(match, "matchDateTime")
        group_name = _nested_str(match, "group", "groupName")
        title = f"{home_name} vs {away_name}"
        desc = f"{score} | {status}"
        if kickoff:
            desc += f" | kickoff: {kickoff}"
        if group_name:
            desc += f" | {group_name}"

        rows.append(
            DomainRecord(
                id=str(match.get("matchID", title)),
                title=title,
                description=desc,
                source="openligadb:getmatchdata",
                metadata={
                    "league_shortcut": league_shortcut,
                    "season": str(season),
                    "status": status,
                    "kickoff": kickoff or "",
                    "group": group_name or "",
                },
            )
        )
    return rows


def get_league_table(
    season: int = 2025,
    league_shortcut: str = "bl1",
    limit: int = 5,
) -> list[DomainRecord]:
    """Get current league table rows."""
    payload = _get_json(f"/getbltable/{league_shortcut}/{season}")
    if not isinstance(payload, list):
        return []

    rows: list[DomainRecord] = []
    for idx, team in enumerate(payload[: max(1, min(limit, 20))], start=1):
        if not isinstance(team, dict):
            continue
        team_name = str(team.get("teamName", "Unknown Team"))
        points = str(team.get("points", ""))
        goal_diff = str(team.get("goalDiff", ""))
        matches = str(team.get("matches", ""))
        title = f"#{idx} {team_name}"
        desc = f"{points} points | goal diff {goal_diff} | matches {matches}"
        rows.append(
            DomainRecord(
                id=f"{season}:{idx}:{team.get('teamInfoId', team_name)}",
                title=title,
                description=desc,
                source="openligadb:getbltable",
                metadata={
                    "league_shortcut": league_shortcut,
                    "season": str(season),
                    "points": points,
                    "goal_diff": goal_diff,
                    "matches": matches,
                },
            )
        )
    return rows


def serialize_domain_records(records: list[DomainRecord]) -> list[dict[str, Any]]:
    return [record.model_dump() for record in records]


def _get_json(path: str) -> Any:
    url = f"{OPENLIGADB_BASE_URL}{path}"
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        raise DomainApiError(f"OpenLigaDB request failed for {url}: {exc}") from exc
    except ValueError as exc:
        raise DomainApiError(f"OpenLigaDB response is not valid JSON for {url}: {exc}") from exc


def _nested_str(obj: dict[str, Any], *keys: str) -> str | None:
    cur: Any = obj
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    if cur is None:
        return None
    return str(cur)


def _score_text(match: dict[str, Any]) -> str:
    results = match.get("matchResults")
    if not isinstance(results, list):
        return "no score yet"
    final = None
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("resultTypeID") == 2:
            final = item
            break
        final = item
    if not isinstance(final, dict):
        return "no score yet"
    p1 = final.get("pointsTeam1")
    p2 = final.get("pointsTeam2")
    if p1 is None or p2 is None:
        return "no score yet"
    return f"{p1}:{p2}"


def _parse_match_time(match: dict[str, Any]) -> datetime | None:
    raw = match.get("matchDateTimeUTC") or match.get("matchDateTime")
    if not isinstance(raw, str) or not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).replace(tzinfo=None)
    except ValueError:
        return None
