"""Numeric fact-checking: verify a statistic against primary data (World Bank), with a
graceful web-search fallback. Almost no research tool checks the *numbers* — this does.

Designed to never hang and never raise: the World Bank endpoint can be slow, so calls are
time-bounded and fall back to a web search rather than blocking the MCP server.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

import httpx

from .search import web_search

WORLD_BANK_URL = "https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
_WB_TIMEOUT = 15.0

# Curated map of common metrics -> World Bank indicator codes. Keys are matched as
# substrings against the claim / metric hint (longest match wins).
WORLD_BANK_INDICATORS = {
    "gdp growth": "NY.GDP.MKTP.KD.ZG",
    "gdp grew": "NY.GDP.MKTP.KD.ZG",
    "gdp grow": "NY.GDP.MKTP.KD.ZG",
    "economic growth": "NY.GDP.MKTP.KD.ZG",
    "gdp per capita": "NY.GDP.PCAP.CD",
    "gdp": "NY.GDP.MKTP.CD",
    "unemployment": "SL.UEM.TOTL.ZS",
    "inflation": "FP.CPI.TOTL.ZG",
    "population growth": "SP.POP.GROW",
    "population grew": "SP.POP.GROW",
    "population": "SP.POP.TOTL",
    "life expectancy": "SP.DYN.LE00.IN",
    "co2 emissions per capita": "EN.ATM.CO2E.PC",
    "co2": "EN.ATM.CO2E.PC",
    "poverty": "SI.POV.DDAY",
    "gini": "SI.POV.GINI",
    "labor force": "SL.TLF.TOTL.IN",
    "government debt": "GC.DOD.TOTL.GD.ZS",
    "exports": "NE.EXP.GNFS.ZS",
    "imports": "NE.IMP.GNFS.ZS",
    "foreign direct investment": "BX.KLT.DINV.WD.GD.ZS",
    "electricity access": "EG.ELC.ACCS.ZS",
    "internet users": "IT.NET.USER.ZS",
}

# Common country names/aliases -> ISO3 (avoids a lookup round-trip for the frequent cases).
_COUNTRY_ISO3 = {
    "united states": "USA", "usa": "USA", "us": "USA", "america": "USA",
    "united kingdom": "GBR", "uk": "GBR", "britain": "GBR", "england": "GBR",
    "india": "IND", "china": "CHN", "japan": "JPN", "germany": "DEU", "france": "FRA",
    "italy": "ITA", "spain": "ESP", "canada": "CAN", "australia": "AUS", "brazil": "BRA",
    "russia": "RUS", "mexico": "MEX", "south korea": "KOR", "korea": "KOR",
    "indonesia": "IDN", "netherlands": "NLD", "saudi arabia": "SAU", "turkey": "TUR",
    "switzerland": "CHE", "world": "WLD", "european union": "EUU", "eu": "EUU",
    "nigeria": "NGA", "south africa": "ZAF", "egypt": "EGY", "pakistan": "PAK",
    "bangladesh": "BGD", "vietnam": "VNM", "argentina": "ARG",
}

_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def _resolve_country(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.strip().lower()
    if len(t) == 3 and t.upper().isalpha():
        return t.upper()
    if t in _COUNTRY_ISO3:
        return _COUNTRY_ISO3[t]
    for name, iso in _COUNTRY_ISO3.items():
        if name in t:
            return iso
    return None


def _resolve_indicator(text: str, explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit
    t = text.lower()
    for phrase in sorted(WORLD_BANK_INDICATORS, key=len, reverse=True):
        if phrase in t:
            return WORLD_BANK_INDICATORS[phrase]
    return None


def _parse_claimed_value(claim: str, explicit: Optional[float]) -> Optional[float]:
    if explicit is not None:
        return float(explicit)
    m = _NUM_RE.search(claim)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _fetch_worldbank(country: str, indicator: str, year: Optional[int]) -> Dict[str, Any]:
    params: Dict[str, Any] = {"format": "json", "per_page": 5}
    if year:
        params["date"] = str(year)
    url = WORLD_BANK_URL.format(country=country, indicator=indicator)
    with httpx.Client(timeout=_WB_TIMEOUT, follow_redirects=True) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        return {"ok": False, "error": "No data for that indicator/country/year."}
    rows = [r for r in data[1] if r.get("value") is not None]
    if not rows:
        return {"ok": False, "error": "Indicator has no value for that year."}
    row = rows[0]
    return {"ok": True, "value": row["value"], "year": row["date"],
            "indicator_name": row["indicator"]["value"]}


def verify_stat(
    claim: str,
    country: Optional[str] = None,
    year: Optional[int] = None,
    claimed_value: Optional[float] = None,
    indicator: Optional[str] = None,
) -> Dict[str, Any]:
    """Verify a numeric/statistical claim against World Bank primary data.

    Works best when you (the host model) extract the structured pieces from the claim and
    pass them in; it also does best-effort keyword mapping on its own.

    Args:
        claim: The statement to check, e.g. "US GDP grew 2.5% in 2023".
        country: Country name or ISO3 (e.g. "United States" / "USA").
        year: The year the claim refers to.
        claimed_value: The numeric value asserted (e.g. 2.5). Parsed from `claim` if omitted.
        indicator: A World Bank indicator code to force (e.g. "NY.GDP.MKTP.KD.ZG");
            otherwise mapped from the claim text. See WORLD_BANK_INDICATORS for supported metrics.

    Returns {"ok": True, "claim", "verdict" ('verified'|'contradicted'|'unverified'),
             "source", "indicator", "country", "year", "actual_value", "claimed_value",
             "notes"}. Never raises; falls back to a web search if the data source is
             unavailable.
    """
    iso3 = _resolve_country(country) or _resolve_country(claim)
    ind = _resolve_indicator(claim, indicator)
    claimed = _parse_claimed_value(claim, claimed_value)

    if iso3 and ind:
        try:
            wb = _fetch_worldbank(iso3, ind, year)
        except Exception as e:  # noqa: BLE001 - never hang/raise; degrade to web search
            wb = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        if wb.get("ok"):
            actual = wb["value"]
            verdict, notes = "unverified", ""
            if claimed is not None:
                tol = max(abs(actual) * 0.05, 0.5)
                if abs(actual - claimed) <= tol:
                    verdict = "verified"
                    notes = f"Claimed {claimed}; World Bank reports {actual:.3g} ({wb['indicator_name']}, {wb['year']}). Within tolerance."
                else:
                    verdict = "contradicted"
                    notes = f"Claimed {claimed}, but World Bank reports {actual:.3g} ({wb['indicator_name']}, {wb['year']})."
            else:
                notes = f"World Bank reports {actual:.3g} for {wb['indicator_name']} ({wb['year']}). No claimed value to compare."
            return {"ok": True, "claim": claim, "verdict": verdict, "source": "world_bank",
                    "indicator": ind, "country": iso3, "year": wb["year"],
                    "actual_value": actual, "claimed_value": claimed, "notes": notes}

    # Fallback: couldn't resolve country/indicator, or the data source was unavailable.
    web = web_search(claim, max_results=3, academic_only=False)
    hint = []
    if not iso3:
        hint.append("could not resolve a country (pass `country`)")
    if not ind:
        hint.append("could not map the metric to a World Bank indicator (pass `indicator`)")
    return {
        "ok": True, "claim": claim, "verdict": "unverified", "source": "web_fallback",
        "indicator": ind, "country": iso3, "year": year,
        "actual_value": None, "claimed_value": claimed,
        "notes": ("Fell back to web search" + (f" ({'; '.join(hint)})" if hint else " (World Bank unavailable)")
                  + ". " + (web.get("answer") or "See web results; verify manually.")),
    }
