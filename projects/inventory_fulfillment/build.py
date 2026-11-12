"""Generate a deterministic, synthetic warehouse analytics case study (stdlib only)."""
from __future__ import annotations
import csv
import json
import math
import random
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
START = datetime(2026, 1, 1)
DAYS = 56
END = START + timedelta(days=DAYS-1)
AS_OF = START + timedelta(days=DAYS)
SEED = 73421
WAREHOUSES = [("WH-N", "North Fulfillment"), ("WH-C", "Central Fulfillment"), ("WH-S", "South Fulfillment")]

def stamp(value):
    return value.strftime("%Y-%m-%dT%H:%M:%S")

def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

def read_csv(name):
    with (RAW / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))

def generate():
    rng = random.Random(SEED)
    products = [dict(sku_id=f"SKU-{i:04}", category=["Home", "Office", "Accessories", "Personal care"][i%4],
                     unit_cost=round(rng.uniform(4, 175), 2), lead_time_days=rng.randint(3, 10)) for i in range(1, 241)]
    weights = [1 / (1 + i/18)**1.7 for i in range(240)]
    orders, counts = [], []
    demand = Counter()
    for day in range(DAYS):
        date = START + timedelta(days=day)
        for wi, (wid, _) in enumerate(WAREHOUSES):
            for _ in range(rng.randint(43, 57)):
                sku = rng.choices(products, weights=weights)[0]
                created = date + timedelta(hours=rng.randint(6, 19), minutes=rng.randint(0, 59))
                promise = datetime.combine((created + timedelta(days=rng.choice([1, 1, 2]))).date(), datetime.min.time()) + timedelta(hours=18)
                cancelled = created + timedelta(hours=1) if rng.random() < .025 else None
                dispatched = None
                if cancelled is None and rng.random() > [.025, .035, .05][wi]:
                    late = rng.random() < [.09, .14, .20][wi]
                    dispatched = promise + timedelta(hours=rng.randint(1, 28)) if late else promise-timedelta(hours=rng.randint(1, 22))
                    dispatched = max(dispatched, created+timedelta(hours=1))
                    if dispatched > AS_OF:
                        dispatched = None
                row = dict(order_id=f"ORD-{len(orders)+1:06}", warehouse_id=wid, sku_id=sku["sku_id"], quantity=rng.randint(1, 7),
                           created_at=stamp(created), promised_dispatch_at=stamp(promise),
                           dispatched_at=stamp(dispatched) if dispatched else "", cancelled_at=stamp(cancelled) if cancelled else "")
                orders.append(row)
                if not cancelled:
                    demand[wid, sku["sku_id"]] += row["quantity"]
            for sku in rng.sample(products, 8):
                expected = rng.randint(0, 150)
                discrepancy = rng.choice([-8, -4, -2, -1, 1, 2, 4, 8]) if rng.random() < [.075, .11, .15][wi] else 0
                counts.append(dict(count_id=f"CNT-{len(counts)+1:06}", warehouse_id=wid, sku_id=sku["sku_id"],
                                   counted_at=stamp(date+timedelta(hours=16)), system_qty=expected,
                                   physical_qty=max(0, expected+discrepancy)))
    snapshots = []
    for wid, _ in WAREHOUSES:
        for sku in products:
            avg = demand[wid, sku["sku_id"]] / DAYS
            on_hand = int(round(avg*rng.uniform(1, 40))) if avg else rng.randint(0, 8)
            if rng.random() < .05:
                on_hand = 0
            snapshots.append(dict(warehouse_id=wid, sku_id=sku["sku_id"], as_of=stamp(AS_OF), on_hand=on_hand))
    # Known raw anomalies exercise quarantine and exact-duplicate handling.
    # They do not participate in accepted business metrics.
    orders.append(dict(orders[0]))
    for suffix, updates in [
        ("ZERO", {"quantity":0}), ("WAREHOUSE", {"warehouse_id":"WH-UNKNOWN"}),
        ("DATE", {"promised_dispatch_at":"2026-02-30T18:00:00"}),
        ("SEQUENCE", {"dispatched_at":"2025-12-31T00:00:00"})
    ]:
        row = dict(orders[1]); row.update(updates); row["order_id"] = f"BAD-{suffix}"; orders.append(row)
    bad_count = dict(counts[0]); bad_count.update(count_id="BAD-NEGATIVE", physical_qty=-2); counts.append(bad_count)
    write_csv(RAW/"warehouses.csv", [dict(warehouse_id=w, warehouse_name=n) for w,n in WAREHOUSES])
    write_csv(RAW/"products.csv", products)
    write_csv(RAW/"orders.csv", orders)
    write_csv(RAW/"cycle_counts.csv", counts)
    write_csv(RAW/"inventory_snapshots.csv", snapshots)

