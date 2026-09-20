# P19 version-matched sensor-batch hooks

These patches are evaluation-only instrumentation for `gz-sim 10.5.0`
(`2d3c7c777cc0a959666e3de497a38dca71b92409`) and `gz-sensors 10.0.2`
(`ba8eecfbba9eb62d665ee70c7e41f0ebb4db0777`). They record the existing
`Manager::RunOnce` boundary and final generated message bytes. They do not
add sensor updates, render calls, scheduling changes, rate changes, or order
changes.

The tracked diffs use zero context so repository whitespace validation remains
strict. Apply or verify them with `git apply --unidiff-zero` against the exact
release commits named above.

Builds must use an isolated prefix. The accepted `/opt/ros` and P18 underlay
must never be overwritten. The hook library must be linked into both patched
projects, and its include directory must be supplied during compilation.
