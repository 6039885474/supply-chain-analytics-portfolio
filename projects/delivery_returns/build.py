"""Deterministic synthetic last-mile analytics. Python 3.10+, standard library only."""
from __future__ import annotations
import csv
import json
import random
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
START = datetime(2026, 1, 1)
ASOF = datetime(2026, 2, 25, 23, 59, 59)
SEED = 41827

def iso(d):
    return d.isoformat(timespec="seconds") if d else ""

def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fields)
        w.writeheader()
        w.writerows(rows)

def generate():
    rng = random.Random(SEED)
    hubs = [{"hub_id": "H01", "hub_name": "North Harbor"},
            {"hub_id": "H02", "hub_name": "Cedar Valley"},
            {"hub_id": "H03", "hub_name": "Riverbend"}]
    shipments, attempts, returns, costs = [], [], [], []
    for day in range(56):
        for _ in range(rng.randint(75, 115)):
            n = len(shipments) + 1
            sid = f"S{n:06d}"
            hub = rng.choices(hubs, weights=[.40, .34, .26])[0]["hub_id"]
            mode = rng.choice(["Standard", "Standard", "Express"])
            shipped = START + timedelta(days=day, hours=rng.randint(7, 18), minutes=rng.randint(0, 59))
            promised = (shipped + timedelta(days=2 if mode == "Express" else 4)).replace(hour=20, minute=0, second=0)
            first = shipped + timedelta(days=rng.randint(1, 3), hours=rng.randint(0, 6))
            fail_prob = {"H01": .11, "H02": .17, "H03": .23}[hub]
            success = rng.random() >= fail_prob
            delivered = first if success else None
            observed_attempts = []
            reason = "delivered" if success else rng.choice(["customer_unavailable", "address_issue", "access_restricted"])
            observed_attempts.append((first, 1, reason))
            if not success:
                second = first + timedelta(days=rng.randint(1, 2), hours=rng.randint(0, 3))
                success = rng.random() > .28
                delivered = second if success else None
                observed_attempts.append((second, 2, "delivered" if success else rng.choice(["customer_unavailable", "address_issue"])))
                if not success:
                    req = second + timedelta(hours=12)
                    close = req + timedelta(days=rng.randint(2, 11), hours=rng.randint(0, 23))
                    if req <= ASOF:
                        returns.append({"return_id": f"R{len(returns)+1:05d}", "shipment_id": sid, "return_type": "RTO", "requested_at": iso(req), "completed_at": iso(close if close <= ASOF else None)})
            if delivered and rng.random() < .075:
                req = delivered + timedelta(days=rng.randint(1, 7))
                close = req + timedelta(days=rng.randint(2, 12), hours=rng.randint(0, 23))
                if req <= ASOF:
                    returns.append({"return_id": f"R{len(returns)+1:05d}", "shipment_id": sid, "return_type": "CUSTOMER_RETURN", "requested_at": iso(req), "completed_at": iso(close if close <= ASOF else None)})
            shipments.append({"shipment_id": sid, "hub_id": hub, "service": mode, "shipped_at": iso(shipped), "promised_at": iso(promised), "delivered_at": iso(delivered if delivered and delivered <= ASOF else None)})
            for timestamp, number, result in observed_attempts:
                if timestamp <= ASOF:
                    attempts.append({"attempt_id": f"{sid}-A{number}", "shipment_id": sid, "attempt_number": number, "attempted_at": iso(timestamp), "outcome": result})
            # Cost ledger covers known charges as of the snapshot, not forecast total life-cycle cost.
            if n % 131 != 0:
                base = rng.randint(280, 540) + (65 if mode == "Express" else 0)
                costs.append({"cost_id": f"{sid}-LINEHAUL", "shipment_id": sid, "cost_type": "linehaul", "posted_at": iso(shipped), "amount_cents": base})
                for timestamp, number, _ in observed_attempts:
                    if timestamp <= ASOF:
                        costs.append({"cost_id": f"{sid}-ATTEMPT{number}", "shipment_id": sid, "cost_type": "delivery_attempt", "posted_at": iso(timestamp), "amount_cents": rng.randint(90, 170)})
    # Known synthetic errors make the cleaning work reproducible.
    attempts = [a for i, a in enumerate(attempts) if not (a["attempt_number"] == 1 and i % 89 == 0)]
    attempts += [dict(a) for a in attempts[30:45]]  # 15 exact duplicate ingestion rows.
    conflicts = []
    for a in attempts[70:73]:
        b = dict(a)
        b["outcome"] = "delivered" if a["outcome"] != "delivered" else "address_issue"
        conflicts.append(b)
    attempts += conflicts  # Three conflicting IDs are quarantined, never arbitrarily selected.
    return {"hubs": hubs, "shipments": shipments, "attempts": attempts, "returns": returns, "costs": costs}

