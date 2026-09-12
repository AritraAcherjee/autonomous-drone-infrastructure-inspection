# Installed Ultralytics reader and raw-write audit

Inspected the installed **Ultralytics 8.4.145** source before any full raw reader
pass. Paths below are relative to `.venv-detection/Lib/site-packages/ultralytics/`.
Source digests are retained in `ultralytics_source_audit.json`.

| Behavior | Installed implementation | Consequence |
|---|---|---|
| Label cache location | `data/dataset.py`, `YOLODataset.get_labels`, line 283 | `Path(label_files[0]).parent.with_suffix('.cache')`: source split's `labels.cache`, under raw for this dataset |
| Label cache writes | `YOLODataset._load_or_scan_cache`, `cache_labels`; `data/utils.py`, `save_dataset_cache_file` | Missing/stale cache triggers verification and cache serialization regardless of image `cache=False` |
| JPEG repair | `data/utils.py`, `verify_image_label` calls `check_image`; line 238 | Missing JPEG end marker can trigger `ImageOps.exif_transpose(...).save(im_file, ...)`, rewriting the source |
| Disk image caching | `data/base.py`, `BaseDataset.__init__`, line 153; `cache_images_to_disk`, line 316 | Source-adjacent `Path(f).with_suffix('.npy')`; disk mode uses NumPy save |
| `cache=False` | `BaseDataset.__init__`, lines 154-163 | Disables preloading image caches, not label verification/cache creation |
| Existing `.npy` files | `BaseDataset.load_image`, lines 247-264 | Still reads adjacent caches even with `cache=False`; may unlink stale/corrupt `.npy` files |
| Runtime JPEG reader | `data/base.py`, `BaseDataset.load_image`; `utils/patches.py`, `imread` | `np.fromfile` then `cv2.imdecode`, `cv2.IMREAD_COLOR` for three-channel detection; BGR output |

The decoder's Pillow fallback is restricted to AVIF/HEIC/HEIF suffixes. The
approved JPEG/MPO source files follow OpenCV's JPEG decode path. MPO auxiliary
frames are not a substitute for the primary image used by this detector reader.

The gate never constructs `YOLODataset`, calls `check_image` or
`verify_image_label`, or executes model code. It calls the exact imported
`ultralytics.data.base.imread` function and asserts that it is the reviewed
`ultralytics.utils.patches.imread`. Source images are decoded without resizing
or augmentation, preserving native resolution for reader evidence.

The minimal metadata consumer resolves the existing canonical YAML relative to
its directory and approved list entries relative to their list files. It matches
every association to the approved manifests, checks source image hashes, rejects
duplicates/excluded identities, and reuses the existing read-only M1 label
validator. Numeric IDs and rows are never remapped, deduplicated or clipped.
M1 corner overshoots <=1e-6 are retained as warnings.

Image cache policy is **False**. This gate creates **no label cache**; its
metadata and CSV evidence provide the read-only loader layer, so a stock cache
redirection subclass is unnecessary here. Settings and any permitted mutable
cache location are guarded under
`outputs/cache/ultralytics/gyu_det_v3_baseline_v1/`. Neither existing raw `.npy`
files nor raw label `.cache` files are loaded by the gate.

Output guards use resolved paths plus Windows `normcase`/`commonpath`, handling
case, separators, traversal and existing symlink/junction targets. A Python audit
guard also refuses audited raw write/delete/rename operations during the gate.
It is defense in depth, not an OS sandbox for arbitrary native code. The inspected
decoder and parser are read-only; pre/post inventories and SHA-256 independently
check their effects. Run with no concurrent writers or changes to junctions.

The pre/post snapshots stat every raw file and hash every included image and
label. Archive contents are not revalidated or rehashed. No M1 artifact is
regenerated. The authoritative MPO warning source is
`outputs/validation/gyu_det_v3/full_validation/image_validation.csv`, selecting
the `auxiliary_frame_decode_failure` issue and intersecting by exact approved
image path. Each intersection image receives an additional decode with the same
runtime reader and a separate evidence CSV row.

This is a reader gate, not an augmentation, DataLoader-worker or trainer test.
A future training loader must preserve this read-only policy and control stock
verification/cache paths; calling stock YOLODataset directly on raw remains
unsafe. No permission to train or download weights follows from this report.

## Observed reader geometry and labels

All 10,398 images decode successfully with 92 distinct runtime dimensions.
Within these same 10,398 records, the stored M1 dimensions have 82 distinct
resolutions; the prior EDA's 85 concerns a different population. For 648 images,
the runtime width and height are swapped relative to stored M1 dimensions.
Those images have EXIF orientation 6 (351 images) or 8 (297 images), and every
observed difference is an axis swap. See `reader_geometry_notes.json` and
`reader_geometry_differences.csv` for the complete read-only comparison.
No image was rewritten. This reader gate checks label associations and numeric
rows; it does not certify spatial box alignment after orientation handling.
Keep this measured backend behavior visible when integrating the future trainer.

The read-only label parser retained 1,803 `derived_box_outside_frame` warnings
within the approved <=1e-6 rounding tolerance. There were no label failures.
