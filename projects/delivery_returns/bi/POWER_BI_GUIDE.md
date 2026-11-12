# Power BI implementation guide

This folder contains a model design and DAX source. A native `.pbix` has not been created or tested. The browser dashboard is the working demonstration.

## Import and type

Import `data/raw/hubs.csv` as Hubs and `data/processed/weekly_metrics.csv` as WeeklyMetrics. Make hub IDs text, week_start Date, counts Whole Number, return_cycle_days Decimal Number, and attributed_cost_cents Whole Number. Relate Hubs[hub_id] one-to-many to WeeklyMetrics[hub_id] with single-direction filtering. Create a unique Week dimension from WeeklyMetrics[week_start] and relate it one-to-many to WeeklyMetrics. Mark Date as appropriate only if you add a complete calendar; a weekly list is not a daily date table.

Import `data/processed/return_metrics.csv` as ReturnMetrics for the open-case table. Relate Hubs to ReturnMetrics on hub_id. Keep the week filter for ReturnMetrics separate or add a clearly named requested-week column and relationship. Do not let the weekly table filter individual cases through a many-to-many relationship.

Create measures individually from `measures.dax`. Format rates as 0.0%, costs as $0.00 and durations as 0.0 days. DAX ratios are 0–1; JSON dashboard rates are 0–100. Blank means no eligible denominator.

## Three report pages

1. **Delivery service:** first-attempt success, on-time delivery, due-undelivered, missing first scans; weekly trend; hub comparison; failure reasons from clean attempt data joined to shipment hub.
2. **Return backlog:** observed RTO share and customer-return share as separate cards; completed-case mean beside completion share; open-return count and aging; actionable case table with request timestamp and owner hub.
3. **Cost and data quality:** cost per covered shipment beside coverage; attributed costs by hub; exact-duplicate and conflicting-attempt counts; data quality issue table.

Include an as-of label of 2026-02-25 23:59:59 UTC and “Synthetic demonstration data”. The supplied weeks use different event anchors by KPI: shipped week for shipment, RTO and cost; attempt week for first-attempt metrics; promised week for delivery SLA; requested week for return metrics. Name the time filter **Metric event week** and show these definitions in tooltips. The first and last calendar weeks are partial.

## Checks before claiming a completed Power BI project

- Match full-window totals to dashboard_data.json.
- Verify hub filters recalculate numerator/denominator, rather than averaging percentages.
- Verify changing the return request-week selection also filters the detail table as intended.
- Confirm undelivered overdue shipments remain in the OTD denominator and future promises remain excluded.
- Save the `.pbix`, export screenshots and document the Power BI Desktop version actually used.
- Do not claim a live SAP, WMS, TMS connection: these are CSV extracts shaped for a portfolio demonstration.
