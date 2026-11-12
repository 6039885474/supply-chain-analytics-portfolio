-- Business logic runs against deduplicated attempt records and a fixed as-of timestamp.
-- Aggregate each many-side before joins to prevent cost and event fan-out.
CREATE VIEW shipment_metrics AS
WITH first_scans AS (
  SELECT shipment_id, attempted_at, outcome FROM attempts WHERE attempt_number=1
), return_flags AS (
  SELECT shipment_id,
    MAX(CASE WHEN return_type='RTO' THEN 1 ELSE 0 END) AS is_rto,
    MAX(CASE WHEN return_type='CUSTOMER_RETURN' THEN 1 ELSE 0 END) AS is_customer_return
  FROM returns,settings WHERE requested_at<=as_of GROUP BY shipment_id
), cost_totals AS (
  SELECT shipment_id,SUM(amount_cents) cost_cents,
    MAX(CASE WHEN cost_type='linehaul' THEN 1 ELSE 0 END) AS cost_covered
  FROM costs,settings WHERE posted_at<=as_of GROUP BY shipment_id
)
SELECT s.*,f.attempted_at first_attempt_at,f.outcome first_outcome,
 CASE WHEN f.attempted_at BETWEEN c.window_start AND c.window_end THEN 1 ELSE 0 END first_attempt_eligible,
 CASE WHEN f.attempted_at BETWEEN c.window_start AND c.window_end AND f.outcome='delivered' THEN 1 ELSE 0 END first_attempt_success,
 CASE WHEN s.promised_at BETWEEN c.window_start AND c.window_end AND s.promised_at<=c.as_of THEN 1 ELSE 0 END on_time_eligible,
 CASE WHEN s.promised_at BETWEEN c.window_start AND c.window_end AND s.promised_at<=c.as_of AND s.delivered_at<=s.promised_at THEN 1 ELSE 0 END on_time_delivered,
 CASE WHEN s.promised_at BETWEEN c.window_start AND c.window_end AND s.promised_at<=c.as_of AND s.delivered_at IS NULL THEN 1 ELSE 0 END matured_undelivered,
 COALESCE(r.is_rto,0) is_rto,COALESCE(r.is_customer_return,0) is_customer_return,
 COALESCE(k.cost_covered,0) cost_covered,
 CASE WHEN k.cost_covered=1 THEN k.cost_cents ELSE NULL END attributed_cost_cents,
 CASE WHEN f.shipment_id IS NULL AND julianday(c.as_of)-julianday(s.shipped_at)>=4 THEN 1 ELSE 0 END missing_first_scan
FROM shipments s CROSS JOIN settings c
LEFT JOIN first_scans f USING(shipment_id)
LEFT JOIN return_flags r USING(shipment_id)
LEFT JOIN cost_totals k USING(shipment_id)
WHERE s.shipped_at BETWEEN c.window_start AND c.window_end;

CREATE VIEW return_metrics AS
SELECT r.return_id,r.shipment_id,r.return_type,r.requested_at,
 CASE WHEN r.completed_at<=c.as_of THEN r.completed_at END completed_at,s.hub_id,
 CASE WHEN r.completed_at<=c.as_of THEN julianday(r.completed_at)-julianday(r.requested_at) END cycle_days,
 CASE WHEN r.completed_at IS NULL OR r.completed_at>c.as_of THEN julianday(c.as_of)-julianday(r.requested_at) END open_age_days
FROM returns r JOIN shipments s USING(shipment_id) CROSS JOIN settings c
WHERE r.requested_at BETWEEN c.window_start AND c.window_end AND r.requested_at<=c.as_of;

-- SQL supplies additive component counts so rates can always be reweighted correctly.
CREATE VIEW weekly_metrics AS
WITH event_rows AS (
 SELECT hub_id,shipped_at event_at,1 shipments,0 first_attempts,0 first_attempt_successes,
 0 on_time_eligible,0 on_time_delivered,0 matured_undelivered,is_rto rto_shipments,
 is_customer_return customer_return_shipments,0 completed_returns,0.0 return_cycle_days,
 0 open_returns,0 open_returns_over_7d,cost_covered cost_covered_shipments,
 COALESCE(attributed_cost_cents,0) attributed_cost_cents,missing_first_scan
 FROM shipment_metrics
 UNION ALL
 SELECT hub_id,first_attempt_at,0,first_attempt_eligible,first_attempt_success,0,0,0,0,0,0,0,0,0,0,0,0
 FROM shipment_metrics WHERE first_attempt_eligible=1
 UNION ALL
 SELECT hub_id,promised_at,0,0,0,on_time_eligible,on_time_delivered,matured_undelivered,0,0,0,0,0,0,0,0,0
 FROM shipment_metrics WHERE on_time_eligible=1
 UNION ALL
 SELECT hub_id,requested_at,0,0,0,0,0,0,0,0,
 CASE WHEN completed_at IS NOT NULL THEN 1 ELSE 0 END,COALESCE(cycle_days,0),
 CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END,
 CASE WHEN completed_at IS NULL AND open_age_days>7 THEN 1 ELSE 0 END,0,0,0 FROM return_metrics
)
SELECT hub_id,date(event_at,'-'||((CAST(strftime('%w',event_at) AS INTEGER)+6)%7)||' days') week_start,
SUM(shipments) shipments,SUM(first_attempts) first_attempts,SUM(first_attempt_successes) first_attempt_successes,
SUM(on_time_eligible) on_time_eligible,SUM(on_time_delivered) on_time_delivered,SUM(matured_undelivered) matured_undelivered,
SUM(rto_shipments) rto_shipments,SUM(customer_return_shipments) customer_return_shipments,
SUM(completed_returns) completed_returns,SUM(return_cycle_days) return_cycle_days,SUM(open_returns) open_returns,
SUM(open_returns_over_7d) open_returns_over_7d,SUM(cost_covered_shipments) cost_covered_shipments,
SUM(attributed_cost_cents) attributed_cost_cents,SUM(missing_first_scan) missing_first_scan
FROM event_rows GROUP BY hub_id,week_start;
