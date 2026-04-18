from __future__ import annotations

import itertools
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st
import streamlit.components.v1 as components
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 15
APP_PASSWORD = os.getenv("APP_PASSWORD", "")
REQUEST_GAP_NOTICE = "手動ボタンで1回だけ取得する前提の設計です。連続取得は避けてください。"

BET_TYPE_LABELS = {
    "tansho": "単勝",
    "fukusho": "複勝",
    "umaren": "馬連",
    "wide": "ワイド",
    "umatan": "馬単",
    "sanrenpuku": "三連複",
    "sanrentan": "三連単",
}

BET_TYPE_QUERY_TYPES = {
    "tansho": ["b1", "a1"],
    "fukusho": ["b2", "a2"],
    "umaren": ["b4", "c4"],
    "wide": ["b5", "c5"],
    "umatan": ["b6", "c6"],
    "sanrenpuku": ["b7", "c7"],
    "sanrentan": ["b8", "c8"],
}


@dataclass
class Bet:
    selection: str
    amount: int
    source: str = ""


@dataclass
class BetResult:
    selection: str
    amount: int
    odds: Optional[float]
    odds_display: str = "-"
    payout: Optional[int] = None
    profit: Optional[int] = None
    is_trigami: Optional[bool] = None
    note: str = ""


