# analytics-metrics-api

FastAPI・DuckDB・Parquet で構成した、offline-first な product analytics Metrics API です。

## 概要

このリポジトリは、ポートフォリオの一部として作成した、**小さいが設計意図の明確なバックエンド API** です。

deterministic な synthetic SaaS event dataset をローカルに生成し、DuckDB で問い合わせ、FastAPI で read-only の HTTP API として公開します。現時点の主要 endpoint は以下です。

- `GET /health`
- `GET /metrics`
- `GET /metrics/{name}`
- `GET /users/{user_id}`

このリポジトリを通じて示したいこと:

- **バックエンドの基礎力**: FastAPI による API 実装を通じて、ルーティング、入力検証、ステータスコード設計、エラーハンドリング、型を意識した境界設計、リソース指向の HTTP 設計を扱えること。
- **データ処理基盤の基礎力**: 再現可能なサンプルデータ生成、DuckDB によるクエリ実行、Parquet を用いたローカルデータ管理、 metric 定義の安定化、オフライン回帰テストを含む一連の流れを設計・実装できること。
- **開発運用の基礎力**: `uv` を用いた再現可能な環境構築、offline-first の CI(continuous integration: 継続的インテグレーション)、golden output を用いたテスト運用、明示的な契約に基づく実装によって、小規模でも保守しやすい構成を意識していること。

### ポートフォリオとしての狙い

このリポジトリは、主に backend / data-oriented role 向けのポートフォリオとして作っています。次の点を確認してもらうことを狙っています。

- 小さくても API contract を意識して設計できる
- app 層・query 層・data generation 層を分離できる
- 再現性と testability を重視した実装判断ができる
- 「とりあえず動く」ではなく、最低限の engineering hygiene を持った repo を作れる

大きな demo ではなく、**実務寄りの判断力を小さな成果物で証明する** ための repository です。

### 開発サマリー

このリポジトリの設計意図や改善の流れを日本語でまとめた資料として、[`docs/development-highlights.ja.md`](docs/development-highlights.ja.md) を用意しています。

## RESTful を意識した設計

この API は、**resource-oriented な HTTP / REST-style design** を意識して設計しています。

- resource は安定した path で表現する
  - `GET /health`
  - `GET /metrics`
  - `GET /metrics/{name}`
  - `GET /users/{user_id}`
- resource identity は path parameter で表す
  - `{name}`
  - `{user_id}`
- filtering / windowing / shaping は query parameter に分ける
  - `start`
  - `end`
  - `group_by`
  - `limit`
- MVP は read-only なので、公開 method は `GET` のみ
- 成功系・失敗系は HTTP status code (`200`, `404`, `422`) で表現
- 正常 response は `data` + `meta` envelope で統一

これは「完全な REST maturity model の実装」ではありません。ここでの狙いは、**小規模なポートフォリオ API でも resource boundary・URL design・HTTP semantics を意識している**ことを示す点にあります。

## このアプリがやること

アプリはローカルの Parquet dataset を読み、DuckDB で query を実行し、metrics catalog と user entity を JSON API として返します。

### 現在の MVP scope

- Dataset: deterministic な synthetic SaaS-style events
  - `signup`
  - `login`
  - `checkout`
  - `cancel`
- Storage: `data/clean/events.parquet`
- Query engine: DuckDB
- API framework: FastAPI
- Main endpoints:
  - `GET /health`
  - `GET /metrics`
  - `GET /metrics/{name}`
  - `GET /users/{user_id}`

### Metrics included in v0.1.0

- `dau`: Daily Active Users
- `new_users`: その日に初めて観測されたユーザー数
- `conversion_rate`: 対象期間内に `signup` したユーザーのうち、同じ期間内に `checkout` も行ったユーザーの割合

### Why these metrics matter

これらの指標は意図的に小さなスコープに絞っていますが、プロダクト分析やビジネス上の典型的な問いに対応しています。

- `dau` はエンゲージメントのベースラインとなる KPI であり、「何人のユーザーが実際にプロダクトを使っているか？」に答えます。
- `new_users` は獲得(acquisition)の KPI であり、「新しいユーザーをプロダクトに流入させられているか？」に答えます。
- `conversion_rate` はファネル効率(funnel efficiency)の KPI であり、「signup が downstream value event にどれだけ効率よく結びついているか？」に答えます。

これらを合わせることで、acquisition・engagement・conversion を捉える最小限の analytics view を提供します。

metric の定義、実務を想定した場合の意味、現在の制約についての詳しい説明は、[METRICS.ja.md](METRICS.ja.md) を参照してください。

## Architecture at a glance

```text
Synthetic generator -> Parquet dataset -> DuckDB queries -> FastAPI endpoints -> JSON responses
```

### Main modules

- `src/app/main.py` — app factory, routes, response shaping
- `src/app/warehouse.py` — DuckDB query layer
- `src/app/metrics_catalog.py` — metric definitions / allow-lists
- `src/app/models.py` — runtime config
- `src/app/synth.py` — deterministic synthetic dataset generation
- `scripts/generate_sample.py` — sample dataset generation CLI
- `tools/write_golden_params.py` — golden parameter file generator
- `tools/regenerate_golden.py` — golden output regeneration
- `tests/` — offline API tests and golden comparisons

## Repository layout

