# LIDAR ICP RUNTIME ACCEPTANCE — PASS

The frozen backend sustained finite, nondegenerate, changing native and canonical local odometry through meaningful deterministic P13 motion, while preserving the canonical odometry and actual TF ownership contracts. One scientific START was dispatched; the attempt is consumed. No retry, RESET, tuning, or second experiment occurred.

This is the authorized sustained-runtime/contract acceptance, **not an accuracy qualification**. Raw post-START net displacement was 2.255362245 m for ICP versus 0.450000021 m for GT. This substantial discrepancy is preserved for Laptop 1 / P19 evaluation. No GT correction, alignment, ATE, or RPE headline metric was calculated on MSI. GT was used only to establish that motion occurred and to provide the evaluation export.

`PARAMETER_BRIDGE_VENDOR_TEARDOWN_DEFECT_REPRODUCED=YES`

`KNOWN VENDOR TEARDOWN DEFECT — REPRODUCED`

The bridge SIGSEGV occurred after evidence completion and controlled shutdown. Its core matches the accepted teardown lifecycle signature. The vendor defect was not fixed. All evidence consistency checks passed and relevant residual processes reached zero.

All UTC dates/times below are 2026-09-19 unless stated otherwise. The machine's local date was 2026-09-18, MDT (UTC−06:00).

## A. Harness correction, regression, Git and scope

- Repository: `/mnt/c/Dev/aegisinspect-07-vio`.
- Branch: `07/lidar-icp-fallback`.
- PRE_FIX_SHA: `44a26a7fb0ef0181afac1641f20ca2f664895347`.
- POST_FIX_SHA: `8ff6f6ed842333565ada94b87327dfcd1a1923c2`.
- Commit subject: `test(sim): bind liveness guard to operational Gazebo runtime`.
- Exactly two committed files, 225 insertions:
  - `scripts/diagnostics/gazebo_runtime_identity.py` (112 lines).
  - `tests/diagnostics/test_gazebo_runtime_identity.py` (113 lines).
- Initial pre-fix branch/HEAD/status/parity and whitespace checks were recorded before edits in the command transcript. Cleanliness, parity, whitespace and zero residuals were checked again after commit, immediately before runtime, before START, and after cleanup.
- Normal push: `git push origin HEAD:refs/heads/07/lidar-icp-fallback` succeeded. Live remote SHA is POST_FIX_SHA; local/remote ahead/behind is `0 0`.
- Final `git status --short`: empty. Final `git diff --check`: PASS. Staged set: empty.
- No generated evidence entered the commit. Evidence is intentionally ignored within this evidence directory. No merge or additional post-experiment commit/push occurred.

The old evidence helper assigned the first argv containing `gz-sim-main` to role `gazebo`. It therefore bound historical transient PID 1536260 (`gz-sim-main --version`) and interpreted its normal disappearance as `ACTIVE_PROCESS_EXIT_gazebo`.

The new committed helper excludes `--version`, validates the exact canonical executable, server/run/headless arguments and world path, requires a complete parent chain to this P13 launch and matching PGID/SID, and requires exactly one candidate. It retains PID, start ticks and full identity, checks subsequent liveness, and never silently rebinds. Missing/unconfirmed/ambiguous identity blocks START; a bound runtime's disappearance, death, PID reuse or identity change fails closed. No arbitrary delay was added. The evidence-only `snapshot.py` integrates this helper into the resumed supervisor; the old evidence files were preserved unchanged.

Regression commands, with no runtime launch or START:

```sh
python3 -B tests/diagnostics/test_gazebo_runtime_identity.py
python3 -B tests/diagnostics/test_icp_graph_ready.py
python3 -B -m pytest -p no:cacheprovider -q ros2_ws/src/aegisinspect_localization/test/test_vio_adapter.py -k "valid_native or tf_uses or nonfinite or zero_norm or negative_timestamp or rtab_icp or adapter_source or launch_keeps_sim"
```

Results: **14/14 identity + 8/8 readiness + 37/37 adapter/static = 59/59 PASS**; four unrelated adapter tests deselected. All required identity tests are covered: version probe ignored, real runtime recognized, real exit fails closed, ambiguity blocks, scientific contract unchanged. Additional tests cover missing ancestry, wrong world/group/session, disappearance, PID reuse, argv mutation, and parent cycles.

