# AEO Monitor

AI検索エンジン最適化（AEO）モニタリングツール。

ChatGPT / Perplexity / Gemini などのAI検索で、あなたのブランドが推薦されているかを追跡・可視化します。

## 🌐 Webサイト

**[https://shinogw.github.io/aeo-monitor/](https://shinogw.github.io/aeo-monitor/)**

## Features

- 🔍 AI検索での言及率モニタリング（ChatGPT / Gemini対応）
- 🏢 競合ベンチマーク比較
- 📊 Webダッシュボード
- 🤖 AI改善提案の自動生成
- 📝 CSV / Markdown レポート出力

## Quick Start

```bash
# クローン
git clone https://github.com/shinogw/aeo-monitor.git
cd aeo-monitor

# 設定ファイルを作成
cp configs/sample-tax.json configs/my-client.json
# my-client.json を編集（自社名・競合・質問を設定）

# APIキー設定
export OPENAI_API_KEY="sk-..."
export GEMINI_API_KEY="..."  # オプション

# モニタリング実行
python3 aeo_monitor.py configs/my-client.json

# ダッシュボード起動
python3 server.py
# → http://localhost:8080
```

## 設定ファイル

`configs/sample-tax.json` をテンプレートとして使用：

```json
{
  "client_name": "クライアント名",
  "industry": "業種",
  "region": "地域",
  "target_brands": ["自社ブランド"],
  "competitors": ["競合A", "競合B"],
  "queries": ["AI検索で投げる質問"],
  "providers": ["chatgpt", "gemini"],
  "runs_per_query": 3
}
```

## 出力

- `reports/report-*.md` — Markdownレポート
- `reports/summary-*.csv` — CSV集計
- `data/dashboard-latest.json` — ダッシュボード用データ
- `reports/advice-*.md` — AI改善提案

## License

MIT
