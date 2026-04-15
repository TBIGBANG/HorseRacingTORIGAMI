# 競馬トリガミ回避ツール 公開版

別Wi‑Fiやモバイル回線からでも使えるように、インターネット公開しやすい形にした Streamlit アプリです。

## 追加したもの
- Render / Railway / Streamlit Community Cloud に載せやすい構成
- `Procfile`
- `runtime.txt`
- `.streamlit/config.toml`
- 簡易アクセスコード機能（環境変数 `APP_PASSWORD`）

## できること
- レースID入力
- 軍資金入力
- 買い目入力
- ボタン押下時だけ netkeiba の該当ページを1回取得
- オッズ抽出
- 買い目ごとの払戻見込とトリガミ判定
- 必要なら購入額の再配分案
- 取得失敗時の手動オッズ入力

## 公開方法

### 1) GitHub にアップロード
このフォルダをそのまま GitHub リポジトリへ置きます。

### 2) Render で公開
- Render で New + > Web Service
- GitHub リポジトリを選択
- Build Command:

```bash
pip install -r requirements.txt
```

- Start Command:

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

- Environment Variables:
  - `APP_PASSWORD` = 好きなアクセスコード

公開後は、発行された `https://xxxxx.onrender.com` を開けば、別Wi‑Fiからでも使えます。

### 3) Railway で公開
- New Project > Deploy from GitHub
- Variables に `APP_PASSWORD` を追加
- Start command は次です

```bash
streamlit run app.py --server.port=$PORT --server.address=0.0.0.0
```

### 4) Streamlit Community Cloud
そのまま載せられることがありますが、外部サイトへのアクセスやスクレイピング周りの制限で動作が不安定になる場合があります。安定性は Render / Railway の方が読みやすいです。

## アクセスコード
環境変数 `APP_PASSWORD` を設定すると、公開URLに入る前にコード入力を求めます。

設定しない場合は誰でも開けます。

## ローカル起動
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 注意
- netkeiba 側の HTML 構造や URL 形式が変わると取得できないことがあります。
- 利用規約は各自で確認してください。
- 公開サーバーからのスクレイピングは、自宅PCからのローカル利用より目立ちやすくなります。
- 長時間の大量アクセスではなく、手動1回取得の前提を守ってください。
