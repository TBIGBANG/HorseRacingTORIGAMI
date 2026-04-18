from __future__ import annotations

import re
from typing import Dict, List, Optional

import requests
import streamlit as st
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)
TIMEOUT = 15


def normalize_race_id(raw: str) -> str:
    return re.sub(r"\D", "", (raw or "").strip())


def build_sp_url(race_id: str) -> str:
    return f"https://race.sp.netkeiba.com/?pid=odds_view&type=b1&race_id={race_id}"


def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": "https://race.sp.netkeiba.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    r = requests.get(url, headers=headers, timeout=TIMEOUT)
    r.raise_for_status()
    raw = r.content

    # mobile pages can be cp932 / EUC-JP / utf-8 depending on path and response
    for enc in ["utf-8", "cp932", "shift_jis", "EUC-JP", r.apparent_encoding, r.encoding, "latin1"]:
        if not enc:
            continue
        try:
            text = raw.decode(enc)
            # prefer decoding that does not produce replacement characters
            if "�" not in text[:3000]:
                return text
        except Exception:
            pass

    for enc in ["utf-8", "cp932", "shift_jis", "EUC-JP", "latin1"]:
        try:
            return raw.decode(enc, errors="replace")
        except Exception:
            pass

    return raw.decode("utf-8", errors="replace")


def clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()


def parse_float_text(s: str) -> str:
    m = re.search(r"\d+(?:\.\d+)?", s or "")
    return m.group(0) if m else ""


def parse_range_text(s: str) -> str:
    s = (s or "").replace("〜", "-").replace("～", "-").replace("―", "-").replace("–", "-").replace("−", "-")
    m = re.search(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)", s)
    return f"{float(m.group(1)):.1f} - {float(m.group(2)):.1f}" if m else ""


def extract_horse_no_from_row(row) -> Optional[str]:
    nums: List[str] = []
    for cell in row.select("td,th,span,div"):
        txt = clean_text(cell.get_text(" ", strip=True))
        if re.fullmatch(r"\d{1,2}", txt):
            n = int(txt)
            if 1 <= n <= 18:
                nums.append(str(n))
    if not nums:
        return None
    # usually 2nd numeric token is horse number (1st can be 枠)
    return nums[1] if len(nums) >= 2 else nums[0]


def extract_name_from_row(row) -> str:
    # preferred selectors
    for sel in [".Horse_Name", ".horse_name", "[class*='Horse_Name']", "[class*='horse_name']"]:
        node = row.select_one(sel)
        if node:
            txt = clean_text(node.get_text(" ", strip=True))
            if txt and not re.search(r"\d", txt):
                return txt

    # fallback: longest non-numeric text in row
    candidates = []
    for cell in row.select("td,th,a,span,div"):
        txt = clean_text(cell.get_text(" ", strip=True))
        if txt and not re.search(r"\d", txt) and len(txt) >= 2:
            candidates.append(txt)
    return max(candidates, key=len) if candidates else ""


def parse_sp_rows(html: str) -> List[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    merged: Dict[str, Dict[str, str]] = {}

    # pass 1: explicit odds ids if they exist
    for row in soup.select("tr"):
        horse_no = extract_horse_no_from_row(row)
        if not horse_no:
            continue

        name = extract_name_from_row(row)
        if horse_no not in merged:
            merged[horse_no] = {"馬番": horse_no, "馬名": "", "単勝": "", "複勝": ""}
        if name and (not merged[horse_no]["馬名"] or "�" in merged[horse_no]["馬名"]):
            merged[horse_no]["馬名"] = name

        win_node = row.select_one(f"[id='odds-1_{int(horse_no):02d}']")
        if win_node is not None:
            win = parse_float_text(clean_text(win_node.get_text(" ", strip=True)))
            if win and win != "---":
                merged[horse_no]["単勝"] = win

        place_node = row.select_one(f"[id='odds-2_{int(horse_no):02d}']")
        if place_node is not None:
            place = parse_range_text(clean_text(place_node.get_text(" ", strip=True)))
            if place:
                merged[horse_no]["複勝"] = place

    # pass 2: global id scan fallback
    for node in soup.select("[id^='odds-1_']"):
        m = re.search(r"odds-1_(\d{1,2})$", node.get("id", ""))
        if not m:
            continue
        horse_no = str(int(m.group(1)))
        merged.setdefault(horse_no, {"馬番": horse_no, "馬名": "", "単勝": "", "複勝": ""})
        win = parse_float_text(clean_text(node.get_text(" ", strip=True)))
        if win and win != "---":
            merged[horse_no]["単勝"] = win

    for node in soup.select("[id^='odds-2_']"):
        m = re.search(r"odds-2_(\d{1,2})$", node.get("id", ""))
        if not m:
            continue
        horse_no = str(int(m.group(1)))
        merged.setdefault(horse_no, {"馬番": horse_no, "馬名": "", "単勝": "", "複勝": ""})
        place = parse_range_text(clean_text(node.get_text(" ", strip=True)))
        if place:
            merged[horse_no]["複勝"] = place

    rows = sorted(merged.values(), key=lambda x: int(x["馬番"]))
    return rows


st.set_page_config(page_title="SP版オッズ取得 修正版", page_icon="🏇", layout="centered")
st.title("SP版オッズ取得 修正版")
st.caption("文字化け対策と重複排除を入れた版です。")

race_id = st.text_input("レースID", placeholder="例: 202609020611")

if st.button("取得", type="primary"):
    race_id = normalize_race_id(race_id)

    if len(race_id) != 12:
        st.error("12桁のレースIDを入力してください。")
        st.stop()

    url = build_sp_url(race_id)

    try:
        html = fetch_html(url)
        data = parse_sp_rows(html)

        st.caption(f"取得元: {url}")
        st.write(f"抽出件数: {len(data)}")

        if not data:
            st.error("取得失敗")
        else:
            st.dataframe(data, use_container_width=True, hide_index=True)

            no_odds = [r for r in data if not r["単勝"] and not r["複勝"]]
            if no_odds:
                st.warning(f"オッズ未取得の馬が {len(no_odds)} 頭あります。")
                with st.expander("HTML先頭確認", expanded=False):
                    st.code(html[:5000])

    except Exception as e:
        st.error(str(e))
