# Inventory and fulfillment performance

A reproducible supply chain analytics case study that connects warehouse order processing, cycle-count results and replenishment exceptions. It answers: **Which warehouse needs attention, which inventory records disagree, and which SKU locations warrant a planning review?**

All records, warehouses, costs and findings in this project are synthetic. There is no employer data, production integration, verified cost saving or implemented operational improvement. The project is an assistant-created starter for the candidate to run, inspect, adapt and explain before presenting it as personal work.

## What is implemented

- Deterministic generation of 56 days of orders and cycle counts, plus an inventory snapshot, for three fictional warehouses and 240 SKUs.
- Data-quality quarantine for deliberately injected order anomalies and negative physical-count quantities.
- SQLite schema, referential-integrity checks, SQL window functions for ABC segmentation, and separate fact tables to prevent join multiplication.
- Defined as-of eligibility for dispatch SLAs and backlog. Future-due orders are not counted as late; overdue open orders remain in the due-order denominator.
- CSV exports and a compact JSON contract for a web dashboard.
- Seven tests covering meaningful KPI edge cases and export reconciliation.
- Power BI modeling instructions and DAX source. A `.pbix` report is an optional next step and is not included.

## Run locally

Python 3.10 or newer is sufficient; no external Python packages or database server are needed.

```bash
cd projects/inventory_fulfillment
python3 build.py
python3 -m unittest discover -s tests -v
```

On Windows, `python` can replace `python3`. The first command regenerates the synthetic raw files and all derived outputs. Changes to raw CSVs are overwritten on the next build. Edit the generator when adapting the case study, or separate the ingestion step before using other licensed data. The fixed seed is 73421; there are no external API calls.

## Dataset and model

The observation window is January 1–February 25, 2026, inclusive. The fixed as-of instant is **February 26, 2026, 00:00 UTC**. Timestamps in CSVs are ISO strings interpreted as UTC. Each synthetic order contains one SKU; this avoids silently mixing orders and order lines.

| File / table | Grain | Important fields |
|---|---|---|
| `warehouses.csv` | One warehouse | warehouse_id, warehouse_name |
| `products.csv` | One SKU | sku_id, category, synthetic unit_cost, lead_time_days |
| `orders.csv` | One source order, before quarantine | order_id, warehouse_id, sku_id, quantity, creation/promise/dispatch/cancellation timestamps |
| `cycle_counts.csv` | One SKU-location audit event | count_id, warehouse_id, sku_id, counted_at, system_qty, physical_qty |
| `inventory_snapshots.csv` | One SKU and warehouse at the fixed as-of | warehouse_id, sku_id, as_of, on_hand |

The accepted order fact contains **8,391 orders**. The count fact contains **1,344 audit events**. The snapshot contains **720 SKU-location rows**. Count events are sampled historical audits, so their accuracy rate should not be generalized to every inventory record. The dataset is not a complete movement ledger; it does not reconstruct historical stock balances from orders.

## KPI definitions

| KPI | Formula and interpretation |
|---|---|
| On-time dispatch | On-time dispatched orders / noncancelled orders whose promised dispatch is at or before as-of. Deadline equality counts as on-time. Overdue undispatched orders remain in the denominator. |
| Inventory record accuracy | Count events with `ABS(physical_qty - system_qty) <= 0` / accepted count events. This is exact-match, record-weighted accuracy, not quantity-weighted accuracy. |
| Absolute variance units | Sum of absolute physical-minus-system differences. Positive and negative discrepancies do not cancel. |
| Open backlog | Noncancelled accepted orders without a dispatch at or before as-of, including future-due orders. |
| Overdue backlog | The subset of open backlog with a dispatch promise at or before as-of. |
| Replenishment exception | Positive observed demand and on-hand at/below `average daily demand × (lead time + 2 buffer days)`. Includes zero-stock locations. |
| Days of cover | On-hand / 56-day average daily demand. Undefined when no demand was observed. |
| ABC class | SKU rank within each warehouse by requested demand value: noncancelled requested units × synthetic unit cost. A covers the first 80%, B the next 15%, C the remainder. A SKU crossing a boundary stays in the preceding class. |

