# METRICS.md

> 日本語版: [METRICS.ja.md](METRICS.ja.md)

## Purpose

This document defines the meaning and interpretation of the metrics exposed by `analytics-metrics-api`.

Its purpose is not simply to list metric names, but to make the following explicit:

- what each metric means
- which business or product question it is intended to answer
- what the metric can indicate
- what the metric cannot tell us on its own
- what limitations exist in the current MVP implementation

In this repository, a **metric** means a **predefined KPI aggregate** returned by the API.

---

## Scope of the current metric layer

As of v0.1.0, the API intentionally exposes only a small set of metrics:

- `dau`
- `new_users`
- `conversion_rate`

This scope is intentionally minimal. The current metric set is designed to cover three core areas with the smallest practical set of indicators:

- acquisition
- engagement
- conversion

This repository is an offline-first MVP built on deterministic synthetic SaaS-like event data, DuckDB, and Parquet. The current metric layer should therefore be read not as a complete analytics system, but as a compact foundation whose definitions, assumptions, and limitations can be reviewed quickly.

> Note: The SaaS-like event data used in this project is synthetic data generated from a fixed seed. It is not intended to directly reproduce real production event data.

---

## How to read this document

Each metric section below is organized around the following five viewpoints:

1. **Definition**  
   What is being computed?

2. **Business or product question**  
   What question is this metric intended to answer?

3. **What this metric can indicate**  
   What kinds of changes or patterns can it suggest?

4. **What this metric cannot tell us on its own**  
   What should not be inferred from this metric alone?

5. **Current implementation notes**  
   What simplifications or MVP-specific constraints apply in this repository?

---

## Overview of the current KPI set

| Metric | Primary role | Main business or product question |
|---|---|---|
| `dau` | Core engagement metric | How many users are actually using the product? |
| `new_users` | Acquisition metric | Are we bringing new users into the product? |
| `conversion_rate` | Funnel-efficiency metric | How effectively does `signup` lead to a later important event such as `checkout`? |

Taken together, these metrics provide a minimal set of indicators for understanding top-of-funnel growth, ongoing usage, and downstream conversion.

---

## Details of each metric

### 1. `dau`

**Metric name:** Daily Active Users

**Definition**  
The number of distinct `user_id` values with any event on each day.

In the current implementation, `dau` supports the following `group_by` values:

- `day`
- `country`
- `plan`

**Business or product question**  
This metric is intended to measure **how many users are actually using the product**.

It is a core engagement KPI and helps us understand the extent to which the product is being used on a day-to-day basis.

**What this metric can indicate**

- whether the number of daily active users is increasing or decreasing
- whether launches, campaigns, or product changes are associated with shifts in usage
- whether usage differs by `country` or `plan`
- whether the user base is expanding or shrinking in terms of daily activity

**What this metric cannot tell us on its own**

On its own, `dau` does not tell us:

- whether the activity is coming from `new_users` or existing users
- whether users are actually getting value from the product
- whether usage leads to `checkout`, revenue, or retention
- whether growth in active users is broad-based or concentrated among a small subset of users

In other words, `dau` is useful for tracking changes in daily active users, but it is weak as a standalone explanation of why those changes happened.

**Current implementation notes**

- This metric treats **any event** as activity.
- At present, it does not distinguish between lightweight actions and product-important actions.
- Because it is computed from an offline event dataset, its expressiveness depends on the current synthetic event model.
- It is best interpreted together with `new_users` and `conversion_rate`.

---

### 2. `new_users`

**Metric name:** New Users

**Definition**  
The number of distinct `user_id` values whose first observed event occurs on that day.

In the current implementation, `new_users` supports only the following `group_by` value:

- `day`

**Business or product question**  
This metric is intended to measure **whether new users are entering the product**.

It functions as an acquisition KPI and represents the entry point of the funnel in the current MVP.

**What this metric can indicate**

- whether new user inflow is increasing or decreasing
- whether acquisition efforts or entry points into the product may be improving
- whether the user base appears to be growing at the point of first observed activity

**What this metric cannot tell us on its own**

On its own, `new_users` does not tell us:

- whether those users come back later
- whether those users convert
- whether those users are likely to continue using the product or eventually reach `checkout`
- whether the growth is sustainable or temporary

A high `new_users` value can still coexist with weak retention or weak downstream conversion.

**Current implementation notes**

- In this repository, “New” is not a detailed user lifecycle state of the kind often used in production systems. It is a simplified operational definition based on the first observed event in the dataset.
- This metric is intentionally simple and does not yet distinguish between “first seen” and stricter definitions of `signup` or activation.
- In the MVP, this metric is best understood not as a complete growth metric, but as an indicator of new-user inflow at the top of the funnel.

---

### 3. `conversion_rate`

**Metric name:** Conversion Rate

**Definition**  
Among users with a `signup` event in the requested `window`, the fraction who also have a `checkout` event within the same `window`.

The returned fields are:

- `numerator`
- `denominator`
- `value`

This metric does not currently support `group_by`.

