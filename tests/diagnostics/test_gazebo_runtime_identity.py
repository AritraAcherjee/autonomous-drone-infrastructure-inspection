"""Synthetic process snapshots only: no ROS, Gazebo, START, RESET, or sleeps."""

from dataclasses import replace
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "gazebo_runtime_identity", ROOT / "scripts/diagnostics/gazebo_runtime_identity.py")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Process = MODULE.ProcessIdentity
Blocker = MODULE.IdentityBlocker
EXE = "/opt/ros/lyrical/opt/gz_sim_vendor/libexec/gz/sim10/gz-sim-main"
WORLD = "/canonical/install/aegisinspect_sim/share/aegisinspect_sim/worlds/inspection_bay.sdf"


class GazeboIdentityTests(unittest.TestCase):
    def setUp(self):
        self.launch = Process(100, 90, 100, 100, 10, "/usr/bin/python3", ("ros2", "launch", "aegisinspect_sim", "sim.launch.py"))
        self.shell = Process(101, 100, 100, 100, 11, "/usr/bin/dash", ("sh", "-c", "gz sim"))
        self.runtime = Process(102, 101, 100, 100, 12, EXE,
                               (EXE, "-r", "-v", "3", "-s", "--headless-rendering", WORLD))
        self.probe = Process(103, 101, 100, 100, 13, EXE, (EXE, "--version"))
        self.guard = MODULE.GazeboRuntimeIdentity(executable=EXE, world=WORLD, launch_pid=100)

    def snapshot(self, *children):
        return [self.launch, self.shell, *children]

    def test_1_version_probe_ignored_even_after_exit(self):
        self.assertIsNone(self.guard.observe(self.snapshot(self.probe)))
        self.assertIsNone(self.guard.observe(self.snapshot(replace(self.probe, alive=False))))
        self.assertEqual(self.guard.ignored_probes, (103,))
        self.assertIsNone(self.guard.bound)

    def test_2_real_runtime_recognized_with_parent_argv_and_liveness(self):
        snapshot = self.snapshot(self.probe, self.runtime)
        self.assertEqual(self.guard.observe(snapshot), self.runtime)
        self.assertEqual(self.guard.observe(list(reversed(snapshot))), self.runtime)
        self.assertEqual(self.guard.require_bound(), self.runtime)

    def test_3_bound_runtime_exit_fails_closed(self):
        self.guard.observe(self.snapshot(self.runtime))
        with self.assertRaisesRegex(Blocker, "ACTIVE_PROCESS_EXIT_gazebo"):
            self.guard.observe(self.snapshot(replace(self.runtime, alive=False)))

    def test_4_ambiguous_runtimes_fail_closed(self):
        second = replace(self.runtime, pid=104, start_ticks=14)
        with self.assertRaisesRegex(Blocker, "PRE_START_GAZEBO_IDENTITY_AMBIGUOUS"):
            self.guard.observe(self.snapshot(self.runtime, second))
        self.assertIsNone(self.guard.bound)

    def test_5_scientific_contract_byte_identical_to_accepted_baseline(self):
        # Freeze the authorized baseline; the separate run also hashes external P13 files.
        hashes = {
            "scripts/diagnostics/icp_graph_ready.py": "4888509d003208e4ee44d210d5800856ba5dd447ccd5d6ea703dcdd037aa8899",
            "ros2_ws/src/aegisinspect_localization/launch/rtabmap_icp_fallback.launch.py": "f41c7fbfc78bee06e94ef16b5f143ec4278d2104fd9591b5719d11f91470ef0e",
            "ros2_ws/src/aegisinspect_localization/scripts/vio_adapter_node.py": "ebdd5a42ce8bd7f748b821d86d70c3c984a8f02213a792e9b0a6cf65a121103d",
            "ros2_ws/src/aegisinspect_localization/aegisinspect_localization/vio_adapter.py": "dd9459c77e71b477d6e85d1f3d649507da335a00470b565afe7c4d40b643558b",
        }
        for name, expected in hashes.items():
            with self.subTest(path=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected)

    def test_missing_runtime_is_explicit_pre_start_blocker(self):
        self.guard.observe(self.snapshot(self.probe))
        with self.assertRaisesRegex(Blocker, "PRE_START_GAZEBO_IDENTITY_UNESTABLISHED"):
            self.guard.require_bound()

    def test_one_observation_cannot_clear_pre_start_barrier(self):
        self.guard.observe(self.snapshot(self.runtime))
        with self.assertRaisesRegex(Blocker, "PRE_START_GAZEBO_LIVENESS_UNCONFIRMED"):
            self.guard.require_bound()

    def test_unrelated_server_is_not_selected(self):
        self.assertIsNone(self.guard.observe(self.snapshot(replace(self.runtime, ppid=999))))

    def test_wrong_world_fails_closed(self):
        wrong = replace(self.runtime, argv=self.runtime.argv[:-1] + ("/other/world.sdf",))
        with self.assertRaisesRegex(Blocker, "PRE_START_GAZEBO_IDENTITY_NONCANONICAL_CHILD"):
            self.guard.observe(self.snapshot(wrong))

    def test_wrong_process_group_or_session_fails_closed(self):
        for field in ("pgid", "sid"):
            with self.subTest(field=field), self.assertRaises(Blocker):
                self.guard.observe(self.snapshot(replace(self.runtime, **{field: 999})))

    def test_disappeared_pid_cannot_rebind_to_new_server(self):
        self.guard.observe(self.snapshot(self.runtime))
        with self.assertRaisesRegex(Blocker, "ACTIVE_PROCESS_EXIT_gazebo"):
            self.guard.observe(self.snapshot(replace(self.runtime, pid=104)))

    def test_pid_reuse_fails_closed(self):
        self.guard.observe(self.snapshot(self.runtime))
        with self.assertRaisesRegex(Blocker, "GAZEBO_BOUND_PID_REUSED"):
            self.guard.observe(self.snapshot(replace(self.runtime, start_ticks=999)))

    def test_argv_change_after_binding_fails_closed(self):
        self.guard.observe(self.snapshot(self.runtime))
        with self.assertRaisesRegex(Blocker, "GAZEBO_BOUND_IDENTITY_CHANGED"):
            self.guard.observe(self.snapshot(replace(self.runtime, argv=self.runtime.argv + ("--extra",))))

    def test_parent_cycle_does_not_establish_ancestry(self):
        self.assertIsNone(self.guard.observe([self.launch, replace(self.shell, ppid=102), self.runtime]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