def inject_mobile_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            font-size: 16px;
        }
        .block-container {
            max-width: 760px;
            padding-top: 5.8rem;
            padding-bottom: 4rem;
            padding-left: 0.95rem;
            padding-right: 0.95rem;
        }
        .app-hero {
            padding: 1rem 1rem 0.8rem 1rem;
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 18px;
            background: rgba(255,255,255,.03);
            margin-bottom: 0.9rem;
            box-shadow: 0 6px 18px rgba(0,0,0,.06);
        }
        .app-hero-title {
            font-size: 1.55rem;
            line-height: 1.25;
            font-weight: 800;
            margin: 0 0 .3rem 0;
            letter-spacing: -.01em;
        }
        .app-hero-sub {
            font-size: .96rem;
            color: rgba(250,250,250,.72);
            line-height: 1.5;
            margin: 0;
        }
        h1 {
            font-size: 1.55rem !important;
            line-height: 1.25 !important;
            margin-top: 0.25rem !important;
            margin-bottom: 0.35rem !important;
        }
        h2, h3 {
            font-size: 1.12rem !important;
            line-height: 1.35 !important;
        }
        p, li, label, .stMarkdown, .stCaption {
            font-size: .97rem !important;
            line-height: 1.55 !important;
        }
        .stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {
            border-radius: 14px !important;
            min-height: 3.1rem !important;
            font-size: 1rem !important;
        }
        .stTextArea textarea {
            min-height: 8.5rem !important;
            padding-top: .75rem !important;
        }
        .stButton > button, .stFormSubmitButton > button {
            min-height: 3.2rem;
            font-size: 1rem;
            font-weight: 700;
            border-radius: 14px;
            width: 100%;
        }
        div[data-testid="stMetric"] {
            background: rgba(255,255,255,.03);
            border: 1px solid rgba(128,128,128,.16);
            border-radius: 16px;
            padding: .7rem .85rem;
        }
        .stAlert {
            border-radius: 14px !important;
        }

        [data-testid="InputInstructions"] {
            display: none !important;
        }
        .stForm [data-testid="InputInstructions"] {
            display: none !important;
        }
        .result-card {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 16px;
            padding: 0.95rem 1rem;
            margin: 0.65rem 0;
            background: rgba(255,255,255,.03);
            box-shadow: 0 4px 14px rgba(0,0,0,.04);
        }
        .result-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: .55rem .7rem;
            margin-top: .55rem;
        }
        .result-label {
            color: #8e8e93;
            font-size: .82rem;
            margin-bottom: .14rem;
        }
        .result-value {
            font-weight: 700;
            word-break: break-word;
        }
        .pill-ok, .pill-bad, .pill-na {
            display: inline-block;
            padding: .28rem .68rem;
            border-radius: 999px;
            font-size: .82rem;
            font-weight: 800;
        }
        .pill-ok { background: rgba(0,200,83,.12); }
        .pill-bad { background: rgba(244,67,54,.15); }
        .pill-na { background: rgba(158,158,158,.18); }
        .mini-box {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 14px;
            padding: .85rem .95rem;
            margin: .45rem 0;
            background: rgba(255,255,255,.025);
        }
        .section-card {
            border: 1px solid rgba(128,128,128,.14);
            border-radius: 16px;
            padding: .4rem .45rem .1rem .45rem;
            background: rgba(255,255,255,.02);
            margin-bottom: .85rem;
        }
        @media (max-width: 640px) {
            .block-container {
                padding-top: 6.4rem;
                padding-left: 0.78rem;
                padding-right: 0.78rem;
                padding-bottom: 4.5rem;
            }
            .app-hero {
                padding: .95rem .9rem .8rem .9rem;
                border-radius: 16px;
            }
            .app-hero-title {
                font-size: 1.42rem;
            }
            .app-hero-sub {
                font-size: .93rem;
            }
            .result-grid {
                grid-template-columns: 1fr 1fr;
                gap: .48rem .6rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )




def render_top_hero(title: str, subtitle: str) -> None:
    st.markdown(
        f"<div class='app-hero'><div class='app-hero-title'>{title}</div><p class='app-hero-sub'>{subtitle}</p></div>",
        unsafe_allow_html=True,
    )

# =========================
# Parsing helpers
# =========================
def expected_selection_len(bet_type: str) -> int:
    return {
        "tansho": 1,
        "fukusho": 1,
        "umaren": 2,
        "wide": 2,
        "umatan": 2,
        "sanrenpuku": 3,
        "sanrentan": 3,
    }[bet_type]


def normalize_selection(selection: str, bet_type: str) -> str:
    nums = re.findall(r"\d+", selection)
    nums = [str(int(n)) for n in nums]
    if not nums:
        return selection.strip()

    if bet_type in {"umaren", "wide", "sanrenpuku"}:
        nums = sorted(nums, key=lambda x: int(x))

    if len(nums) == 1:
        return nums[0]
    return "-".join(nums)


def expand_selection_input(selection_text: str, bet_type: str, max_horses: int = 18) -> List[str]:
    text = selection_text.strip()
    if not text:
        return []

    need = expected_selection_len(bet_type)
    groups_raw = [g.strip() for g in text.split("-") if g.strip()]

    # 単勝・複勝は「1,3,5」や「1/3/5」にも対応
    if need == 1 and len(groups_raw) == 1:
        groups_raw = [re.sub(r"[／/]", ",", groups_raw[0])]

    if len(groups_raw) != need:
        return []

    groups: List[List[str]] = []
    for g in groups_raw:
        normalized_group = re.sub(r"[、/／\s]+", ",", g)
        upper_group = normalized_group.upper()
        if "ALL" in [token.strip().upper() for token in upper_group.split(",") if token.strip()]:
            nums = [str(n) for n in range(1, max_horses + 1)]
        else:
            nums = [str(int(n)) for n in re.findall(r"\d+", normalized_group)]
        if not nums:
            return []
        groups.append(nums)

    expanded: List[str] = []
    seen = set()
    for combo in itertools.product(*groups):
        if len(set(combo)) != need:
            continue
        if bet_type in {"umaren", "wide", "sanrenpuku"}:
            combo = tuple(sorted(combo, key=lambda x: int(x)))
        selection = "-".join(combo)
        if selection not in seen:
            seen.add(selection)
            expanded.append(selection)
    return expanded


def parse_bets(text: str, bet_type: str, max_horses: int = 18) -> Tuple[List[Bet], List[str], List[Tuple[int, str, List[str], int]]]:
    bets: List[Bet] = []
    errors: List[str] = []
    previews: List[Tuple[int, str, List[str], int]] = []

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [p for p in re.split(r"[\t ]+", line) if p]
        if len(parts) < 2:
            errors.append(f"{idx}行目: '買い目 金額' の形式で入力してください")
            continue
        amount_text = parts[-1]
        selection_text = " ".join(parts[:-1]).replace(" ", "")
        try:
            amount = int(amount_text)
        except ValueError:
            errors.append(f"{idx}行目: 金額は整数で入力してください")
            continue
        if amount <= 0 or amount % 100 != 0:
            errors.append(f"{idx}行目: 金額は100円単位の正の整数にしてください")
            continue

        expanded = expand_selection_input(selection_text, bet_type, max_horses=max_horses)
        if not expanded:
            errors.append(
                f"{idx}行目: 買い目を解釈できませんでした。"
                f" 券種{BET_TYPE_LABELS[bet_type]}なら 例: {example_for_bet_type(bet_type)}"
            )
            continue

        previews.append((idx, selection_text, expanded, amount))
        for selection in expanded:
            bets.append(Bet(selection=normalize_selection(selection, bet_type), amount=amount, source=selection_text))

    return bets, errors, previews


def parse_manual_odds(text: str, bet_type: str, max_horses: int = 18) -> Tuple[Dict[str, float], List[str]]:
    odds_map: Dict[str, float] = {}
    errors: List[str] = []
    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [p for p in re.split(r"[\t ]+", line) if p]
        if len(parts) < 2:
            errors.append(f"手動オッズ {idx}行目: '買い目 オッズ' の形式で入力してください")
            continue
        odds_text = parts[-1]
        selection_text = " ".join(parts[:-1]).replace(" ", "")
        try:
            odds = float(odds_text)
        except ValueError:
            errors.append(f"手動オッズ {idx}行目: オッズは数値で入力してください")
            continue

        expanded = expand_selection_input(selection_text, bet_type, max_horses=max_horses)
        if not expanded:
            errors.append(f"手動オッズ {idx}行目: 買い目を解釈できませんでした")
            continue

        for selection in expanded:
            odds_map[normalize_selection(selection, bet_type)] = odds
    return odds_map, errors


def example_for_bet_type(bet_type: str) -> str:
    return {
        "tansho": "3,5,8 100",
        "fukusho": "3,5,8 100",
        "umaren": "1-3,5,8 300 / 1-ALL 100",
        "wide": "1-3,5,8 300 / 1-ALL 100",
        "umatan": "1-3,5,8 300 / 1-ALL 100",
        "sanrenpuku": "1-2-3,4,5 300 / 1,2-3,4-ALL 100",
        "sanrentan": "1-2-3,4,5 300 / 1,2-3,4-ALL 100",
    }[bet_type]


# =========================
# Scraping
# =========================
def normalize_race_id(raw: str) -> str:
    value = (raw or "").strip()
    digits = re.sub(r"\D", "", value)
    return digits


def build_odds_urls(race_id: str, bet_type: str) -> List[str]:
    if bet_type in {"tansho", "fukusho"}:
        return [f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"]

    urls: List[str] = []
    for q in BET_TYPE_QUERY_TYPES.get(bet_type, []):
        urls.append(f"https://race.netkeiba.com/odds/index.html?type={q}&race_id={race_id}")
    urls.append(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}")
    urls.append(f"https://race.netkeiba.com/race/odds.html?race_id={race_id}")

    seen = set()
    ordered: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered




def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://race.netkeiba.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    with requests.Session() as session:
        response = session.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()

        html_bytes = response.content
        content_type = response.headers.get("Content-Type", "")

        # 1) Header charset
        m = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type, flags=re.I)
        if m:
            enc = m.group(1)
            try:
                return html_bytes.decode(enc, errors="replace")
            except Exception:
                pass

        # 2) Meta charset in head
        head_ascii = html_bytes[:4096].decode("ascii", errors="ignore")
        m = re.search(r'charset=["\']?([A-Za-z0-9_\-]+)', head_ascii, flags=re.I)
        if m:
            enc = m.group(1)
            try:
                return html_bytes.decode(enc, errors="replace")
            except Exception:
                pass

        # 3) Practical fallbacks
        for enc in [response.apparent_encoding, response.encoding, "EUC-JP", "cp932", "utf-8"]:
            if not enc:
                continue
            try:
                return html_bytes.decode(enc, errors="replace")
            except Exception:
                pass

        return html_bytes.decode("latin1", errors="replace")


def detect_field_size(html: str) -> Optional[int]:
    soup = BeautifulSoup(html, "html.parser")
    values: List[int] = []

    # Prefer race meta like "18頭"
    page_text = soup.get_text(" ", strip=True)
    m = re.search(r"(\d{1,2})頭", page_text)
    if m:
        n = int(m.group(1))
        if 1 <= n <= 18:
            return n

    # Fallback: collect visible horse numbers from odds/shutuba tables
    for table in soup.select("table"):
        for tr in table.select("tr"):
            cells = tr.select("th,td")
            for cell in cells:
                txt = cell.get_text(" ", strip=True)
                if re.fullmatch(r"\d{1,2}", txt):
                    n = int(txt)
                    if 1 <= n <= 18:
                        values.append(n)

    return max(values) if values else None


def build_race_context_urls(race_id: str) -> List[str]:
    return [
        f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}",
        f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}",
    ]


