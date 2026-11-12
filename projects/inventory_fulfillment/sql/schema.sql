PRAGMA foreign_keys = ON;
CREATE TABLE settings (as_of TEXT NOT NULL, period_start TEXT NOT NULL, period_end TEXT NOT NULL, count_tolerance_units INTEGER NOT NULL);
CREATE TABLE warehouses (warehouse_id TEXT PRIMARY KEY, warehouse_name TEXT NOT NULL);
CREATE TABLE products (sku_id TEXT PRIMARY KEY, category TEXT NOT NULL, unit_cost REAL NOT NULL CHECK(unit_cost>0), lead_time_days INTEGER NOT NULL CHECK(lead_time_days>0));
CREATE TABLE orders (
 order_id TEXT PRIMARY KEY, warehouse_id TEXT NOT NULL REFERENCES warehouses, sku_id TEXT NOT NULL REFERENCES products,
 quantity INTEGER NOT NULL CHECK(quantity>0), created_at TEXT NOT NULL, promised_dispatch_at TEXT NOT NULL,
 dispatched_at TEXT, cancelled_at TEXT
);
CREATE TABLE cycle_counts (
 count_id TEXT PRIMARY KEY, warehouse_id TEXT NOT NULL REFERENCES warehouses, sku_id TEXT NOT NULL REFERENCES products,
 counted_at TEXT NOT NULL, system_qty INTEGER NOT NULL CHECK(system_qty>=0), physical_qty INTEGER NOT NULL CHECK(physical_qty>=0)
);
CREATE TABLE snapshots (
 warehouse_id TEXT NOT NULL REFERENCES warehouses, sku_id TEXT NOT NULL REFERENCES products,
 as_of TEXT NOT NULL, on_hand INTEGER NOT NULL CHECK(on_hand>=0), PRIMARY KEY(warehouse_id,sku_id,as_of)
);
CREATE INDEX ix_orders_warehouse_created ON orders(warehouse_id,created_at);
CREATE INDEX ix_counts_warehouse_counted ON cycle_counts(warehouse_id,counted_at);
