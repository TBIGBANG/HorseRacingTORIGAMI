from __future__ import annotations

import requests
import streamlit as st

USER_AGENT = "Mozilla/5.0"
TIMEOUT = 15

def fetch_raw(race_id: str):
    url = "https://race.netkeiba.com/api/api_get_jra_odds.html"
    params = {
        "raceId": race_id,
        "type": "b1",
        "compress": "true"
    }
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}",
        "X-Requested-With": "XMLHttpRequest"
    }
    r = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
    r.raise_for_status()
    return r.content

st.title("APIレスポンス確認ツール")

race_id = st.text_input("レースID")

if st.button("API取得"):
    try:
        raw = fetch_raw(race_id)

        st.write("バイト長:", len(raw))

        st.subheader("① raw bytes（先頭）")
        st.code(raw[:500])

        try:
            txt = raw.decode("utf-8")
            st.subheader("② utf-8デコード")
            st.code(txt[:1000])
        except Exception as e:
            st.write("utf-8 decode失敗:", e)

        import gzip, zlib, base64

        # gzip
        try:
            g = gzip.decompress(raw).decode("utf-8")
            st.subheader("③ gzip解凍")
            st.code(g[:1000])
        except Exception:
            pass

        # zlib
        for wbits in [15, -15, 31]:
            try:
                z = zlib.decompress(raw, wbits).decode("utf-8")
                st.subheader(f"④ zlib解凍 wbits={wbits}")
                st.code(z[:1000])
                break
            except Exception:
                pass

        # base64
        try:
            b = base64.b64decode(raw)
            st.subheader("⑤ base64→decode")
            st.code(b[:500])
        except Exception:
            pass

    except Exception as e:
        st.error(str(e))