Offline historical replay ignored probe 1536260 and bound actual historical runtime 1531874 without executing any historical wrapper. Integration import validation confirmed that the resumed supervisor used the corrected snapshot implementation and committed helper.

Nineteen prior frozen source/configuration/binary/evidence inputs were preserved, plus the two new diagnostic files: all 21 initial/final SHA-256 comparisons passed. No P13, world, sensor, bridge mapping, LiDAR, ICP parameter, adapter, ROS domain, topic, frame, extrinsic, TF ownership, GT policy or motion timing changes were made. The three ICP startup warnings about internal convenience normalization of voxel/normal/max-point values were emitted by the unchanged backend; no parameter-setting command or tuning was performed.

Evidence: `raw/harness_tests/`, `raw/existing_readiness_tests/`, `raw/adapter_regressions/`, `raw/stage_scope/`, `raw/harness_commit/`, `raw/harness_push/`, `raw/historical_identity_replay/`, `raw/integration_import_check/`, `raw/harness_integration_diff/`, `raw/conditional_resume_validation/`, `conditional_resume_gate.json`, `source_hashes.json`, `final_source_hashes.json`, `raw/final_integrity/`.

## B. Operational Gazebo identity and unchanged launch provenance

Bound Gazebo PID **1538941**, PPID **1538939**, PGID/SID **1538900**, start ticks **8844503**. It remained the unique bound identity throughout active runtime. There were 41 confirmed observations before START and 70 identity records overall.

Full argv:

```text
/opt/ros/lyrical/opt/gz_sim_vendor/libexec/gz/sim10/gz-sim-main -r -v 3 -s --headless-rendering /mnt/c/Dev/autonomous-drone-infrastructure-inspection/ros2_ws/install/aegisinspect_sim/share/aegisinspect_sim/worlds/inspection_bay.sdf
```

Parent chain: P13 `ros2 launch` 1538900 → shell/Gazebo launcher 1538939 → operational server 1538941. The operational argv contains no `--version`. No version probe was observed in the resumed live snapshots; exclusion was independently demonstrated by synthetic regression and exact historical process-inventory replay, not by claiming an unobserved live probe.

Established environment was sourced in this order:

```sh
source /opt/ros/lyrical/setup.bash
source /mnt/c/Dev/autonomous-drone-infrastructure-inspection/ros2_ws/install/setup.bash
source /mnt/c/Dev/aegisinspect-07-vio/ros2_ws/install/setup.bash
```

Unchanged launch commands, in order:

```sh
ros2 launch aegisinspect_description description.launch.py
ros2 launch aegisinspect_sim sim.launch.py headless:=true
ros2 launch aegisinspect_localization rtabmap_icp_fallback.launch.py
```

Description and simulation came from the accepted canonical workspace; localization came from this repository's installed overlay; `rtabmap_odom` came from `/opt/ros/lyrical`. Complete package prefixes, argv, start times, limits, mappings and copied launch parameter files are retained.

| Role | PID | Parent / group |
|---|---:|---|
| Evidence supervisor/observer | 1538735 | Invocation recorded in `runtime_invocation.json` |
| Description launch | 1538845 | PPID 1538735; PGID/SID 1538845 |
| robot_state_publisher | 1538880 | Description launch |
| P13 launch | 1538900 | PPID 1538735; PGID/SID 1538900 |
| Gazebo launcher | 1538939 | P13 launch |
| Operational Gazebo server | 1538941 | Launcher 1538939 |
| motion_control_node | 1538940 | P13 launch |
| parameter_bridge | 1538942 | P13 launch |
| Localization launch | 1539208 | PPID 1538735; PGID/SID 1539208 |
| icp_odometry | 1539243 | Localization launch |
| vio_adapter | 1539244 | Localization launch |

Evidence: `pre_start_gazebo_identity.json`, `gazebo_identity.jsonl`, `process_inventory.json`, `process_trees.jsonl`, `events.jsonl`, `package_prefixes.json`, `proc_*`, `raw/scientific_runtime/`.

## C. Pre-START guards

`PRE_START_GUARDS_PASS=YES` was saved at **01:50:21.147132 UTC**, before START dispatch. Every recorded guard passed: Git/integrity, conditional resume, initial residual count, operational Gazebo, /clock, LiDAR, ICP, adapter, actual TF, evaluation-only GT capture, START service readiness, and absence of active failures. All safety counters remained zero and the scientific attempt remained unconsumed at this barrier.

