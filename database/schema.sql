PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS structures (
    structure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    location_text TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_structures_name
ON structures(name);


CREATE TABLE IF NOT EXISTS inspections (
    inspection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    structure_id INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL
        CHECK (
            status IN (
                'PLANNED',
                'RUNNING',
                'PROCESSING',
                'REVIEW',
                'COMPLETED',
                'FAILED'
            )
        ),
    system_version TEXT NOT NULL,
    notes TEXT,
    FOREIGN KEY (structure_id)
        REFERENCES structures(structure_id)
        ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_inspections_structure
ON inspections(structure_id);

CREATE INDEX IF NOT EXISTS idx_inspections_status
ON inspections(status);


CREATE TABLE IF NOT EXISTS defects (
    defect_id TEXT PRIMARY KEY,

    inspection_id INTEGER NOT NULL,

    track_id TEXT,

    class_name TEXT NOT NULL,

    confidence REAL NOT NULL
        CHECK (
            confidence >= 0.0
            AND confidence <= 1.0
        ),

    x_m REAL NOT NULL,
    y_m REAL NOT NULL,
    z_m REAL NOT NULL,

    coordinate_frame TEXT NOT NULL,

    observation_count INTEGER NOT NULL
        CHECK (observation_count >= 1),

    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,

    model_version TEXT NOT NULL,

    review_status TEXT NOT NULL
        DEFAULT 'UNREVIEWED'
        CHECK (
            review_status IN (
                'UNREVIEWED',
                'CONFIRMED',
                'REJECTED',
                'NEEDS_INVESTIGATION'
            )
        ),

    review_notes TEXT,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY (inspection_id)
        REFERENCES inspections(inspection_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_defects_inspection
ON defects(inspection_id);

CREATE INDEX IF NOT EXISTS idx_defects_class
ON defects(class_name);

CREATE INDEX IF NOT EXISTS idx_defects_review_status
ON defects(review_status);

CREATE INDEX IF NOT EXISTS idx_defects_confidence
ON defects(confidence);

CREATE INDEX IF NOT EXISTS idx_defects_inspection_review
ON defects(inspection_id, review_status);


CREATE TABLE IF NOT EXISTS evidence (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,

    defect_id TEXT NOT NULL,

    frame_id TEXT NOT NULL,

    timestamp TEXT NOT NULL,

    image_path TEXT,
    crop_path TEXT,

    confidence REAL NOT NULL
        CHECK (
            confidence >= 0.0
            AND confidence <= 1.0
        ),

    bbox_x1 REAL NOT NULL,
    bbox_y1 REAL NOT NULL,
    bbox_x2 REAL NOT NULL,
    bbox_y2 REAL NOT NULL,

    FOREIGN KEY (defect_id)
        REFERENCES defects(defect_id)
        ON DELETE CASCADE,

    UNIQUE (
        defect_id,
        frame_id,
        bbox_x1,
        bbox_y1,
        bbox_x2,
        bbox_y2
    )
);

CREATE INDEX IF NOT EXISTS idx_evidence_defect
ON evidence(defect_id);

CREATE INDEX IF NOT EXISTS idx_evidence_defect_timestamp
ON evidence(defect_id, timestamp);
