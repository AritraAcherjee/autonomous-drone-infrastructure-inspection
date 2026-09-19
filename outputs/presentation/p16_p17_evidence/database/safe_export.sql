BEGIN TRANSACTION;
CREATE TABLE defects (
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
INSERT INTO "defects" VALUES('P15D-10627c5f-3f84-5c64-ab2d-3e574b6e97ee',2026091901,NULL,'Honeycombing',4.55309357494115829e-03,3.90000271274700871e+00,-9.877989958311785e-02,3.29301370791225357e-03,'map',1,'1970-01-01T00:00:21.813000Z','1970-01-01T00:00:21.813000Z','DET-FINAL-v1','UNREVIEWED',NULL,'2026-09-19T05:08:46Z','2026-09-19T05:08:46Z');
CREATE TABLE evidence (
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
INSERT INTO "evidence" VALUES(1,'P15D-10627c5f-3f84-5c64-ab2d-3e574b6e97ee','camera_optical_frame','1970-01-01T00:00:21.813000Z','/mnt/c/Dev/aegisinspect-07-vio/outputs/evidence/stop_b_map_frame_spatial_chain/corrected_capture/rgb_21813000000.png',NULL,4.55309357494115829e-03,3.105999755859375e+01,0.0,640.0,480.0);
CREATE TABLE inspections (
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
INSERT INTO "inspections" VALUES(2026091901,1,'2026-09-19T04:02:49.673541Z',NULL,'PROCESSING','P15 190bf7653b203c97418842474aa7cbd8016bfd44; P17 66d33acd00704d2f79b157471702e3709ce9d716 + scoped P16 boundary corrections','Detector classification: Honeycombing. Detector confidence: 0.004553093574941158. Extremely low confidence; unreviewed machine output, not physical defect confirmation or an engineering/safety conclusion. Coordinates are metric in a session-local map, not globally drift-corrected. First/last seen and evidence time encode ROS simulation 21.813 s as 1970-01-01T00:00:21.813000Z; this is not wall-clock capture time. Inspection started_at records the accepted runtime invocation UTC; no completed_at is asserted.');
CREATE TABLE structures (
    structure_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    location_text TEXT,
    created_at TEXT NOT NULL
);
INSERT INTO "structures" VALUES(1,'Stop-B inspection_bay simulation session','Evidence-session container for the accepted real DET-FINAL-v1 model observation from simulated RGB-D; not a surveyed physical structure.',NULL,'2026-09-19T05:08:46Z');
CREATE INDEX idx_structures_name
ON structures(name);
CREATE INDEX idx_inspections_structure
ON inspections(structure_id);
CREATE INDEX idx_inspections_status
ON inspections(status);
CREATE INDEX idx_defects_inspection
ON defects(inspection_id);
CREATE INDEX idx_defects_class
ON defects(class_name);
CREATE INDEX idx_defects_review_status
ON defects(review_status);
CREATE INDEX idx_defects_confidence
ON defects(confidence);
CREATE INDEX idx_defects_inspection_review
ON defects(inspection_id, review_status);
CREATE INDEX idx_evidence_defect
ON evidence(defect_id);
CREATE INDEX idx_evidence_defect_timestamp
ON evidence(defect_id, timestamp);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('structures',1);
INSERT INTO "sqlite_sequence" VALUES('inspections',2026091901);
INSERT INTO "sqlite_sequence" VALUES('evidence',1);
COMMIT;