```text
analytics-metrics-api/
  pyproject.toml
  uv.lock
  README.md
  README.ja.md
  METRICS.md
  METRICS.ja.md
  data/
    clean/
      .gitkeep
  warehouse/
    warehouse.duckdb
  src/
    app/
      __init__.py
      main.py
      warehouse.py
      metrics_catalog.py
      models.py
      synth.py
  scripts/
    generate_sample.py
  tools/
    write_golden_params.py
    regenerate_golden.py
  tests/
    conftest.py
    golden/
      params.json
      dau_by_day_rows.json
      user_42.json
    test_health.py
    test_entities.py
    test_metrics_list.py
    test_metrics_known_value.py
  .github/
    workflows/
      ci.yml
  sql/
    debug/
      conversion_rate_window.sql
      new_users_window.sql
      dau_window_by_plan.sql
      dau_window_by_day.sql
      dau_window_by_country.sql
```

`sql/debug/` には、ローカルの Parquet データセットに対して DuckDB で metric のロジックを直接確認するための手動検証用 SQL を置いています。これらのファイルは開発補助用であり、`src/app/warehouse.py` に実装されているアプリケーション本体のクエリを置き換えるものではありません。

## Quickstart

### 1. Dependencies を入れる

```bash
uv sync --locked
```

### 2. deterministic sample dataset を生成する

```bash
uv run python scripts/generate_sample.py \
  --seed 18790314 \
  --start 2026-01-01 \
  --days 7 \
  --n_users 50 \
  --events_per_user 3 \
  --known_user_id 42
```

生成物:

```text
data/clean/events.parquet
```

### 3. API を起動する

```bash
uv run uvicorn app.main:app --reload
```

### 4. Endpoint を叩く

Health:

```bash
curl "http://127.0.0.1:8000/health"
```

Metric catalog:

```bash
curl "http://127.0.0.1:8000/metrics"
```

DAU by day:

```bash
curl "http://127.0.0.1:8000/metrics/dau?start=2026-01-01&end=2026-01-07&group_by=day&limit=365"
```

User entity:

```bash
curl "http://127.0.0.1:8000/users/42"
```

## Example responses

### `GET /health`

```json
{
  "status": "ok",
  "version": "0.1.0",
  "dataset": "synthetic_saas_v0",
  "warehouse": {
    "duckdb": "ready",
    "events_rows": 150
  }
}
```

### `GET /metrics`

```json
{
  "data": {
    "metrics": [
      {
        "name": "dau",
        "title": "Daily Active Users",
        "description": "Unique users with any event per day.",
        "supported_group_by": ["day", "country", "plan"],
        "required_columns": ["event_time", "user_id"]
      }
    ]
  },
  "meta": {
    "dataset": "synthetic_saas_v0"
  }
}
```

### `GET /users/42`

```json
{
  "data": {
    "user_id": 42,
    "signup_time": "2026-01-01T00:37:00Z",
    "country": "US",
    "plan": "pro"
  },
  "meta": {
    "dataset": "synthetic_saas_v0"
  }
}
```

## Testing

この repository は **offline-first** を前提にしています。

### Run tests

```bash
uv run pytest
```

### テストが見ていること

- `GET /health` が `200` を返す
- `GET /users/{user_id}` が missing user に対して `404` を返す
- `GET /users/{user_id}` が固定 user に対して stable な known output を返す
- `GET /metrics` が stable な catalog structure を返す
- `GET /metrics/dau` が固定 window に対して known expected rows を返す

### Testing design notes

- テスト用 dataset は固定 golden parameters から deterministic に生成する
- Golden files は Parquet snapshot ではなく JSON を commit する
- Metric tests は `response["data"]["rows"]` のような stable subset を比較する
- Entity tests は `response["data"]` を比較する
- `pytest-socket` は default で socket を disable し、`TestClient` が必要な `client` fixture だけ `socket_enabled` で許可する

Golden outputs の再生成:

```bash
uv run python tools/regenerate_golden.py
```

## CI

この repository には、offline-first の検証を行うための GitHub Actions workflow が含まれています。

### CI で実行するもの

現在の CI では、次のチェックを実行します。

- `uv run ruff check .`
- `uv run pytest`
- `uv run pyrefly check`

### この project に CI を置く理由

この repository における CI の目的は、project を再現しやすくし、レビューしやすく保つことです。

- スタイル上の問題や静的な問題を自動で確認する
- 外部ネットワークに依存せずにテストを実行する
- lint や test に加えて、型の整合性も確認する

目的は大がかりな delivery pipeline を作ることではなく、小さな portfolio project の中で、再現性を意識した engineering 上の姿勢を示すことにあります。

## 意図的な設計判断

### 1. service-heavy ではなく offline-first

MVP では cloud dependency・external API・mandatory container を避けています。これにより、signal を application structure・query logic・reproducibility に集中させています。

### 2. opaque な sample dump ではなく deterministic synthetic data

Dataset は固定 seed と明示的な parameters から生成します。挙動が inspectable で repeatable になります。

### 3. 重い DB stack ではなく DuckDB + Parquet

ポートフォリオ用の MVP としては、DuckDB と Parquet で local analytical query・schema awareness・read pattern を十分示せます。

### 4. ad hoc endpoint ではなく resource-oriented API

Route は小さいですが、意味のある resource として整理しています。

- catalog resource: `/metrics`
- metric resource: `/metrics/{name}`
- user resource: `/users/{user_id}`

### 5. brittle な full-response 比較ではなく golden-output tests

`meta` などの補助情報に引きずられて test suite が noisy にならないよう、stable な部分を比較対象にしています。

## 何を見てほしいか(まとめ)

- 小さな HTTP API を設計できるか
- API・query・data generation の責務分離ができているか
- 再現性と一貫したテスト運用方針があるか
- MVP project として適切な scope に収められているか

## Roadmap

Possible follow-up PR:

- richer metric contracts と追加 KPI の導入
- `users.parquet` を追加し、events-derived な user entity より優先する
- dbt-based transformations の追加
- minimal TypeScript client または UI の追加
- metric documentation と data contract checks の拡充

## License

MIT License. See `LICENSE` file.
