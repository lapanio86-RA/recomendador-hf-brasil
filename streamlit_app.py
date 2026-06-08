# -*- coding: utf-8 -*-
"""
Recomendador HF Brasil

Streamlit app online para recomendar bandas de radioamadorismo de 160m a 6m
com base nos dados SAO publicados pelo INPE/Embrace.
"""

from __future__ import annotations

import html
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import requests
import streamlit as st


BASE_URL = "https://embracedata.inpe.br/ionosonde"
DAYS_BACK = 3
CACHE_TTL_SECONDS = 300
UTC = timezone.utc
BRT = timezone(timedelta(hours=-3), name="BRT")


STATIONS = [
    ("BLJ03", "Belem"),
    ("SAA0K", "Sao Luis"),
    ("FZA0M", "Fortaleza"),
    ("BVJ03", "Boa Vista"),
    ("CGK21", "Campo Grande"),
    ("CAJ2M", "Cachoeira Paulista"),
    ("SMK29", "Santa Maria"),
    ("JUA0P", "Juazeirinho"),
]


GROUP4_FIELDS = [
    ("foF2", "MHz"),
    ("foF1", "MHz"),
    ("M_D", ""),
    ("MUF_D", "MHz"),
    ("fmin", "MHz"),
    ("foEs", "MHz"),
    ("fminF", "MHz"),
    ("fminE", "MHz"),
    ("foE", "MHz"),
    ("fxI", "MHz"),
    ("hF", "km"),
    ("hF2", "km"),
    ("hE", "km"),
    ("hEs", "km"),
    ("hmE", "km"),
    ("yE", "km"),
    ("QF", "km"),
    ("QE", "km"),
    ("DownF", "km"),
    ("DownE", "km"),
    ("DownEs", "km"),
    ("FF", "MHz"),
    ("FE", "MHz"),
    ("D", "km"),
    ("fMUF", "MHz"),
    ("hMUF", "km"),
    ("delta_foF2", "MHz"),
    ("foEp", "MHz"),
    ("f_hF", "MHz"),
    ("f_hF2", "MHz"),
    ("foF1p", "MHz"),
    ("hmF2", "km"),
    ("hmF1", "km"),
    ("zhalfNm", "km"),
    ("foF2p", "MHz"),
    ("fminEs", "MHz"),
    ("yF2", "km"),
    ("yF1", "km"),
    ("TEC", "TECU"),
    ("scaleF2", "km"),
    ("B0", "km"),
    ("B1", ""),
    ("D1", ""),
    ("foEa", "MHz"),
    ("hEa", "km"),
    ("foP", "MHz"),
    ("hP", "km"),
    ("fbEs", "MHz"),
    ("typeEs", ""),
]


HAM_BANDS = [
    {"band": "160m", "freq": 1.84},
    {"band": "80m", "freq": 3.65},
    {"band": "60m", "freq": 5.357},
    {"band": "40m", "freq": 7.1},
    {"band": "30m", "freq": 10.125},
    {"band": "20m", "freq": 14.2},
    {"band": "17m", "freq": 18.118},
    {"band": "15m", "freq": 21.225},
    {"band": "12m", "freq": 24.94},
    {"band": "10m", "freq": 28.5},
    {"band": "6m", "freq": 50.1},
]


STATUS_RANK = {
    "bom": 3,
    "razoavel": 2,
    "ruim": 1,
    "sem_dado": 0,
}


@dataclass
class SaoFile:
    filename: str
    url: str
    timestamp_utc: datetime


@dataclass
class ParsedSAO:
    station: str | None
    station_name: str | None
    timestamp_utc: datetime | None
    values: dict[str, float | None]


def fmt_num(value: float | None, decimals: int = 2) -> str:
    if value is None:
        return "sem dado"
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return "sem dado"
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


def fmt_mhz(value: float | None) -> str:
    return "sem dado" if value is None else f"{fmt_num(value)} MHz"


def clean_value(value: float | None) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    if abs(value - 9999.0) < 0.001 or abs(value - 999.9) < 0.001:
        return None
    return value


def parse_sao_filename(filename: str) -> SaoFile | None:
    match = re.match(r"^([A-Z0-9]+)_(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})\.SAO$", filename, re.I)
    if not match:
        return None
    _station, year, doy, hh, mm, ss = match.groups()
    base = datetime(int(year), 1, 1, tzinfo=UTC) + timedelta(days=int(doy) - 1)
    timestamp = base.replace(hour=int(hh), minute=int(mm), second=int(ss), microsecond=0)
    return SaoFile(filename=filename, url="", timestamp_utc=timestamp)


