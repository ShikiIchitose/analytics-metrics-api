# METRICS.md

## 目的

このドキュメントは、`analytics-metrics-api` が公開する metric の意味と解釈を定義するものです。

目的は、単に metric 名を並べることではなく、次の点を明示することにあります。

- 各 metric が何を意味するか
- どの事業上・プロダクト上の問いに答えるためのものか
- その metric から何が示唆されうるか
- その metric 単独では何が分からないか
- 現在の MVP 実装にどのような制約があるか

この repository では、**metric** とは API が返す **predefined KPI aggregate** を意味します。

---

## 現在の metric layer の範囲

v0.1.0 時点で API が公開している metric は、意図的に小さく絞られています。

- `dau`
- `new_users`
- `conversion_rate`

この範囲は意図的に最小限です。現在の metric set は、次の 3 つを最低限の指標で扱うために設計されています。

- acquisition
- engagement
- conversion

この repository は、deterministic な synthetic SaaS-like event data、DuckDB、Parquet を基盤とする offline-first の MVP です。したがって、現在の metric layer は、完全な analytics system というより、**各指標の定義・前提・制約を短時間で確認できる基盤**として読むべきものです。

> 注: 本プロジェクトで用いる SaaS-like event data は、固定 seed に基づいて生成した synthetic data です。実際の運用 event data をそのまま再現したものではありません。

---

## このドキュメントの読み方

以下の各 metric section は、次の 5 つの観点に沿って構成されています。

1. **定義**  
   何を計算しているのか。

2. **事業上・プロダクト上の問い**  
   どの問いに答えるための metric なのか。

3. **この指標から分かること・示唆されること**  
   どのような変化や傾向を示唆しうるか。

4. **この指標だけでは分からないこと**  
   その metric 単独では何を推論すべきでないか。

5. **現在の実装上の注意点**  
   この repository では、どのような簡略化や MVP 特有の制約があるか。

---

## 現在の KPI set の全体像

| Metric | 主な役割 | 主な事業上・プロダクト上の問い |
|---|---|---|
| `dau` | engagement の基本指標 | 実際に product を使っている user 数を把握する |
| `new_users` | acquisition の指標 | 新しい user を product に流入させられているかを見る |
| `conversion_rate` | funnel efficiency の指標 | `signup` が `checkout` のような後段の重要 event にどれだけ結びついているかを見る |

これらを合わせることで、入口の増加、継続的な利用、後段の転換を捉えるための最小限の指標セットを提供します。

---

## 各 metric の詳細

### 1. `dau`

**指標名:** Daily Active Users

**定義**  
各日について、何らかの event を持つ distinct `user_id` の数。

現在の実装では、`dau` は次の `group_by` をサポートします。

- `day`
- `country`
- `plan`

**事業上・プロダクト上の問い**  
この metric は、**実際にプロダクトを使っている user 数を把握すること**を目的としています。

これは engagement の基本的な KPI であり、product が日々どの程度利用されているかを把握するのに役立ちます。

**この指標から分かること・示唆されること**

- 日々の利用者数が増えているか減っているか
- launch, campaign, product change の前後で利用者数に変化があるか
- `country` や `plan` ごとに利用者数の違いがあるか
- 日次の利用者数という観点で、利用者層が広がっているか縮小しているか

**この指標だけでは分からないこと**

`dau` 単独では、次のことは分かりません。

- activity が `new_users` によるものか、既存 user によるものか
- users が本当にプロダクトから価値を得ているか
- usage が `checkout`、revenue、retention につながっているか
- 利用者数の増加が広い範囲で起きているのか、一部の users に偏っているのか

つまり、`dau` は**日次利用者数の増減を見る指標**としては有用ですが、単独で原因説明をする指標としては弱いです。

**現在の実装上の注意点**

- この metric では、**あらゆる event** を activity とみなします。
- 現時点では、軽い操作とプロダクト上重要な行動を区別していません。
- offline event dataset から計算されるため、表現力は現在の synthetic event model に依存します。
- `new_users` や `conversion_rate` と合わせて解釈するのが望ましいです。

