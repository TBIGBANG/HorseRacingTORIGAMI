
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
        }
        .app-hero-title {
            font-size: 1.55rem;
            line-height: 1.25;
            font-weight: 800;
            margin: 0 0 .3rem 0;
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


def normalize_selection(selection: str, bet_type: str) -> str:
    nums = [str(int(x)) for x in re.findall(r"\d{1,2}", selection)]
    if bet_type in {"tansho", "fukusho"}:
        return nums[0] if nums else selection.strip()
    if bet_type in {"umaren", "wide", "sanrenpuku"}:
        nums = sorted(nums, key=lambda x: int(x))
    return "-".join(nums)


def expected_selection_len(bet_type: str) -> int:
    return {
        "tansho": 1, "fukusho": 1, "umaren": 2, "wide": 2,
        "umatan": 2, "sanrenpuku": 3, "sanrentan": 3,
    }[bet_type]


def expand_token_group(part: str, max_horses: int) -> List[str]:
    part = part.strip().upper()
    if part == "ALL":
        return [str(i) for i in range(1, max_horses + 1)]
    out = []
    for item in part.split(","):
        item = item.strip()
        if re.fullmatch(r"\d{1,2}", item):
            n = int(item)
            if 1 <= n <= 18:
                out.append(str(n))
    return out


def expand_selection_input(selection_text: str, bet_type: str, max_horses: int = 18) -> List[str]:
    selection_text = selection_text.replace(" ", "").strip()
    if not selection_text:
        return []

    if bet_type in {"tansho", "fukusho"}:
        vals = expand_token_group(selection_text, max_horses)
        return sorted(set(vals), key=lambda x: int(x))

    parts = selection_text.split("-")
    need = expected_selection_len(bet_type)
    if len(parts) != need:
        return []

    groups = [expand_token_group(p, max_horses) for p in parts]
    if any(not g for g in groups):
        return []

    seen = set()
    out = []
    for combo in itertools.product(*groups):
        if len(set(combo)) != need:
            continue
        normalized = normalize_selection("-".join(combo), bet_type)
        if normalized not in seen:
            seen.add(normalized)
            out.append(normalized)
    return sorted(out, key=lambda s: tuple(int(x) for x in s.split("-")))


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
    odds_display_map: Dict[str, str] = {}
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
        selection_text = "".join(parts[:-1]).replace(" ", "")

        expanded = expand_selection_input(selection_text, bet_type, max_horses=max_horses)
        if not expanded:
            errors.append(f"手動オッズ {idx}行目: 買い目を解釈できませんでした")
            continue

        display = odds_text.replace("〜", "-").replace("～", "-")
        if bet_type == "fukusho":
            m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", display)
            if m:
                num = float(m.group(1))
                display = f"{float(m.group(1)):.1f}-{float(m.group(2)):.1f}"
            else:
                try:
                    num = float(display)
                    display = f"{num:.1f}"
                except ValueError:
                    errors.append(f"手動オッズ {idx}行目: 複勝は 4.4-8.0 の形式で入力してください")
                    continue
        else:
            try:
                num = float(display)
                display = f"{num:.1f}"
            except ValueError:
                errors.append(f"手動オッズ {idx}行目: オッズは数値で入力してください")
                continue

        for selection in expanded:
            norm = normalize_selection(selection, bet_type)
            odds_map[norm] = num
            odds_display_map[norm] = display

    return odds_map, odds_display_map, errors


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
    urls = []
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


def detect_field_size_from_soup(soup: BeautifulSoup) -> Optional[int]:
    nums = []
    for node in soup.select("td, span"):
        txt = node.get_text(" ", strip=True)
        if re.fullmatch(r"\d{1,2}", txt):
            n = int(txt)
            if 1 <= n <= 18:
                nums.append(n)
    return max(nums) if nums else None


def parse_range_text(raw: str) -> Tuple[Optional[float], Optional[str]]:
    txt = (raw or "").replace(",", "").replace("〜", "-").replace("～", "-").replace("―", "-").replace("–", "-").replace("−", "-").strip()
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", txt)
    if m:
        low = float(m.group(1))
        high = float(m.group(2))
        return low, f"{low:.1f}-{high:.1f}"
    m2 = re.search(r"(?<!\d)(\d+(?:\.\d+)?)(?!\d)", txt)
    if m2:
        val = float(m2.group(1))
        return val, f"{val:.1f}"
    return None, None


def parse_tansho_rows(html: str) -> Tuple[Dict[str, float], Dict[str, str], List[Dict[str, str]], Optional[int]]:
    soup = BeautifulSoup(html, "html.parser")
    field_size = detect_field_size_from_soup(soup)

    odds_map: Dict[str, float] = {}
    odds_display_map: Dict[str, str] = {}
    rows_debug: List[Dict[str, str]] = []

    for tr in soup.select("tr"):
        tds = tr.select("td")
        if not tds:
            continue

        waku = None
        umaban = None
        name = None
        odds = None

        for td in tds:
            text = td.get_text(" ", strip=True)
            classes = " ".join(td.get("class", []))
            a = td.select_one("a")
            if a:
                a_txt = a.get_text(" ", strip=True)
                if a_txt and not re.fullmatch(r"\d{1,2}", a_txt) and len(a_txt) > 1:
                    name = a_txt

            if re.fullmatch(r"\d", text):
                n = int(text)
                if 1 <= n <= 8 and waku is None:
                    waku = str(n)

            if re.fullmatch(r"\d{1,2}", text):
                n = int(text)
                if 1 <= n <= 18:
                    umaban = str(n)

            if re.fullmatch(r"\d+(?:\.\d+)?", text):
                val = float(text)
                if 1.0 <= val <= 1000:
                    if odds is None:
                        odds = val
                    if "odds" in classes.lower():
                        odds = val

        if umaban and name and odds is not None:
            if field_size is None or int(umaban) <= field_size:
                odds_map[umaban] = odds
                odds_display_map[umaban] = f"{odds:.1f}"
                rows_debug.append({
                    "waku": waku or "-",
                    "umaban": umaban,
                    "name": name,
                    "odds": f"{odds:.1f}",
                })

    return odds_map, odds_display_map, rows_debug, field_size


def parse_fukusho_rows(html: str) -> Tuple[Dict[str, float], Dict[str, str], Optional[int]]:
    soup = BeautifulSoup(html, "html.parser")
    field_size = detect_field_size_from_soup(soup)
    place_map: Dict[str, float] = {}
    place_display: Dict[str, str] = {}

    for table in soup.select("table"):
        rows = table.select("tr")
        if len(rows) < 2:
            continue
        headers = [re.sub(r"\s+", "", c.get_text(" ", strip=True)) for c in rows[0].select("th,td")]
        horse_idx = None
        odds_idx = None
        for idx, h in enumerate(headers):
            if horse_idx is None and ("馬番" in h or h == "馬" or "馬番号" in h):
                horse_idx = idx
            if odds_idx is None and "オッズ" in h:
                odds_idx = idx
        if horse_idx is None or odds_idx is None:
            continue

        sample = " ".join(r.get_text(" ", strip=True) for r in rows[:3])
        if "複勝" not in sample and "複" not in sample:
            continue

        for tr in rows[1:]:
            cells = tr.select("th,td")
            if max(horse_idx, odds_idx) >= len(cells):
                continue
            horse_text = cells[horse_idx].get_text(" ", strip=True)
            odds_text = cells[odds_idx].get_text(" ", strip=True)
            if not re.fullmatch(r"\d{1,2}", horse_text):
                continue
            horse = str(int(horse_text))
            if field_size is not None and int(horse) > field_size:
                continue
            value, display = parse_range_text(odds_text)
            if value is not None and display is not None:
                place_map[horse] = value
                place_display[horse] = display

    return place_map, place_display, field_size


def likely_odds_value(value: str) -> Optional[float]:
    txt = value.strip().replace(",", "")
    if not re.fullmatch(r"\d{1,5}(?:\.\d{1,2})?", txt):
        return None
    num = float(txt)
    return num if num > 0 else None


def extract_selection_from_text(text: str, bet_type: str, field_size: Optional[int] = None) -> Optional[str]:
    raw_nums = re.findall(r"(?<!\d)\d{1,2}(?!\d)", text)
    nums = [n for n in raw_nums if field_size is None or 1 <= int(n) <= field_size]
    need = expected_selection_len(bet_type)
    if len(nums) < need:
        return None
    return normalize_selection("-".join(nums[:need]), bet_type)


def detect_odds_column_indexes(table) -> List[int]:
    indexes = []
    for tr in table.select("tr")[:6]:
        cells = tr.select("th,td")
        headers = [re.sub(r"\s+", "", c.get_text(" ", strip=True)) for c in cells]
        for idx, h in enumerate(headers):
            if "オッズ" in h:
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

    if bet_type == "tansho":
        primary_url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
        try_urls = [primary_url] + [u for u in candidate_urls if u != primary_url]
        for url in try_urls:
            last_url = url
            try:
                html = fetch_html(url)
                odds_map, odds_display, rows_debug, field_size = parse_tansho_rows(html)
                if odds_map:
                    notes = []
                    if field_size:
                        notes.append(f"認識頭数: {field_size}頭")
                    notes.append("単勝は行ベースで、何枠・馬番・馬名・オッズを抽出しています。")
                    preview = rows_debug[:5]
                    if preview:
                        notes.append("抽出例: " + " / ".join(f"{r['waku']}枠 {r['umaban']} {r['name']} {r['odds']}倍" for r in preview))
                    return odds_map, odds_display, url, " / ".join(notes)
            except Exception as exc:
                last_error = exc

    if bet_type == "fukusho":
        primary_url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
        try_urls = [primary_url] + [u for u in candidate_urls if u != primary_url]
        for url in try_urls:
            last_url = url
            try:
                html = fetch_html(url)
                odds_map, odds_display, field_size = parse_fukusho_rows(html)
                if odds_map:
                    notes = []
                    if field_size:
                        notes.append(f"認識頭数: {field_size}頭")
                    notes.append("複勝の計算は下限オッズを使用します。")
                    return odds_map, odds_display, url, " / ".join(notes)
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
                warning = f"認識頭数: {field_size}頭" if field_size else None
                return odds_map, odds_display, url, warning
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
            results.append(BetResult(selection=bet.selection, amount=bet.amount, odds=None, odds_display="-", note="オッズ未取得"))
            continue
        payout = int(round(bet.amount * odds))
        profit = payout - total_stake
        results.append(BetResult(
            selection=bet.selection, amount=bet.amount, odds=odds,
            odds_display=odds_display_map.get(bet.selection, f"{odds:.1f}"),
            payout=payout, profit=profit, is_trigami=profit < 0,
        ))
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

    proposal = []
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


def render_result_cards(results: List[BetResult]) -> None:
    for r in results:
        odds_text = f"{r.odds_display}倍" if r.odds is not None else "-"
        payout_text = f"{r.payout:,}円" if r.payout is not None else "-"
        profit_text = f"{r.profit:+,}円" if r.profit is not None else "-"
        note_text = r.note or "-"
        st.markdown(
            f"""
            <div class="result-card">
              <div style="display:flex; justify-content:space-between; align-items:center; gap:.6rem;">
                <div style="font-weight:700; font-size:1.02rem;">{r.selection}</div>
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
        bets_text = st.text_area("買い目入力", placeholder=f"例:\n{example_for_bet_type(bet_type)}")
        manual_odds_text = st.text_area("手動オッズ入力（取得失敗時だけ使う）", placeholder="例:\n1 24.0\n2 64.8\nまたは複勝なら\n1 4.4-8.0")
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
    source_url = ""
    scrape_note = None

    if race_id.strip():
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
    render_result_cards(results)

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
