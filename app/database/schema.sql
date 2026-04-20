-- SQLite Database Schema for Shopify Sync App

-- stores table (replaces config_stores.toml)
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT UNIQUE NOT NULL,
    store_name TEXT NOT NULL,
    title TEXT,
    api_version TEXT DEFAULT '2026-01',
    access_token_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- cached locations from Shopify
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    location_name TEXT,
    is_primary BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(store_id),
    UNIQUE(store_id, location_id)
);

-- sync runs (track each file processing)
CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_original_name TEXT,
    sync_mode TEXT NOT NULL,
    identifier_type TEXT,
    status TEXT DEFAULT 'pending',
    total_rows INTEGER DEFAULT 0,
    processed_rows INTEGER DEFAULT 0,
    missing_rows INTEGER DEFAULT 0,
    duplicate_rows INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

-- sync items (per-row results)
CREATE TABLE IF NOT EXISTS sync_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    reference TEXT NOT NULL,
    location_id TEXT,
    quantity INTEGER,
    status TEXT NOT NULL,
    error_message TEXT,
    shopify_product_id TEXT,
    shopify_variant_id TEXT,
    applied_delta INTEGER,
    final_quantity INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES sync_runs(id)
);

-- uploaded files metadata
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id TEXT NOT NULL,
    file_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER,
    row_count INTEGER,
    processed BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (store_id) REFERENCES stores(store_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sync_runs_store ON sync_runs(store_id);
CREATE INDEX IF NOT EXISTS idx_sync_runs_status ON sync_runs(status);
CREATE INDEX IF NOT EXISTS idx_sync_runs_started ON sync_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_sync_items_run ON sync_items(run_id);
CREATE INDEX IF NOT EXISTS idx_locations_store ON locations(store_id);
CREATE INDEX IF NOT EXISTS idx_files_store ON files(store_id);