def day_of_year_utc(dt: datetime) -> int:
    start = datetime(dt.year, 1, 1, tzinfo=UTC)
    current = datetime(dt.year, dt.month, dt.day, tzinfo=UTC)
    return (current - start).days + 1


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_text(url: str) -> str:
    response = requests.get(
        url,
        timeout=25,
        headers={
            "User-Agent": "Mozilla/5.0 INPE-HF-Brasil/1.0",
            "Accept": "text/html,text/plain,*/*",
            "Cache-Control": "no-cache",
        },
    )
    response.raise_for_status()
    return response.text


def list_remote_sao(station: str, last_count: int = 6) -> list[SaoFile]:
    station = station.upper().strip()
    now = datetime.now(UTC)
    items: list[SaoFile] = []

    for offset in range(DAYS_BACK + 1):
        dt = now - timedelta(days=offset)
        year = dt.year
        doy = str(day_of_year_utc(dt)).zfill(3)
        dir_url = f"{BASE_URL}/{station}/{year}/{doy}/"
        try:
            html_text = fetch_text(dir_url)
        except Exception:
            continue

        pattern = re.compile(rf"{re.escape(station)}_\d{{13}}\.SAO", re.I)
        for filename in sorted(set(pattern.findall(html_text))):
            item = parse_sao_filename(filename)
            if item:
                item.url = dir_url + filename
                items.append(item)

    items.sort(key=lambda item: item.timestamp_utc, reverse=True)
    return items[:last_count]


def parse_data_index(lines: list[str]) -> list[int]:
    raw = (lines[0] if len(lines) > 0 else "").ljust(120)
    raw += (lines[1] if len(lines) > 1 else "").ljust(120)
    values = []
    for i in range(0, 240, 3):
        text = raw[i : i + 3].strip()
        values.append(int(text) if text else 0)
    return [0] + values


def take_fixed(lines: list[str], pos: int, count: int, width: int, per_line: int) -> tuple[list[float | None], int]:
    line_count = math.ceil(count / per_line) if count else 0
    raw = "".join(line.ljust(width * per_line) for line in lines[pos : pos + line_count])
    values: list[float | None] = []
    for i in range(count):
        text = raw[i * width : (i + 1) * width].strip()
        try:
            values.append(float(text) if text else None)
        except ValueError:
            values.append(None)
    return values, pos + line_count


def take_text(lines: list[str], pos: int, count: int, mode: str = "chars") -> tuple[str, int]:
    if mode == "lines":
        return "\n".join(lines[pos : pos + count]), pos + count
    line_count = math.ceil(count / 120) if count else 0
    text = "".join(line.ljust(120) for line in lines[pos : pos + line_count])[:count]
    return text, pos + line_count


def parse_timestamp_group3(group3: str) -> datetime | None:
    if not group3 or len(group3) < 19:
        return None
    try:
        year = int(group3[2:6])
        month = int(group3[9:11])
        day = int(group3[11:13])
        hour = int(group3[13:15])
        minute = int(group3[15:17])
        second = int(group3[17:19])
        return datetime(year, month, day, hour, minute, second, tzinfo=UTC)
    except Exception:
        return None


def parse_sao_text(text: str) -> ParsedSAO:
    lines = text.replace("\r", "").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if len(lines) < 3:
        raise ValueError("Arquivo SAO muito curto ou invalido.")

    idx = parse_data_index(lines)
    pos = 2

    _, pos = take_fixed(lines, pos, idx[1] if len(idx) > 1 else 0, 7, 16)
    group2, pos = take_text(lines, pos, idx[2] if len(idx) > 2 else 0, "lines")
    group3, pos = take_text(lines, pos, idx[3] if len(idx) > 3 else 0, "chars")
    group4_count = idx[4] if len(idx) > 4 else 0
    group4, _pos = take_fixed(lines, pos, group4_count, 8, 15)

    cleaned = [clean_value(value) for value in group4]
    values = {
        key: cleaned[i] if i < len(cleaned) else None
        for i, (key, _unit) in enumerate(GROUP4_FIELDS)
    }

    station_match = re.search(r"/([A-Z0-9]+)\b", group2.strip())
    name_match = re.search(r"\bNAME\s+([^,]+)", group2.strip(), re.I)
    return ParsedSAO(
        station=station_match.group(1) if station_match else None,
        station_name=name_match.group(1).strip() if name_match else None,
        timestamp_utc=parse_timestamp_group3(group3),
        values=values,
    )


