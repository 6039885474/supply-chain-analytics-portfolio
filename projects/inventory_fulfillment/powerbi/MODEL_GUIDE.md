# Power BI reconstruction guide

This repository includes CSV inputs and DAX source. It does **not** include a completed `.pbix` file. Rebuild and review the report in Power BI Desktop before describing a Power BI implementation as completed.

## Import and model

Import `data/raw/warehouses.csv` as **DimWarehouse** and `data/raw/products.csv` as **DimProduct**. Import `data/processed/fact_orders.csv` as **FactOrders**, `fact_cycle_counts.csv` as **FactCycleCounts**, and `stock_analysis.csv` as **FactStock**. Use text for identifiers, whole numbers for quantities/flags, decimal numbers for costs and ratios, and date/time for timestamps. Blank timestamps are nulls.

Create single-direction, one-to-many relationships from each dimension to all three facts through `warehouse_id` and `sku_id`. Do not directly join the three facts: orders, counts, and snapshots have different grains, and direct joins multiply rows. Hide raw additive columns that users might accidentally sum.

Prepare the date keys in Power Query before creating relationships:

- In **FactOrders**, set the exported `order_date` column to the **Date** type.
- In **FactCycleCounts**, set `counted_at` to **Date/Time**, add a custom column named `count_date` with `Date.From([counted_at])`, and set the new column to the **Date** type. Do not relate the timestamp directly to a date-only calendar: the count timestamps are at 16:00, so they will not match midnight calendar values.

Create **DimDate[Date]** as a unique, complete Date column for Jan 1–Feb 25, 2026. Add single-direction, one-to-many relationships from **DimDate[Date]** to **FactOrders[order_date]** and **FactCycleCounts[count_date]**. The snapshot is fixed at Feb 26 00:00 UTC, so **do not connect the date slicer to FactStock**. Label snapshot cards with this fixed date. An order date slicer defines a creation cohort; it does not move the as-of instant.

## Pages

1. **Operations overview:** warehouse slicer; cards for on-time dispatch, cycle-count accuracy, open backlog and overdue backlog; weekly numerator/denominator trends. Format DAX rates as percentages (the DAX measures return 0–1). SQL/JSON rates are already 0–100.
2. **Inventory exceptions:** fixed-date SKU-location table with ABC class, on-hand, average daily demand, lead time, reorder point, days of cover, and exception. Sort stockouts before below-reorder items, then ABC class. Show no-demand stock separately from stockouts.
3. **Data quality and definitions:** rejected rows, reason counts, 0-unit accuracy tolerance, due-order eligibility, refresh/as-of timestamp and the synthetic-data statement.

## Reconciliation checkpoints

With no slicers, confirm 8,391 accepted orders; 7,982 eligible orders; 6,543 on-time orders; 449 open backlog, of which 291 are overdue; and 1,199 accurate counts out of 1,344. Rates should be 81.97% and 89.21%. The snapshot contains 720 SKU-location rows and 153 replenishment exceptions. The raw ingest quarantines 6 rows; do not treat those as six inaccurate physical counts.

## Interpretation

On-time dispatch is not on-time delivery. Exact-match count-record accuracy is not unit-weighted inventory accuracy. The replenishment rule uses a 56-day average and a two-day buffer; it is an illustrative screening rule. Incoming POs, reservations, transfers, seasonality and order constraints are not modeled, so the dashboard cannot approve purchase quantities.