def clean_attempts(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["attempt_id"]].append(row)
    clean, issues = [], []
    for aid, group in groups.items():
        unique = {tuple(sorted(r.items())) for r in group}
        if len(unique) > 1:
            issues.append({"issue": "conflicting_attempt_id", "record_id": aid, "shipment_id": group[0]["shipment_id"], "rows_affected": len(group), "action": "Quarantine every row for this ID"})
        else:
            clean.append(group[0])
            if len(group) > 1:
                issues.append({"issue": "exact_duplicate_attempt", "record_id": aid, "shipment_id": group[0]["shipment_id"], "rows_affected": len(group)-1, "action": "Keep one identical row"})
    return clean, issues

def make_db(data, attempts):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    schemas = {
        "hubs": "hub_id TEXT PRIMARY KEY, hub_name TEXT NOT NULL",
        "shipments": "shipment_id TEXT PRIMARY KEY,hub_id TEXT,service TEXT,shipped_at TEXT,promised_at TEXT,delivered_at TEXT",
        "attempts": "attempt_id TEXT PRIMARY KEY,shipment_id TEXT,attempt_number INTEGER,attempted_at TEXT,outcome TEXT",
        "returns": "return_id TEXT PRIMARY KEY,shipment_id TEXT,return_type TEXT,requested_at TEXT,completed_at TEXT",
        "costs": "cost_id TEXT PRIMARY KEY,shipment_id TEXT,cost_type TEXT,posted_at TEXT,amount_cents INTEGER"}
    for name, definition in schemas.items():
        db.execute(f"CREATE TABLE {name} ({definition})")
        rows = attempts if name == "attempts" else data[name]
        fields = list(rows[0])
        db.executemany(f"INSERT INTO {name} VALUES ({','.join('?' for _ in fields)})", [[r[k] if r[k] != "" else None for k in fields] for r in rows])
    db.execute("CREATE TABLE settings (window_start TEXT, window_end TEXT, as_of TEXT)")
    db.execute("INSERT INTO settings VALUES (?,?,?)", (iso(START), iso(ASOF), iso(ASOF)))
    db.executescript((ROOT / "sql" / "analytics.sql").read_text())
    return db

def rows(db, query):
    return [dict(x) for x in db.execute(query)]

def summary(db, hub=None, week=None):
    # All event dates must be within the reporting window. Weekly views use each KPI's defined event date.
    conditions, params = [], []
    if hub:
        conditions.append("hub_id = ?"); params.append(hub)
    if week:
        conditions.append("week_start = ?"); params.append(week)
    clause = " WHERE " + " AND ".join(conditions) if conditions else ""
    sums = dict(db.execute("SELECT COALESCE(SUM(shipments),0) shipments, COALESCE(SUM(first_attempts),0) first_attempts, COALESCE(SUM(first_attempt_successes),0) first_attempt_successes, COALESCE(SUM(on_time_eligible),0) on_time_eligible, COALESCE(SUM(on_time_delivered),0) on_time_delivered, COALESCE(SUM(matured_undelivered),0) matured_undelivered, COALESCE(SUM(rto_shipments),0) rto_shipments, COALESCE(SUM(customer_return_shipments),0) customer_return_shipments, COALESCE(SUM(completed_returns),0) completed_returns, COALESCE(SUM(return_cycle_days),0) return_cycle_days, COALESCE(SUM(open_returns),0) open_returns, COALESCE(SUM(open_returns_over_7d),0) open_returns_over_7d, COALESCE(SUM(cost_covered_shipments),0) cost_covered_shipments, COALESCE(SUM(attributed_cost_cents),0) attributed_cost_cents, COALESCE(SUM(missing_first_scan),0) missing_first_scan FROM weekly_metrics" + clause, params).fetchone())
    ratio = lambda numerator, denominator: round(100 * sums[numerator] / sums[denominator], 2) if sums[denominator] else None
    sums.update({"first_attempt_success_rate_pct": ratio("first_attempt_successes", "first_attempts"), "on_time_delivery_rate_pct": ratio("on_time_delivered", "on_time_eligible"), "rto_rate_pct": ratio("rto_shipments", "shipments"), "customer_return_rate_pct": ratio("customer_return_shipments", "shipments"), "avg_return_cycle_days": round(sums["return_cycle_days"] / sums["completed_returns"], 2) if sums["completed_returns"] else None, "cost_per_shipment_usd": round(sums["attributed_cost_cents"] / 100 / sums["cost_covered_shipments"], 2) if sums["cost_covered_shipments"] else None, "attributed_cost_usd": round(sums["attributed_cost_cents"] / 100, 2), "cost_coverage_pct": ratio("cost_covered_shipments", "shipments")})
    sums["return_cycle_days"] = round(sums["return_cycle_days"], 4)
    return sums

