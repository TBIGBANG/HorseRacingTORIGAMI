# 競馬オッズAPI確認ツール

この版は HTML の `---.-` を読むのではなく、
JS が参照している `https://race.netkeiba.com/api/api_get_jra_odds.html`
を直接呼んでオッズを取りに行きます。

## Render 設定

Build Command:
```bash
pip install -r requirements.txt
```

Start Command:
```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```
