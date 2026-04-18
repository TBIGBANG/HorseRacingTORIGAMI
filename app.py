
from __future__ import annotations
import re
import requests
import streamlit as st
from bs4 import BeautifulSoup

def normalize_race_id(raw: str) -> str:
    return re.sub(r"\D", "", (raw or "").strip())

def fetch_html(race_id: str) -> str:
    url = f"https://race.sp.netkeiba.com/?pid=odds_view&type=b1&race_id={race_id}"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.text

def parse(html: str):
    soup = BeautifulSoup(html, "html.parser")
    rows = []

    for tr in soup.select("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue

        texts = [td.get_text(strip=True) for td in tds]

        # 馬番検出
        nums = [t for t in texts if re.fullmatch(r"\d{1,2}", t)]
        if not nums:
            continue
        horse_no = nums[-1]

        # 馬名
        name = ""
        name_el = tr.select_one(".Horse_Name")
        if name_el:
            name = name_el.get_text(strip=True)
        else:
            # fallback
            for t in texts:
                if not re.search(r"\d", t) and len(t) > 1:
                    name = t

        # オッズ抽出
        win = ""
        place = ""

        odds_text = " ".join(texts)

        m = re.search(r"(\d+\.\d+)", odds_text)
        if m:
            win = m.group(1)

        m = re.search(r"(\d+\.\d+\s*-\s*\d+\.\d+)", odds_text)
        if m:
            place = m.group(1)

        rows.append({
            "馬番": horse_no,
            "馬名": name,
            "単勝": win,
            "複勝": place
        })

    return rows

st.title("SP版オッズ取得")

race_id = st.text_input("レースID")

if st.button("取得"):
    race_id = normalize_race_id(race_id)

    if len(race_id) != 12:
        st.error("12桁のレースID")
        st.stop()

    html = fetch_html(race_id)
    data = parse(html)

    if not data:
        st.error("取得失敗")
    else:
        st.dataframe(data)
