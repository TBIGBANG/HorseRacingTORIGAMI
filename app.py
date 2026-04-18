from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st
from bs4 import BeautifulSoup

APP_DIR = Path(__file__).resolve().parent
PLAYWRIGHT_DIR = APP_DIR / ".playwright"
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_DIR)

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
except Exception:
    PlaywrightTimeoutError = Exception
    sync_playwright = None


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
TIMEOUT_SECONDS = 20


def normalize_race_id(raw: str) -> str:
    return re.sub(r"\D", "", (raw or "").strip())


def build_b1_url(race_id: str) -> str:
    return f"https://race.netkeiba.com/odds/index.html?type=b1&race_id={race_id}"


def ensure_playwright_ready() -> None:
    """
    Render で browser executable が見つからない場合に備えて、
    起動時にも Playwright browser を自己修復インストールする。
    """
    if sync_playwright is None:
        raise RuntimeError("Playwright ライブラリ自体が読み込めません。requirements.txt を確認してください。")

    PLAYWRIGHT_DIR.mkdir(parents=True, exist_ok=True)

    def try_launch() -> bool:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-dev-shm-usage", "--no-sandbox", "--disable-gpu"],
                )
                browser.close()
            return True
        except Exception:
            return False

    if try_launch():
        return

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_DIR)

    # まずは全部入り install
    subprocess.run(
        ["python", "-m", "playwright", "install"],
        env=env,
        check=False,
    )

    if try_launch():
        return

    # 念のため chromium だけも再実行
    subprocess.run(
        ["python", "-m", "playwright", "install", "chromium"],
        env=env,
        check=False,
    )

    if try_launch():
        return

    raise RuntimeError(
        f"Playwright browser の準備に失敗しました。"
        f" PLAYWRIGHT_BROWSERS_PATH={PLAYWRIGHT_DIR}"
    )


def fetch_html_raw(url: str) -> str:
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


def fetch_html_rendered(url: str, timeout_ms: int = 20000) -> str:
    ensure_playwright_ready()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        page = browser.new_page(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 2600},
            locale="ja-JP",
        )
        page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

        selectors = [
            "span[id^='odds-1_']",
            "span[id^='odds-2_']",
            "#odds_tan_block table.RaceOdds_HorseList_Table",
            "#odds_view_form table.RaceOdds_HorseList_Table",
        ]

        found_any = False
        for selector in selectors:
            try:
                page.wait_for_selector(selector, timeout=timeout_ms)
                found_any = True
                break
            except PlaywrightTimeoutError:
                pass

        if found_any:
            page.wait_for_timeout(1200)
            for _ in range(12):
                texts = page.locator("span[id^='odds-1_'], span[id^='odds-2_']").all_text_contents()
                joined = " ".join(t.strip() for t in texts if t and t.strip())
                if re.search(r"\d+\.\d+|\d+\s*-\s*\d+", joined):
                    break
                page.wait_for_timeout(500)

        html = page.content()
        browser.close()
        return html


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


def parse_b1_odds(html: str) -> Tuple[Dict[str, str], Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")

    horse_map: Dict[str, str] = {}
    win_map: Dict[str, float] = {}
    win_display: Dict[str, str] = {}
    place_map: Dict[str, float] = {}
    place_display: Dict[str, str] = {}

    def extract_row_odds_text(row, horse_no: int, is_place: bool) -> str:
        suffix = f"{horse_no:02d}"

        sel = f"span[id='odds-2_{suffix}']" if is_place else f"span[id='odds-1_{suffix}']"
        node = row.select_one(sel)
        if node is not None:
            txt = node.get_text(" ", strip=True)
            if txt:
                return txt

        node = row.select_one("td.Odds span.Odds, td.Odds span[class*='Odds']")
        if node is not None:
            txt = node.get_text(" ", strip=True)
            if txt:
                return txt

        node = row.select_one("td.Odds")
        if node is not None:
            txt = node.get_text(" ", strip=True)
            if txt:
                return txt

        cells = row.select("td")
        if cells:
            txt = cells[-1].get_text(" ", strip=True)
            if txt:
                return txt

        return ""

    row_groups = [
        ("#odds_tan_block table.RaceOdds_HorseList_Table tr", False),
        ("#odds_fuku_block table.RaceOdds_HorseList_Table tr", True),
        ("#odds_view_form table.RaceOdds_HorseList_Table tr", False),
    ]

    for selector, default_is_place in row_groups:
        for row in soup.select(selector):
            name_cell = row.select_one(".Horse_Name")
            if name_cell is None:
                continue

            cells = row.select("td")
            if len(cells) < 2:
                continue

            horse_no: Optional[int] = None
            is_place = default_is_place

            odds_span = row.select_one("span[id^='odds-1_'], span[id^='odds-2_']")
            if odds_span is not None:
                m = re.search(r"odds-(\d+)_(\d{1,2})$", odds_span.get("id", ""))
                if m:
                    horse_no = int(m.group(2))
                    is_place = (m.group(1) == "2")

            if horse_no is None:
                nums: List[int] = []
                for cell in cells:
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

            odds_text = extract_row_odds_text(row, horse_no, is_place)
            if not odds_text:
                continue

            if is_place:
                val, disp = parse_place_text(odds_text)
                if val is not None and disp is not None:
                    place_map[horse_key] = val
                    place_display[horse_key] = disp
            else:
                val, disp = parse_win_text(odds_text)
                if val is not None and disp is not None:
                    win_map[horse_key] = val
                    win_display[horse_key] = disp

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


def fetch_b1_data(race_id: str, use_render: bool) -> Tuple[str, Dict[str, str], Dict[str, float], Dict[str, str], Dict[str, float], Dict[str, str]]:
    url = build_b1_url(race_id)
    html = fetch_html_rendered(url) if use_render else fetch_html_raw(url)
    horse_map, win_map, win_display, place_map, place_display = parse_b1_odds(html)
    return url, horse_map, win_map, win_display, place_map, place_display


st.set_page_config(page_title="競馬オッズ確認ツール", page_icon="🏇", layout="centered")
st.title("競馬オッズ確認ツール")
st.caption("まずは netkeiba の単勝・複勝を正しく取れることだけを確認する版です。")

race_id = st.text_input("レースID", placeholder="例: 202609020611")
use_render = st.checkbox("JS差し込み後のHTMLを使う（Playwright）", value=True)

if st.button("netkeibaから1回取得", type="primary"):
    race_id = normalize_race_id(race_id)

    if len(race_id) != 12:
        st.error("12桁のレースIDを入力してください。")
        st.stop()

    try:
        url, horse_map, win_map, win_display, place_map, place_display = fetch_b1_data(race_id, use_render=use_render)

        st.success("取得処理は完了しました。")
        st.caption(f"取得元: {url}")
        st.caption(f"Playwright browser path: {os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '')}")

        if not win_map and not place_map:
            st.warning("オッズを取得できませんでした。")
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