def get_value(parsed: ParsedSAO, key: str) -> float | None:
    return parsed.values.get(key)


def calc_muf(parsed: ParsedSAO) -> float | None:
    fof2 = get_value(parsed, "foF2")
    factor = get_value(parsed, "M_D")
    field = get_value(parsed, "MUF_D")
    calculated = fof2 * factor if fof2 is not None and factor is not None else None
    return calculated if calculated is not None else field


def muf_for_distance(parsed: ParsedSAO, distance_km: int) -> float | None:
    fof2 = get_value(parsed, "foF2")
    if not fof2:
        return None
    height = get_value(parsed, "hmF2") or get_value(parsed, "hF2") or 300.0
    m3000 = get_value(parsed, "M_D")
    if distance_km == 3000 and m3000:
        factor = m3000
    else:
        factor = math.sqrt(1.0 + (distance_km / (2.0 * height)) ** 2)
        if m3000:
            factor = min(factor, m3000)
    return fof2 * factor


def classify_frequency(freq: float, limit: float | None, fmin: float | None = None) -> dict[str, str]:
    if limit is None:
        return {"status": "sem_dado", "label": "Sem dado", "detail": "referencia ausente"}
    if fmin is not None and fmin > freq:
        return {
            "status": "ruim",
            "label": "Ruim",
            "detail": f"fmin {fmt_mhz(fmin)} acima da faixa",
        }

    margin = limit - freq
    detail = f"ref {fmt_mhz(limit)} | {margin:+.2f} MHz"
    if freq <= limit * 0.82:
        return {"status": "bom", "label": "Bom", "detail": detail}
    if freq <= limit * 0.96:
        return {"status": "razoavel", "label": "Razoavel", "detail": detail}
    if freq <= limit * 1.05:
        return {"status": "razoavel", "label": "Limite", "detail": detail}
    return {"status": "ruim", "label": "Ruim", "detail": detail}


def classify_6m(parsed: ParsedSAO, mode: str) -> dict[str, str]:
    muf = calc_muf(parsed)
    foes = get_value(parsed, "foEs")

    if mode == "local":
        return {
            "status": "sem_dado",
            "label": "Sem leitura",
            "detail": "INPE SAO nao mede tropo/local",
        }

    if muf is not None and muf >= 50.1:
        return {"status": "bom", "label": "Bom", "detail": f"F2 rara | MUF {fmt_mhz(muf)}"}

    if foes is None:
        return {"status": "sem_dado", "label": "Sem dado", "detail": "foEs ausente"}
    if foes >= 10.0:
        return {"status": "bom", "label": "Bom", "detail": f"foEs {fmt_mhz(foes)} forte"}
    if foes >= 7.0:
        return {"status": "razoavel", "label": "Monitorar", "detail": f"foEs {fmt_mhz(foes)}"}
    return {"status": "ruim", "label": "Ruim", "detail": f"foEs {fmt_mhz(foes)}"}


def classify_band(parsed: ParsedSAO, band: str, freq: float) -> dict[str, dict[str, str] | str | float]:
    if band == "6m":
        return {
            "band": band,
            "freq": freq,
            "local": classify_6m(parsed, "local"),
            "regional": classify_6m(parsed, "regional"),
            "dx": classify_6m(parsed, "dx"),
        }

    fmin = get_value(parsed, "fmin")
    return {
        "band": band,
        "freq": freq,
        "local": classify_frequency(freq, get_value(parsed, "foF2"), fmin=fmin),
        "regional": classify_frequency(freq, muf_for_distance(parsed, 800), fmin=fmin),
        "dx": classify_frequency(freq, calc_muf(parsed), fmin=fmin),
    }


def band_rows(parsed: ParsedSAO) -> list[dict[str, dict[str, str] | str | float]]:
    return [classify_band(parsed, item["band"], item["freq"]) for item in HAM_BANDS]


def best_bands(rows: list[dict[str, object]], mode: str) -> list[str]:
    valid = []
    for row in rows:
        cell = row[mode]
        if isinstance(cell, dict) and STATUS_RANK[cell["status"]] >= STATUS_RANK["razoavel"]:
            valid.append((STATUS_RANK[cell["status"]], float(row["freq"]), str(row["band"])))
    valid.sort(reverse=True)
    return [band for _rank, _freq, band in valid]


