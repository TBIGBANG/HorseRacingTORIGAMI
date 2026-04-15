# 競馬トリガミ回避ツール（単勝 行ベース抽出版）

## 今回の変更
単勝オッズの netkeiba 抽出を、行ベースのロジックに変更しています。

### 単勝の抽出方針
- `type=b1` ページを優先取得
- 各 `tr` を1行として見る
- その行から `何枠 / 馬番 / 馬名 / オッズ` を抽出
- 印やチェック列があっても、列番号固定ではなく行の中身で判定
- 単勝はこの行ベース抽出を最優先で使用

## 起動
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Render Start Command
```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```
