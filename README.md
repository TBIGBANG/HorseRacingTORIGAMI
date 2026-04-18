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