def css() -> str:
    return """
<style>
    .block-container {
        max-width: 1600px;
        padding: 3.2rem 0.8rem 0.8rem 0.8rem;
    }
    .hf-shell {
        background: #151719;
        border: 1px solid #2d3338;
        border-radius: 8px;
        padding: 12px 14px;
        color: #f6f7f9;
        font-family: Arial, sans-serif;
    }
    .hf-title {
        font-size: 28px;
        font-weight: 800;
        letter-spacing: 0;
        margin: 0;
    }
    .hf-subtitle {
        color: #c8d0d8;
        font-size: 13px;
        margin: 2px 0 9px 0;
    }
    .metric-grid {
        display: grid;
        gap: 7px;
        margin-bottom: 7px;
    }
    .metric-grid {
        grid-template-columns: repeat(5, minmax(0, 1fr));
    }
    .summary-strip {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 7px;
        margin-bottom: 6px;
    }
    .summary-pill {
        background: #24292d;
        border: 1px solid #3a424a;
        border-radius: 6px;
        color: #ffffff;
        font-size: 13px;
        font-weight: 800;
        padding: 5px 8px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .summary-pill span {
        color: #bac4ce;
        font-size: 11px;
        text-transform: uppercase;
        margin-right: 6px;
    }
    .muf-ruler {
        background: #0f1114;
        border: 1px solid #303740;
        border-radius: 6px;
        margin: 7px 0 6px 0;
        padding: 7px 10px 5px 10px;
    }
    .ruler-title {
        color: #dbe4ec;
        font-size: 12px;
        font-weight: 800;
        margin-bottom: 4px;
        text-transform: uppercase;
    }
    .ruler-track {
        position: relative;
        height: 74px;
        background:
            linear-gradient(to right, rgba(255,255,255,0.08) 1px, transparent 1px),
            linear-gradient(to right, #d84a36 0%, #e9b735 24%, #42c979 55%, #27c7d9 100%);
        background-size: 14.285% 100%, 100% 100%;
        border-radius: 4px;
        border: 1px solid rgba(255,255,255,0.16);
        overflow: hidden;
    }
    .ruler-marker {
        position: absolute;
        top: var(--marker-top);
        left: var(--marker-left);
        transform: translateX(-50%);
        z-index: 3;
    }
    .ruler-marker-label {
        background: var(--marker-color);
        color: #101010;
        border-radius: 3px;
        padding: 2px 5px;
        font-size: 10px;
        font-weight: 900;
        white-space: nowrap;
        box-shadow: 0 1px 3px rgba(0,0,0,0.35);
    }
    .ruler-band {
        position: absolute;
        left: var(--band-left);
        bottom: 2px;
        transform: translateX(-50%);
        color: #ffffff;
        font-size: 9px;
        font-weight: 800;
        text-shadow: 0 1px 2px #000;
        white-space: nowrap;
    }
    .ruler-band::before {
        content: "";
        position: absolute;
        left: 50%;
        bottom: 12px;
        height: 10px;
        border-left: 1px solid rgba(255,255,255,0.7);
    }
    .ruler-scale {
        display: grid;
        grid-template-columns: repeat(8, 1fr);
        color: #aeb8c2;
        font-size: 10px;
        margin-top: 2px;
    }
    .ruler-scale span {
        text-align: left;
    }
    .ruler-scale span:last-child {
        text-align: right;
    }
    .metric-card, .summary-card {
        background: #24292d;
        border: 1px solid #3a424a;
        border-radius: 6px;
        padding: 7px 9px;
        min-height: 58px;
    }
    .card-title {
        color: #bac4ce;
        font-size: 11px;
        font-weight: 700;
        text-transform: uppercase;
    }
    .card-value {
        color: #ffffff;
        font-size: 21px;
        font-weight: 800;
        line-height: 1.1;
        margin-top: 3px;
    }
    .card-detail {
        color: #d5dce2;
        font-size: 11px;
        margin-top: 3px;
    }
    .band-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 5px;
        table-layout: fixed;
        margin-top: 2px;
    }
    .band-table th {
        color: #c8d0d8;
        font-size: 11px;
        font-weight: 800;
        text-transform: uppercase;
        text-align: left;
        padding: 1px 8px;
    }
    .band-table td {
        border: 1px solid rgba(255,255,255,0.13);
        border-radius: 6px;
        padding: 5px 8px;
        vertical-align: middle;
        height: 32px;
        overflow: hidden;
    }
    .band-col {
        width: 72px;
    }
    .freq-col {
        width: 82px;
    }
    .band-cell, .freq-cell {
        background: #24292d;
        color: #ffffff;
        font-weight: 800;
    }
    .freq-cell {
        color: #d7dee5;
        font-size: 12px;
        font-weight: 700;
    }
    .status-label {
        display: block;
        font-size: 15px;
        font-weight: 900;
        line-height: 1;
    }
    .status-detail {
        display: block;
        font-size: 9px;
        margin-top: 2px;
        line-height: 1.2;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .bom {
        background: #0b6b3a;
        color: #ffffff;
    }
    .razoavel {
        background: #d29b00;
        color: #171717;
    }
    .ruim {
        background: #8f1d2c;
        color: #ffffff;
    }
    .sem_dado {
        background: #4f5661;
        color: #ffffff;
    }
    .note {
        color: #b8c1ca;
        font-size: 11px;
        margin-top: 6px;
    }
    @media (max-width: 900px) {
        .metric-grid, .summary-strip {
            grid-template-columns: 1fr;
        }
        .status-label {
            font-size: 14px;
        }
        .status-detail {
            font-size: 10px;
        }
    }
</style>
"""


