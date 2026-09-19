"""Fail-closed Gazebo identity for diagnostic harnesses; no runtime mutations.

The caller supplies canonical launch metadata and fresh process snapshots.
Discovery may be pending during its existing bounded readiness window; it
must call require_bound() before permitting any scientific START.
"""

from dataclasses import dataclass


class IdentityBlocker(RuntimeError):
    """The diagnostic harness cannot safely identify/retain its runtime."""


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    ppid: int
    pgid: int
    sid: int
    start_ticks: int
    executable: str
    argv: tuple[str, ...]
    alive: bool = True


def descends_from(process, ancestor_pid, processes):
    """Require a complete, acyclic parent chain in the supplied snapshot."""
    seen = {process.pid}
    parent = process.ppid
    while parent not in seen:
        if parent == ancestor_pid:
            return True
        seen.add(parent)
        if parent not in processes:
            return False
        parent = processes[parent].ppid
    return False


class GazeboRuntimeIdentity:
    """Bind exactly one canonical server and never silently replace its PID."""

    def __init__(self, *, executable, world, launch_pid):
        self.executable = executable
        self.world = world
        self.launch_pid = launch_pid
        self.bound = None
        self.confirmed_observations = 0
        self.ignored_probes = ()

    def observe(self, snapshot):
        by_pid = {p.pid: p for p in snapshot}
        if len(by_pid) != len(snapshot):
            raise IdentityBlocker("PRE_START_GAZEBO_IDENTITY_DUPLICATE_PID_RECORD")
        launch = by_pid.get(self.launch_pid)
        if launch is None or not launch.alive:
            raise IdentityBlocker("GAZEBO_LAUNCH_PARENT_NOT_ALIVE")
        if self.bound is not None:
            current = by_pid.get(self.bound.pid)
            if current is None or not current.alive:
                raise IdentityBlocker("ACTIVE_PROCESS_EXIT_gazebo")
            if current.start_ticks != self.bound.start_ticks:
                raise IdentityBlocker("GAZEBO_BOUND_PID_REUSED")

        candidates = []
        ignored = []
        for process in snapshot:
            if process.executable != self.executable:
                continue
            if "--version" in process.argv:
                ignored.append(process.pid)
                continue
            if not descends_from(process, self.launch_pid, by_pid):
                continue
            canonical = (
                process.alive
                and process.start_ticks > 0
                and process.pgid == launch.pgid
                and process.sid == launch.sid
                and bool(process.argv)
                and process.argv[0] == self.executable
                and "-r" in process.argv
                and "-s" in process.argv
                and "--headless-rendering" in process.argv
                and process.argv.count(self.world) == 1
                and not {"--help", "-h", "--versions"}.intersection(process.argv)
            )
            if not canonical:
                raise IdentityBlocker("PRE_START_GAZEBO_IDENTITY_NONCANONICAL_CHILD")
            candidates.append(process)
        self.ignored_probes = tuple(sorted(ignored))
        if len(candidates) > 1:
            raise IdentityBlocker("PRE_START_GAZEBO_IDENTITY_AMBIGUOUS")
        if not candidates:
            if self.bound is not None:
                raise IdentityBlocker("GAZEBO_BOUND_IDENTITY_LOST")
            return None
        selected = candidates[0]  # Unique after validating the entire snapshot.
        if self.bound is not None and selected != self.bound:
            raise IdentityBlocker("GAZEBO_BOUND_IDENTITY_CHANGED")
        self.bound = selected
        self.confirmed_observations += 1
        return self.bound

    def require_bound(self):
        """Pre-START barrier: identified and observed alive again, without sleeps."""
        if self.bound is None:
            raise IdentityBlocker("PRE_START_GAZEBO_IDENTITY_UNESTABLISHED")
        if self.confirmed_observations < 2:
            raise IdentityBlocker("PRE_START_GAZEBO_LIVENESS_UNCONFIRMED")
        return self.bound