def _extract_horse_no_from_row(row, odds_span=None) -> Optional[str]:
    # Prefer odds span id suffix like odds-1_01 / odds-2_01
    if odds_span is not None:
        span_id = odds_span.get("id", "") if hasattr(odds_span, "get") else ""
        m = re.search(r"odds-\d+_(\d{1,2})$", span_id)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 18:
                return str(n)

    # Then look for a dedicated horse number cell if present
    candidate_texts: List[str] = []

    # cells with Waku class often contain horse number in second numeric cell
    for cell in row.select("td,th"):
        txt = cell.get_text(" ", strip=True)
        if re.fullmatch(r"\d{1,2}", txt):
            n = int(txt)
            if 1 <= n <= 18:
                candidate_texts.append(str(n))

    # If there are multiple numeric cells, first may be 枠(1-8), second is often 馬番
    if len(candidate_texts) >= 2:
        return candidate_texts[1]
    if len(candidate_texts) == 1:
        return candidate_texts[0]

    return None


def _detect_block_type(container, odds_span=None) -> Optional[str]:
    # 1) From id like odds-1_01 or odds-2_01
    if odds_span is not None:
        span_id = odds_span.get("id", "") if hasattr(odds_span, "get") else ""
        if span_id.startswith("odds-1_"):
            return "win"
        if span_id.startswith("odds-2_"):
            return "place"

    # 2) From nearest wrapper ids
    current = container
    for _ in range(6):
        if current is None:
            break
        node_id = current.get("id", "") if hasattr(current, "get") else ""
        classes = " ".join(current.get("class", [])) if hasattr(current, "get") else ""
        blob = f"{node_id} {classes}"
        if "odds_tan_block" in blob:
            return "win"
        if "odds_fuku_block" in blob:
            return "place"
        current = getattr(current, "parent", None)

    # 3) From nearby header text
    current = container
    for _ in range(4):
        if current is None:
            break
        h = current.select_one("h2")
        if h:
            txt = re.sub(r"\s+", "", h.get_text(" ", strip=True))
            if "単勝" in txt:
                return "win"
            if "複勝" in txt:
                return "place"
        current = getattr(current, "parent", None)
    return None


