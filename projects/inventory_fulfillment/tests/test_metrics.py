"""Boundary examples test KPI meaning, not generated target percentages."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import build

class MetricBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.conn=build.connect_db(":memory:")
        self.conn.execute("INSERT INTO warehouses VALUES('W','Test warehouse')")
        self.conn.executemany("INSERT INTO products VALUES(?,?,?,?)",[("A","Test",1,3),("B","Test",1,3),("C","Test",1,3)])

    def tearDown(self):
        self.conn.close()

    def views(self):
        self.conn.executescript((ROOT/"sql/analytics.sql").read_text())

    def test_due_cohort_includes_overdue_open_and_excludes_future_cancelled(self):
        self.conn.executemany("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)",[
            ("on","W","A",1,"2026-01-01T09:00:00","2026-01-02T18:00:00","2026-01-02T18:00:00",None),
            ("late","W","A",1,"2026-01-01T09:00:00","2026-01-02T18:00:00","2026-01-03T09:00:00",None),
            ("overdue","W","A",1,"2026-01-01T09:00:00","2026-01-02T18:00:00",None,None),
            ("future","W","A",1,"2026-02-25T09:00:00","2026-02-27T18:00:00",None,None),
            ("cancelled","W","A",1,"2026-01-01T09:00:00","2026-01-02T18:00:00",None,"2026-01-01T10:00:00")])
        self.views()
        actual=tuple(self.conn.execute("SELECT SUM(is_eligible),SUM(is_on_time),SUM(is_open),SUM(is_overdue) FROM order_metrics").fetchone())
        self.assertEqual(actual,(3,1,2,1))
        self.assertAlmostEqual(build.pct(actual[1],actual[0]),33.33)

    def test_accuracy_is_record_weighted_and_absolute_variances_do_not_cancel(self):
        self.conn.executemany("INSERT INTO cycle_counts VALUES(?,?,?,?,?,?)",[
            ("c1","W","A","2026-01-01T16:00:00",100,102),
            ("c2","W","B","2026-01-01T16:00:00",100,98),
            ("c3","W","C","2026-01-01T16:00:00",0,0)])
        self.views()
        actual=tuple(self.conn.execute("SELECT COUNT(*),SUM(is_accurate),SUM(absolute_variance_units),SUM(signed_variance_units) FROM count_metrics").fetchone())
        self.assertEqual(actual,(3,1,4,0))

    def test_abc_threshold_crossing_and_zero_demand_are_defined(self):
        self.conn.executemany("INSERT INTO orders VALUES(?,?,?,?,?,?,?,?)",[
            ("a","W","A",81,"2026-01-01T09:00:00","2026-01-02T18:00:00",None,None),
            ("b","W","B",15,"2026-01-01T09:00:00","2026-01-02T18:00:00",None,None),
            ("c","W","C",4,"2026-01-01T09:00:00","2026-01-02T18:00:00",None,None)])
        self.conn.execute("INSERT INTO warehouses VALUES('Z','Zero demand')")
        self.views()
        self.assertEqual([tuple(r) for r in self.conn.execute("SELECT sku_id,abc_class FROM sku_abc WHERE warehouse_id='W' ORDER BY sku_id")],[("A","A"),("B","B"),("C","C")])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM sku_abc WHERE warehouse_id='Z' AND abc_class='C'").fetchone()[0],3)

    def test_no_eligible_orders_returns_blank_rate(self):
        self.assertIsNone(build.pct(0,0))

    def test_raw_duplicate_and_invalid_quantity_are_not_double_counted(self):
        row=dict(order_id="x",warehouse_id="W",sku_id="A",quantity="1",created_at="2026-01-01T09:00:00",promised_dispatch_at="2026-01-02T18:00:00",dispatched_at="",cancelled_at="")
        invalid={**row,"order_id":"bad","quantity":"0"}
        accepted,rejected=build.validate_orders([row,dict(row),invalid],{"W"},{"A"})
        self.assertEqual(len(accepted),1)
        self.assertEqual([x["reason"] for x in rejected],["exact_duplicate","nonpositive_quantity"])

    def test_replenishment_flags_do_not_treat_zero_demand_as_stockout(self):
        self.conn.executemany("INSERT INTO snapshots VALUES(?,?,?,?)",[("W","A",build.stamp(build.AS_OF),0),("W","B",build.stamp(build.AS_OF),5),("W","C",build.stamp(build.AS_OF),0)])
        self.conn.execute("INSERT INTO orders VALUES('d','W','A',56,'2026-01-01T09:00:00','2026-01-02T18:00:00',NULL,NULL)")
        self.views()
        self.assertEqual([tuple(r) for r in self.conn.execute("SELECT sku_id,exception FROM stock_analysis ORDER BY sku_id")],[("A","Stockout"),("B","No observed demand"),("C","Within policy")])

class BuiltDataIntegrityTests(unittest.TestCase):
    def test_exported_cohort_balances(self):
        import json
        payload=json.loads((ROOT/"dashboard_data.json").read_text())
        s=payload["summary"]
        self.assertEqual(s["orders_created"],s["cancelled_orders"]+s["dispatched_orders"]+s["open_backlog"])
        self.assertLessEqual(s["overdue_backlog"],s["open_backlog"])
        self.assertEqual(sum(r["eligible_orders"] for r in payload["weeks"]),s["eligible_orders"])
        self.assertEqual(sum(r["count_records"] for r in payload["weeks"]),s["count_records"])
        self.assertEqual(sum(r["replenishment_exceptions"] for r in payload["warehouses"]),s["replenishment_exceptions"])
        self.assertEqual(payload["quality"]["quarantined_rows"],6)

if __name__=="__main__":
    unittest.main()
