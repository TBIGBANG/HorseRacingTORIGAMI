# 競馬オッズ確認ツール（クリーン版・Playwright対応）

この版は、まず netkeiba の `type=b1` ページから
- 馬名
- 単勝
- 複勝

が正しく取れるかだけを確認するための最小版です。

## Render 設定

Build Command:
```bash
bash render-build.sh
```

Start Command:
```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

環境変数（任意）:
```text
PLAYWRIGHT_BROWSERS_PATH=0
```