- Pre-runtime residual count: **0**. Source hashes unchanged; clean post-fix HEAD and live remote parity confirmed.
- `/clock`: `CLOCK_FIRST_READY_ELAPSED_SEC=7.873351244998048`; exactly one publisher `/aegis/sim/sensor_bridge`; compatible BEST_EFFORT / VOLATILE / KEEP_LAST depth 1. Live initial simulation samples included 0.004, 0.006, 0.007, 0.008, 0.009 and 0.010 seconds. Time continued advancing throughout capture.
- LiDAR: `/aegis/sensors/lidar/points`, `sensor_msgs/msg/PointCloud2`, frame `lidar_link`; x/y/z plus intensity/ring fields; width 360, height 16, 5,760 points, point step 18, row step 6,480, payload 103,680 bytes. Valid advancing stream at 10.0 Hz simulation time. All 567 captured clouds passed the layout/contract checks; no LiDAR disappearance.
- ICP: process 1539243 and `/icp_odometry` alive; committed bounded graph helper PASS, `ICP_FIRST_READY_ELAPSED_SEC=1.7057493589963997`; `use_sim_time=true`, `frame_id=base_link`, `odom_frame_id=odom`, `publish_tf=false`; subscribed to LiDAR; sole expected `/odom` publisher `/icp_odometry`, type `nav_msgs/msg/Odometry`.
- Adapter: `/vio_adapter` process 1539244 alive; input `/odom`; canonical output `/aegis/localization/vio/odom`; unchanged fail-closed validity checks. No native invalid sample or adapter rejection warning was observed.
- Actual TF: 309 pre-START operational transforms, all `/vio_adapter`; zero competing ICP transforms, zero duplicate owners, zero `map -> odom`. Graph endpoint presence was not used as a substitute for transmitted-message ownership.
- A 30.000565-second stationary preflight (01:49:49.052766–01:50:19.053329 UTC) passed before the final barrier. No motion START occurred during it.

Evidence: `pre_start_guard.json`, `clock_ready.json`, `committed_graph_helper.log`, `stationary_preflight.json`, `icp_odometry_parameters.json`, `graph.jsonl`, `gid_owners.json`, `tf.jsonl`, `tf_static.jsonl`.

## D. One-shot START accounting

- START called: **YES, exactly once**.
- Service: `/aegis/sim/motion/start`, type `std_srvs/srv/Trigger`, request `{}`.
- Exact invocation: `self.start_client.call_async(Trigger.Request())` in evidence supervisor `motion.py`.
- Invocation record: **01:50:21.154478 UTC**; latest observed simulation time **35.763 s**.
- Post-dispatch record: **01:50:21.163446 UTC**; invocation count **1**.
- Response: **01:50:21.265514 UTC**, `success=true`, message **`START accepted.`**; latest observed simulation time **35.805 s**.
- `P13_START_CALL_COUNT=1` and `SCIENTIFIC_MOTION_ATTEMPT_CONSUMED=YES` from dispatch onward. A durable exclusive attempt marker prevents supervisor re-dispatch.

Relative-time exports use the latest observed /clock at invocation, not an invented exact plugin epoch. The response clock differs by 42 ms; the plugin adopts its epoch on a subsequent simulation update. Both records are retained for P19. No GT-based temporal adjustment was applied. The approximately 3–18 s primary-window counts below use the recorded 35.763 s reference.

Evidence: `start_invocation.json` (also the exclusive one-shot marker), `start_dispatched.json`, `start_response.json`, `safety.json`, `exports/metadata.json`.

## E. Scientific result, diagnostics and P19 handoff

Scientific evidence completed at **01:50:43.430561 UTC**, through simulation time 56.806 s. The frozen approximately 3 s initialization / 15 s motion / 2 s hold trajectory was unchanged. There were 24 scientific-motion process-liveness snapshots; all required processes remained alive. No active-runtime kernel SIGSEGV, ICP crash, adapter crash, graph instability or LiDAR loss was observed.

