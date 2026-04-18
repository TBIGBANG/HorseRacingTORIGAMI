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


def build_sp_url(race_id: str) -> str:
    return f"https://race.sp.netkeiba.com/?pid=odds_view&type=b1&race_id={race_id}"


def mojibake_score(text: str) -> int:
    # Common mojibake markers seen in the uploaded files.
    bad_tokens = ["„", "�", "Ē", "ŗ", "¤", "½", "¶", "Ć", "Š"]
    return sum(text.count(tok) for tok in bad_tokens)


def decode_html_bytes(raw: bytes, fallback_domain_hint: str = "sp") -> str:
    """
    Prefer EUC-JP first for the SP page because the uploaded HTML head declares it.
    The uploaded SP head shows <meta charset="EUC-JP"> fileciteturn10file8
    """
    # Inspect ASCII-safe head first
    head_ascii = raw[:4096].decode("ascii", errors="ignore")
    meta_euc = 'charset="EUC-JP"' in head_ascii or 'charset=EUC-JP' in head_ascii

    candidates: List[str] = []
    if meta_euc or fallback_domain_hint == "sp":
        candidates = ["euc_jp", "cp932", "shift_jis", "utf-8", "latin1"]
    else:
        candidates = ["utf-8", "cp932", "shift_jis", "euc_jp", "latin1"]

    best_text = ""
    best_score = 10**9

    for enc in candidates:
        try:
            txt = raw.decode(enc)
            score = mojibake_score(txt)
            # Strongly prefer readable Japanese over mojibake
            if score < best_score:
                best_text = txt
                best_score = score
        except Exception:
            pass

    if best_text:
        return best_text

    return raw.decode("utf-8", errors="replace")


def fetch_html(race_id: str) -> Tuple[str, str]:
    url = build_sp_url(race_id)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://race.netkeiba.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    html = decode_html_bytes(r.content, fallback_domain_hint="sp")
    return url, html


def parse_rows(html: str) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    items: Dict[str, Dict[str, str]] = {}

    # Primary: parse rows from RaceOdds_HorseList_Table
    for tr in soup.select("table.RaceOdds_HorseList_Table tr"):
        name_cell = tr.select_one(".Horse_Name")
        if name_cell is None:
            continue

        horse_no: Optional[int] = None

        odds_span = tr.select_one("span[id^='odds-1_'], span[id^='odds-2_']")
        if odds_span is not None:
            m = re.search(r"odds-\d+_(\d{1,2})$", odds_span.get("id", ""))
            if m:
                horse_no = int(m.group(1))

        if horse_no is None:
            nums: List[int] = []
            for cell in tr.select("td,th"):
                txt = cell.get_text(" ", strip=True)
                if re.fullmatch(r"\d{1,2}", txt):
                    n = int(txt)
                    if 1 <= n <= 18:
                        nums.append(n)
            if len(nums) >= 2:
                horse_no = nums[1]
            elif len(nums) == 1:
                horse_no = nums[0]

        if horse_no is None:
            continue

        key = str(horse_no)
        row = items.setdefault(key, {"馬番": key, "馬名": "", "単勝": "", "複勝": ""})

        horse_name = re.sub(r"\s+", " ", name_cell.get_text(" ", strip=True)).strip()
        if horse_name:
            row["馬名"] = horse_name

        win_node = tr.select_one(f"span[id='odds-1_{horse_no:02d}']")
        if win_node is not None:
            win_text = win_node.get_text(" ", strip=True)
            if win_text and win_text != "---.-":
                row["単勝"] = win_text

        place_node = tr.select_one(f"span[id='odds-2_{horse_no:02d}']")
        if place_node is not None:
            place_text = place_node.get_text(" ", strip=True)
            if place_text and place_text != "---.-":
                row["複勝"] = place_text

    rows = sorted(items.values(), key=lambda x: int(x["馬番"]))
    debug = {
        "row_count": str(len(rows)),
        "mojibake_score": str(mojibake_score(html)),
    }
    return rows, debug


st.set_page_config(page_title="SP版オッズ取得", page_icon="🏇", layout="centered")
st.title("SP版オッズ取得")
st.caption("文字コード対策版。SPページは EUC-JP を優先して読みます。")

race_id = st.text_input("レースID", placeholder="例: 202609020611")

if st.button("取得", type="primary"):
    race_id = normalize_race_id(race_id)

    if len(race_id) != 12:
        st.error("12桁のレースIDを入力してください。")
        st.stop()

    try:
        url, html = fetch_html(race_id)
        rows, debug = parse_rows(html)

        st.caption(f"取得元: {url}")

        if not rows:
            st.error("取得失敗")
            with st.expander("HTML先頭確認", expanded=True):
                st.code(html[:4000])
            st.stop()

        st.dataframe(rows, use_container_width=True, hide_index=True)

        with st.expander("デバッグ情報", expanded=False):
            st.json(debug)
            st.code(html[:2000])

    except Exception as exc:
        st.error(f"注意エラー: {exc}")