---

### 2. `new_users`

**指標名:** New Users

**定義**  
その日に最初に観測された event を持つ distinct `user_id` の数。

現在の実装では、`new_users` は次の `group_by` のみをサポートします。

- `day`

**事業上・プロダクト上の問い**  
この metric は、**新しい user をプロダクトに流入させられているかを見ること**を目的としています。

これは acquisition KPI として機能し、現在の MVP における funnel の入口を表します。

**この指標から分かること・示唆されること**

- 新規流入が増加しているか減少しているか
- 獲得施策や導入時の入口が改善している可能性
- 最初に観測された activity の時点で user base が拡大しているかどうか

**この指標だけでは分からないこと**

`new_users` 単独では、次のことは分かりません。

- それらの users が後で再訪するか
- それらの users が転換するか
- それらの users が後で継続利用や `checkout` につながりやすいか
- 成長が持続的なのか一時的なのか

`new_users` が高くても、retention や downstream conversion が弱い可能性はあります。

**現在の実装上の注意点**

- この repository における “New” は、実務で使われるような詳細なユーザー状態ではなく、dataset 内で最初に観測された event を基準にした簡易な定義です。
- この metric は意図的に単純化されており、“first seen” とより厳密な `signup` / activation の定義はまだ区別していません。
- MVP では、これは完成した growth metric というより、**新規流入の入口を測る指標**として理解するのが適切です。

---

### 3. `conversion_rate`

**指標名:** Conversion Rate

**定義**  
対象 `window` 内で `signup` を持つ users のうち、同じ `window` 内で `checkout` も持つ users の割合。

返却 fields は次の通りです。

- `numerator`
- `denominator`
- `value`

この metric は現在 `group_by` をサポートしていません。

**事業上・プロダクト上の問い**  
この metric は、**`signup` が `checkout` のような後段の重要 event にどれだけ効率よく結びついているかを見ること**を目的としています。

これは現在の metric set の中で、最も明確な funnel-efficiency KPI です。

**この指標から分かること・示唆されること**

- `signup` から後続の重要な行動への移行が改善しているか悪化しているか
- onboarding や conversion flow の変更が `checkout` までの進みやすさに影響しているか
- acquisition volume が、後段の event 発生につながっているか

**この指標だけでは分からないこと**

`conversion_rate` 単独では、次のことは分かりません。

- なぜ users が転換しないのか
- `checkout` event が revenue の質を表すのか、単なる event occurrence に過ぎないのか
- users が選択した `window` の外側で転換しているか
- 国・`plan`・segment ごとの差異がどうなっているか

また、この指標は小さな `denominator` に敏感であり、低い件数の `window` では過度に解釈すべきではありません。

**現在の実装上の注意点**

- MVP では same-window simplification を採用しています。つまり、`signup` と `checkout` はどちらも要求された date `window` 内に存在する必要があります。
- API は慎重な解釈を支えるため、`numerator` と `denominator` を明示的に返します。
- `denominator < 20` の場合は warning が付与されます。
- `group_by` が未対応のため、現時点では `plan` や `country` ごとに分けた転換率ではなく、全体の `window` に対する転換率として機能します。

---

## 現在の KPI set がどのように組み合わさるか

現在の metric layer は意図的に小さく設計されていますが、この 3 つの metrics は恣意的ではありません。

それぞれ、異なる analytics 上の問いに対応しています。

- `new_users` → acquisition  
  新しい users は system に入ってきているか

- `dau` → engagement  
  users はプロダクトを実際に使っているか

- `conversion_rate` → funnel efficiency  
  `signup` は `checkout` のような後段の重要 event に結びついているか

つまり、この MVP はすでに最小限の product analytics structure を持っています。

1. users が system に入る
2. users が activity を示す
3. 一部の users がより重要な action に進む

---

## 現在の指標で分かること / まだ分からないこと

