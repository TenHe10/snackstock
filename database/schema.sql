CREATE TABLE IF NOT EXISTS products (
    barcode TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT '',
    purchase_price REAL NOT NULL,
    retail_price REAL NOT NULL,
    min_stock INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS stock_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode TEXT NOT NULL,
    change_qty INTEGER NOT NULL,
    type TEXT NOT NULL,
    sale_order_id INTEGER,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (barcode) REFERENCES products (barcode),
    FOREIGN KEY (sale_order_id) REFERENCES sales_orders (id)
);

CREATE TABLE IF NOT EXISTS stock_totals (
    barcode TEXT PRIMARY KEY,
    current_qty INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (barcode) REFERENCES products (barcode)
);

CREATE TABLE IF NOT EXISTS expiry_management (
    barcode TEXT NOT NULL,
    batch_no TEXT NOT NULL,
    expiry_date DATE NOT NULL,
    current_qty INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (barcode, batch_no, expiry_date),
    FOREIGN KEY (barcode) REFERENCES products (barcode)
);

CREATE TABLE IF NOT EXISTS sales_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    total_due REAL NOT NULL,
    total_received REAL NOT NULL,
    discount REAL NOT NULL DEFAULT 0,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sales_order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    barcode TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_retail_price REAL NOT NULL,
    unit_purchase_price REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES sales_orders (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_stock_logs_timestamp ON stock_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_sales_orders_timestamp ON sales_orders(timestamp);
