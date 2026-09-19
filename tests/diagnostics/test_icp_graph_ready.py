"""No ROS runtime or historical wrapper execution is required for these checks."""

import importlib.util
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "icp_graph_ready", ROOT / "scripts/diagnostics/icp_graph_ready.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class GraphGateTests(unittest.TestCase):
    def run_gate(self, snapshots, *, alive=lambda: {"icp": True, "adapter": True}):
        now = [0.0]
        samples = iter(snapshots)
        last = [set()]
        events = []

        def observe():
            last[0] = next(samples, last[0])
            return last[0]

        def sleep(seconds):
            now[0] += seconds

        status = GATE.wait_for_nodes(observe, alive, timeout=1.0, interval=0.25,
                                     clock=lambda: now[0], sleep=sleep, report=events.append)
        return status, now[0], events

    def test_alive_process_precedes_graph_discovery(self):
        status, elapsed, _ = self.run_gate([
            {"/vio_adapter"}, {"/vio_adapter"}, {"/vio_adapter", "/icp_odometry"}])
        self.assertEqual((status, elapsed), (0, 0.5))

    def test_permanent_missing_node_is_bounded_and_not_signal_shaped(self):
        status, elapsed, events = self.run_gate([{"/vio_adapter"}])
        self.assertEqual((status, elapsed), (20, 1.0))
        self.assertEqual(events[-1]["reason"], "GRAPH_READINESS_TIMEOUT")

    def test_probe_name_and_wrong_namespace_do_not_count_as_icp(self):
        self.assertEqual(self.run_gate([{
            "/vio_adapter", "/aegis_icp_graph_readiness_probe", "/other/icp_odometry"}])[0], 20)

    def test_stale_graph_does_not_hide_dead_process(self):
        self.assertEqual(self.run_gate([{"/icp_odometry", "/vio_adapter"}],
                                      alive=lambda: {"icp": False, "adapter": True})[0], 21)

    def test_adapter_is_required(self):
        self.assertEqual(self.run_gate([{"/icp_odometry"}])[0], 20)

    def test_discovery_after_deadline_cannot_pass(self):
        now = [0.0]

        def observe():
            now[0] = 2.0
            return {"/icp_odometry", "/vio_adapter"}

        self.assertEqual(GATE.wait_for_nodes(
            observe, lambda: {"icp": True, "adapter": True}, timeout=1,
            clock=lambda: now[0]), 20)

    def test_explicit_139_survives_successful_exit_trap_and_tee(self):
        # Independently constructed, ROS-free shell fixture. Never sources a wrapper.
        result = subprocess.run(["bash", "--noprofile", "--norc", "-c", r'''
(
    set -eo pipefail
    trap 'printf "CLEANUP_STUB=SUCCESS\n"' EXIT
    names='/aegis/robot_state_publisher
/aegis/sim/motion_control_node
/aegis/sim/sensor_bridge
/vio_adapter'
    printf '%s\n' "$names" | grep -Fxq '/icp_odometry' || exit 139
) | tee /dev/null
statuses=("${PIPESTATUS[@]}")
printf 'BODY=%s TEE=%s\n' "${statuses[0]}" "${statuses[1]}"
'''], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn("CLEANUP_STUB=SUCCESS", result.stdout)
        self.assertIn("BODY=139 TEE=0", result.stdout)
        self.assertNotIn("Segmentation", result.stderr)

    def test_uncollected_background_failure_does_not_set_body_status(self):
        result = subprocess.run(["bash", "--noprofile", "--norc", "-c", r'''
(
    set -eo pipefail
    bash -c 'exit 11' &
    printf 'CLEANUP_STUB=SUCCESS\n'
    printf 'BODY_COMPLETE=YES\n'
) | tee /dev/null
statuses=("${PIPESTATUS[@]}")
printf 'BODY=%s TEE=%s\n' "${statuses[0]}" "${statuses[1]}"
'''], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn("BODY=0 TEE=0", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
