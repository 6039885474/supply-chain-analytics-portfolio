# Last-mile delivery and returns analytics

A runnable portfolio demonstration of delivery-service measurement, reverse-logistics aging, and cost attribution. Every record is generated synthetic data. Hub names are fictional. The project has no connection to FedEx, Shadowfax, Delhivery or employer systems.

## Business decisions

Which hub has a first-attempt problem? How much of the delivery promise cohort is still undelivered? Which open return cases need follow-up? Are apparent cost differences affected by missing ledger records? The output supports these questions; it does not claim operational improvements or realized savings.

## Run

Requires Python 3.10+ with its standard library; no package installation, network or credentials are required.

```bash
cd projects/delivery_returns
python build.py
python -m unittest discover -s tests -v
```

Build uses seed 41827 and overwrites only this project's generated `data/` files and `dashboard_data.json`. It creates a local SQLite database for exploration. The SQL views are in `sql/analytics.sql`. CSVs can be opened in Excel, Power BI or Tableau. The portfolio's browser dashboard consumes `dashboard_data.json`.

## Inputs and grains

| Input | Grain/key | Relevant fields |
|---|---|---|
| hubs.csv | One fictional hub / hub_id | Hub label |
| shipments.csv | One parcel / shipment_id | Hub, service, shipped, promised and delivered timestamps |
| attempts.csv | One ingested scan row; attempt_id may repeat | Shipment, attempt number, timestamp, outcome |
| returns.csv | One return case / return_id | Shipment, RTO or CUSTOMER_RETURN, requested and completed timestamps |
| costs.csv | One ledger charge / cost_id | Shipment, cost type, posting timestamp, integer USD cents |

The fixed report window is Jan 1–Feb 25, 2026 inclusive (56 days); the as-of timestamp is Feb 25 at 23:59:59 UTC. Dates and costs are invented for demonstration. The first/last Monday-start weeks are partial. Raw events are snapshot observations; future promises are allowed, future delivery/return completions are not treated as completed.

## Metric contracts

| Metric | Numerator / calculation | Denominator and limitation |
|---|---|---|
| First-attempt success | Valid number-1 attempts marked delivered | Valid first attempts observed in window; missing scans are excluded and reported separately |
| On-time delivery | Delivery timestamp on/before promise | Promises in window that have matured by as-of; due-undelivered parcels remain failures |
| Observed RTO share | Shipped-window parcels with RTO initiated by as-of | All shipped-window parcels; recent cohorts are incomplete, so this is not final lifetime RTO probability |
| Observed customer-return share | Shipped-window parcels with a post-delivery customer return requested by as-of | All shipped-window parcels; separate event from failed-delivery RTO |
| Completed return cycle | Mean elapsed calendar days from request to completed receipt | Return cases requested in window and completed by as-of; show open cases and aging beside this mean |
| Open-return aging | As-of minus request timestamp for open cases | All open return cases; over-seven-day threshold is a demonstration review rule, not an employer SLA |
| Attributed cost per covered shipment | Known linehaul and delivery-attempt charges posted by as-of | Shipped-window parcels with a linehaul ledger record; missing cost stays unknown |

Costs exclude reverse transport, overhead, taxes and unposted charges. Therefore the metric is an attributed partial cost, not full delivery profitability. RTO and customer-return shares use a common shipped cohort but are never combined into one return rate.

Weekly rows use the relevant event date for each KPI: shipped date for shipment/RTO/cost, attempted date for first-attempt service, promised date for OTD, and requested date for return-cycle/open-aging. The counts are additive within each metric. A weekly row does not represent a single common parcel cohort. Hub-only and full-window comparisons are the simplest starting points.

## Cleaning, validation and SQL design

- Fifteen deliberately repeated scan rows are collapsed only when all attributes match. Three conflicting attempt IDs are quarantined completely and listed in the issue log.
- No attempt number 2 is promoted to number 1 when the first scan is absent. Missing first scans are flagged after four elapsed days; this rule is a demonstration assumption.
- Costs and return flags are aggregated to parcel grain before joining. This prevents many-to-many joins from multiplying cost or shipment totals.
- Zero eligible records yields null ratios. Missing cost is not silently assigned zero.
- Return completions later than as-of are censored, even if such a timestamp is supplied in a test fixture.
- Seven unittest cases use hand-calculated fixtures for late/undelivered/future promises, duplicate/conflicting scans, missing costs, cost fan-out, return censoring, empty filters and referential integrity.

## Generated outputs

- `data/processed/shipment_metrics.csv`: parcel-level analytic features, eligible flags and attributed charges.
- `data/processed/return_metrics.csv`: return-level durations and open aging.
- `data/processed/weekly_metrics.csv`: additive components by hub/event week.
- `data/processed/attempts_clean.csv`: cleaned attempt records.
- `data/processed/data_quality_issues.csv`: duplicated or conflicting raw IDs and handling.
- `dashboard_data.json`: metadata, summary, hub summaries, weekly components and rates, every open return case ordered oldest first, first-attempt failure reasons, issue log and definitions. The `exceptions` list is complete so filtering it by hub preserves the full selected backlog.
- `bi/`: Power BI model guide and DAX measures; a `.pbix` is not included.

## Snapshot results from the supplied seed

The generated run contains 5,457 parcels. It records 4,339 first-attempt successes among 5,188 eligible first attempts (83.64%) and 4,022 on-time deliveries among 5,118 matured promises (78.59%). The matured cohort includes 257 undelivered parcels.

There are 232 observed RTO parcels and 325 customer-return parcels. Of 557 return cases, 479 are completed and 78 remain open. The completed-case mean is 7.09 days; 18 open cases are older than seven days. Known attributed charges average $5.75 for 5,416 cost-covered parcels (99.25% coverage). These are computed synthetic measurements, not an employee's business results.

## Suggested analysis and next steps

1. Compare failure reasons across hubs, with counts and denominator size visible.
2. Prioritize the oldest open cases and distinguish RTO from customer returns before proposing workflows.
3. Add a second as-of snapshot and compare the same matured shipment cohort to reveal late arrivals; do not call a simple before/after change a causal improvement.
4. Implement the supplied Power BI model, reproduce the metrics, and commit screenshots plus the native report after verifying slicers.

## Resume wording after personal reproduction and review

“Developed a last-mile delivery and returns analytics portfolio using SQL and synthetic shipment events, defining service-level cohorts, return aging, and cost-coverage checks across three fictional hubs.”

Add actual observed dataset counts only after running the build and explaining the calculations. Do not use synthetic service rates as claimed improvements in an employer role.