def validate_orders(rows, warehouse_ids, sku_ids):
    accepted, rejects, seen = [], [], {}
    for row_num, row in enumerate(rows, 2):
        why = None
        try:
            if row["order_id"] in seen:
                why = "exact_duplicate" if row == seen[row["order_id"]] else "conflicting_duplicate"
            elif row["warehouse_id"] not in warehouse_ids or row["sku_id"] not in sku_ids:
                why = "unknown_dimension_key"
            elif int(row["quantity"]) <= 0:
                why = "nonpositive_quantity"
            else:
                created = datetime.fromisoformat(row["created_at"])
                promised = datetime.fromisoformat(row["promised_dispatch_at"])
                dispatched = datetime.fromisoformat(row["dispatched_at"]) if row["dispatched_at"] else None
                cancelled = datetime.fromisoformat(row["cancelled_at"]) if row["cancelled_at"] else None
                if not START <= created < AS_OF:
                    why = "created_outside_period"
                elif promised < created or (dispatched and dispatched < created) or (cancelled and cancelled < created):
                    why = "invalid_event_sequence"
                elif dispatched and cancelled:
                    why = "dispatch_and_cancel_conflict"
                elif (dispatched and dispatched>AS_OF) or (cancelled and cancelled>AS_OF):
                    why = "future_actual_event"
        except (ValueError, TypeError):
            why = "invalid_date_or_number"
        if why:
            rejects.append(dict(table="orders", row_number=row_num, record_id=row["order_id"], reason=why))
        else:
            seen[row["order_id"]] = row
            accepted.append(row)
    return accepted, rejects

