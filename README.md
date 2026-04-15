# 競馬トリガミ回避ツール（行ベース抽出版）

## 変更点
この版では、単勝・複勝の netkeiba 抽出ロジックを **馬番ごとの行ベース** に変更しています。

### 単勝・複勝の抽出方針
- `type=b1` ページを優先取得
- 表のヘッダーから `馬番` 列と `オッズ` 列を探す
- **各行の馬番セルと、その同じ行のオッズセルだけ** を読む
- ページ全体の数字や race_id などは単勝・複勝抽出に使わない

## 起動方法
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Render の start command
```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```