def fetch_horse_names(race_id: str) -> Dict[str, str]:
    race_id = normalize_race_id(race_id)
    if not race_id or len(race_id) != 12:
        return {}

    url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
    try:
        html = fetch_html(url)
    except Exception:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    horse_map: Dict[str, str] = {}

    # Primary: odds tables
    for row in soup.select("table.RaceOdds_HorseList_Table tr"):
        name_cell = row.select_one(".Horse_Name")
        if name_cell is None:
            continue
        odds_span = row.select_one("span[id^='odds-1_'], span[id^='odds-2_']")
        horse_no = _extract_horse_no_from_row(row, odds_span)
        if not horse_no:
            continue
        horse_name = re.sub(r"\s+", " ", name_cell.get_text(" ", strip=True)).strip()
        if horse_name:
            horse_map[horse_no] = horse_name

    return horse_map


def parse_win_place_table(html: str) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, str]]:
    """
    Robust parser for PC type=b1 page.
    Works even if wrappers shift slightly, as long as rows still contain:
    - Horse_Name cell
    - Odds cell/span
    - odds-1_XX / odds-2_XX ids OR nearby 単勝/複勝 context
    """
    soup = BeautifulSoup(html, "html.parser")
    win_map: Dict[str, float] = {}
    win_display: Dict[str, str] = {}
    place_map: Dict[str, float] = {}
    place_display: Dict[str, str] = {}

    def parse_place_text(raw: str) -> Tuple[Optional[float], Optional[str]]:
        raw = (
            (raw or "")
            .replace(",", "")
            .replace("〜", "-")
            .replace("～", "-")
            .replace("―", "-")
            .replace("–", "-")
            .replace("−", "-")
            .strip()
        )
        m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", raw)
        if m:
            low = float(m.group(1))
            high = float(m.group(2))
            return low, f"{low:.1f}-{high:.1f}"
        nums = re.findall(r"\d+(?:\.\d+)?", raw)
        if nums:
            val = float(nums[0])
            return val, f"{val:.1f}"
        return None, None

    seen_rows = set()

    # Primary strategy: iterate rows in RaceOdds_HorseList_Table
    for row in soup.select("table.RaceOdds_HorseList_Table tr"):
        cells = row.select("td,th")
        if len(cells) < 2:
            continue

        name_cell = row.select_one(".Horse_Name")
        odds_span = row.select_one("span[id^='odds-1_'], span[id^='odds-2_'], td.Odds span.Odds, .Odds span, span.Odds")
        odds_cell = row.select_one("td.Odds, .Popular")
        horse_no = _extract_horse_no_from_row(row, odds_span)
        if not horse_no:
            continue

        block_type = _detect_block_type(row, odds_span)
        if not block_type:
            # infer from row text: range => place, otherwise win
            probe = ""
            if odds_span is not None:
                probe = odds_span.get_text(" ", strip=True)
            elif odds_cell is not None:
                probe = odds_cell.get_text(" ", strip=True)
            block_type = "place" if re.search(r"\d+(?:\.\d+)?\s*[-〜～―–−]\s*\d+(?:\.\d+)?", probe) else "win"

        odds_text = ""
        if odds_span is not None:
            odds_text = odds_span.get_text(" ", strip=True)
        elif odds_cell is not None:
            odds_text = odds_cell.get_text(" ", strip=True)
        else:
            # fallback: last cell text if row has Horse_Name
            if name_cell is not None and cells:
                odds_text = cells[-1].get_text(" ", strip=True)

        if not odds_text:
            continue

        row_key = (block_type, horse_no)
        if row_key in seen_rows:
            continue
        seen_rows.add(row_key)

        if block_type == "win":
            nums = re.findall(r"\d+(?:\.\d+)?", odds_text.replace(",", ""))
            if nums:
                val = float(nums[0])
                win_map[horse_no] = val
                win_display[horse_no] = f"{val:.1f}"
        else:
            val, disp = parse_place_text(odds_text)
            if val is not None and disp is not None:
                place_map[horse_no] = val
                place_display[horse_no] = disp

    # Secondary fallback: direct id scan if rows changed a lot
    if not win_map:
        for span in soup.select("span[id^='odds-1_']"):
            m = re.search(r"odds-1_(\d{1,2})$", span.get("id", ""))
            if not m:
                continue
            horse_no = str(int(m.group(1)))
            nums = re.findall(r"\d+(?:\.\d+)?", span.get_text(" ", strip=True).replace(",", ""))
            if nums:
                val = float(nums[0])
                win_map[horse_no] = val
                win_display[horse_no] = f"{val:.1f}"

    if not place_map:
        for span in soup.select("span[id^='odds-2_']"):
            m = re.search(r"odds-2_(\d{1,2})$", span.get("id", ""))
            if not m:
                continue
            horse_no = str(int(m.group(1)))
            val, disp = parse_place_text(span.get_text(" ", strip=True))
            if val is not None and disp is not None:
                place_map[horse_no] = val
                place_display[horse_no] = disp

    return win_map, win_display, place_map, place_display


