from __future__ import annotations

import base64
import gzip
import json
import re
import zlib
from typing import Any, Dict, List, Optional, Tuple

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


def build_odds_api_url() -> str:
    return "https://race.netkeiba.com/api/api_get_jra_odds.html"


def fetch_bytes(url: str, params: Optional[Dict[str, Any]] = None, race_id: str = "") -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        "Referer": f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}" if race_id else "https://race.netkeiba.com/",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "X-Requested-With": "XMLHttpRequest",
    }
    response = requests.get(url, headers=headers, params=params, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.content


def fetch_fragment_html(race_id: str) -> str:
    url = build_odds_fragment_url(race_id)
    raw = fetch_bytes(url, race_id=race_id)
    for enc in ["EUC-JP", "utf-8", "cp932", "latin1"]:
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def parse_fragment_rows(html: str) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    horse_map: Dict[str, str] = {}
    win_placeholder: Dict[str, str] = {}
    place_placeholder: Dict[str, str] = {}

    for row in soup.select("table.RaceOdds_HorseList_Table tr"):
        name_cell = row.select_one(".Horse_Name")
        if name_cell is None:
            continue

        horse_no: Optional[int] = None

        odds_span = row.select_one("span[id^='odds-1_'], span[id^='odds-2_']")
        if odds_span is not None:
            m = re.search(r"odds-\d+_(\d{1,2})$", odds_span.get("id", ""))
            if m:
                horse_no = int(m.group(1))

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
            win_placeholder[horse_key] = win_node.get_text(" ", strip=True)

        place_node = row.select_one(f"span[id='odds-2_{horse_no:02d}']")
        if place_node is not None:
            place_placeholder[horse_key] = place_node.get_text(" ", strip=True)

    return horse_map, win_placeholder, place_placeholder


def try_json_loads(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except Exception:
        return None


def try_extract_json_object(text: str) -> Optional[Any]:
    obj = try_json_loads(text)
    if obj is not None:
        return obj

    m = re.search(r'(\{.*\})', text, flags=re.S)
    if m:
        obj = try_json_loads(m.group(1))
        if obj is not None:
            return obj

    m = re.search(r'(\[.*\])', text, flags=re.S)
    if m:
        obj = try_json_loads(m.group(1))
        if obj is not None:
            return {"odds": obj}

    m = re.search(r'"data"\s*:\s*"(.+?)"', text, flags=re.S)
    if m:
        try:
            inner = m.group(1).encode("utf-8").decode("unicode_escape")
            obj = try_json_loads(inner)
            if obj is not None:
                return obj
        except Exception:
            pass

    return None


def try_decompress_bytes(raw: bytes) -> Optional[str]:
    try:
        return raw.decode("utf-8")
    except Exception:
        pass

    try:
        return gzip.decompress(raw).decode("utf-8")
    except Exception:
        pass

    for wbits in [zlib.MAX_WBITS, -zlib.MAX_WBITS, 15 + 32]:
        try:
            return zlib.decompress(raw, wbits).decode("utf-8")
        except Exception:
            pass

    try:
        b = base64.b64decode(raw)
        return try_decompress_bytes(b)
    except Exception:
        pass

    return None


def parse_api_payload_obj(obj: Any) -> Tuple[Dict[str, str], Dict[str, str]]:
    win: Dict[str, str] = {}
    place: Dict[str, str] = {}

    def add_win(no: Any, val: Any) -> None:
        try:
            key = str(int(no))
            win[key] = f"{float(val):.1f}"
        except Exception:
            pass

    def add_place(no: Any, lo: Any, hi: Any) -> None:
        try:
            key = str(int(no))
            place[key] = f"{float(lo):.1f} - {float(hi):.1f}"
        except Exception:
            pass

    data = obj.get("data", obj) if isinstance(obj, dict) else obj
    odds = data.get("odds", data) if isinstance(data, dict) else data

    # Preferred known structure
    if isinstance(odds, dict):
        type1 = odds.get("1", odds.get(1, {}))
        type2 = odds.get("2", odds.get(2, {}))

        if isinstance(type1, dict):
            for no, arr in type1.items():
                if isinstance(arr, list) and arr:
                    add_win(no, arr[0])

        if isinstance(type2, dict):
            for no, arr in type2.items():
                if isinstance(arr, list) and len(arr) >= 2:
                    add_place(no, arr[0], arr[1])

    # Fallback recursive search
    def walk(o: Any) -> None:
        if isinstance(o, dict):
            # case: {"1": {"1": [24.0], "2": [64.8]}, "2": {...}}
            for k, v in o.items():
                if (k == "1" or k == 1) and isinstance(v, dict):
                    for no, arr in v.items():
                        if isinstance(arr, list) and arr:
                            add_win(no, arr[0])
                elif (k == "2" or k == 2) and isinstance(v, dict):
                    for no, arr in v.items():
                        if isinstance(arr, list) and len(arr) >= 2:
                            add_place(no, arr[0], arr[1])
                walk(v)
        elif isinstance(o, list):
            for item in o:
                walk(item)

    walk(obj)
    return win, place


def fetch_api_odds(race_id: str) -> Tuple[Dict[str, str], Dict[str, str], str]:
    url = build_odds_api_url()
    attempts = [
        {"raceId": race_id, "type": "b1", "_": "1", "compress": "true", "isPremium": "0"},
        {"raceId": race_id, "type": "b1", "_": "1", "compress": "false", "isPremium": "0"},
        {"race_id": race_id, "type": "b1", "_": "1", "compress": "true", "isPremium": "0"},
        {"race_id": race_id, "type": "b1", "_": "1", "compress": "false", "isPremium": "0"},
        {"raceId": race_id, "type": "b1", "compress": "true"},
        {"raceId": race_id, "type": "b1", "compress": "false"},
        {"raceId": race_id, "compress": "true"},
        {"raceId": race_id, "compress": "false"},
    ]

    debug_notes: List[str] = []

    for params in attempts:
        try:
            raw = fetch_bytes(url, params=params, race_id=race_id)
            debug_notes.append(f"attempt params={params} bytes={len(raw)}")

            # direct decodes
            for enc in ["utf-8", "EUC-JP", "cp932", "latin1"]:
                try:
                    text = raw.decode(enc)
                    obj = try_extract_json_object(text)
                    if obj is not None:
                        win, place = parse_api_payload_obj(obj)
                        if win or place:
                            return win, place, " / ".join(debug_notes + [f"decoded={enc}", "json=direct"])
                except Exception:
                    pass

            # decompression path
            dec_text = try_decompress_bytes(raw)
            if dec_text:
                obj = try_extract_json_object(dec_text)
                if obj is not None:
                    win, place = parse_api_payload_obj(obj)
                    if win or place:
                        return win, place, " / ".join(debug_notes + ["json=decompressed"])

            # requests text path
            try:
                text = raw.decode("utf-8", errors="replace")
                obj = try_extract_json_object(text)
                if obj is not None:
                    win, place = parse_api_payload_obj(obj)
                    if win or place:
                        return win, place, " / ".join(debug_notes + ["json=text-fallback"])
            except Exception:
                pass

        except Exception as exc:
            debug_notes.append(f"attempt params={params} err={exc}")

    return {}, {}, " / ".join(debug_notes)


st.set_page_config(page_title="競馬オッズAPI確認ツール", page_icon="🏇", layout="centered")
st.title("競馬オッズAPI確認ツール")
st.caption("HTMLの ---.- を使わず、JSが参照している api_get_jra_odds.html を直接読みに行く版です。")

race_id = st.text_input("レースID", placeholder="例: 202609020611")

if st.button("netkeibaから1回取得", type="primary"):
    race_id = normalize_race_id(race_id)

    if len(race_id) != 12:
        st.error("12桁のレースIDを入力してください。")
        st.stop()

    try:
        fragment_url = build_odds_fragment_url(race_id)
        fragment_html = fetch_fragment_html(race_id)
        horse_map, win_placeholder, place_placeholder = parse_fragment_rows(fragment_html)

        win_api, place_api, debug_msg = fetch_api_odds(race_id)

        st.caption(f"HTML取得元: {fragment_url}")
        st.caption("オッズAPI: https://race.netkeiba.com/api/api_get_jra_odds.html")

        rows = []
        keys = sorted(set(horse_map.keys()) | set(win_placeholder.keys()) | set(place_placeholder.keys()) | set(win_api.keys()) | set(place_api.keys()), key=lambda x: int(x))

        for horse_no in keys:
            rows.append({
                "馬番": horse_no,
                "馬名": horse_map.get(horse_no, ""),
                "HTML単勝": win_placeholder.get(horse_no, ""),
                "API単勝": win_api.get(horse_no, ""),
                "HTML複勝": place_placeholder.get(horse_no, ""),
                "API複勝": place_api.get(horse_no, ""),
            })

        st.write(f"馬名 {len(horse_map)}件 / API単勝 {len(win_api)}件 / API複勝 {len(place_api)}件")
        st.dataframe(rows, use_container_width=True, hide_index=True)

        if not win_api and not place_api:
            st.warning("APIからオッズを復元できませんでした。レスポンス形式の追加解析が必要です。")
            with st.expander("デバッグ情報", expanded=True):
                st.code(debug_msg)
                st.code(fragment_html[:3000])

    except Exception as exc:
        st.error(f"注意エラー: {exc}")