**Business or product question**  
This metric is intended to measure **how efficiently `signup` leads to a later important event such as `checkout`**.

It is the clearest funnel-efficiency KPI in the current metric set.

**What this metric can indicate**

- whether movement from `signup` to a later important action is improving or deteriorating
- whether changes to onboarding or the conversion flow may be affecting how easily users reach `checkout`
- whether acquisition volume is translating into later event occurrence

**What this metric cannot tell us on its own**

On its own, `conversion_rate` does not tell us:

- why users fail to convert
- whether the `checkout` event reflects revenue quality or only the occurrence of an event
- whether users convert outside the selected `window`
- how behavior differs across countries, `plan` values, or other segments

This metric is also sensitive to a small `denominator`, so it should not be over-interpreted in low-volume windows.

**Current implementation notes**

- The MVP uses a same-window simplification. In other words, both `signup` and `checkout` must occur within the requested date `window`.
- The API returns `numerator` and `denominator` explicitly to support more careful interpretation.
- A warning is attached when `denominator < 20`.
- Because `group_by` is not supported yet, this currently functions as an overall conversion rate for the selected `window`, rather than a segmented conversion rate by `plan` or `country`.

---

## How the current KPI set works together

The current metric layer is intentionally small, but these three metrics are not arbitrary.

Each one corresponds to a different analytics question:

- `new_users` → acquisition  
  Are new users entering the system?

- `dau` → engagement  
  Are users actually using the product?

- `conversion_rate` → funnel efficiency  
  Does `signup` lead to a later important event such as `checkout`?

This means the MVP already captures a minimal product-analytics structure:

1. users enter the system
2. users show activity
3. some users move on to a more important action

---

## What the current metrics can show well / what they still cannot show well

### What the current metrics can show relatively well

The current set of metrics is reasonably good at showing the following:

- whether activity is occurring, and whether it is increasing or decreasing over time
- whether inflow of new users appears to be growing
- whether `signup` is leading to a later important event such as `checkout`
- whether simple segmented views such as `dau by country` or `dau by plan` are available

### What the current metrics still cannot answer well on their own

In the current MVP, the following questions cannot yet be answered strongly enough:

- whether users continue using the product after day 1 or day 7
- which `plan` or `country` has a higher conversion rate
- how much revenue is being generated
- whether users are churning
- what the full flow from acquisition to retention looks like
- how different cohorts change over time

These are natural next questions, but they are intentionally outside the current MVP scope.

---

## MVP-level limitations of the metric layer

The current metric layer has several deliberate limitations.  
Also, because this repository uses synthetic event data, it does not fully capture the distributions, biases, missingness, delays, outliers, or measurement errors often found in production data.

### 1. Synthetic dataset

The data is deterministic and synthetic. This is useful for reproducibility and offline testing, but it does not fully reflect the complexity found in real production data.

### 2. Narrow event vocabulary

The event model is intentionally small. This makes the meaning of each metric easier to inspect, but it also limits how precisely differences in user behavior can be represented.

### 3. Simplified user lifecycle semantics

“New user” and “conversion” are simplified operational definitions for the MVP, not detailed production-grade business definitions.

### 4. Limited segmentation

`dau` can be grouped by `day`, `country`, and `plan`, but the current metric set does not yet provide sufficiently fine-grained breakdowns for every KPI.

### 5. No retention or revenue layer

The current API does not yet expose retention, revenue, churn, or cohort-style metrics.

---

## Future KPI extension candidates

The current metric layer is designed with future extension in mind.

For example, the following additions would be natural next steps:

- **Retention metrics**
  - e.g. D1, D7, D30 retention
  - to measure whether users return after first use

- **Revenue-oriented metrics**
  - revenue totals
  - average revenue per user
  - to measure whether later events such as `checkout` are connected to business value

- **Churn-oriented metrics**
  - cancellation-based or inactivity-based churn
  - to measure whether users are leaving or becoming less active

- **Segmented funnel metrics**
  - conversion by `plan`
  - conversion by `country`
  - to measure which segments have higher or lower conversion rates

- **Cohort-based metrics**
  - time-series changes by signup cohort
  - to measure how users acquired at different times behave afterward

---

## Why making metric semantics explicit matters

This repository is not only about returning JSON from an API.

One of its key design goals is to make metric semantics explicit and reviewable.

- metric names are defined intentionally
- required columns are documented
- supported groupings are explicit
- metric behavior is kept small enough to reason about clearly
- future extensions can be discussed from a stable baseline

This explicitness matters for both engineering and analytics. In real systems, undocumented metrics easily become ambiguous, hard to trust, and difficult to change safely.

---

## Summary

As of v0.1.0, `analytics-metrics-api` exposes an intentionally small KPI layer.

- `dau`
- `new_users`
- `conversion_rate`

These metrics are intended to provide a minimal but meaningful set of indicators for:

- acquisition
- engagement
- conversion

The current implementation is intentionally narrow in scope, but it still demonstrates an important engineering principle.

> Metrics become more useful in practice when their definitions, business meaning, and interpretation limits are made explicit.
