
from __future__ import annotations

import itertools
import math
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st
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
    "fukusho": ["b1", "a2", "b2"],
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
        [data-testid="InputInstructions"] {
            display: none !important;
        }
        .result-card {
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 16px;
            padding: 0.95rem 1rem;
            margin: 0.65rem 0;
            background: rgba(255,255,255,.03);
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
            background: rgba(255,255,255,.03);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def check_password_gate() -> bool:
    inject_mobile_css()
    if not APP_PASSWORD:
        return True

    if st.session_state.get("authed"):
        return True

    st.markdown(
        """
        <div class="app-hero">
          <div class="app-hero-title">アクセスコード入力</div>
          <p class="app-hero-sub">アクセスコードを入力してアプリを開いてください。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    code = st.text_input("アクセスコード", type="password", placeholder="アクセスコードを入力")
    if st.button("開く"):
        if code == APP_PASSWORD:
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("アクセスコードが違います。")
    return False


def normalize_number_token(token: str) -> Optional[str]:
    token = token.strip()
    if not re.fullmatch(r"\d{1,2}", token):
        return None
    value = int(token)
    if 1 <= value <= 18:
        return str(value)
    return None


def normalize_selection(selection: str, bet_type: str) -> str:
    nums = [str(int(x)) for x in re.findall(r"\d{1,2}", selection)]
    if bet_type in {"tansho", "fukusho"}:
        return nums[0] if nums else selection.strip()

    if bet_type in {"umaren", "wide", "sanrenpuku"}:
        nums = sorted(nums, key=lambda x: int(x))
    return "-".join(nums)


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


def expand_token_group(part: str, max_horses: int) -> List[str]:
    part = part.strip().upper()
    if part == "ALL":
        return [str(i) for i in range(1, max_horses + 1)]

    values: List[str] = []
    for item in part.split(","):
        token = normalize_number_token(item)
        if token is not None:
            values.append(token)
    return values


def expand_selection_input(selection_text: str, bet_type: str, max_horses: int = 18) -> List[str]:
    selection_text = selection_text.replace(" ", "").strip()
    if not selection_text:
        return []

    if bet_type in {"tansho", "fukusho"}:
        out = []
        for token in expand_token_group(selection_text, max_horses):
            out.append(token)
        return sorted(set(out), key=lambda x: int(x))

    parts = selection_text.split("-")
    need = expected_selection_len(bet_type)
    if len(parts) != need:
        return []

    groups = [expand_token_group(part, max_horses) for part in parts]
    if any(not g for g in groups):
        return []

    combos = []
    seen = set()
    for combo in itertools.product(*groups):
        if len(set(combo)) != need:
            continue
        normalized = normalize_selection("-".join(combo), bet_type)
        if normalized not in seen:
            seen.add(normalized)
            combos.append(normalized)

    def sort_key(s: str):
        return tuple(int(x) for x in s.split("-"))

    return sorted(combos, key=sort_key)


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
        selection_text = "".join(parts[:-1]).replace(" ", "")
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
            errors.append(f"{idx}行目: 買い目を解釈できませんでした")
            continue

        previews.append((idx, selection_text, expanded, amount))
        for selection in expanded:
            bets.append(Bet(selection=normalize_selection(selection, bet_type), amount=amount, source=selection_text))

    return bets, errors, previews


def parse_manual_odds(text: str, bet_type: str, max_horses: int = 18) -> Tuple[Dict[str, float], Dict[str, str], List[str]]:
    odds_map: Dict[str, float] = {}
    odds_display: Dict[str, str] = {}
    errors: List[str] = []

    for idx, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        parts = [p for p in re.split(r"[\t ]+", line) if p]
        if len(parts) < 2:
            errors.append(f"手動オッズ {idx}行目: '買い目 オッズ' の形式で入力してください")
            continue
        odds_text = parts[-1].strip()
        selection_text = "".join(parts[:-1]).replace(" ", "")

        expanded = expand_selection_input(selection_text, bet_type, max_horses=max_horses)
        if not expanded:
            errors.append(f"手動オッズ {idx}行目: 買い目を解釈できませんでした")
            continue

        display_text = odds_text.replace("〜", "-").replace("～", "-")
        numeric_odds: Optional[float] = None
        if bet_type == "fukusho":
            m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", display_text)
            if m:
                numeric_odds = float(m.group(1))
                display_text = f"{float(m.group(1)):.1f}-{float(m.group(2)):.1f}"
            else:
                try:
                    numeric_odds = float(display_text)
                    display_text = f"{numeric_odds:.1f}"
                except ValueError:
                    errors.append(f"手動オッズ {idx}行目: 複勝オッズは 4.4-8.0 または 4.4 の形式で入力してください")
                    continue
        else:
            try:
                numeric_odds = float(display_text)
                display_text = f"{numeric_odds:.1f}"
            except ValueError:
                errors.append(f"手動オッズ {idx}行目: オッズは数値で入力してください")
                continue

        for selection in expanded:
            norm = normalize_selection(selection, bet_type)
            odds_map[norm] = float(numeric_odds)
            odds_display[norm] = display_text

    return odds_map, odds_display, errors


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


def normalize_race_id(raw: str) -> str:
    return re.sub(r"\D", "", (raw or "").strip())


def build_odds_urls(race_id: str, bet_type: str) -> List[str]:
    urls: List[str] = []
    for q in BET_TYPE_QUERY_TYPES.get(bet_type, []):
        urls.append(f"https://race.netkeiba.com/odds/index.html?type={q}&race_id={race_id}")
    urls.append(f"https://race.netkeiba.com/odds/index.html?race_id={race_id}")
    urls.append(f"https://race.netkeiba.com/race/odds.html?race_id={race_id}")
    out = []
    seen = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


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
        response.encoding = response.apparent_encoding or response.encoding
        return response.text


def fetch_horse_names(race_id: str) -> Dict[str, str]:
    race_id = normalize_race_id(race_id)
    if not race_id or len(race_id) != 12:
        return {}

    url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
    try:
        html = fetch_html(url)
    except Exception:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    horse_map: Dict[str, str] = {}

    for table in soup.select("table"):
        rows = table.select("tr")
        if len(rows) < 2:
            continue

        headers = [re.sub(r"\s+", "", c.get_text(" ", strip=True)) for c in rows[0].select("th,td")]
        horse_idx = None
        name_idx = None

        for i, h in enumerate(headers):
            if horse_idx is None and ("馬番" in h or h == "馬" or "馬番号" in h):
                horse_idx = i
            if name_idx is None and ("馬名" in h or "出走馬" in h):
                name_idx = i

        if horse_idx is None:
            continue

        for tr in rows[1:]:
            cells = tr.select("th,td")
            if horse_idx >= len(cells):
                continue

            horse_text = cells[horse_idx].get_text(" ", strip=True)
            if not re.fullmatch(r"\d{1,2}", horse_text):
                continue
            horse_no = str(int(horse_text))

            horse_name = ""
            if name_idx is not None and name_idx < len(cells):
                a = cells[name_idx].select_one("a")
                horse_name = a.get_text(" ", strip=True) if a else cells[name_idx].get_text(" ", strip=True)
            else:
                a = tr.select_one("a")
                if a:
                    horse_name = a.get_text(" ", strip=True)

            horse_name = re.sub(r"\s+", " ", horse_name).strip()
            if horse_name:
                horse_map[horse_no] = horse_name

    return horse_map


def format_selection_with_names(selection: str, horse_map: Dict[str, str], bet_type: str) -> str:
    nums = selection.split("-")
    if bet_type in {"tansho", "fukusho"}:
        num = nums[0]
        name = horse_map.get(num, "")
        return f"{num} {name}" if name else num

    parts = []
    for num in nums:
        name = horse_map.get(num, "")
        parts.append(f"{num} {name}" if name else num)
    return "-".join(parts)


def detect_field_size_from_soup(soup: BeautifulSoup) -> Optional[int]:
    values: List[int] = []

    selectors = [
        "td[class*='Umaban']",
        "span[class*='Umaban']",
        "[class*='Horse_Num']",
        "[class*='umaban']",
    ]
    for sel in selectors:
        for node in soup.select(sel):
            txt = node.get_text(" ", strip=True)
            if re.fullmatch(r"\d{1,2}", txt):
                num = int(txt)
                if 1 <= num <= 18:
                    values.append(num)

    for table in soup.select("table"):
        for cell in table.select("th,td"):
            txt = cell.get_text(" ", strip=True)
            if re.fullmatch(r"\d{1,2}", txt):
                num = int(txt)
                if 1 <= num <= 18:
                    values.append(num)

    if values:
        return max(values)

    text = soup.get_text("\n", strip=True)
    m = re.search(r"(\d{1,2})頭", text)
    if m:
        num = int(m.group(1))
        if 1 <= num <= 18:
            return num
    return None


def parse_range_text(raw: str) -> Tuple[Optional[float], Optional[str]]:
    normalized = (
        (raw or "")
        .replace(",", "")
        .replace("〜", "-")
        .replace("～", "-")
        .replace("―", "-")
        .replace("–", "-")
        .replace("−", "-")
        .strip()
    )
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", normalized)
    if m:
        low = float(m.group(1))
        high = float(m.group(2))
        return low, f"{low:.1f}-{high:.1f}"
    m2 = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", normalized)
    if m2:
        val = float(m2.group(1))
        return val, f"{val:.1f}"
    return None, None


def find_table_context_label(table) -> str:
    texts: List[str] = []

    prev = table.find_previous(["h1", "h2", "h3", "h4", "div", "span", "p"])
    if prev:
        texts.append(prev.get_text(" ", strip=True))

    for parent in list(table.parents)[:5]:
        txt = parent.get_text(" ", strip=True)
        if txt:
            texts.append(txt[:120])

    for txt in texts:
        compact = re.sub(r"\s+", "", txt)
        if "単勝" in compact and "複勝" not in compact:
            return "tansho"
        if "複勝" in compact and "単勝" not in compact:
            return "fukusho"
    return ""


def parse_win_place_rows(html: str) -> Tuple[Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, str], Optional[int]]:
    """
    Row-based parser.
    It only uses:
    - a table row
    - the horse-number cell in that row
    - the odds cell in that same row
    No page-wide numeric fallback is used for 単勝/複勝.
    """
    soup = BeautifulSoup(html, "html.parser")
    field_size = detect_field_size_from_soup(soup)

    win_map: Dict[str, float] = {}
    win_display: Dict[str, str] = {}
    place_map: Dict[str, float] = {}
    place_display: Dict[str, str] = {}

    for table in soup.select("table"):
        rows = table.select("tr")
        if len(rows) < 2:
            continue

        header_cells = rows[0].select("th,td")
        headers = [re.sub(r"\s+", "", c.get_text(" ", strip=True)) for c in header_cells]
        horse_idx = None
        odds_idx = None

        for idx, h in enumerate(headers):
            if horse_idx is None and ("馬番" in h or h == "馬" or "馬番号" in h):
                horse_idx = idx
            if odds_idx is None and "オッズ" in h:
                odds_idx = idx

        if horse_idx is None or odds_idx is None:
            continue

        context = find_table_context_label(table)
        if not context:
            sample = " ".join(row.get_text(" ", strip=True) for row in rows[:3])
            compact = re.sub(r"\s+", "", sample)
            if "複勝" in compact:
                context = "fukusho"
            elif "単勝" in compact:
                context = "tansho"

        if not context:
            sample_cells = []
            for tr in rows[1:4]:
                cells = tr.select("th,td")
                if odds_idx < len(cells):
                    sample_cells.append(cells[odds_idx].get_text(" ", strip=True))
            joined = " ".join(sample_cells)
            if re.search(r"\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?", joined):
                context = "fukusho"
            else:
                context = "tansho"

        for tr in rows[1:]:
            cells = tr.select("th,td")
            if max(horse_idx, odds_idx) >= len(cells):
                continue

            horse_text = cells[horse_idx].get_text(" ", strip=True)
            odds_text = cells[odds_idx].get_text(" ", strip=True)

            if not re.fullmatch(r"\d{1,2}", horse_text):
                continue

            horse_no = int(horse_text)
            if not (1 <= horse_no <= 18):
                continue
            if field_size is not None and horse_no > field_size:
                continue

            horse = str(horse_no)
            if not odds_text or odds_text in {"-", "--", "—"}:
                continue

            if context == "tansho":
                value, display = parse_range_text(odds_text)
                if value is not None and display is not None:
                    win_map[horse] = value
                    win_display[horse] = display
            else:
                value, display = parse_range_text(odds_text)
                if value is not None and display is not None:
                    place_map[horse] = value
                    place_display[horse] = display

    return win_map, win_display, place_map, place_display, field_size


def likely_odds_value(value: str) -> Optional[float]:
    txt = value.strip().replace(",", "")
    if not re.fullmatch(r"\d{1,5}(?:\.\d{1,2})?", txt):
        return None
    num = float(txt)
    if num <= 0:
        return None
    return num


def extract_selection_from_text(text: str, bet_type: str, field_size: Optional[int] = None) -> Optional[str]:
    raw_nums = re.findall(r"(?<!\d)\d{1,2}(?!\d)", text)
    if field_size is not None:
        nums = [n for n in raw_nums if 1 <= int(n) <= field_size]
    else:
        nums = raw_nums

    need = expected_selection_len(bet_type)
    if len(nums) < need:
        return None
    return normalize_selection("-".join(nums[:need]), bet_type)


def detect_odds_column_indexes(table) -> List[int]:
    indexes: List[int] = []
    for tr in table.select("tr")[:6]:
        cells = tr.select("th,td")
        headers = [re.sub(r"\s+", "", c.get_text(" ", strip=True)) for c in cells]
        for idx, header in enumerate(headers):
            if "オッズ" in header:
                indexes.append(idx)
        if indexes:
            break
    return sorted(set(indexes))


def extract_odds_from_cell(cell) -> Optional[float]:
    candidates = []
    for attr in ["data-rate", "data-odds", "data-value", "aria-label", "title"]:
        val = cell.attrs.get(attr)
        if isinstance(val, str):
            candidates.append(val)
    candidates.append(cell.get_text(" ", strip=True))

    for raw in candidates:
        nums = re.findall(r"\d{1,5}(?:\.\d{1,2})?", raw.replace(",", ""))
        for num in nums:
            cand = likely_odds_value(num)
            if cand is not None:
                return cand
    return None


def extract_odds_candidates_from_tables(html: str, bet_type: str, field_size: Optional[int] = None) -> Dict[str, float]:
    soup = BeautifulSoup(html, "html.parser")
    odds_map: Dict[str, float] = {}

    for table in soup.select("table"):
        odds_indexes = detect_odds_column_indexes(table)
        rows = table.select("tr")
        if not odds_indexes or not rows:
            continue

        for tr in rows:
            cells = tr.select("th,td")
            if len(cells) < 2:
                continue
            joined = " ".join(c.get_text(" ", strip=True) for c in cells)
            selection = extract_selection_from_text(joined, bet_type, field_size=field_size)
            if not selection:
                continue

            odds = None
            for idx in odds_indexes:
                if idx < len(cells):
                    odds = extract_odds_from_cell(cells[idx])
                    if odds is not None:
                        break

            if odds is not None:
                odds_map.setdefault(selection, odds)

    return odds_map


def scrape_netkeiba_odds(race_id: str, bet_type: str) -> Tuple[Dict[str, float], Dict[str, str], str, Optional[str]]:
    race_id = normalize_race_id(race_id)
    if not race_id or len(race_id) != 12:
        raise ValueError("レースIDが不正です。12桁のレースIDを入力してください。")

    candidate_urls = build_odds_urls(race_id, bet_type)
    last_error: Optional[Exception] = None
    last_url = candidate_urls[0]

    if bet_type in {"tansho", "fukusho"}:
        primary_url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
        candidate_urls = [primary_url] + [u for u in candidate_urls if u != primary_url]

        for url in candidate_urls:
            last_url = url
            try:
                html = fetch_html(url)
                win_map, win_display, place_map, place_display, field_size = parse_win_place_rows(html)
                notes = []
                if field_size:
                    notes.append(f"認識頭数: {field_size}頭")
                notes.append("単勝・複勝は馬番ごとの行ベースで抽出しています。")
                if bet_type == "tansho" and win_map:
                    return win_map, win_display, url, " / ".join(notes)
                if bet_type == "fukusho" and place_map:
                    notes.append("複勝の計算は下限オッズを使用します。")
                    return place_map, place_display, url, " / ".join(notes)
            except Exception as exc:
                last_error = exc

    for url in candidate_urls:
        last_url = url
        try:
            html = fetch_html(url)
            soup = BeautifulSoup(html, "html.parser")
            field_size = detect_field_size_from_soup(soup)
            odds_map = extract_odds_candidates_from_tables(html, bet_type, field_size=field_size)
            if odds_map:
                odds_display = {k: f"{v:.1f}" for k, v in odds_map.items()}
                note = f"認識頭数: {field_size}頭" if field_size else None
                return odds_map, odds_display, url, note
        except Exception as exc:
            last_error = exc

    warning = "オッズ抽出に失敗しました。手動オッズ入力を使ってください。"
    if last_error is not None:
        warning += f" 直近エラー: {last_error}"
    return {}, {}, last_url, warning


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
        return [], "この買い目構成では、全てを非トリガミにする再配分は理論上できません。"

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


def render_result_cards(results: List[BetResult], horse_map: Dict[str, str], bet_type: str) -> None:
    for r in results:
        odds_text = f"{r.odds_display}倍" if r.odds is not None else "-"
        payout_text = f"{r.payout:,}円" if r.payout is not None else "-"
        profit_text = f"{r.profit:+,}円" if r.profit is not None else "-"
        note_text = r.note or "-"
        display_selection = format_selection_with_names(r.selection, horse_map, bet_type)
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


def main() -> None:
    st.set_page_config(page_title="競馬トリガミ回避ツール", page_icon="🏇", layout="centered")
    if not check_password_gate():
        return

    st.markdown(
        """
        <div class="app-hero">
          <div class="app-hero-title">競馬トリガミ回避ツール</div>
          <p class="app-hero-sub">レースID・軍資金・買い目を入力して、netkeibaのオッズ取得または手動オッズ入力で判定します。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("main_form"):
        race_id = st.text_input("レースID", placeholder="例: 202609020611")
        bankroll = st.number_input("軍資金", min_value=100, step=100, value=3000)
        max_horses = st.number_input("出走頭数（ALL展開用）", min_value=1, max_value=18, step=1, value=18)
        bet_type = st.selectbox("券種", options=list(BET_TYPE_LABELS.keys()), format_func=lambda k: BET_TYPE_LABELS[k])
        bets_text = st.text_area(
            "買い目入力",
            placeholder=f"例:\n{example_for_bet_type(bet_type)}",
        )
        manual_odds_text = st.text_area(
            "手動オッズ入力（取得失敗時だけ使う）",
            placeholder="例:\n1 24.0\n2 64.8\nまたは複勝なら\n1 4.4-8.0",
        )
        submitted = st.form_submit_button("判定する")

    if not submitted:
        st.info(REQUEST_GAP_NOTICE)
        return

    bets, bet_errors, previews = parse_bets(bets_text, bet_type, max_horses=int(max_horses))
    if bet_errors:
        for err in bet_errors:
            st.error(err)
        return
    if not bets:
        st.warning("買い目を入力してください。")
        return

    with st.expander("展開プレビュー", expanded=True):
        total_points = 0
        total_amount = 0
        for line_no, source, expanded, amount in previews:
            total_points += len(expanded)
            total_amount += len(expanded) * amount
            st.markdown(
                f'<div class="mini-box"><b>{line_no}行目</b> {source} → {", ".join(expanded[:20])}'
                + (f" …他{len(expanded)-20}点" if len(expanded) > 20 else "")
                + f"<br>1点あたり: {amount:,}円 / 点数: {len(expanded)} / 行合計: {len(expanded)*amount:,}円</div>",
                unsafe_allow_html=True,
            )

        c1, c2 = st.columns(2)
        c1.metric("合計点数", f"{total_points}点")
        c2.metric("合計購入額", f"{total_amount:,}円")

    odds_map: Dict[str, float] = {}
    odds_display_map: Dict[str, str] = {}
    horse_map: Dict[str, str] = {}
    source_url = ""
    scrape_note = None

    if race_id.strip():
        try:
            horse_map = fetch_horse_names(race_id)
        except Exception:
            horse_map = {}
        try:
            odds_map, odds_display_map, source_url, scrape_note = scrape_netkeiba_odds(race_id, bet_type)
        except Exception as exc:
            st.warning(f"netkeiba取得に失敗しました: {exc}")

    if not odds_map and manual_odds_text.strip():
        manual_map, manual_display, manual_errors = parse_manual_odds(manual_odds_text, bet_type, max_horses=int(max_horses))
        if manual_errors:
            for err in manual_errors:
                st.error(err)
            return
        odds_map = manual_map
        odds_display_map = manual_display

    if source_url:
        st.caption(f"取得元: {source_url}")
    if scrape_note:
        st.info(scrape_note)

    results, total_stake = calculate_results(bets, odds_map, odds_display_map)

    c1, c2 = st.columns(2)
    c1.metric("総購入額", f"{total_stake:,}円")
    c2.metric("軍資金", f"{int(bankroll):,}円")

    st.subheader("判定結果")
    render_result_cards(results, horse_map, bet_type)

    valid_results = [r for r in results if r.odds is not None]
    if valid_results:
        st.subheader("再配分案")
        proposal, proposal_note = suggest_reallocation(int(bankroll), odds_map, bets)
        if proposal:
            st.info(proposal_note)
            for sel, amount, odds, payout, profit in proposal:
                st.markdown(
                    f'<div class="mini-box"><b>{sel}</b><br>提案購入額: {amount:,}円 / オッズ: {odds:.1f}倍 / 払戻見込: {payout:,}円 / 収支: {profit:+,}円</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.warning(proposal_note)
    else:
        st.warning("有効なオッズが取得できていません。手動オッズ入力も試してください。")


if __name__ == "__main__":
    main()
