"""Bounded, exact-name ICP/adapter discovery gate; never starts or resets motion."""

import argparse
import json
from pathlib import Path
import time


def wait_for_nodes(observe, alive, *, timeout=15.0, interval=0.5,
                   clock=time.monotonic, sleep=time.sleep, report=lambda event: None):
    """Require both processes alive and both exact names before the deadline."""
    if timeout <= 0 or interval <= 0:
        raise ValueError("timeout and interval must be positive")
    start = clock()
    expected = {"/icp_odometry", "/vio_adapter"}
    while True:
        live = alive()
        if not all(live.values()) or not live:
            report({"reason": "PROCESS_EXITED", "alive": live})
            return 21
        names = set(observe())
        elapsed = clock() - start
        live = alive()
        report({"elapsed_seconds": elapsed, "nodes": sorted(names), "alive": live})
        if not all(live.values()) or not live:
            return 21
        if elapsed <= timeout and expected.issubset(names):
            return 0
        if elapsed >= timeout:
            report({"reason": "GRAPH_READINESS_TIMEOUT", "missing": sorted(expected - names)})
            return 20
        sleep(min(interval, timeout - elapsed))


def process_alive(pid):
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
        return stat.rsplit(")", 1)[1].split()[0] not in {"Z", "X"}
    except (FileNotFoundError, ProcessLookupError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--icp-pid", required=True, type=int)
    parser.add_argument("--adapter-pid", required=True, type=int)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    if min(args.icp_pid, args.adapter_pid) <= 0 or args.timeout <= 0:
        parser.error("PIDs and timeout must be positive")
    import rclpy
    from rclpy.node import Node

    rclpy.init(args=[])
    node = Node("aegis_localization_readiness")
    try:
        def observe():
            rclpy.spin_once(node, timeout_sec=0.05)
            return {f"{namespace.rstrip('/')}/{name}"
                    for name, namespace in node.get_node_names_and_namespaces()}

        status = wait_for_nodes(
            observe,
            lambda: {"icp": process_alive(args.icp_pid),
                     "adapter": process_alive(args.adapter_pid)},
            timeout=args.timeout,
            report=lambda event: print(json.dumps(event), flush=True),
        )
        print(f"ICP_GRAPH_READINESS_EXIT_CODE={status}", flush=True)
        return status
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