| Measurement | Native /odom | Canonical Aegis odometry |
|---|---:|---:|
| Total captured, including pre-START | 427 | 427 |
| Post-START samples | 118 | 118 |
| Primary ~3–18 s samples / valid samples | 76 / 76 | 76 / 76 |
| Post-START valid / finite positions / finite quaternions | 118 / 118 / 118 | 118 / 118 / 118 |
| Zero-norm quaternions / nonfinite samples / invalid samples | 0 / 0 / 0 | 0 / 0 / 0 |
| Simulation timestamp coverage | 35.8–56.4 s | 35.8–56.4 s |
| Coverage duration | 20.6 s | 20.6 s |
| Observed post-START output rate | 5.679612 Hz | 5.679612 Hz |
| Primary valid rate | 5.066667 Hz | 5.066667 Hz |
| Largest gap, also including primary-window edges | 0.4 s | 0.4 s |
| Header / child frames | odom / base_link | odom / base_link |
| Net translation / net rotation | 2.255362245 m / 0.955264° | Identical |
| Maximum translation / orientation excursion | 2.274733810 m / 18.460740° | Identical |
| Finite populated covariance samples / negative diagonal samples | 118 / 0 | 118 / 0 |

Timestamps strictly advanced. Valid sample counts in the fifteen primary one-second bins were `[9,6,5,5,5,5,5,5,5,4,5,5,3,4,5]`. There was no collapse to a few poses, invalid-quaternion dominance or prolonged dropout. Predeclared evidence criteria in `SCOPE.md` were not changed after the run.

Native/canonical starting position was approximately `[0.000019081608, 0.000006810678, -0.000000214917]`, starting quaternion `[-0.000000086131, 0.000000008695, -0.000000003043, 1.0]`. Ending position was `[0.425564140081, -2.214449644089, -0.041867502034]`, ending quaternion `[0.005073986339, -0.003444081427, -0.005646551227, 0.999965254109]`. Full precision is in the raw data and CSVs.

Native/canonical timestamps, positions, orientations, linear/angular twist, and both covariance arrays matched exactly for all 118 post-START pairs: zero missing canonical stamps, zero field mismatches. All 427 captured native samples were valid; observed rejected-native count and adapter rejection-warning count were zero. No unavailable lifetime rejection counter is inferred from that observation. Covariance checks establish finite populated arrays and nonnegative diagonals, not calibrated uncertainty or accuracy.

ICP diagnostics: 427 full and 427 lite OdomInfo messages captured, 118 post-START; all 118 reported `lost=false`, none `lost=true`. Correspondences ranged 1,180–1,986 and ICP inlier ratios 0.205182–0.345993. No registration-failure, rejection, lost-tracking or reinitialization event was observed. The unchanged backend emitted three startup convenience-normalization warnings, preserved verbatim in `sensor_diagnostics_summary.json` and `localization.log`. A separate scan-rejection counter was not available. LiDAR ran at 10 Hz while odometry was approximately 5–6 Hz; this report does not claim every scan produced an odometry update or infer zero skipped scans.

During post-START capture, 210 LiDAR messages spanned 35.8–56.7 s at 10.0 Hz simulation time (9.495138 Hz wall time), maximum gap 0.1 s. /clock strictly advanced through 56.806 s; maximum received clock-sample gap was 0.053 s. No active-runtime sensor contract violation occurred.

Actual TF: `/vio_adapter` exclusively transmitted `odom -> base_link`, publisher GID `010f5c48ac7c61650000000000001503`. Counts were **427 total**, **118 post-START**, **76 primary-window**. Competing ICP count **0**, duplicate operational owner count **0**, and dynamic/static `map -> odom` count **0**. Transmitted translation/quaternion/timestamps matched canonical odometry exactly. Evidence includes callback publisher GIDs and graph GID-to-node attribution, not just endpoints.

GT: **5,670 total**, **2,104 post-START**, **1,500 primary-window** poses; all post-START poses valid. Timestamp coverage **35.77–56.8 s**, duration **21.03 s**, rate **100 Hz**, maximum gap **10 ms**, frame `world`. Start position `[0,0,1.5]`, quaternion `[0,0,0,1]`; end position `[0.450000021465,-0.000000017913,1.499999985284]`, quaternion `[0.000000123844,-0.000000193412,0.000000205280,0.9999999999999526]`. Net displacement **0.450000021 m**, net rotation **0.000035285°**, maximum translation excursion **0.726945853 m**, maximum orientation excursion **18.786661°**. Thus P13 meaningfully translated and rotated, then nearly returned to its initial orientation. The only observed GT subscriber was the evidence observer. GT was never fed into ICP, adapter, TF, filtering or operational localization.

