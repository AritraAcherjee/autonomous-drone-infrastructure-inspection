/*
 * P20 working-draft renderer. Facts are intentionally constrained to the
 * hardened assembly source and the verified P16/P17 presentation package.
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const PptxGenJS = require('pptxgenjs');
// PptxGenJS 4 exposes the enum on each presentation instance. Keep the
// renderer's static helpers explicit and compatible with the pinned package.
PptxGenJS.ShapeType = { rect: 'rect', line: 'line', roundRect: 'roundRect', ellipse: 'ellipse' };

const ROOT = path.resolve(__dirname, '../../..');
const ASSEMBLY = path.join(ROOT, 'docs', 'presentation', 'assembly', 'slide_content.md');
const READY = path.join(ROOT, 'docs', 'presentation', 'assembly', 'section_readiness.json');
const PLACEHOLDERS = path.join(ROOT, 'docs', 'presentation', 'assembly', 'runtime_placeholders.json');
const EVIDENCE = path.join(ROOT, 'outputs', 'presentation', 'p16_p17_evidence');
const P18_EVIDENCE = path.join(ROOT, 'outputs', 'presentation', 'p18_evidence');
const OUTPUT = path.resolve(ROOT, process.argv.includes('--output')
  ? process.argv[process.argv.indexOf('--output') + 1]
  : 'outputs/presentation/AegisInspect_P20_working_draft.pptx');
const METADATA = OUTPUT.replace(/\.pptx$/i, '.provenance.json');

const TITLE = 'AegisInspect: Multimodal Drone Infrastructure Inspection';
const NAVY = '0B1F33';
const BLUE = '1565C0';
const CYAN = '00A6A6';
const TEAL = '00796B';
const AMBER = 'D97706';
const RED = 'B42318';
const WHITE = 'FFFFFF';
const INK = '17212B';
const MUTED = '52616B';
const LIGHT = 'F3F7FA';
const FONT = 'Aptos';

function sha256(file) {
  return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
}

function requireFile(file) {
  if (!fs.existsSync(file)) throw new Error(`Required source asset is missing: ${file}`);
}

function sourceMustContain(source, literals) {
  const normalizedSource = source.replace(/\s+/g, ' ');
  const missing = literals.filter((literal) => !normalizedSource.includes(literal.replace(/\s+/g, ' ')));
  if (missing.length) throw new Error(`Assembly source lacks required facts: ${missing.join(', ')}`);
}

function verifyHashInventory(directory) {
  const inventory = path.join(directory, 'hashes.sha256');
  requireFile(inventory);
  const entries = fs.readFileSync(inventory, 'utf8').split(/\r?\n/).filter(Boolean).filter((line) => /^[0-9a-f]{64}\s+/i.test(line)).map((line) => {
    const match = /^([0-9a-f]{64})\s+\*?(.+)$/i.exec(line);
    if (!match) throw new Error(`Invalid hash inventory entry: ${line}`);
    return { hash: match[1].toLowerCase(), relative: match[2] };
  });
  for (const entry of entries) {
    const asset = path.join(directory, entry.relative);
    requireFile(asset);
    if (sha256(asset) !== entry.hash) throw new Error(`Evidence hash mismatch: ${asset}`);
  }
  return entries.length;
}

function addFooter(slide, number) {
  slide.addShape(PptxGenJS.ShapeType.line, { x: 0.45, y: 7.12, w: 12.42, h: 0, line: { color: 'D5DEE5', width: 0.6 } });
  slide.addText('AEGISINSPECT  |  FINALIZATION READY  |  LAST-EVIDENCE INGESTION OPEN', {
    x: 0.48, y: 7.18, w: 9.5, h: 0.18, fontFace: FONT, fontSize: 7.5, color: MUTED, margin: 0,
  });
  slide.addText(String(number).padStart(2, '0'), {
    x: 12.05, y: 7.16, w: 0.75, h: 0.2, fontFace: FONT, fontSize: 8, color: MUTED, bold: true, align: 'right', margin: 0,
  });
}

function addTitle(slide, title, eyebrow = 'AEGISINSPECT / P20') {
  slide.background = { color: WHITE };
  slide.addText(eyebrow, { x: 0.52, y: 0.28, w: 3.4, h: 0.22, fontFace: FONT, fontSize: 8, bold: true, color: BLUE, charSpace: 1.4, margin: 0 });
  slide.addText(title, { x: 0.52, y: 0.55, w: 12.1, h: 0.48, fontFace: FONT, fontSize: 25, bold: true, color: NAVY, margin: 0, breakLine: false, fit: 'shrink' });
  slide.addShape(PptxGenJS.ShapeType.line, { x: 0.52, y: 1.16, w: 1.05, h: 0, line: { color: CYAN, width: 3 } });
}

function addStatus(slide, text, color = BLUE) {
  const width = Math.min(5.7, 0.18 * text.length + 0.35);
  slide.addShape(PptxGenJS.ShapeType.roundRect, { x: 0.54, y: 1.3, w: width, h: 0.3, rectRadius: 0.06, fill: { color }, line: { color } });
  slide.addText(text, { x: 0.66, y: 1.38, w: width - 0.22, h: 0.1, fontFace: FONT, fontSize: 7.5, bold: true, color: WHITE, margin: 0, charSpace: 0.55, fit: 'shrink' });
}

function addBullets(slide, items, opts = {}) {
  const x = opts.x ?? 0.72;
  const y = opts.y ?? 1.82;
  const w = opts.w ?? 5.9;
  const h = opts.h ?? 4.9;
  const size = opts.size ?? 15.5;
  const color = opts.color ?? INK;
  const text = items.map((item) => `- ${item}`).join('\n');
  slide.addText(text, { x, y, w, h, fontFace: FONT, fontSize: size, color, breakLine: false, margin: 0.04, paraSpaceAfterPt: 11, breakLine: false, fit: 'shrink', valign: 'top' });
}

function addBody(slide, text, opts = {}) {
  slide.addText(text, { x: opts.x ?? 0.72, y: opts.y ?? 1.82, w: opts.w ?? 5.9, h: opts.h ?? 4.9, fontFace: FONT, fontSize: opts.size ?? 16, color: opts.color ?? INK, margin: opts.margin ?? 0.04, breakLine: false, fit: 'shrink', valign: opts.valign ?? 'top', bold: opts.bold ?? false, align: opts.align ?? 'left' });
}

function addCard(slide, title, value, x, y, w, h, color = BLUE, note = '', options = {}) {
  slide.addShape(PptxGenJS.ShapeType.roundRect, { x, y, w, h, rectRadius: 0.05, fill: { color: LIGHT }, line: { color: 'DCE6ED', width: 0.6 } });
  slide.addShape(PptxGenJS.ShapeType.rect, { x, y, w: 0.08, h, fill: { color }, line: { color } });
  const displayTitle = options.preserveTitleCase ? title : title.toUpperCase();
  slide.addText(displayTitle, { x: x + 0.22, y: y + 0.17, w: w - 0.34, h: 0.16, fontFace: FONT, fontSize: options.titleSize ?? 7.2, bold: true, color: MUTED, margin: 0, charSpace: options.preserveTitleCase ? 0 : 0.65, fit: 'shrink' });
  slide.addText(value, { x: x + 0.22, y: y + 0.43, w: w - 0.34, h: note ? h - 0.7 : h - 0.54, fontFace: FONT, fontSize: options.valueSize ?? 20, bold: true, color: NAVY, margin: 0, fit: 'shrink', valign: 'mid' });
  if (note) slide.addText(note, { x: x + 0.22, y: y + h - 0.28, w: w - 0.34, h: 0.15, fontFace: FONT, fontSize: 7.5, color: MUTED, margin: 0, fit: 'shrink' });
}

function addNotes(slide, sourceHash, detail) {
  slide.addNotes(`P20 FINALIZATION_READY_FOR_LAST-EVIDENCE_INGESTION\nAssembly source: docs/presentation/assembly/slide_content.md\nAssembly SHA-256: ${sourceHash}\nSpeaker note: ${detail}`);
}

function standardSlide(pptx, number, title, status, color, notes, builder) {
  const slide = pptx.addSlide();
  addTitle(slide, title);
  if (status) addStatus(slide, status, color);
  builder(slide);
  addFooter(slide, number);
  addNotes(slide, notes.sourceHash, notes.detail);
  return slide;
}

async function main() {
  [ASSEMBLY, READY, PLACEHOLDERS,
    path.join(EVIDENCE, 'dashboard', 'dashboard_overview.png'),
    path.join(EVIDENCE, 'dashboard', 'dashboard_detail.png'),
    path.join(EVIDENCE, 'report', 'inspection_2026091901.md'),
    path.join(P18_EVIDENCE, 'dashboard', 'dashboard_completion_overview_final.png'),
    path.join(P18_EVIDENCE, 'dashboard', 'clean_repeatability_overview.png')].forEach(requireFile);
  const source = fs.readFileSync(ASSEMBLY, 'utf8');
  const readiness = JSON.parse(fs.readFileSync(READY, 'utf8'));
  const placeholders = JSON.parse(fs.readFileSync(PLACEHOLDERS, 'utf8'));
  sourceMustContain(source, [TITLE, 'DET-FINAL-v1 / YOLO26s', '0.29669431228680787', '0.17480040543737643', '0.18618618618618618', '0.004553093574941158', 'UNREVIEWED', '0.595396782192 m', '0.340604743330 m', '1.707265244063 deg', 'dashboard-evidence completion package is PASS', 'clean repeatability run is PASS', '0.3886917344', '0.2657391403', 'Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.']);
  if (readiness.final_title !== TITLE) throw new Error('Readiness title does not match assembly source');
  if (!placeholders.localization.ate_translation_rmse_m.includes('0.595396782192')) throw new Error('Runtime placeholder does not preserve accepted ATE');
  const p16p17InventoryEntries = verifyHashInventory(EVIDENCE);
  const p18InventoryEntries = verifyHashInventory(P18_EVIDENCE);

  const sourceHash = sha256(ASSEMBLY);
  const notes = { sourceHash, detail: 'Evidence-derived factual content only; see on-slide status boundary.' };
  const pptx = new PptxGenJS();
  pptx.layout = 'LAYOUT_WIDE';
  pptx.author = 'AegisInspect P20';
  pptx.company = 'AegisInspect';
  pptx.subject = 'Evidence-bound presentation; ready for bounded final evidence ingestion';
  pptx.title = TITLE;
  pptx.lang = 'en-CA';
  pptx.theme = { headFontFace: FONT, bodyFontFace: FONT, lang: 'en-CA' };

  let n = 0;
  const slide = (title, status, color, detail, builder) => standardSlide(pptx, ++n, title, status, color, { ...notes, detail }, builder);

  const titleSlide = pptx.addSlide();
  titleSlide.background = { color: NAVY };
  titleSlide.addShape(PptxGenJS.ShapeType.rect, { x: 0, y: 0, w: 13.333, h: 0.18, fill: { color: CYAN }, line: { color: CYAN } });
  titleSlide.addText('AEGISINSPECT / P20', { x: 0.72, y: 0.78, w: 3.5, h: 0.25, fontFace: FONT, fontSize: 10, bold: true, color: '8ED8E1', charSpace: 1.6, margin: 0 });
  titleSlide.addText(TITLE, { x: 0.72, y: 1.35, w: 11.3, h: 1.5, fontFace: FONT, fontSize: 29, bold: true, color: WHITE, margin: 0, fit: 'shrink' });
  titleSlide.addText('An evidence-bound inspection pipeline combining defect detection, localization, 3D geometry, mapping, persistence and deterministic reporting.', { x: 0.75, y: 3.25, w: 9.7, h: 0.7, fontFace: FONT, fontSize: 17, color: 'D3E0EB', margin: 0, fit: 'shrink' });
  titleSlide.addShape(PptxGenJS.ShapeType.roundRect, { x: 0.75, y: 5.3, w: 3.45, h: 0.4, rectRadius: 0.06, fill: { color: TEAL }, line: { color: TEAL } });
  titleSlide.addText('FINALIZATION READY', { x: 0.9, y: 5.41, w: 3.1, h: 0.12, fontFace: FONT, fontSize: 8.5, bold: true, color: WHITE, charSpace: 1.2, align: 'center', margin: 0 });
  titleSlide.addText('Evidence-bound. No Stop C or full-autonomy claim.', { x: 0.76, y: 6.15, w: 5.7, h: 0.25, fontFace: FONT, fontSize: 11, color: 'AFC3D2', margin: 0 });
  addFooter(titleSlide, ++n);
  addNotes(titleSlide, sourceHash, 'Open with the product purpose, then state that every claim is evidence-bound and that full autonomy is not claimed.');

  slide('Inspection Problem and Objective', 'IMPLEMENTED / EVIDENCE-DRIVEN', BLUE, 'Frame the problem as repeatable evidence capture and traceable review. The objective is an integrated, measurable workflow—not a claim of a validated autonomous mission.', (s) => {
    addBody(s, 'Infrastructure inspection requires repeatable visual review and traceable defect documentation. AegisInspect keeps each subsystem claim tied to its evidence.', { x: 0.72, y: 1.85, w: 5.6, h: 1.35, size: 19 });
    addBullets(s, ['Acquire RGB, depth, IMU and LiDAR observations', 'Detect structural defects and project observations into 3D', 'Persist records for human review and deterministic reporting', 'Evaluate detector, localization and spatial outputs reproducibly'], { x: 6.8, y: 1.9, w: 5.8, h: 3.6, size: 16 });
    addBody(s, 'Boundary: this deck does not claim a validated full autonomous mission.', { x: 0.74, y: 5.55, w: 11.6, h: 0.42, size: 14, color: RED, bold: true });
  });

  slide('Evidence-Bound System Architecture', 'IMPLEMENTED / SYSTEM CHAIN', BLUE, 'Walk left to right from sensing to report. Call out demonstrated P16-P18 handoff, measured localization, and the bounded P19/LL pending items.', (s) => {
    const steps = ['CAMERA\n/ DETECTOR', 'DEPTH', 'CAMERA\nXYZ', 'LOCALIZATION\n/ MAP RELATION', 'MAP XYZ\n/ P15', 'P16\nPERSISTENCE', 'P17\nREPORT'];
    steps.forEach((step, i) => {
      const x = 0.55 + i * 1.8;
      s.addShape(PptxGenJS.ShapeType.roundRect, { x, y: 2.25, w: 1.45, h: 0.86, rectRadius: 0.05, fill: { color: i < 5 ? 'E8F2FA' : 'E7F6F2' }, line: { color: i < 5 ? BLUE : TEAL, width: 0.8 } });
      s.addText(step, { x: x + 0.1, y: 2.51, w: 1.25, h: 0.28, fontFace: FONT, fontSize: 9.5, bold: true, color: NAVY, align: 'center', margin: 0, fit: 'shrink' });
      if (i < steps.length - 1) s.addText('>', { x: x + 1.5, y: 2.48, w: 0.22, h: 0.3, fontFace: FONT, fontSize: 18, color: CYAN, align: 'center', margin: 0 });
    });
    addCard(s, 'Demonstrated', 'P16/P17 real handoff', 0.8, 4.15, 3.45, 1.2, TEAL, 'verified persistence, dashboard and report');
    addCard(s, 'Measured', 'P19 localization', 4.95, 4.15, 3.45, 1.2, BLUE, 'no frozen accuracy PASS/FAIL threshold');
    addCard(s, 'Pending', 'P19 3D + LL detector', 9.1, 4.15, 3.45, 1.2, AMBER, 'final correspondence / learned model', { valueSize: 16 });
  });

  slide('GYU-DET Dataset and Defect Classes', 'SUPPORTED / DATA FOUNDATION', CYAN, 'State the frozen dataset counts and six classes. These counts establish the data foundation; they are not performance metrics.', (s) => {
    addCard(s, 'Supervised images', '10,398', 0.75, 1.9, 2.6, 1.2, BLUE, 'GYU-DET V3 baseline-v1');
    addCard(s, 'Annotations', '48,392', 3.6, 1.9, 2.6, 1.2, CYAN, '6 defect classes');
    addCard(s, 'Held-out test', '1,053', 6.45, 1.9, 2.6, 1.2, TEAL, 'images');
    addCard(s, 'Test instances', '5,886', 9.3, 1.9, 2.6, 1.2, AMBER, 'GT instances');
    addBullets(s, ['Crack', 'Breakage', 'Honeycombing', 'Hole', 'Exposed Reinforcement', 'Seepage'], { x: 1.1, y: 3.65, w: 4.2, h: 2.1, size: 17 });
    addBody(s, 'Dataset counts are data-foundation facts, not detector-performance metrics.', { x: 6.15, y: 4.0, w: 5.2, h: 0.7, size: 18, color: NAVY, bold: true, align: 'center' });
  });

  slide('DET-FINAL-v1 Held-Out Detection Evidence', 'SUPPORTED / REAL HELD-OUT', CYAN, 'Present mAP as detection performance on the one-time held-out split. The diagnostic confidence came from validation; no threshold was tuned on test.', (s) => {
    addBody(s, 'DET-FINAL-v1 / YOLO26s', { x: 0.72, y: 1.85, w: 4.5, h: 0.42, size: 22, color: NAVY, bold: true });
    addCard(s, 'mAP50', '0.29669431228680787', 0.72, 2.55, 3.7, 1.35, BLUE, 'held-out GYU test', { preserveTitleCase: true, valueSize: 13 });
    addCard(s, 'mAP50-95', '0.17480040543737643', 4.75, 2.55, 3.7, 1.35, CYAN, 'held-out GYU test', { preserveTitleCase: true, valueSize: 13 });
    addCard(s, 'Mean class F1', '0.3556245448108634', 8.78, 2.55, 3.7, 1.35, TEAL, 'validation-selected threshold');
    addBullets(s, ['1,053 test images; 5,886 instances', 'Validation-selected operating threshold: 0.18618618618618618', 'Macro precision: 0.37674095487474335', 'Macro recall: 0.37432339044543'], { x: 0.9, y: 4.35, w: 6.1, h: 1.65, size: 14.5 });
    addBody(s, 'mAP is a detection metric, not generic or drone accuracy. The operating threshold was selected using validation data, not the test set.', { x: 7.45, y: 4.48, w: 4.75, h: 1.1, size: 14.5, color: RED, bold: true, align: 'center' });
  });

  slide('Localization and Simulation Architecture', 'SUPPORTED / SIMULATION RUNTIME', BLUE, 'Separate runtime acceptance from accuracy: LiDAR ICP ran successfully, while trajectory accuracy is reported later as MEASURED without a PASS threshold.', (s) => {
    addBullets(s, ['ROS 2 Lyrical and Gazebo Sim 10.5.0', 'RGB, CameraInfo, IMU, 3D LiDAR, depth, simulation clock and TF', 'Accepted LiDAR ICP runtime acceptance: PASS', 'Localization accuracy is MEASURED against simulation ground truth'], { x: 0.72, y: 1.9, w: 5.8, h: 3.4, size: 17 });
    addCard(s, 'Runtime acceptance', 'PASS', 7.1, 2.05, 2.45, 1.2, TEAL, 'LiDAR ICP runtime');
    addCard(s, 'Accuracy status', 'MEASURED', 9.88, 2.05, 2.45, 1.2, BLUE, 'not PASS / FAIL classified');
    addBody(s, 'No frozen localization-accuracy pass/fail threshold exists.', { x: 7.1, y: 4.1, w: 5.2, h: 0.75, size: 18, color: RED, bold: true, align: 'center' });
  });

  slide('Simulated Depth and Camera-Frame XYZ', 'SUPPORTED / SIMULATION RUNTIME', CYAN, 'Explain the metric-depth contract and ProjectCamera output frame. This is simulation/runtime evidence, not real-world depth or global-position accuracy.', (s) => {
    addCard(s, 'Depth contract', '32FC1', 0.8, 1.95, 2.65, 1.15, BLUE, 'metres / camera_optical_frame');
    addCard(s, 'Depth validation', '103 tests', 3.75, 1.95, 2.65, 1.15, CYAN, '0 errors, failures or skips');
    addCard(s, 'Projection validation', '196 tests', 6.7, 1.95, 2.65, 1.15, TEAL, '0 errors, failures or skips');
    addCard(s, 'Result frame', 'camera_optical_frame', 9.65, 1.95, 2.65, 1.15, AMBER, 'runtime-validated service', { valueSize: 13 });
    addBody(s, 'Depth and projection are supported in simulation. Camera-frame XYZ alone does not establish real-world depth accuracy, map-frame defect localization, or global localization accuracy.', { x: 1.05, y: 4.05, w: 11.1, h: 1.2, size: 20, color: NAVY, bold: true, align: 'center' });
  });

  slide('Map-Frame Defect Localization / P15', 'DEMONSTRATED / VERIFIED REAL HANDOFF', TEAL, 'Trace one accepted record from camera geometry through pose transform, aggregation and map XYZ. Final quantitative 3D correspondence remains pending.', (s) => {
    addBullets(s, ['Detection / track', 'Robust depth', 'Camera XYZ', 'Pose transform', 'Map XYZ', 'Temporal aggregation', 'Persistent defect record'], { x: 0.82, y: 1.85, w: 3.2, h: 4.4, size: 16 });
    s.addShape(PptxGenJS.ShapeType.line, { x: 4.15, y: 1.9, w: 0, h: 3.9, line: { color: 'D5DEE5', width: 1 } });
    addBody(s, 'Accepted mapped-defect lineage', { x: 4.65, y: 1.9, w: 5.9, h: 0.3, size: 20, color: NAVY, bold: true });
    addBody(s, 'P15D-10627c5f-3f84-5c64-ab2d-3e574b6e97ee\nmap XYZ: (3.9000027127470087, -0.09877989958311785, 0.0032930137079122536)\nTimestamp: 1970-01-01T00:00:21.813000Z', { x: 4.65, y: 2.55, w: 7.25, h: 1.6, size: 15.5, color: INK });
    addBody(s, 'P19 3D evaluation remains pending a controlled experiment with accepted explicit GT-to-mapped-defect correspondence.', { x: 4.65, y: 4.7, w: 7.25, h: 0.75, size: 15, color: RED, bold: true });
  });

  slide('P16 Persistence and Dashboard Review', 'DEMONSTRATED / VERIFIED REAL HANDOFF', TEAL, 'Show that the record persists and is reviewable. Stress that it is extremely-low-confidence and UNREVIEWED, not a confirmed physical defect.', (s) => {
    const image = path.join(EVIDENCE, 'dashboard', 'dashboard_overview.png');
    s.addImage({ path: image, x: 0.48, y: 1.6, w: 8.45, h: 5.45, sizing: { type: 'crop', x: 0.48, y: 1.6, w: 8.45, h: 5.45 } });
    addCard(s, 'Review', 'UNREVIEWED', 9.25, 1.85, 3.2, 1.1, AMBER, 'accepted review state');
    addBody(s, 'Detector classification: Honeycombing\nConfidence: 0.004553093574941158\nObservation count: 1\nModel: DET-FINAL-v1', { x: 9.3, y: 3.3, w: 3.05, h: 1.85, size: 12.5, color: INK });
    addBody(s, 'Extremely-low-confidence, unreviewed machine output used to demonstrate system lineage.', { x: 9.22, y: 5.72, w: 3.18, h: 0.55, size: 11.25, color: RED, bold: true, align: 'center' });
  });

  slide('P17 Deterministic Reporting', 'DEMONSTRATED / VERIFIED REAL HANDOFF', TEAL, 'Point out that the report preserves coordinates, confidence, provenance and review state without inventing severity, repairs or safety conclusions.', (s) => {
    const excerpt = ['Inspection ID: 2026091901', 'Defect ID: P15D-10627c5f-3f84-5c64-ab2d-3e574b6e97ee', 'Class: Honeycombing', 'Confidence: 0.004553093574941158', 'Coordinate frame: map', 'Review Status: UNREVIEWED', 'Model Version: DET-FINAL-v1'].join('\n');
    s.addShape(PptxGenJS.ShapeType.roundRect, { x: 0.75, y: 1.8, w: 7.1, h: 4.8, rectRadius: 0.05, fill: { color: 'F8FAFC' }, line: { color: 'DCE6ED', width: 0.8 } });
    s.addText('DETERMINISTIC REPORT EXCERPT', { x: 1.0, y: 2.08, w: 4.5, h: 0.2, fontFace: FONT, fontSize: 9, bold: true, color: BLUE, charSpace: 1, margin: 0 });
    s.addText(excerpt, { x: 1.0, y: 2.55, w: 6.55, h: 2.8, fontFace: 'Courier New', fontSize: 13.5, color: INK, margin: 0.02, fit: 'shrink' });
    addCard(s, 'Report verification', 'HASH-VERIFIED', 8.35, 1.95, 3.65, 1.2, TEAL, 'deterministic P17 report');
    addBody(s, 'The report preserves persisted and mapped evidence without inferring severity, dimensions, repair action or structural safety.', { x: 8.35, y: 3.7, w: 3.7, h: 1.45, size: 15, color: NAVY, bold: true, align: 'center' });
  });

  slide('P18 Integrated-System Demonstration', 'DEMONSTRATED / VERIFIED PACKAGE', TEAL, 'The first retry validated the same-observation chain but missed the browser capture; the accepted completion package supplies that screenshot. This is integration evidence, not full autonomy.', (s) => {
    const image = path.join(P18_EVIDENCE, 'dashboard', 'dashboard_completion_overview_final.png');
    s.addImage({ path: image, x: 0.48, y: 1.6, w: 8.45, h: 5.45, sizing: { type: 'crop', x: 0.48, y: 1.6, w: 8.45, h: 5.45 } });
    addCard(s, 'Dashboard completion', 'PASS', 9.25, 1.85, 3.2, 1.1, TEAL, 'real browser screenshot');
    addBody(s, 'The first integrated retry validated the same-observation data chain, but its browser capture was absent. The separate dashboard-evidence completion package supplies the accepted real dashboard capture.', { x: 9.22, y: 3.28, w: 3.18, h: 1.95, size: 12.3, color: INK, align: 'center' });
    addBody(s, 'This demonstrates integrated runtime and dashboard evidence; it does not establish full autonomy or production readiness.', { x: 9.22, y: 5.72, w: 3.18, h: 0.55, size: 10.7, color: RED, bold: true, align: 'center' });
  });

  slide('P18 Clean Repeatability', 'DEMONSTRATED / VERIFIED PACKAGE', TEAL, 'Explain that a new execution identity repeated detection-to-report behavior under unchanged source and configuration, including browser evidence.', (s) => {
    const image = path.join(P18_EVIDENCE, 'dashboard', 'clean_repeatability_overview.png');
    s.addImage({ path: image, x: 0.48, y: 1.6, w: 8.45, h: 5.45, sizing: { type: 'crop', x: 0.48, y: 1.6, w: 8.45, h: 5.45 } });
    addCard(s, 'Clean repeatability', 'PASS', 9.25, 1.85, 3.2, 1.1, TEAL, 'accepted execution identity');
    addBody(s, 'The clean repeatability package records a new detection and mapped-defect identity, P16 PASS, browser screenshots PASS and P17 PASS under unchanged source and configuration.', { x: 9.22, y: 3.28, w: 3.18, h: 1.95, size: 12.3, color: INK, align: 'center' });
    addBody(s, 'P19 3D correspondence and LL-DETECTOR evaluation remain pending.', { x: 9.22, y: 5.72, w: 3.18, h: 0.55, size: 10.7, color: RED, bold: true, align: 'center' });
  });

  slide('P19 Localization Evaluation', 'MEASURED / FROZEN METHODOLOGY', BLUE, 'Report all three values with the frozen interval and alignment method. They are measured against simulation ground truth and are not classified PASS or FAIL.', (s) => {
    addCard(s, 'ATE translation RMSE', '0.595396782192 m', 0.72, 2.0, 3.7, 1.35, BLUE, '76 matched samples; interval 3-18 s');
    addCard(s, 'RPE translation RMSE', '0.340604743330 m', 4.82, 2.0, 3.7, 1.35, CYAN, 'delta 1 s +/- 50 ms');
    addCard(s, 'RPE rotation RMSE', '1.707265244063 deg', 8.92, 2.0, 3.7, 1.35, TEAL, '44 pairs');
    addBody(s, 'Ground-truth bracket maximum 50 ms; linear translation interpolation; quaternion SLERP; SE(3) no-scale alignment; scale = 1.', { x: 1.1, y: 4.05, w: 11.0, h: 0.52, size: 17, color: INK, align: 'center' });
    addBody(s, 'Runtime acceptance: PASS. Localization accuracy: MEASURED. No frozen localization-accuracy pass/fail threshold exists.', { x: 1.0, y: 5.15, w: 11.2, h: 0.55, size: 17, color: RED, bold: true, align: 'center' });
  });

  slide('P19 Spatial Validation Status', 'PENDING / FINAL 3D CORRESPONDENCE', AMBER, 'State the implemented and demonstrated spatial chain, the measured localization result, and the one bounded pending item. Do not frame the pending correspondence as integrated-system failure.', (s) => {
    addCard(s, 'Implemented', 'Depth -> camera XYZ', 0.7, 1.8, 2.85, 1.05, BLUE, 'projection and map transform');
    addCard(s, 'Demonstrated', 'Map XYZ -> report', 3.8, 1.8, 2.85, 1.05, TEAL, 'P15 / P16 / P17 / P18');
    addCard(s, 'Measured', 'ATE / RPE', 6.9, 1.8, 2.55, 1.05, CYAN, 'simulation-ground-truth trajectory');
    addCard(s, 'Pending', '3D correspondence', 9.7, 1.8, 2.9, 1.05, AMBER, 'final quantitative validation');
    addBullets(s, ['Depth projection and camera-frame XYZ are implemented', 'Map-frame XYZ, defect aggregation and persistence/reporting are demonstrated', 'Full P18 core-system integration and repeatability are demonstrated', 'Localization ATE/RPE are measured'], { x: 0.82, y: 3.25, w: 6.2, h: 2.35, size: 15 });
    s.addShape(PptxGenJS.ShapeType.roundRect, { x: 7.4, y: 3.25, w: 5.0, h: 2.2, rectRadius: 0.04, fill: { color: 'FFF9EC' }, line: { color: 'E8C878', width: 0.8, dash: 'dash' } });
    addBody(s, 'FINAL RESULT SLOT\nIf accepted: insert actual GT↔mapped-defect correspondence and metric.\n\nFallback: final quantitative simulator-ground-truth correspondence validation for 3D defect-position accuracy remains pending.', { x: 7.7, y: 3.62, w: 4.4, h: 1.45, size: 12.5, color: INK, align: 'center' });
    addBody(s, 'The pending P19 research measurement does not invalidate the demonstrated P18 integrated chain.', { x: 1.15, y: 5.85, w: 11.0, h: 0.35, size: 14, color: RED, bold: true, align: 'center' });
  });

  slide('Workstream 04: Low-Light Robustness', 'SUPPORTED / FROZEN VALIDATION BENCHMARK', BLUE, 'Explain the monotonic RAW degradation, that CLAHE is worse at L0-L3 and offers no general recovery, and that both are effectively collapsed at L4. The LL-DETECTOR slot remains optional.', (s) => {
    const levels = ['L0', 'L1', 'L2', 'L3', 'L4'];
    const raw = [0.3886917344, 0.3796280361, 0.3342489847, 0.1263098877, 0.0031301687];
    const clahe = [0.2657391403, 0.2656420531, 0.2240838264, 0.0746161035, 0.0033883546];
    const chart = { x: 0.95, y: 2.05, w: 6.65, h: 3.25, max: 0.42 };
    [0, 0.1, 0.2, 0.3, 0.4].forEach((tick) => {
      const y = chart.y + chart.h - (tick / chart.max) * chart.h;
      s.addShape(PptxGenJS.ShapeType.line, { x: chart.x, y, w: chart.w, h: 0, line: { color: 'DCE6ED', width: 0.6 } });
      s.addText(tick.toFixed(1), { x: 0.45, y: y - 0.08, w: 0.4, h: 0.16, fontFace: FONT, fontSize: 8, color: MUTED, align: 'right', margin: 0 });
    });
    const point = (index, value) => ({ x: chart.x + 0.55 + index * 1.4, y: chart.y + chart.h - (value / chart.max) * chart.h });
    [[raw, BLUE], [clahe, AMBER]].forEach(([series, color]) => {
      series.forEach((value, index) => {
        const p = point(index, value);
        if (index) {
          const previous = point(index - 1, series[index - 1]);
          s.addShape(PptxGenJS.ShapeType.line, { x: previous.x, y: previous.y, w: p.x - previous.x, h: p.y - previous.y, line: { color, width: 2.2 } });
        }
        s.addShape(PptxGenJS.ShapeType.ellipse, { x: p.x - 0.07, y: p.y - 0.07, w: 0.14, h: 0.14, fill: { color }, line: { color } });
      });
    });
    levels.forEach((label, index) => {
      const p = point(index, 0);
      s.addText(label, { x: p.x - 0.2, y: chart.y + chart.h + 0.18, w: 0.4, h: 0.16, fontFace: FONT, fontSize: 9, color: INK, align: 'center', margin: 0 });
    });
    addBody(s, 'mAP50', { x: 0.28, y: 3.45, w: 0.5, h: 0.2, size: 9, color: MUTED, align: 'center' });
    s.addShape(PptxGenJS.ShapeType.line, { x: 1.3, y: 5.85, w: 0.45, h: 0, line: { color: BLUE, width: 2.2 } });
    addBody(s, 'RAW', { x: 1.82, y: 5.73, w: 0.55, h: 0.2, size: 9, color: INK });
    s.addShape(PptxGenJS.ShapeType.line, { x: 2.55, y: 5.85, w: 0.45, h: 0, line: { color: AMBER, width: 2.2 } });
    addBody(s, 'CLAHE', { x: 3.07, y: 5.73, w: 0.75, h: 0.2, size: 9, color: INK });
    addBody(s, 'RAW vs CLAHE mAP50', { x: 8.05, y: 1.78, w: 4.25, h: 0.28, size: 17, color: NAVY, bold: true, align: 'center' });
    const rows = levels.map((level, i) => `${level}  ${raw[i].toFixed(10)}  ${clahe[i].toFixed(10)}`).join('\n');
    addBody(s, 'Level       RAW             CLAHE\n' + rows, { x: 8.12, y: 2.25, w: 4.15, h: 1.85, size: 10.5, color: INK, align: 'left' });
    s.addShape(PptxGenJS.ShapeType.roundRect, { x: 8.0, y: 4.35, w: 4.35, h: 1.75, rectRadius: 0.04, fill: { color: 'FFF9EC' }, line: { color: 'E8C878', width: 0.8, dash: 'dash' } });
    addBody(s, 'LL-DETECTOR INSERTION SLOT\nState A: add accepted L0-L4 series.\nState B: Learned low-light adaptation was implemented, but final presentation-time model training/evaluation was not completed.', { x: 8.3, y: 4.66, w: 3.75, h: 1.02, size: 10.5, color: INK, align: 'center' });
  });

  slide('Evidence, Provenance and Reproducibility', 'SUPPORTED / HASH-BOUND', TEAL, 'Use this only for Q&A: identify the compact evidence index and explain that accepted artifacts are preserved rather than rewritten.', (s) => {
    addBullets(s, ['Git preservation provenance: canonical P17 preservation state', 'Runtime evidence provenance: recovered P16/P17 ZIP, DB and report', 'P19 localization evidence preservation commit', 'Full hashes retained in the verified P20 evidence package'], { x: 0.85, y: 1.85, w: 5.5, h: 3.5, size: 16 });
    addCard(s, 'P16/P17 package', '29 / 29 PASS', 7.1, 1.9, 4.8, 1.25, TEAL, 'verified package hash inventory');
    addBody(s, 'Concise identifiers\nP17 Git: eb4013fa...bbfe488f\nP16/P17 ZIP: df3f87f0...9f313ec2\nP19 evidence: 4c7bd79a...9a4d78a', { x: 7.25, y: 3.75, w: 4.5, h: 1.45, size: 15, color: INK });
  });

  slide('Limitations and Evidence Boundaries', 'SUPPORTED / CLAIM BOUNDARIES', RED, 'Be direct: detector performance is modest, external transfer is weak, simulation is not field accuracy, and two bounded final inputs remain open.', (s) => {
    addBullets(s, ['Held-out detector mAP remains modest; metrics are not generic accuracy', 'DamSegment zero-shot transfer is weak, especially Crack recall', 'Accepted P16/P17 example is extremely-low-confidence, unreviewed machine output', 'P19 localization is measured, not threshold-classified as accurate', 'P19 3D requires final explicit simulator-ground-truth correspondence', 'RAW and CLAHE collapse at L4; LL-DETECTOR training/evaluation remains pending', 'P18 demonstrates integration and repeatability, not full autonomy or production readiness'], { x: 0.85, y: 1.85, w: 11.4, h: 4.7, size: 16 });
  });

  slide('Application and Commercial Value', 'IMPLEMENTED / APPLICATION VALUE', BLUE, 'Translate the engineering into user value: repeatable evidence capture, traceable review, and modular deployment. These are application benefits, not market validation or production-readiness claims.', (s) => {
    addCard(s, 'Inspect', 'Repeatable capture', 0.75, 1.9, 3.6, 1.25, BLUE, 'multimodal observations');
    addCard(s, 'Review', 'Traceable evidence', 4.85, 1.9, 3.6, 1.25, CYAN, 'human-in-the-loop records');
    addCard(s, 'Report', 'Deterministic output', 8.95, 1.9, 3.6, 1.25, TEAL, 'consistent audit trail');
    addBullets(s, ['Supports bridge, building, tunnel and industrial-asset inspection workflows', 'Modular interfaces allow detector, localization and sensing upgrades', 'Persistent records support comparison over time and accountable review', 'Offline evidence package reduces operational presentation and demo risk'], { x: 1.05, y: 3.75, w: 11.2, h: 2.05, size: 17 });
    addBody(s, 'Application value is demonstrated by the system workflow; commercial deployment readiness is not claimed.', { x: 1.15, y: 6.05, w: 11.0, h: 0.32, size: 13.5, color: RED, bold: true, align: 'center' });
  });

  slide('Current Demonstrated Capability', 'DEMONSTRATED / EVIDENCE-BOUND', TEAL, 'Close on what works today, then name only the two bounded inputs still expected from ARMOURY and MSI.', (s) => {
    addBody(s, 'AegisInspect demonstrates a robotics/computer-vision inspection pipeline combining deep-learning structural-defect detection, depth and 3D projection, localization/map-frame processing, mapped-defect persistence, dashboard review, deterministic reporting and measured localization evaluation.', { x: 1.0, y: 2.0, w: 11.1, h: 1.35, size: 22, color: NAVY, bold: true, align: 'center' });
    addBody(s, 'Next accepted inputs: final P19 3D correspondence; LL-DETECTOR L0-L4 evaluation.', { x: 1.2, y: 4.55, w: 10.8, h: 0.55, size: 18, color: MUTED, align: 'center' });
    addBody(s, 'Implemented is not the same as measured. Pending results remain visible.', { x: 1.0, y: 5.65, w: 11.1, h: 0.35, size: 16, color: RED, bold: true, align: 'center' });
  });

  if (n !== 19) throw new Error(`Expected 19 slides; generated ${n}`);
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });
  await pptx.writeFile({ fileName: OUTPUT });
  const metadata = {
    classification: 'P20 FINALIZATION_READY_FOR_LAST-EVIDENCE_INGESTION',
    title: TITLE,
    generated_at_utc: new Date().toISOString(),
    generation_command: 'node docs/presentation/deck/generate_deck.js',
    pptxgenjs_version: '4.0.1',
    slide_count: n,
    assembly_source: path.relative(ROOT, ASSEMBLY).replaceAll('\\', '/'),
    assembly_source_sha256: sourceHash,
    p16_p17_evidence_package: path.relative(ROOT, EVIDENCE).replaceAll('\\', '/'),
    p16_p17_evidence_inventory_entries: p16p17InventoryEntries,
    p18_evidence_package: path.relative(ROOT, P18_EVIDENCE).replaceAll('\\', '/'),
    p18_evidence_inventory_entries: p18InventoryEntries,
    output_sha256: sha256(OUTPUT),
  };
  fs.writeFileSync(METADATA, `${JSON.stringify(metadata, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(metadata, null, 2));
}

main().catch((error) => { console.error(error.stack || error); process.exit(1); });