### 現在の指標で比較的見やすいこと

現在の指標群は、次のような点を比較的見やすくしています。

- 利用が発生しているか、またそれが時間とともに増減しているか
- 新しく入ってくる user が増えているように見えるか
- `signup` が `checkout` のような後段の重要な event につながっているか
- `dau by country` や `dau by plan` のように、簡単な区分ごとの見方ができるか

### 現在の指標だけでは、まだ十分に答えにくいこと

現在の MVP では、次のような問いに対しては、まだ十分に強い答えを返せません。

- users が day 1 や day 7 の後も継続して利用しているか
- どの `plan` や `country` で転換率が高いか
- どれだけの revenue が生まれているか
- users が離脱しているか
- acquisition から retention までの全体の流れがどうなっているか
- どの cohort が時間とともにどう変化するか

---

## 指標層における MVP としての制約

現在の指標層には、意図的に設けられた制約がいくつかあります。  
また､この repository の event data は synthetic data であり、実運用データに見られる分布、偏り、欠損、遅延、外れ値、計測誤差を完全には含みません。

### 1. Synthetic dataset

data は deterministic かつ synthetic です。これは reproducibility と offline testing に有利ですが、実運用の real production data に見られる複雑さをすべて反映しているわけではありません。

### 2. Narrow event vocabulary

event model は意図的に小さく絞られています。これにより各 metric の意味は追いやすくなりますが、行動の細かな違いまでは表現しにくくなっています。

### 3. Simplified user lifecycle semantics

“New user” や “conversion” は、実務で使われるより詳細な定義ではなく、MVP のために簡略化した運用上の定義です。

### 4. Limited segmentation

`dau` は `day`, `country`, `plan` で集計できますが、現在の指標群は、すべての KPI に対して十分に細かな切り分けを提供しているわけではありません。

### 5. No retention or revenue layer

現在の API は retention, revenue, churn, cohort-style metrics をまだ公開していません。

---

## 将来的に追加するとよい KPI の拡張候補

現在の指標層は、今後の拡張を見据えて設計されています。

たとえば、将来的には次のような追加が考えられます。

- **Retention metrics**
  - 例: D1, D7, D30 retention
  - first use の後も user が戻ってくるかを見る

- **Revenue-oriented metrics**
  - revenue totals
  - average revenue per user
  - `checkout` のような後段 event が事業上の価値につながっているかを見る

- **Churn-oriented metrics**
  - cancellation-based または inactivity-based churn
  - user が離脱しているか、または利用が弱まっているかを見る

- **Segmented funnel metrics**
  - conversion by `plan`
  - conversion by `country`
  - どの segment で転換率が高いか、低いかを見る

- **Cohort-based metrics**
  - signup cohort ごとの時系列での変化
  - 異なる時期に獲得した users が、その後どう振る舞うかを見る

---

## なぜ metric semantics を明示することが重要なのか

この repository は、単に API から JSON を返すことだけを目的としていません。

重要な設計目標の 1 つは、metric semantics を明示的かつレビュー可能にすることです。

- metric names は意図して定義されている
- required columns は文書化されている
- supported groupings は明示されている
- metric behavior は小さく保たれ、論理的に追いやすい
- future extensions は安定した baseline から議論できる

この明示性は、engineering と analytics の両方にとって重要です。実システムでは、文書化されていない metrics は曖昧になりやすく、信頼しづらく、安全に変更しにくくなります。

---

## まとめ

v0.1.0 時点で、`analytics-metrics-api` は意図的に小さな KPI layer を公開しています。

- `dau`
- `new_users`
- `conversion_rate`

これらの metrics は、次の 3 つに対する最小限だが意味のある指標セットを提供することを目的としています。

- acquisition
- engagement
- conversion

現在の実装は意図的に狭い範囲ですが、それでも 1 つの重要な engineering principle を示しています。

> 指標は、その定義・事業上の意味・解釈上の限界が明示されているとき、より実務で使いやすくなると考えます｡
