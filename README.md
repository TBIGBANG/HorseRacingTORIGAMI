# 競馬オッズ確認ツール（超軽量版）

この版は Playwright を使いません。  
`odds_get_form.html?type=b1&race_id=...` を直接取得して、単勝・複勝を解析します。

## Render 設定

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```
