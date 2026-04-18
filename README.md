# 競馬オッズAPI確認ツール（race_id修正版）

APIレスポンスの `reason: race_id empty` に対応して、
パラメータ名を `race_id` に修正した版です。

## Render 設定

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```
