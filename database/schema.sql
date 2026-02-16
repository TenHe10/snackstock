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
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (barcode) REFERENCES products (barcode)
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

CREATE INDEX IF NOT EXISTS idx_stock_logs_timestamp ON stock_logs(timestamp);
