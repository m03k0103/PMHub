-- ==============================================================================
-- 政策会議ウォッチ (PMHub) マスターデータベース スキーマ定義
-- SQLite 3 (WAL モード対応 / FTS5 trigram 全文検索対応)
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- 1. 会議体マスターテーブル (councils)
CREATE TABLE IF NOT EXISTS councils (
    id TEXT PRIMARY KEY,
    ministry TEXT NOT NULL,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    official_url TEXT,
    archive_url TEXT,
    description TEXT,
    past_year_count INTEGER DEFAULT 0,
    is_closed INTEGER DEFAULT 0,
    closed_reason TEXT,
    manual_lock INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_councils_ministry ON councils(ministry);
CREATE INDEX IF NOT EXISTS idx_councils_category ON councils(category);
CREATE INDEX IF NOT EXISTS idx_councils_is_closed ON councils(is_closed);

-- 2. 開催回テーブル (meetings)
CREATE TABLE IF NOT EXISTS meetings (
    id TEXT PRIMARY KEY,
    council_id TEXT NOT NULL REFERENCES councils(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    date TEXT NOT NULL,
    round INTEGER,
    official_url TEXT,
    summary TEXT,
    tags_json TEXT,                    -- JSON array (e.g. '["答申", "中間とりまとめ"]')
    is_date_unconfirmed INTEGER DEFAULT 0,
    is_newly_discovered INTEGER DEFAULT 0,
    discovered_at TEXT,
    last_updated_from_crawl TEXT,
    manual_lock INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_meetings_council_id ON meetings(council_id);
CREATE INDEX IF NOT EXISTS idx_meetings_date ON meetings(date DESC);
CREATE INDEX IF NOT EXISTS idx_meetings_council_date ON meetings(council_id, date DESC);

-- 3. 開催回配付資料テーブル (materials)
CREATE TABLE IF NOT EXISTS materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meeting_id TEXT NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    type TEXT DEFAULT 'PDF',
    is_private INTEGER DEFAULT 0,
    manual_lock INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(meeting_id, url)
);

CREATE INDEX IF NOT EXISTS idx_materials_meeting_id ON materials(meeting_id);
CREATE INDEX IF NOT EXISTS idx_materials_type ON materials(type);

-- 4. 会議体常設資料テーブル (council_materials: 名簿・設置根拠等)
CREATE TABLE IF NOT EXISTS council_materials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    council_id TEXT NOT NULL REFERENCES councils(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    type TEXT DEFAULT 'PDF',
    manual_lock INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(council_id, url)
);

CREATE INDEX IF NOT EXISTS idx_council_materials_council_id ON council_materials(council_id);

-- 5. クローラー・管理用テーブル (admin_data.json 用)
CREATE TABLE IF NOT EXISTS scraping_rules (
    council_id TEXT PRIMARY KEY REFERENCES councils(id) ON DELETE CASCADE,
    rule_json TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crawl_statuses (
    council_id TEXT PRIMARY KEY REFERENCES councils(id) ON DELETE CASCADE,
    last_attempt TEXT,
    result TEXT,
    result_reason TEXT,
    extraction_method TEXT,
    materials_count INTEGER DEFAULT 0,
    dates_count INTEGER DEFAULT 0,
    failure_reason TEXT,
    consecutive_failures INTEGER DEFAULT 0,
    manual_lock_active INTEGER DEFAULT 0,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_configs (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. Track [Search] 配付資料全文検索仮想テーブル (FTS5 trigram)
CREATE VIRTUAL TABLE IF NOT EXISTS fts_materials USING fts5(
    material_id UNINDEXED,
    meeting_id UNINDEXED,
    council_id UNINDEXED,
    ministry UNINDEXED,
    meeting_date UNINDEXED,
    council_name,
    meeting_name,
    material_name,
    page_number UNINDEXED,
    page_text,
    tokenize = 'trigram'
);
