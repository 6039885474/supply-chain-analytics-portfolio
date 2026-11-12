"""Small hand-calculated fixtures expose cohort, fan-out, missingness and cutoff errors."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build import clean_attempts, make_db, summary, generate

class MetricsTest(unittest.TestCase):
    def setUp(self):
        self.data = {
          "hubs": [{"hub_id":"H01","hub_name":"Test Hub"}],
          "shipments": [
            {"shipment_id":"A","hub_id":"H01","service":"Standard","shipped_at":"2026-01-01T10:00:00","promised_at":"2026-01-03T20:00:00","delivered_at":"2026-01-02T10:00:00"},
            {"shipment_id":"B","hub_id":"H01","service":"Standard","shipped_at":"2026-01-01T10:00:00","promised_at":"2026-01-04T20:00:00","delivered_at":"2026-01-07T10:00:00"},
            {"shipment_id":"C","hub_id":"H01","service":"Standard","shipped_at":"2026-01-01T10:00:00","promised_at":"2026-01-05T20:00:00","delivered_at":""},
            {"shipment_id":"D","hub_id":"H01","service":"Standard","shipped_at":"2026-02-25T10:00:00","promised_at":"2026-02-28T20:00:00","delivered_at":""}],
          "attempts": [
            {"attempt_id":"A-1","shipment_id":"A","attempt_number":1,"attempted_at":"2026-01-02T10:00:00","outcome":"delivered"},
            {"attempt_id":"B-1","shipment_id":"B","attempt_number":1,"attempted_at":"2026-01-03T10:00:00","outcome":"address_issue"},
            {"attempt_id":"B-2","shipment_id":"B","attempt_number":2,"attempted_at":"2026-01-07T10:00:00","outcome":"delivered"}],
          "returns": [
            {"return_id":"RA","shipment_id":"A","return_type":"CUSTOMER_RETURN","requested_at":"2026-01-02T12:00:00","completed_at":"2026-01-06T12:00:00"},
            {"return_id":"RB","shipment_id":"B","return_type":"CUSTOMER_RETURN","requested_at":"2026-02-20T12:00:00","completed_at":"2026-03-01T12:00:00"},
            {"return_id":"RC","shipment_id":"C","return_type":"RTO","requested_at":"2026-01-05T12:00:00","completed_at":""}],
          "costs": [
            {"cost_id":"A-L","shipment_id":"A","cost_type":"linehaul","posted_at":"2026-01-01T10:00:00","amount_cents":1000},
            {"cost_id":"A-A","shipment_id":"A","cost_type":"delivery_attempt","posted_at":"2026-01-02T10:00:00","amount_cents":100},
            {"cost_id":"B-L","shipment_id":"B","cost_type":"linehaul","posted_at":"2026-01-01T10:00:00","amount_cents":2000},
            {"cost_id":"B-A","shipment_id":"B","cost_type":"delivery_attempt","posted_at":"2026-01-03T10:00:00","amount_cents":300},
            {"cost_id":"D-L","shipment_id":"D","cost_type":"linehaul","posted_at":"2026-02-25T10:00:00","amount_cents":500}]}
        self.db = make_db(self.data, self.data["attempts"])
    def tearDown(self):
        self.db.close()
    def test_future_promises_excluded_and_undelivered_included(self):
        s=summary(self.db)
        self.assertEqual((s["on_time_eligible"],s["on_time_delivered"],s["matured_undelivered"]),(3,1,1))
        self.assertAlmostEqual(s["on_time_delivery_rate_pct"],33.33)
    def test_missing_scan_and_second_attempt_do_not_become_first(self):
        s=summary(self.db)
        self.assertEqual((s["first_attempts"],s["first_attempt_successes"],s["missing_first_scan"]),(2,1,1))
    def test_returns_remain_distinct_and_future_completion_is_censored(self):
        s=summary(self.db)
        self.assertEqual((s["rto_shipments"],s["customer_return_shipments"]),(1,2))
        self.assertEqual((s["completed_returns"],s["open_returns"],s["open_returns_over_7d"]),(1,2,1))
        self.assertEqual(s["avg_return_cycle_days"],4.0)
    def test_cost_fanout_and_missing_cost_denominator(self):
        s=summary(self.db)
        self.assertEqual(s["attributed_cost_cents"],3900)
        self.assertEqual(s["cost_covered_shipments"],3)
        self.assertEqual(s["cost_per_shipment_usd"],13.0)
        self.assertEqual(s["cost_coverage_pct"],75)
        self.assertIsNone(self.db.execute("SELECT attributed_cost_cents FROM shipment_metrics WHERE shipment_id='C'").fetchone()[0])
    def test_empty_filter_rates_are_null(self):
        s=summary(self.db,hub="does-not-exist")
        self.assertIsNone(s["first_attempt_success_rate_pct"])
        self.assertIsNone(s["cost_per_shipment_usd"])
    def test_exact_duplicate_collapsed_conflict_quarantined(self):
        a=dict(self.data["attempts"][0]); conflict={**a,"outcome":"address_issue"}
        clean,issues=clean_attempts([a,dict(a)])
        self.assertEqual(len(clean),1)
        self.assertEqual(issues[0]["issue"],"exact_duplicate_attempt")
        clean,issues=clean_attempts([a,conflict])
        self.assertEqual(clean,[])
        self.assertEqual(issues[0]["issue"],"conflicting_attempt_id")
    def test_generated_integrity_and_counts_reconcile(self):
        data=generate(); clean,_=clean_attempts(data["attempts"])
        shipment_ids={s["shipment_id"] for s in data["shipments"]}
        self.assertEqual(len(shipment_ids),len(data["shipments"]))
        for table in (clean,data["returns"],data["costs"]):
            self.assertTrue(all(r["shipment_id"] in shipment_ids for r in table))
        scan_keys=[(a["shipment_id"],a["attempt_number"]) for a in clean]
        self.assertEqual(len(scan_keys),len(set(scan_keys)))
        db=make_db(data,clean); s=summary(db)
        self.assertEqual(s["shipments"],len(data["shipments"]))
        self.assertEqual(s["completed_returns"]+s["open_returns"],len(data["returns"]))
        self.assertEqual(s["shipments"],sum(summary(db,h["hub_id"])["shipments"] for h in data["hubs"]))
        self.assertTrue(all(r["amount_cents"]>=0 for r in data["costs"]))
        db.close()

if __name__=="__main__":
    unittest.main()
