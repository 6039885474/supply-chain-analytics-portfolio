-- One order contains one SKU in this synthetic dataset. Rates are order weighted.
-- Endpoints are inclusive at the as-of instant; cancellations at/before as-of are excluded.
CREATE VIEW order_metrics AS
SELECT o.*,
 date(created_at) AS order_date,
 CASE WHEN cancelled_at IS NOT NULL AND cancelled_at <= s.as_of THEN 1 ELSE 0 END AS is_cancelled,
 CASE WHEN (cancelled_at IS NULL OR cancelled_at > s.as_of)
   AND promised_dispatch_at <= s.as_of THEN 1 ELSE 0 END AS is_eligible,
 CASE WHEN (cancelled_at IS NULL OR cancelled_at > s.as_of)
   AND promised_dispatch_at <= s.as_of AND dispatched_at IS NOT NULL
   AND dispatched_at <= promised_dispatch_at AND dispatched_at <= s.as_of THEN 1 ELSE 0 END AS is_on_time,
 CASE WHEN (cancelled_at IS NULL OR cancelled_at > s.as_of)
   AND (dispatched_at IS NULL OR dispatched_at > s.as_of) THEN 1 ELSE 0 END AS is_open,
 CASE WHEN (cancelled_at IS NULL OR cancelled_at > s.as_of)
   AND promised_dispatch_at <= s.as_of
   AND (dispatched_at IS NULL OR dispatched_at > s.as_of) THEN 1 ELSE 0 END AS is_overdue,
 CASE WHEN dispatched_at IS NOT NULL AND dispatched_at <= s.as_of THEN 1 ELSE 0 END AS is_dispatched,
 CAST((julianday(date(created_at))-julianday(s.period_start))/7 AS INTEGER) AS week_index
FROM orders o CROSS JOIN settings s;

CREATE VIEW count_metrics AS
SELECT c.*, abs(physical_qty-system_qty) AS absolute_variance_units,
 physical_qty-system_qty AS signed_variance_units,
 CASE WHEN abs(physical_qty-system_qty)<=s.count_tolerance_units THEN 1 ELSE 0 END AS is_accurate,
 CAST((julianday(date(counted_at))-julianday(s.period_start))/7 AS INTEGER) AS week_index
FROM cycle_counts c CROSS JOIN settings s;

-- ABC uses requested-demand value, not revenue, realized consumption, or annual spend.
-- The SKU crossing each threshold stays in the preceding class.
CREATE VIEW sku_demand AS
SELECT w.warehouse_id,p.sku_id,p.category,p.unit_cost,p.lead_time_days,
 COALESCE(SUM(CASE WHEN m.is_cancelled=0 THEN m.quantity ELSE 0 END),0) AS demand_units,
 COALESCE(SUM(CASE WHEN m.is_cancelled=0 THEN m.quantity ELSE 0 END),0)*p.unit_cost AS demand_value
FROM warehouses w CROSS JOIN products p
LEFT JOIN order_metrics m ON m.warehouse_id=w.warehouse_id AND m.sku_id=p.sku_id
GROUP BY w.warehouse_id,p.sku_id;

CREATE VIEW sku_abc AS
WITH ranked AS (
 SELECT *,SUM(demand_value) OVER(PARTITION BY warehouse_id) AS warehouse_value,
 COALESCE(SUM(demand_value) OVER(PARTITION BY warehouse_id ORDER BY demand_value DESC,sku_id
 ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),0) AS prior_value
 FROM sku_demand
)
SELECT *,CASE WHEN warehouse_value=0 THEN 'C' WHEN prior_value/warehouse_value<0.8 THEN 'A'
 WHEN prior_value/warehouse_value<0.95 THEN 'B' ELSE 'C' END AS abc_class FROM ranked;

-- Demonstration policy: lead-time demand plus two days of demand as a buffer.
-- No purchase orders, reservations, transfers, or minimum order quantities are modeled.
CREATE VIEW stock_analysis AS
WITH base AS (
 SELECT a.*,s.on_hand,s.as_of,
 demand_units/(julianday(t.period_end)-julianday(t.period_start)+1) AS avg_daily_demand
 FROM sku_abc a JOIN snapshots s USING(warehouse_id,sku_id) CROSS JOIN settings t
), policy AS (
 SELECT *,avg_daily_demand*(lead_time_days+2) AS reorder_point,
 CASE WHEN avg_daily_demand>0 THEN on_hand/avg_daily_demand ELSE NULL END AS days_of_cover
 FROM base
)
SELECT *,CASE WHEN avg_daily_demand=0 AND on_hand>0 THEN 'No observed demand'
 WHEN avg_daily_demand>0 AND on_hand=0 THEN 'Stockout'
 WHEN avg_daily_demand>0 AND on_hand<=reorder_point THEN 'Below reorder point'
 WHEN avg_daily_demand>0 AND days_of_cover>30 THEN 'Excess cover'
 ELSE 'Within policy' END AS exception FROM policy;
