# 競馬オッズ確認ツール（Playwright 自己修復版）

Render 設定:

Build Command:
```bash
bash render-build.sh
```

Start Command:
```bash
bash render-start.sh
```

この版は:
- `.playwright/` に browser を固定
- Build 時に `python -m playwright install`
- 実行時にも不足していたら自己修復インストール


## タイムアウト対策
この版では `Page.goto(..., wait_until="domcontentloaded")` をやめて、より軽い待機方式に変更しています。

- 画像・広告・フォントなど重い通信をブロック
- `goto` は `commit` までで先に進む
- `odds_get_form.html?type=b1...` を優先取得
- タイムアウトしても、その時点の DOM で解析