def connect_db(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript((ROOT/"sql/schema.sql").read_text())
    conn.execute("INSERT INTO settings VALUES(?,?,?,?)", (stamp(AS_OF), START.date().isoformat(), END.date().isoformat(), 0))
    return conn

def insert_rows(conn, table, rows):
    fields = list(rows[0])
    conn.executemany(f"INSERT INTO {table} ({','.join(fields)}) VALUES({','.join('?' for _ in fields)})",
                     [[None if r[f]=="" else r[f] for f in fields] for r in rows])

def pct(n, d):
    return round(100*n/d, 2) if d else None

def records(conn, sql, args=()):
    return [dict(row) for row in conn.execute(sql, args)]

def summary(conn, wid=None):
    where, args = (" WHERE warehouse_id=?", (wid,)) if wid else ("", ())
    o = records(conn, "SELECT COUNT(*) AS orders_created,SUM(is_eligible) AS eligible_orders,SUM(is_on_time) AS on_time_orders,"
                "SUM(is_cancelled) AS cancelled_orders,SUM(is_open) AS open_backlog,SUM(is_overdue) AS overdue_backlog,"
                "SUM(is_dispatched) AS dispatched_orders FROM order_metrics"+where, args)[0]
    c = records(conn, "SELECT COUNT(*) AS count_records,SUM(is_accurate) AS accurate_count_records,"
                "SUM(absolute_variance_units) AS absolute_variance_units FROM count_metrics"+where, args)[0]
    s = records(conn, "SELECT COUNT(*) AS stocked_sku_locations,"
                "SUM(CASE WHEN exception='Stockout' THEN 1 ELSE 0 END) AS stockout_sku_locations,"
                "SUM(CASE WHEN exception IN ('Stockout','Below reorder point') THEN 1 ELSE 0 END) AS replenishment_exceptions,"
                "SUM(CASE WHEN exception='Excess cover' THEN 1 ELSE 0 END) AS excess_cover_sku_locations FROM stock_analysis"+where, args)[0]
    return {**o, **c, **s, "on_time_dispatch_pct":pct(o["on_time_orders"],o["eligible_orders"]),
            "record_accuracy_pct":pct(c["accurate_count_records"],c["count_records"])}

def build():
    RAW.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    generate()
    warehouses, products = read_csv("warehouses.csv"), read_csv("products.csv")
    orders_raw = read_csv("orders.csv")
    orders, rejected = validate_orders(orders_raw, {w["warehouse_id"] for w in warehouses}, {s["sku_id"] for s in products})
    counts_raw = read_csv("cycle_counts.csv")
    counts = []
    for rn, row in enumerate(counts_raw,2):
        if int(row["system_qty"])<0 or int(row["physical_qty"])<0:
            rejected.append(dict(table="cycle_counts",row_number=rn,record_id=row["count_id"],reason="negative_count_quantity"))
        else:
            counts.append(row)
    db = OUT/"warehouse_analytics.sqlite"
    if db.exists(): db.unlink()
    conn = connect_db(db)
    insert_rows(conn,"warehouses",warehouses); insert_rows(conn,"products",products)
    insert_rows(conn,"orders",orders); insert_rows(conn,"cycle_counts",counts)
    insert_rows(conn,"snapshots",read_csv("inventory_snapshots.csv"))
    conn.executescript((ROOT/"sql/analytics.sql").read_text())
    conn.commit()
    assert conn.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
    assert not conn.execute("PRAGMA foreign_key_check").fetchall()
    weeks = []
    for idx in range(8):
        for wid,_ in WAREHOUSES:
            o=records(conn,"SELECT COUNT(*) AS orders_created,SUM(is_eligible) AS eligible_orders,SUM(is_on_time) AS on_time_orders,"
                      "SUM(is_dispatched) AS dispatched_orders FROM order_metrics WHERE warehouse_id=? AND week_index=?",(wid,idx))[0]
            c=records(conn,"SELECT COUNT(*) AS count_records,SUM(is_accurate) AS accurate_count_records,"
                      "SUM(absolute_variance_units) AS absolute_variance_units FROM count_metrics WHERE warehouse_id=? AND week_index=?",(wid,idx))[0]
            weeks.append({"week_start":(START+timedelta(days=7*idx)).date().isoformat(),
                          "week_end":(START+timedelta(days=7*idx+6)).date().isoformat(),"warehouse_id":wid,
                          **o,**c,"on_time_dispatch_pct":pct(o["on_time_orders"],o["eligible_orders"]),
                          "record_accuracy_pct":pct(c["accurate_count_records"],c["count_records"])})
    stocks=records(conn,"SELECT warehouse_id,sku_id,category,abc_class,on_hand,ROUND(avg_daily_demand,3) AS avg_daily_demand,"
                   "ROUND(reorder_point,2) AS reorder_point,ROUND(days_of_cover,2) AS days_of_cover,exception FROM stock_analysis "
                   "WHERE exception!='Within policy' ORDER BY CASE exception WHEN 'Stockout' THEN 1 WHEN 'Below reorder point' THEN 2 ELSE 3 END,abc_class,warehouse_id,sku_id")
    abc=records(conn,"SELECT warehouse_id,abc_class,COUNT(*) AS sku_count,SUM(demand_units) AS demand_units,"
                "ROUND(SUM(demand_value),2) AS requested_demand_value,ROUND(100.0*SUM(demand_value)/MAX(warehouse_value),2) AS demand_value_share_pct "
                "FROM sku_abc GROUP BY warehouse_id,abc_class ORDER BY warehouse_id,abc_class")
    quality={"raw_rows":{"orders":len(orders_raw),"cycle_counts":len(counts_raw)},
             "accepted_rows":{"orders":len(orders),"cycle_counts":len(counts)},
             "quarantined_rows":len(rejected),"issues":rejected}
    definitions={
        "record_accuracy_pct":"100 × count records with abs(physical_qty − system_qty) ≤ 0 units / accepted cycle-count records. Record weighted; not unit-weighted accuracy or all-inventory accuracy.",
        "on_time_dispatch_pct":"100 × noncancelled orders dispatched by their promised dispatch timestamp / all noncancelled orders whose promised dispatch timestamp is at/before as_of. Overdue undispatched orders stay in the denominator; future-due orders are excluded.",
        "open_backlog":"Accepted, noncancelled orders without a dispatch at/before as_of, including orders not yet due. Overdue backlog is the due subset.",
        "replenishment_exceptions":"SKU-location snapshots with observed positive demand and on_hand ≤ average daily demand × (lead_time_days + 2 buffer days). Includes stockouts; a screening policy, not an approved buy quantity.",
        "abc":"Each warehouse's SKU list ranked by 56-day requested demand value (noncancelled quantity × unit_cost). A covers first 80%, B next 15%, C remaining; crossing SKU stays in preceding class. Not revenue or realized savings.",
        "weeks":"Fixed consecutive seven-day creation cohorts starting Jan 1; dispatch performance is finalized as of Feb26. These are not ISO calendar weeks. Cycle counts use their count date in the same seven-day windows."}
    payload={"metadata":{"title":"Inventory and Fulfillment Performance","synthetic":True,"seed":SEED,"period_start":START.date().isoformat(),
                         "period_end":END.date().isoformat(),"as_of":stamp(AS_OF)+"Z","day_count":DAYS,"sku_count":len(products),
                         "warehouse_count":len(warehouses),"count_tolerance_units":0,"currency":"USD (synthetic costs)"},
             "summary":summary(conn),"warehouses":[{**w,**summary(conn,w["warehouse_id"])} for w in warehouses],
             "weeks":weeks,"stock_exceptions":stocks,"abc":abc,"quality":quality,"definitions":definitions}
    (ROOT/"dashboard_data.json").write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    for file, query in [("fact_orders.csv","SELECT * FROM order_metrics"),("fact_cycle_counts.csv","SELECT * FROM count_metrics"),
                        ("stock_analysis.csv","SELECT * FROM stock_analysis"),("sku_abc.csv","SELECT * FROM sku_abc")]:
        write_csv(OUT/file,records(conn,query))
    write_csv(OUT/"weekly_metrics.csv",weeks)
    write_csv(OUT/"quarantine.csv",rejected)
    write_csv(OUT/"warehouse_summary.csv",payload["warehouses"])
    (OUT/"quality_report.json").write_text(json.dumps(quality,indent=2)+"\n")
    (OUT/"metric_summary.json").write_text(json.dumps(payload["summary"],indent=2)+"\n")
    conn.close()
    print(json.dumps({"status":"built","synthetic":True,"summary":payload["summary"],"quarantined_rows":len(rejected)},indent=2))
    return payload

if __name__ == "__main__":
    build()