def scrape_netkeiba_odds(race_id: str, bet_type: str) -> Tuple[Dict[str, float], Dict[str, str], str, Optional[str]]:
    race_id = normalize_race_id(race_id)
    if not race_id or len(race_id) != 12:
        raise ValueError("レースIDが不正です。12桁のレースIDを入力してください。")

    candidate_urls: List[str] = build_odds_urls(race_id, bet_type)
    detected_field_size: Optional[int] = None

    for ctx_url in build_race_context_urls(race_id):
        try:
            ctx_html = fetch_html(ctx_url)
            detected_field_size = detect_field_size(ctx_html)
            if detected_field_size:
                break
        except Exception:
            pass

    last_error: Optional[Exception] = None
    last_url = candidate_urls[0]

    if bet_type in {"tansho", "fukusho"}:
        candidate_urls = [f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"]
        for url in candidate_urls:
            last_url = url
            try:
                html = fetch_html(url)
                local_field_size = detected_field_size or detect_field_size(html)
                win_map, win_display, place_map, place_display = parse_win_place_table(html)
                if local_field_size:
                    win_map = {k: v for k, v in win_map.items() if int(k) <= local_field_size}
                    win_display = {k: v for k, v in win_display.items() if int(k) <= local_field_size}
                    place_map = {k: v for k, v in place_map.items() if int(k) <= local_field_size}
                    place_display = {k: v for k, v in place_display.items() if int(k) <= local_field_size}

                if bet_type == "tansho" and win_map:
                    warning_parts = [f"認識頭数: {local_field_size}頭"] if local_field_size else []
                    return win_map, win_display, url, " / ".join(warning_parts) if warning_parts else None

                if bet_type == "fukusho" and place_map:
                    warning_parts = ["複勝の計算は下限オッズを使用します。"]
                    if local_field_size:
                        warning_parts.insert(0, f"認識頭数: {local_field_size}頭")
                    return place_map, place_display, url, " / ".join(warning_parts)
            except Exception as exc:
                last_error = exc

    for url in candidate_urls:
        last_url = url
        try:
            html = fetch_html(url)
            local_field_size = detected_field_size or detect_field_size(html)
            odds_map = extract_odds_candidates_from_tables(html, bet_type, field_size=local_field_size)
            if odds_map:
                odds_display = {k: f"{v:.1f}" for k, v in odds_map.items()}
                warning_parts = []
                if local_field_size:
                    warning_parts.append(f"認識頭数: {local_field_size}頭")
                if len(odds_map) < 2:
                    warning_parts.append("一部しか抽出できていない可能性があります。結果を確認してください。")
                warning = " / ".join(warning_parts) if warning_parts else None
                return odds_map, odds_display, url, warning
        except Exception as exc:
            last_error = exc

    warning = "オッズ抽出に失敗しました。netkeiba側のHTML構造が変わっている可能性があります。手動オッズ入力を使ってください。"
    if detected_field_size:
        warning += f" 認識頭数: {detected_field_size}頭。"
    if last_error is not None:
        warning += f" 直近エラー: {last_error}"
    return {}, {}, last_url, warning


# =========================
# Core calculations
# =========================
def calculate_results(bets: List[Bet], odds_map: Dict[str, float], odds_display_map: Optional[Dict[str, str]] = None) -> Tuple[List[BetResult], int]:
    total_stake = sum(b.amount for b in bets)
    results: List[BetResult] = []
    odds_display_map = odds_display_map or {}

    for bet in bets:
        odds = odds_map.get(bet.selection)
        if odds is None:
            results.append(
                BetResult(
                    selection=bet.selection,
                    amount=bet.amount,
                    odds=None,
                    odds_display="-",
                    payout=None,
                    profit=None,
                    is_trigami=None,
                    note="オッズ未取得",
                )
            )
            continue
        payout = int(round(bet.amount * odds))
        profit = payout - total_stake
        results.append(
            BetResult(
                selection=bet.selection,
                amount=bet.amount,
                odds=odds,
                odds_display=odds_display_map.get(bet.selection, f"{odds:.1f}"),
                payout=payout,
                profit=profit,
                is_trigami=profit < 0,
            )
        )
    return results, total_stake


def suggest_reallocation(bankroll: int, odds_map: Dict[str, float], selected_bets: List[Bet]) -> Tuple[List[Tuple[str, int, float, int, int]], str]:
    valid = [(b.selection, odds_map.get(b.selection)) for b in selected_bets if odds_map.get(b.selection) is not None]
    if not valid:
        return [], "再配分案を出すためのオッズが不足しています。"

    reciprocal_sum = sum(1 / odds for _, odds in valid if odds and odds > 0)
    if reciprocal_sum > 1:
        return [], "この買い目構成では、全てを非トリガミにする再配分は理論上できません。低オッズの買い目を減らすか除外してください。"

    raw = {sel: bankroll / odds for sel, odds in valid if odds}
    rounded = {sel: max(100, int(math.ceil(v / 100.0) * 100)) for sel, v in raw.items()}
    total = sum(rounded.values())

    if total > bankroll:
        items = sorted(valid, key=lambda x: x[1], reverse=True)
        i = 0
        while total > bankroll and i < 10000:
            sel, _ = items[i % len(items)]
            if rounded[sel] > 100:
                rounded[sel] -= 100
                total -= 100
            i += 1

    if total <= 0:
        return [], "再配分案を計算できませんでした。"

    proposal: List[Tuple[str, int, float, int, int]] = []
    for sel, odds in valid:
        amount = rounded[sel]
        payout = int(round(amount * odds))
        profit = payout - total
        proposal.append((sel, amount, odds, payout, profit))

    return proposal, "軍資金の範囲で、できるだけ全買い目が非トリガミになるよう100円単位で丸めた案です。"


def result_pill(result: BetResult) -> str:
    if result.is_trigami is True:
        return '<span class="pill-bad">トリガミ</span>'
    if result.is_trigami is False:
        return '<span class="pill-ok">OK</span>'
    return '<span class="pill-na">未判定</span>'


def render_result_cards(results: List[BetResult], horse_map: Dict[str, str]) -> None:
    for r in results:
        name = horse_map.get(r.selection, "")
        display_selection = f"{r.selection} {name}" if name else r.selection
        odds_text = f"{r.odds_display}倍" if r.odds is not None else "-"
        payout_text = f"{r.payout:,}円" if r.payout is not None else "-"
        profit_text = f"{r.profit:+,}円" if r.profit is not None else "-"
        note_text = r.note or "-"
        st.markdown(
            f"""
            <div class="result-card">
              <div style="display:flex; justify-content:space-between; align-items:center; gap:.6rem;">
                <div style="font-weight:700; font-size:1.02rem;">{display_selection}</div>
                <div>{result_pill(r)}</div>
              </div>
              <div class="result-grid">
                <div><div class="result-label">購入額</div><div class="result-value">{r.amount:,}円</div></div>
                <div><div class="result-label">オッズ</div><div class="result-value">{odds_text}</div></div>
                <div><div class="result-label">払戻見込</div><div class="result-value">{payout_text}</div></div>
                <div><div class="result-label">収支</div><div class="result-value">{profit_text}</div></div>
              </div>
              <div style="margin-top:.55rem;"><span class="result-label">備考</span> <span class="result-value">{note_text}</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )




def get_auth_cookies() -> Dict[str, str]:
    ctx = getattr(st, "context", None)
    cookies = getattr(ctx, "cookies", None) if ctx is not None else None
    if not cookies:
        return {}
    try:
        return dict(cookies)
    except Exception:
        return {}


def mark_auth_cookie(hours: int = 24) -> None:
    max_age = hours * 3600
    expires_at = int(time.time()) + max_age
    components.html(
        f"""
        <script>
        document.cookie = "tg_auth_ok=1; max-age={max_age}; path=/; SameSite=Lax";
        document.cookie = "tg_auth_exp={expires_at}; max-age={max_age}; path=/; SameSite=Lax";
        window.parent.location.reload();
        </script>
        """,
        height=0,
    )


def clear_auth_cookie() -> None:
    components.html(
        """
        <script>
        document.cookie = "tg_auth_ok=; max-age=0; path=/; SameSite=Lax";
        document.cookie = "tg_auth_exp=; max-age=0; path=/; SameSite=Lax";
        </script>
        """,
        height=0,
    )


def has_valid_auth_cookie() -> bool:
    cookies = get_auth_cookies()
    if cookies.get("tg_auth_ok") != "1":
        return False
    try:
        expires_at = int(cookies.get("tg_auth_exp", "0") or "0")
    except ValueError:
        return False
    if expires_at <= int(time.time()):
        clear_auth_cookie()
        return False
    return True

def require_access() -> None:
    if not APP_PASSWORD:
        return
    if st.session_state.get("auth_ok"):
        return
    if has_valid_auth_cookie():
        st.session_state.auth_ok = True
        return

    render_top_hero("🔐 アクセスコードを入力", "共有されたコードを入れると、このツールを開けます。24時間は再入力不要です。")
    st.warning("この公開アプリは簡易アクセスコードで保護されています。")
    st.markdown("<div class='section-card'>", unsafe_allow_html=True)
    code = st.text_input("アクセスコード", type="password", placeholder="共有されたコードを入力")
    if st.button("入る", use_container_width=True):
        if code == APP_PASSWORD:
            st.session_state.auth_ok = True
            st.success("認証しました。24時間は再入力不要です。")
            mark_auth_cookie(hours=24)
            st.stop()
        else:
            st.error("アクセスコードが違います。")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


def render_preview(previews: List[Tuple[int, str, List[str], int]]) -> None:
    if not previews:
        return
    with st.expander("買い目の展開結果を確認", expanded=True):
        for idx, source, expanded, amount in previews:
            preview_text = " / ".join(expanded[:12])
            if len(expanded) > 12:
                preview_text += f" / ...（残り{len(expanded) - 12}件）"
            st.markdown(
                f"<div class='mini-box'><b>{idx}行目</b> : <code>{source}</code><br>"
                f"→ <b>{len(expanded)}通り</b> ・1点 {amount:,}円<br>{preview_text}</div>",
                unsafe_allow_html=True,
            )


def main() -> None:
    st.set_page_config(page_title="競馬トリガミ回避ツール", page_icon="🏇", layout="centered")
    inject_mobile_css()
    require_access()

    render_top_hero("🏇 競馬トリガミ回避ツール", "スマホ向けに見やすく調整済みです。買い目の一括展開に対応し、ボタンを押した時だけ1回オッズ取得します。")

    with st.expander("使い方 / 入力例", expanded=False):
        st.markdown(
            """
            - 1行の末尾に購入額を書いてください。
            - 1行で複数通りをまとめて入力できます。
            - 例（三連複）: `1-2-3,4,5 300` → `1-2-3 / 1-2-4 / 1-2-5`
            - 例（三連複フォーメーション）: `1,2-3,4-5,6 100`
            - 例（馬連フォーメーション）: `1,2-3,4,5 500`
            - 例（ALL対応）: `1-ALL 100` / `1-2-ALL 100`
            - 例（単勝）: `3,5,8 100` → `3 / 5 / 8`
            - 「netkeibaから1回取得」を押した時だけ対象ページへ1回アクセスします。
            - 単勝・複勝は、馬番に対応する単勝列・複勝列から抽出します。
            - 取得に失敗した場合でも、手動オッズ入力で判定できます。
            """
        )

    if "last_odds_map" not in st.session_state:
        st.session_state.last_odds_map = {}
    if "last_fetch_url" not in st.session_state:
        st.session_state.last_fetch_url = None
    if "last_odds_display_map" not in st.session_state:
        st.session_state.last_odds_display_map = {}

    horse_map: Dict[str, str] = {}

    default_examples = {
        "tansho": "3,5,8 100",
        "fukusho": "3,5,8 100",
        "umaren": "1,2-3,4,5 300\n1-ALL 100",
        "wide": "1,2-3,4,5 300\n1-ALL 100",
        "umatan": "1,2-3,4,5 300\n1-ALL 100",
        "sanrenpuku": "1-2-3,4,5 300\n1,2-3,4-ALL 100",
        "sanrentan": "1-2-3,4,5 300\n1,2-3,4-ALL 100",
    }

    with st.form("bet_form", clear_on_submit=False, enter_to_submit=False):
        race_id = st.text_input("レースID", placeholder="例: 202609020611")
        bankroll = st.number_input("軍資金（円）", min_value=100, step=100, value=3000)
        max_horses = st.number_input("出走頭数（ALL用）", min_value=1, max_value=18, step=1, value=18, help="ALL を展開する時に使います。不明なら18のままでOKです。")
        bet_type = st.selectbox("券種", list(BET_TYPE_LABELS.keys()), format_func=lambda x: BET_TYPE_LABELS[x])
        st.info(REQUEST_GAP_NOTICE)

        bets_text = st.text_area(
            "買い目と購入額（1行で複数通り入力可 / 末尾に金額）",
            placeholder=default_examples[bet_type],
            height=150,
            help="例: 1-2-3,4,5 300 / 1,2-3,4-5,6 100 / 1-ALL 100 / 3,5,8 100",
        )
        manual_odds_text = st.text_area(
            "手動オッズ入力（任意。取得失敗時のフォールバック）",
            placeholder="1-2-3 12.5\n1-2-4 10.8\n1-2-5 18.2",
            height=130,
            help="例: 1-2-3 12.5 / 1-2-4 10.8 / 1-2-5 18.2",
        )

        btn1, btn2 = st.columns(2)
        with btn1:
            fetch_clicked = st.form_submit_button("netkeibaから1回取得", type="primary", use_container_width=True)
        with btn2:
            calc_manual_clicked = st.form_submit_button("手動オッズだけで計算", use_container_width=True)

    bets, bet_errors, previews = parse_bets(bets_text, bet_type, max_horses=int(max_horses))
    manual_odds, manual_errors = parse_manual_odds(manual_odds_text, bet_type, max_horses=int(max_horses))

    for err in bet_errors + manual_errors:
        st.error(err)

    if bets:
        total_points = len(bets)
        total_input_stake = sum(b.amount for b in bets)
        c1, c2 = st.columns(2)
        c1.metric("展開後の点数", f"{total_points}点")
        c2.metric("展開後の合計購入額", f"{total_input_stake:,}円")
        render_preview(previews)

    odds_map: Dict[str, float] = dict(manual_odds)
    odds_display_map: Dict[str, str] = {k: f"{v:.1f}" for k, v in manual_odds.items()}

    if race_id:
        try:
            horse_map = fetch_horse_names(race_id)
        except Exception:
            horse_map = {}

    if fetch_clicked:
        if not race_id:
            st.error("レースIDを入力してください。")
        else:
            try:
                fetched_odds, fetched_odds_display, fetched_url, warning = scrape_netkeiba_odds(race_id=race_id, bet_type=bet_type)
                st.session_state.last_odds_map = fetched_odds
                st.session_state.last_odds_display_map = fetched_odds_display
                st.session_state.last_fetch_url = fetched_url
                odds_map.update(fetched_odds)
                odds_display_map.update(fetched_odds_display)
                if fetched_odds:
                    st.success(f"取得完了: {len(fetched_odds)}件のオッズを抽出しました。")
                else:
                    st.warning("オッズを抽出できませんでした。手動オッズ入力を使ってください。")
                st.caption(f"取得元: {fetched_url}")
                if warning:
                    st.warning(warning)
            except Exception as exc:
                st.error(f"取得に失敗しました: {exc}")
                if manual_odds:
                    st.info("手動オッズ入力を使って計算できます。")
    elif st.session_state.last_odds_map:
        odds_map.update(st.session_state.last_odds_map)
        odds_display_map.update(st.session_state.last_odds_display_map)

    if calc_manual_clicked or fetch_clicked:
        if not bets:
            st.warning("買い目がありません。")
            return

        results, total_stake = calculate_results(bets, odds_map, odds_display_map)

        c1, c2, c3 = st.columns(3)
        c1.metric("総購入額", f"{total_stake:,}円")
        c2.metric("軍資金", f"{int(bankroll):,}円")
        trigami_count = sum(1 for r in results if r.is_trigami)
        c3.metric("トリガミ件数", f"{trigami_count}件")

        if total_stake > bankroll:
            st.warning("総購入額が軍資金を超えています。")

        tab_cards, tab_table, tab_realloc = st.tabs(["見やすい表示", "表で見る", "再配分案"])

        with tab_cards:
            render_result_cards(results, horse_map)
            missing_count = sum(1 for r in results if r.odds is None)
            if trigami_count:
                st.warning(f"トリガミの買い目が {trigami_count} 件あります。")
            else:
                st.success("取得できた買い目についてはトリガミなしです。")
            if missing_count:
                st.info(f"オッズ未取得の買い目が {missing_count} 件あります。")

        with tab_table:
            rows = []
            for r in results:
                rows.append({
                    "買い目": r.selection,
                    "購入額": r.amount,
                    "オッズ": r.odds_display if r.odds is not None else None,
                    "払戻見込": r.payout,
                    "収支": r.profit,
                    "判定": "トリガミ" if r.is_trigami else ("OK" if r.is_trigami is False else "未判定"),
                    "備考": r.note,
                })
            st.dataframe(rows, use_container_width=True, hide_index=True)

        with tab_realloc:
            proposal, message = suggest_reallocation(int(bankroll), odds_map, bets)
            st.write(message)
            if proposal:
                total_proposal = sum(x[1] for x in proposal)
                st.metric("提案総購入額", f"{total_proposal:,}円")
                proposal_rows = []
                for sel, amount, odds, payout, profit in proposal:
                    proposal_rows.append({
                        "買い目": sel,
                        "提案購入額": amount,
                        "オッズ": odds,
                        "払戻見込": payout,
                        "収支": profit,
                    })
                st.dataframe(proposal_rows, use_container_width=True, hide_index=True)

    elif st.session_state.last_fetch_url:
        st.caption(f"前回取得元: {st.session_state.last_fetch_url}")


if __name__ == "__main__":
    main()
