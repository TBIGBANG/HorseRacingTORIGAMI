
from __future__ import annotations

import re
import os
import streamlit as st
import requests
from bs4 import BeautifulSoup

st.set_page_config(page_title="トリガミ回避ツール")

def fetch_html(url: str) -> str:
    headers = {"User-Agent": "Mozilla/5.0"}
    r = requests.get(url, headers=headers, timeout=10)
    r.raise_for_status()
    return r.text

def parse_odds(html: str):
    soup = BeautifulSoup(html, "html.parser")
    result = {}

    # idベース取得（最安定）
    for span in soup.select("span[id^='odds-1_']"):
        m = re.search(r"odds-1_(\d+)", span.get("id",""))
        if not m:
            continue
        horse = str(int(m.group(1)))
        txt = span.get_text(strip=True)
        if re.search(r"\d", txt):
            result[horse] = txt

    return result

st.title("競馬 トリガミ回避ツール")

race_id = st.text_input("レースID")

if st.button("オッズ取得"):
    if not race_id:
        st.error("レースIDを入力してください")
    else:
        url = f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"
        try:
            html = fetch_html(url)
            odds = parse_odds(html)

            if odds:
                st.success(f"{len(odds)}件取得")
                for k,v in sorted(odds.items(), key=lambda x:int(x[0])):
                    st.write(f"{k}番: {v}")
            else:
                st.warning("オッズ取得できません（JSの可能性）")

        except Exception as e:
            st.error(str(e))