def safe(text: object) -> str:
    return html.escape(str(text))


def metric_card(title: str, value: str, detail: str) -> str:
    return f"""
<div class="metric-card">
    <div class="card-title">{safe(title)}</div>
    <div class="card-value">{safe(value)}</div>
    <div class="card-detail">{safe(detail)}</div>
</div>
"""


def summary_card(title: str, value: str, detail: str) -> str:
    return f"""
<div class="summary-card">
    <div class="card-title">{safe(title)}</div>
    <div class="card-value">{safe(value)}</div>
    <div class="card-detail">{safe(detail)}</div>
</div>
"""


def pct_mhz(value: float, max_mhz: float = 35.0) -> float:
    return max(0.0, min(100.0, value / max_mhz * 100.0))


def render_muf_ruler(parsed: ParsedSAO) -> str:
    marker_defs = [
        ("fmin", get_value(parsed, "fmin"), "#ff5b3d", "4px"),
        ("foE", get_value(parsed, "foE"), "#ffd447", "19px"),
        ("foEs", get_value(parsed, "foEs"), "#b093ff", "34px"),
        ("foF2", get_value(parsed, "foF2"), "#59d4ff", "49px"),
        ("MUF", calc_muf(parsed), "#ffffff", "4px"),
    ]

    markers = ""
    for label, value, color, top in marker_defs:
        if value is None:
            continue
        markers += f"""
        <div class="ruler-marker" style="--marker-left:{pct_mhz(value):.2f}%; --marker-color:{safe(color)}; --marker-top:{safe(top)};">
            <div class="ruler-marker-label">{safe(label)} {safe(fmt_num(value, 1))}</div>
        </div>
"""

    bands = ""
    for item in HAM_BANDS:
        if item["band"] == "6m":
            continue
        bands += f"""
        <div class="ruler-band" style="--band-left:{pct_mhz(float(item['freq'])):.2f}%;">{safe(item['band'])}</div>
"""

    scale = "".join(f"<span>{value}</span>" for value in [0, 5, 10, 15, 20, 25, 30, 35])
    return f"""
<div class="muf-ruler">
    <div class="ruler-title">Regua 0-35 MHz: bandas e marcadores SAO</div>
    <div class="ruler-track">
        {markers}
        {bands}
    </div>
    <div class="ruler-scale">{scale}</div>
</div>
"""


def status_td(cell: dict[str, str]) -> str:
    status = cell["status"]
    return f"""
<td class="{safe(status)}">
    <span class="status-label">{safe(cell["label"])}</span>
    <span class="status-detail">{safe(cell["detail"])}</span>
</td>
"""