P19 exports: `exports/native.csv`, `exports/canonical.csv`, `exports/gt.csv`, and `exports/metadata.json`. CSVs retain all pre/post samples, nanosecond/decimal timestamps, relative-time reference, XYZ, quaternion, frames and validity. Raw CDR and JSONL retain full covariance/twist. Metadata includes branch/post-fix SHA, all source/config hashes, trajectory identity, times, frozen parameters and contracts. The frozen P19 rules are preserved: GT bracket <=50 ms, linear translation interpolation, quaternion SLERP, SE3 no-scale Umeyama, ATE translation RMSE, RPE translation/rotation, Delta 1 s +/-50 ms, primary approximately 3–18 s. No headline P19 metrics were computed here.

The displacement discrepancy stated at the top remains material and unresolved as an accuracy matter. It is not hidden by this runtime PASS and was not corrected or tuned away.

Evidence: `scientific_analysis.json`, `offline_audit.json`, `sensor_diagnostics_summary.json`, `native.jsonl`, `canonical.jsonl`, `gt.jsonl`, `icp_info*.jsonl`, `raw_cdr/`, `localization.log`, `exports/`.

## F. Controlled shutdown, vendor exception and cleanup

Evidence complete: **01:50:43.430561 UTC**. Controlled shutdown began: **01:50:43.445776 UTC**.

Normal signal sequence, recorded in `shutdown_signals.json`:

1. Localization PGID 1539208: SIGINT at **01:50:43.468443 UTC**.
2. P13 PGID 1538900: SIGINT at **01:50:43.468522 UTC**.
3. Description PGID 1538845: SIGINT at **01:50:43.468599 UTC**.

These were sequential dispatches only microseconds apart, producing concurrent teardown. ROS launch also reported forwarding SIGINT to its children. Shutdown ordering was not changed to avoid the known crash.

| Launch-reported child | PID | Exit status |
|---|---:|---|
| robot_state_publisher | 1538880 | 0 |
| motion_control_node | 1538940 | 0 |
| Gazebo launcher | 1538939 | -2 / SIGINT |
| parameter_bridge | 1538942 | -11 / SIGSEGV |
| icp_odometry | 1539243 | 0 |
| vio_adapter | 1539244 | -2 / SIGINT |

All three top-level launch parents returned 0. The bridge child status is recorded separately; launch-parent success is not interpreted as child success. The Gazebo server was a grandchild; an independent numeric wait status was not exposed by ros2 launch, but the bound PID remained alive until controlled shutdown and was absent afterward. Adapter traceback contains KeyboardInterrupt during the requested shutdown, including repeated SIGINT during rclpy cleanup, not an active-runtime adapter crash. No adapter debugging or fix was performed.

The first bridge kernel SIGSEGV record was **01:50:43.476957 UTC**, after controlled shutdown and the signal sequence. A second middleware worker fault was logged at **01:50:43.478011 UTC**. All three active/pre-shutdown kernel-delta captures were empty.

Core: `cores/core.1538942`, 232,386,560 bytes, SHA-256 `1fb1ac7dd86200a764cec527f18d5185b1e811f50802ac2123a8b0a59b8c9498`. Original `/tmp/aegis-icp-resume-core.w3Ur13/core.1538942` was preserved and matched the copied hash. Executable `/opt/ros/lyrical/lib/ros_gz_bridge/parameter_bridge`, build ID `b4517a78b3479198c60d23022266e5ec167ff7e4`, package `ros-lyrical-ros-gz-bridge 3.0.9-1resolute.20260817.170928`. Active middleware was Fast DDS 3.6.2 / rmw_fastrtps_cpp 9.4.9, established from process mappings and installed package identities.