All warehouse totals and weekly ratios must be computed from summed numerators and denominators. Do not average warehouse percentages. The eight weekly buckets are seven-day creation cohorts beginning January 1, not ISO calendar weeks. Count trends use the same bucket boundaries but the count-event date. Snapshot KPIs remain fixed at February 26.

## Reproduced findings

These are generated dataset observations, not achieved business outcomes.

| Measure | Reproduced value |
|---|---:|
| Due eligible orders | 7,982 |
| On-time dispatched orders | 6,543 |
| On-time dispatch | 81.97% |
| Exact-match count events | 1,199 / 1,344 |
| Inventory record accuracy | 89.21% |
| Absolute count variance | 509 units |
| Open backlog / overdue subset | 449 / 291 orders |
| Replenishment exceptions | 153 SKU locations |
| Stockout subset | 59 SKU locations |
| Raw rows quarantined | 6 |

South Fulfillment has **73.63%** on-time dispatch and **85.49%** count-record accuracy, compared with North's **88.40%** and **93.08%**. In this simulation, that makes South a useful first investigation target. It does not establish a causal explanation or prove that a particular intervention will work.

Across warehouses, class A contains 61–63 of the 240 SKUs and approximately 80% of requested demand value. The proposed decision is to review A-class stockout and below-reorder exceptions first, then check incoming orders, reservations and supplier lead times before recommending replenishment. Those extra inputs are not modeled here.

## Data-quality decisions

The generator deliberately injects one exact duplicate order, one zero-quantity order, one unknown warehouse key, one impossible promised date, one dispatch-before-creation sequence and one negative physical count. They are exported to `data/processed/quarantine.csv`. The exact duplicate keeps the first valid occurrence; a conflicting later duplicate is quarantined for review. These checks do not establish that every possible source-data defect is covered.

Raw anomalies are different from valid physical-count discrepancies. Six rejected source rows must not be included in the inventory record-accuracy denominator. The tested mini-fixtures additionally demonstrate zero denominators, cancellation handling, future-due backlog, boundary timestamps, absolute variances and zero-demand inventory.

## Files and frontend contract

- `build.py`: generator, validation, SQL execution and exports.
- `sql/schema.sql`: table grains, keys and constraints.
- `sql/analytics.sql`: order/count flags, demand aggregation, ABC and inventory policy views.
- `tests/test_metrics.py`: independently specified business edge cases and dataset reconciliations.
- `data/raw/`: synthetic source CSVs.
- `data/processed/`: accepted facts, stock/ABC analysis, weekly metrics, quarantine, metric summaries and a local SQLite database.
- `powerbi/`: reconstruction guide and DAX measures.
- `dashboard_data.json`: dashboard payload.

The JSON top level contains `metadata`, `summary`, `warehouses`, `weeks`, `stock_exceptions`, `abc`, `quality` and `definitions`. `warehouses` rows use `warehouse_id` and `warehouse_name`, then the same metric keys as `summary`. `weeks` rows contain warehouse and week identifiers, numeric numerators/denominators and display rates. `stock_exceptions` contains only locations outside the illustrative policy. `abc` uses `demand_value_share_pct`. Rates in JSON are already expressed on a 0–100 scale. Missing/undefined rates and days of cover are JSON nulls.

## Candidate review and optional extensions

Before adding this work to a resume, run it, reconcile the key numbers, explain the due-order denominator, review the SQL, and make a substantive change. Useful extensions include a configurable count tolerance, a physical count audit drilldown, or an evaluated replenishment policy with incoming POs. Document the change and rerun the tests.

Do not list a SAP connector, SAP implementation, production deployment, Power BI report, warehouse improvement or cost saving as completed unless it was actually built or measured. The project demonstrates analytics on synthetic warehouse-style exports; it does not connect to a live WMS, TMS or SAP system.