def render_dashboard(station_label: str, item: SaoFile, parsed: ParsedSAO) -> str:
    rows = band_rows(parsed)
    ts = parsed.timestamp_utc or item.timestamp_utc
    brt = ts.astimezone(BRT)
    age_min = round((datetime.now(UTC) - item.timestamp_utc).total_seconds() / 60)
    station_title = parsed.station or station_label.split(" - ", 1)[0]
    station_name = parsed.station_name or station_label.split(" - ", 1)[-1]

    metric_html = "".join([
        metric_card("foF2", fmt_mhz(get_value(parsed, "foF2")), "base local/NVIS"),
        metric_card("MUF(3000)", fmt_mhz(calc_muf(parsed)), "base DX F2"),
        metric_card("fmin", fmt_mhz(get_value(parsed, "fmin")), "absorve abaixo deste valor"),
        metric_card("foEs", fmt_mhz(get_value(parsed, "foEs")), "alerta de E esporadica"),
        metric_card("TEC", fmt_num(get_value(parsed, "TEC")), "informacao complementar"),
    ])

    local_best = best_bands(rows, "local")
    regional_best = best_bands(rows, "regional")
    dx_best = best_bands(rows, "dx")
    summary_html = f"""
<div class="summary-strip">
    <div class="summary-pill"><span>Local</span>{safe(", ".join(local_best[:5]) or "sem banda clara")}</div>
    <div class="summary-pill"><span>Regional</span>{safe(", ".join(regional_best[:5]) or "sem banda clara")}</div>
    <div class="summary-pill"><span>DX</span>{safe(", ".join(dx_best[:5]) or "sem banda clara")}</div>
</div>
"""

    table = """
<table class="band-table">
    <colgroup>
        <col class="band-col">
        <col class="freq-col">
        <col>
        <col>
        <col>
    </colgroup>
    <thead>
        <tr>
            <th>Banda</th>
            <th>Freq.</th>
            <th>Local</th>
            <th>Regional</th>
            <th>DX</th>
        </tr>
    </thead>
    <tbody>
"""
    for row in rows:
        table += f"""
        <tr>
            <td class="band-cell">{safe(row["band"])}</td>
            <td class="freq-cell">{safe(fmt_mhz(float(row["freq"])))}</td>
            {status_td(row["local"])}
            {status_td(row["regional"])}
            {status_td(row["dx"])}
        </tr>
"""
    table += """
    </tbody>
</table>
"""

    return f"""
{css()}
<div class="hf-shell">
    <h1 class="hf-title">Recomendador HF Brasil</h1>
    <div class="hf-subtitle">
        Recomendacao de bandas para radioamadorismo com dados SAO do INPE/Embrace |
        {safe(station_title)} - {safe(station_name)} | {safe(ts.strftime("%Y-%m-%d %H:%M UTC"))}
        ({safe(brt.strftime("%H:%M BRT"))}) | idade {safe(age_min)} min
    </div>
    <div class="metric-grid">{metric_html}</div>
    {summary_html}
    {render_muf_ruler(parsed)}
    {table}
    <div class="note">
        Leitura baseada no ultimo arquivo SAO publicado pelo INPE/Embrace. Local, regional e DX sao avaliados separadamente; uma banda pode estar boa para DX e ruim para local.
    </div>
</div>
"""


def load_latest(station_code: str) -> tuple[SaoFile, ParsedSAO]:
    items = list_remote_sao(station_code)
    if not items:
        raise RuntimeError("Nenhum arquivo SAO encontrado para esta estacao nos ultimos dias.")
    latest = items[0]
    text = fetch_text(latest.url)
    return latest, parse_sao_text(text)


def main() -> None:
    st.set_page_config(
        page_title="Recomendador HF Brasil",
        layout="wide",
    )

    st.markdown(
        """
<style>
    .block-container{padding-top:3.2rem!important;}
    div[data-testid="stButton"] > button {
        margin-top: 1.65rem;
        height: 2.55rem;
    }
    div[data-testid="stCaptionContainer"] {
        padding-top: 1.95rem;
    }
</style>
""",
        unsafe_allow_html=True,
    )

    station_labels = [f"{code} - {name}" for code, name in STATIONS]
    control_col, refresh_col, cache_col = st.columns([4, 1.2, 0.8])
    with control_col:
        selected = st.selectbox(
            "Estacao de dados INPE/Embrace",
            station_labels,
            index=station_labels.index("CAJ2M - Cachoeira Paulista"),
        )
    with refresh_col:
        if st.button("Atualizar", use_container_width=True):
            st.cache_data.clear()
    with cache_col:
        st.caption(f"cache {CACHE_TTL_SECONDS // 60} min")

    station_code = selected.split(" - ", 1)[0]

    with st.spinner("Buscando ultimo SAO no INPE/Embrace..."):
        try:
            item, parsed = load_latest(station_code)
        except Exception as exc:
            st.error(f"Nao foi possivel carregar dados: {exc}")
            return

    dashboard_html = render_dashboard(selected, item, parsed)
    if hasattr(st, "html"):
        st.html(dashboard_html)
    else:
        st.markdown(dashboard_html, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