Reused the previously available isolated GDB executable, without installing/upgrading packages or changing runtime library environment. Full command and complete `thread apply all bt full`, registers, library and mapping transcripts are in `raw/core_gdb/`. Crashing thread 1, LWP 1538981, PC `0x79ce9e94687a` in Fast DDS, was in a DataReader take path. It accessed `0x79ce9f375a50`, inside pre-shutdown `librmw_fastrtps_cpp.so` mapping `0x79ce9f373000–0x79ce9f376000`. The address is absent from the core's actual ELF PT_LOAD ranges; that RMW library is absent from the core mappings. Main LWP 1538942 was in `exit` / dynamic finalization / `tracetools_fini` / `dlclose` while middleware worker threads remained active. This confirms consistency with the already-accepted vendor teardown mechanism, not merely a vendor library name in a stack. Symbols are incomplete; no new broader root-cause claim or fix is made.

`vendor_teardown_signature.json` records 14 passing exception checks: runtime and evidence completion precede shutdown, no active SIGSEGV, matching child/core fault and lifecycle, ICP clean exit, complete uncorrupted evidence, and zero residuals. The defect is therefore nonblocking under this authorization.

Postprocessing note: `raw/core_preservation/command.json` has return code 1 because a trailing `printenv RMW_IMPLEMENTATION` found the variable unset in the offline shell. Core preservation and hash comparison had already succeeded; package collection was completed separately. This is not a runtime failure. Active middleware identity comes from the captured live process mappings.

Final host inventory at **01:51:17.481459 UTC**: **RELEVANT_RESIDUAL_PROCESS_COUNT=0**. Every owned runtime and observer PID was absent, including bridge, Gazebo, P13 launch, motion node, description, robot_state_publisher, ICP, adapter and evidence monitor. No RESET or unrelated cleanup was performed. Process-scoped core settings ended with the runtime; global core pattern remained `core`, and the ordinary shell core limit remained 0.

Evidence: `shutdown_start.json`, `shutdown_signals.json`, `child_statuses.json`, `events.jsonl`, launch logs, `kernel_*`, `raw/shutdown_journal/`, `vendor_teardown_signature.json`, `raw/core_gdb/`, `raw/bridge_packages/`, `raw/fastdds_package_identity/`, `final_host_processes.json`.

## G. Safety and final disposition

```text
P13_START_CALL_COUNT=1
ICP_START_CALL_COUNT=0
RESET_CALL_COUNT=0
SCIENTIFIC_MOTION_ATTEMPT_CONSUMED=YES
RELEVANT_RESIDUAL_PROCESS_COUNT=0
PARAMETER_BRIDGE_VENDOR_TEARDOWN_DEFECT_REPRODUCED=YES
```

Exactly one START; no second START, RESET, retry, tuning, alternate backend experiment, vendor fix or map-frame integration. The held scientific attempt is now consumed regardless of subsequent offline interpretation. Return control to 00; do not rerun this experiment.

## H. Evidence package and integrity

Directory: `/mnt/c/Dev/aegisinspect-07-vio/outputs/evidence/07_lidar_icp_motion_acceptance_resume/`.

- Report: `REPORT.md`.
- Authorization and scope: `SCOPE.md`, `session_tool_io.jsonl` (user instructions, visible tool calls/outputs and progress transcript through sealing).
- Raw command/validation/debugger logs: `raw/`; launch logs: `description.log`, `p13.log`, `localization.log`, `ros_logs/`.
- Machine-readable final classification: `final_decision.json`.
- Source/configuration copies and hashes: `frozen_inputs/`, `source_hashes.json`, `final_source_hashes.json`.
- Raw messages: topic JSONL files and `raw_cdr/*.cdrframes` (little-endian 32-bit length followed by each unmodified serialized ROS message).
- Native export: `exports/native.csv` (427 rows).
- Canonical export: `exports/canonical.csv` (427 rows).
- GT export: `exports/gt.csv` (5,670 rows).
- P19 metadata: `exports/metadata.json`.
- Core and full debugger transcript: `cores/core.1538942`, `raw/core_gdb/stdout.txt`, `raw/core_gdb/stderr.txt`, `raw/core_gdb/command.json`.
- Manifest: `SHA256SUMS.txt`, covering every evidence file including this report, raw logs, exports, frozen inputs, scripts and core, except the manifest itself.

Offline raw-CDR/metadata/export/source/process consistency audit: **26/26 PASS**. Manifest verification: **PASS, 236 evidence artifacts**, using `sha256sum --check --quiet SHA256SUMS.txt`. The manifest and transcript are resealed and reverified after this final report update; the final command result is returned to 00. No artifact is changed after final sealing.