def build():
    data = generate()
    attempts, issues = clean_attempts(data["attempts"])
    for table, records in data.items():
        write_csv(ROOT / "data/raw" / f"{table}.csv", records)
    db = make_db(data, attempts)
    for table in ["shipment_metrics", "return_metrics", "weekly_metrics"]:
        write_csv(ROOT / "data/processed" / f"{table}.csv", rows(db, f"SELECT * FROM {table}"))
    write_csv(ROOT / "data/processed/attempts_clean.csv", attempts)
    write_csv(ROOT / "data/processed/data_quality_issues.csv", issues)
    write_csv(ROOT / "data/processed/settings.csv", [{"window_start": iso(START), "window_end": iso(ASOF), "as_of": iso(ASOF)}])
    hubs = [{**h, **summary(db, h["hub_id"])} for h in data["hubs"]]
    weeks = []
    for rec in rows(db, "SELECT DISTINCT hub_id,week_start FROM weekly_metrics ORDER BY week_start,hub_id"):
        weeks.append({**rec, **summary(db, rec["hub_id"], rec["week_start"])})
    # Export every open case so a frontend hub filter retains the complete selected backlog.
    exceptions = rows(db, "SELECT r.return_id,r.shipment_id,r.hub_id,r.return_type,r.requested_at,r.open_age_days FROM return_metrics r WHERE completed_at IS NULL ORDER BY open_age_days DESC,return_id")
    reasons = rows(db, "SELECT s.hub_id,a.outcome AS reason,COUNT(*) AS attempts FROM attempts a JOIN shipments s USING(shipment_id) WHERE a.attempt_number=1 AND a.outcome!='delivered' GROUP BY s.hub_id,a.outcome ORDER BY attempts DESC")
    definitions = {
        "first_attempt_success_rate_pct": "Delivered first attempts / valid observed attempt_number=1 events in the window. Missing/conflicting scans are excluded and counted separately.",
        "on_time_delivery_rate_pct": "Shipments promised during the window and due by as-of that delivered on/before promise / all shipments in that matured promised cohort, including undelivered.",
        "rto_rate_pct": "Shipped-cohort parcels with RTO initiated by as-of / all parcels shipped in the window. Observed share, not final lifetime RTO probability.",
        "customer_return_rate_pct": "Shipped-cohort parcels with customer return requested by as-of / all parcels shipped in window. Different business event from RTO.",
        "avg_return_cycle_days": "Mean requested-to-completed duration for return cases requested in the window and completed by as-of. Always read alongside open count/aging.",
        "cost_per_shipment_usd": "Attributed charges posted by as-of for shipped-window parcels with a linehaul cost record / number of those cost-covered parcels. Missing cost is not zero.",
        "weeks": "Monday-start week; shipment/RTO/cost metrics use shipped date, first attempts use attempted date, OTD uses promised date, return-cycle metrics use requested date. Do not interpret weekly rows as a single shipment cohort."
    }
    output = {"metadata": {"title": "Last-mile Delivery and Returns", "data_source": "Deterministic synthetic data; no employer records", "seed": SEED, "window_start": iso(START), "window_end": iso(ASOF), "as_of": iso(ASOF), "currency": "USD", "timezone": "UTC", "raw_counts": {k: len(v) for k,v in data.items()}, "clean_attempts": len(attempts), "quality_issues": len(issues)}, "summary": summary(db), "hubs": hubs, "weeks": weeks, "exceptions": exceptions, "failure_reasons": reasons, "quality": issues, "definitions": definitions}
    (ROOT / "dashboard_data.json").write_text(json.dumps(output, indent=2) + "\n")
    # The database is an optional locally rebuilt artifact, ignored in Git.
    disk = sqlite3.connect(ROOT / "data/analytics.sqlite")
    db.backup(disk); disk.close(); db.close()
    print(json.dumps(output["summary"], indent=2))
    return output

if __name__ == "__main__":
    build()
