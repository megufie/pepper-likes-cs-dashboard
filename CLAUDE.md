# PEPPER LIKES CS Dashboard

## プロジェクト概要

外国人インフルエンサー × 企業マッチングプラットフォーム「PEPPER LIKES」の
カスタマーサクセス（CS）チーム向け分析ダッシュボード。

## スタック

- Python 3.14 + Streamlit + DuckDB（インメモリ）
- 本番MySQL（読み取り専用）+ Google Sheets + Slack の3ソース統合

## 起動

```bash
cd ~/Documents/cs-dashbord
./start.sh
# → http://localhost:8501
```

## データソース

| ソース | 用途 | 状態 |
|---|---|---|
| 本番DB（MySQL） | ユーザー、契約、募集、応募、メッセージ（読み取り専用） | ⚠️ 2026-03-26以降のメッセージ/応募は同期されていない |
| 契約マスタシート | 継続率・解約理由・担当営業 | ✅ 最新 |
| 個別対策確認シート | 案件×応募数 | ✅ 最新 |
| 採用・投稿数シート | 月別 採用/投稿カウント | ✅ 最新 |
| Slack #likes_解約報告 | 解約速報・理由 | ✅ リアルタイム |

## 認証情報（gitignore済）

- `.env` — DB接続情報、Slack Bot Token、Slack Channel ID
- `credentials.json` — GCP サービスアカウント鍵
- 共有先：
   - サービスアカウント `cs-dashboard-reader@chrome-cascade-495715-j0.iam.gserviceaccount.com`
   - シート2件に閲覧者権限付与済
- Slack App: `CS Dashboard Reader` を `#likes_解約報告` に招待済

## 主な画面（8ページ）

1. **概要** — KPI・継続月数ランキング・企業×月マトリクス（採用数）
2. **継続率分析** — 6/12ヶ月継続率・コホートヒートマップ・プラン/担当別
3. **継続・契約** — 月次活動マトリクス
4. **週次活動** — 週次メッセージ・連続0件アラート
5. **解約分析** — Slack速報・理由内訳・3ソース整合性
6. **募集品質KPI** — 12点重み付けスコア・募集年齢分布
7. **応募分析** — 月別応募/採用・バケット・都道府県/ジャンル別
8. **企業レポート** — 単一企業ドリルダウン

## 既知の課題

1. **DBのメッセージ/応募データが2026-03-26で更新停止**
   - 新メッセージング基盤の場所を要確認（開発チーム）
2. **Slackトークンとサービスアカウントは外部に漏洩しない**
   - 万一の場合は再発行で無効化可能

## ファイル構成

```
cs-dashbord/
├── app.py                      # Streamlit エントリポイント
├── config.py                   # 環境設定読み込み
├── start.sh                    # 起動スクリプト
├── requirements.txt
├── .env                        # 認証情報（gitignore）
├── credentials.json            # GCP鍵（gitignore）
├── src/
│   ├── loader.py               # DB + シート + Slack 統合読み込み
│   ├── queries.py              # SQL クエリ群
│   ├── analytics.py            # 集計ロジック
│   ├── sheet_loader.py         # Google Sheets 読み込み
│   └── slack_loader.py         # Slack #likes_解約報告 読み込み
└── data/                       # ローカルCSVテストデータ（不使用）
```

## 重要な業務ロジック

- **掲載中の判定**：`projects.status='publish' AND proposal_status='open'`
- **継続月数**：シート由来。`掲載開始日 → 解約日（or 今日）` のカレンダー月単位
- **応募0件**：個別対策確認シートで `G∈{募集中,空白} AND H∈{解約連絡あり,公開中,空白} AND L=0`
- **解約**：Slackが速報源、シートが詳細、DB（package_subscribers）は購読履歴

## Claude Code への引き継ぎ

何か追加変更したいときの観点：
- メッセージング系指標は DB が古いので、新基盤確認後に接続更新
- シート連携は `@st.cache_resource` でキャッシュされるので、変更後は streamlit 再起動が必要
- 新しい画面追加時は `app.py` の `PAGE_LABELS` / `PAGE_KEYS` / 8番目のレンダー関数を追加
