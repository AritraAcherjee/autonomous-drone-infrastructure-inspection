# Stop-B opt-in session-local map boundary

The accepted 07 local odometry and Aegis adapter remain unchanged. The optional
`aegisinspect_mapping/session_map.launch.py` uses the existing tf2 static publisher
to declare identity `map -> odom`, owned by `/aegis/mapping/session_map_origin`.
Map is coincident with this session's odometry origin and axes. It is metric and
session-local, not a Gazebo world frame, globally drift-corrected localization,
loop closure or global SLAM. Starting a new odometry session creates a new map
session; records must not be silently merged across sessions. Default foundation
launch/contracts remain unchanged; their map relation is still reserved unless
this explicit opt-in extension is launched.

Before launch, inspect actual dynamic and transient-local static TF and require
no existing parent/owner for odom. Launch exactly one instance. The spatial
consumer's `TfOwnership` verifies actual transmitted publisher GIDs: one map
owner and one `/vio_adapter` owner of `odom -> base_link`. Duplicate GIDs, unknown
owners and competing parent edges block mapped output even if node names match.
Endpoint presence alone is not ownership evidence. No distributed exclusivity
against an uncooperative external publisher is claimed; continuous traffic
validation is required for this bounded runtime.

`spatial_projection.camera_to_map` consumes a successful existing 08 ProjectCamera
response and the original observation header. It demands matching positive
observation time and optical frame, queries tf2 only at that exact time, validates
the returned transform stamp/frames, then uses tf2_geometry_msgs to transform
the metric point into `map`. Missing timestamped TF fails closed. There is no
latest/now/Time(0) fallback. Zero observations are rejected at this boundary
because tf2 otherwise interprets zero as latest; the 08 camera-only zero-time
contract is not changed.

Map-coordinate scalars are explicitly converted to built-in `float` because
tf2_geometry_msgs can return NumPy scalars while P15 accepts built-in numbers
only. This changes representation, not coordinates; strict finite validation
is retained. The initial stationary capture exposed this boundary mismatch;
its failure evidence is retained separately from the corrected capture.

The chain is map -> odom -> base_link -> camera_link -> camera_optical_frame.
Camera +X right, +Y down, +Z forward and all 08 depth/intrinsic/ROI semantics are
preserved. No ground-truth subscription, correction or transform is introduced.

P15 already exists in the canonical repository under `src/defect_mapping` and
is reused read-only rather than copied into the localization branch. Its pure
`MappedObservation`, `create_state`, `ingest_observation` and state serialization
form the integration boundary. Same-observation replay must return REPLAY without
incrementing count. Existing `src/integrations/p15_p16_adapter.py` prepares P16 DTOs;
this task does not start persistence, dashboard, reporting or P18.

P15 expects timezone-aware datetime values. For a simulation observation, any
handoff must explicitly identify simulation time and preserve the original ROS
nanoseconds. An epoch-encoded UTC datetime is only a schema representation of
simulation seconds, not measured wall time. Reject timestamps not exactly
representable in the datetime's microseconds; never silently round or replace
the observation time. Original nanoseconds remain authoritative in evidence.
