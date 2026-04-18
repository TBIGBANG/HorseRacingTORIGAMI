from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 15


def normalize_race_id(raw: str) -> str:
    return re.sub(r"\D", "", (raw or "").strip())


def build_odds_fragment_url(race_id: str) -> str:
    return f"https://race.netkeiba.com/odds/odds_get_form.html?type=b1&race_id={race_id}&rf=shutuba_submenu"


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://race.netkeiba.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    response = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "")
    html_bytes = response.content

    m = re.search(r"charset=([A-Za-z0-9_\-]+)", content_type, flags=re.I)
    if m:
        enc = m.group(1)
        try:
            return html_bytes.decode(enc, errors="replace")
        except Exception:
            pass

    head_text = html_bytes[:4096].decode("ascii", errors="ignore")
    m = re.search(r'charset=["\']?([A-Za-z0-9_\-]+)', head_text, flags=re.I)
    if m:
        enc = m.group(1)
        try:
            return html_bytes.decode(enc, errors="replace")
        except Exception:
            pass

    for enc in [response.apparent_encoding, response.encoding, "EUC-JP", "utf-8", "cp932"]:
        if not enc:
            continue
        try:
            return html_bytes.decode(enc, errors="replace")
        except Exception:
            pass

    return html_bytes.decode("latin1", errors="replace")


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


def parse_win_text(raw: str) -> Tuple[Optional[float], Optional[str]]:
    nums = re.findall(r"\d+(?:\.\d+)?", (raw or "").replace(",", ""))
    if not nums:
        return None, None
    val = float(nums[0])
    return val, f"{val:.1f}"


def parse_b1_fragment(html: str) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")

    horse_map: Dict[str, str] = {}
    win_map: Dict[str, float] = {}
    win_display: Dict[str, str] = {}
    place_map: Dict[str, float] = {}
    place_display: Dict[str, str] = {}

    # Row-based parsing from the light odds fragment
    for row in soup.select("table.RaceOdds_HorseList_Table tr"):
        name_cell = row.select_one(".Horse_Name")
        if name_cell is None:
            continue

        horse_no: Optional[int] = None

        # Prefer id suffix in the same row
        odds_span = row.select_one("span[id^='odds-1_'], span[id^='odds-2_']")
        if odds_span is not None:
            m = re.search(r"odds-\d+_(\d{1,2})$", odds_span.get("id", ""))
            if m:
                horse_no = int(m.group(1))

        # Fallback: second numeric td is usually 馬番
        if horse_no is None:
            nums: List[int] = []
            for cell in row.select("td,th"):
                txt = cell.get_text(" ", strip=True)
                if re.fullmatch(r"\d{1,2}", txt):
                    n = int(txt)
                    if 1 <= n <= 18:
                        nums.append(n)
            if len(nums) >= 2:
                horse_no = nums[1]
            elif len(nums) == 1:
                horse_no = nums[0]

        if horse_no is None or not (1 <= horse_no <= 18):
            continue

        horse_key = str(horse_no)
        horse_name = re.sub(r"\s+", " ", name_cell.get_text(" ", strip=True)).strip()
        if horse_name:
            horse_map[horse_key] = horse_name

        win_node = row.select_one(f"span[id='odds-1_{horse_no:02d}']")
        if win_node is not None:
            val, disp = parse_win_text(win_node.get_text(" ", strip=True))
            if val is not None and disp is not None:
                win_map[horse_key] = val
                win_display[horse_key] = disp

        place_node = row.select_one(f"span[id='odds-2_{horse_no:02d}']")
        if place_node is not None:
            val, disp = parse_place_text(place_node.get_text(" ", strip=True))
            if val is not None and disp is not None:
                place_map[horse_key] = val
                place_display[horse_key] = disp

    # Global id scan fallback
    for span in soup.select("span[id^='odds-1_']"):
        m = re.search(r"odds-1_(\d{1,2})$", span.get("id", ""))
        if not m:
            continue
        horse_key = str(int(m.group(1)))
        val, disp = parse_win_text(span.get_text(" ", strip=True))
        if val is not None and disp is not None:
            win_map.setdefault(horse_key, val)
            win_display.setdefault(horse_key, disp)

    for span in soup.select("span[id^='odds-2_']"):
        m = re.search(r"odds-2_(\d{1,2})$", span.get("id", ""))
        if not m:
            continue
        horse_key = str(int(m.group(1)))
        val, disp = parse_place_text(span.get_text(" ", strip=True))
        if val is not None and disp is not None:
            place_map.setdefault(horse_key, val)
            place_display.setdefault(horse_key, disp)

    return horse_map, win_map, win_display, place_map, place_display


st.set_page_config(page_title="競馬オッズ確認ツール", page_icon="🏇", layout="centered")
st.title("競馬オッズ確認ツール")
st.caption("軽量版。Playwrightを使わず、odds_get_form.html を直接取得します。")

race_id = st.text_input("レースID", placeholder="例: 202609020611")

if st.button("netkeibaから1回取得", type="primary"):
    race_id = normalize_race_id(race_id)

    if len(race_id) != 12:
        st.error("12桁のレースIDを入力してください。")
        st.stop()

    url = build_odds_fragment_url(race_id)

    try:
        html = fetch_html(url)
        horse_map, win_map, win_display, place_map, place_display = parse_b1_fragment(html)

        st.success("取得処理は完了しました。")
        st.caption(f"取得元: {url}")

        if not win_map and not place_map:
            st.warning("オッズを取得できませんでした。取得HTMLにオッズ文字列が含まれていない可能性があります。")
            with st.expander("取得HTMLの先頭を確認", expanded=False):
                st.code(html[:4000])
            st.stop()

        rows = []
        keys = sorted(set(horse_map.keys()) | set(win_map.keys()) | set(place_map.keys()), key=lambda x: int(x))
        for horse_no in keys:
            rows.append({
                "馬番": horse_no,
                "馬名": horse_map.get(horse_no, ""),
                "単勝": win_display.get(horse_no, ""),
                "複勝": place_display.get(horse_no, ""),
            })

        st.write(f"単勝 {len(win_map)}件 / 複勝 {len(place_map)}件 / 馬名 {len(horse_map)}件")
        st.dataframe(rows, use_container_width=True, hide_index=True)

    except Exception as exc:
        st.error(f"注意エラー: {exc}")
