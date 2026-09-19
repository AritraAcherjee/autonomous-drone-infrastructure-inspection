"""Synchronized batch-one timing; callable boundaries include preprocessing/postprocessing.

Input is already decoded BGR in host memory. Disk I/O, loading the model and
benchmark generation are excluded. Total includes enhancement and the detector
call (host/device transfer, preprocessing, forward pass and postprocessing).
"""

from __future__ import annotations

import math
import platform
import statistics
import time

from .evaluation import ARMOURY_PHYSICAL_HOSTNAME, NON_OFFICIAL, STRATEGIES, enhance, require_condition

WARMUPS = 50
BATCH = 1
IMGSZ = 640


def latency_contract() -> dict:
    return dict(batch=BATCH, imgsz=IMGSZ, warmups=WARMUPS, raw_enhancement_ms=0.0,
                cuda_synchronization="explicit before and after each measured boundary, including total",
                percentile="linear interpolation at (n-1)*0.95",
                input="decoded BGR host memory; disk I/O/model load excluded",
                detector="preprocess + host/device transfer + forward + postprocess",
                total="enhancement + detector + orchestration/synchronization overhead",
                fps="1000 / mean end_to_end_ms")


def summarize(samples) -> dict:
    values = list(samples)
    if not values or any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("timing samples must be nonempty finite nonnegative milliseconds")
    ordered = sorted(values)
    position = (len(ordered) - 1) * 0.95
    lo, hi = math.floor(position), math.ceil(position)
    return dict(mean=math.fsum(values) / len(values), median=statistics.median(values),
                p95=ordered[lo] + (ordered[hi] - ordered[lo]) * (position - lo))


def measure(*, strategy, images, detector, iterations=100, device="cpu", host="Laptop 1",
            hardware=None, synchronize=None, clock=time.perf_counter_ns, warmups=50, batch=1, imgsz=640) -> dict:
    """Inject callables for synthetic tests; official Desktop uses torch.cuda.synchronize.

The clock returns nanoseconds. CUDA synchronization is mandatory for GPU even
for debug runs. Raw strategies have exactly 0.0 enhancement latency. Exactly
50 complete pipeline calls warm the detector and enhancement without timing.
"""
    require_condition(strategy, "L0")
    if any(type(v) is not int for v in (warmups, batch, imgsz, iterations)) or (warmups, batch, imgsz) != (WARMUPS, BATCH, IMGSZ):
        raise ValueError("latency requires 50 warmups, batch=1, imgsz=640")
    if iterations < 1 or not images:
        raise ValueError("positive iteration count and nonempty images required")
    if device not in ("cpu", "cuda:0") or (device.startswith("cuda") and synchronize is None):
        raise ValueError("GPU timing requires an explicit CUDA synchronization callable")
    if host == "ARMOURY" and (device != "cuda:0" or not hardware):
        raise ValueError("official ARMOURY latency requires CUDA and hardware identity")
    if host == "ARMOURY" and platform.node().casefold() != ARMOURY_PHYSICAL_HOSTNAME:
        raise ValueError("official latency cannot be labelled ARMOURY on a different machine")
    sync = synchronize if device.startswith("cuda") else lambda: None
    for i in range(WARMUPS):
        detector(enhance(images[i % len(images)], strategy), batch=BATCH, imgsz=IMGSZ)
    sync()
    samples = []
    for i in range(iterations):
        image = images[i % len(images)]
        sync()
        total_start = clock()
        if strategy == STRATEGIES[1]:
            sync()
            enhancement_start = clock()
            image = enhance(image, strategy)
            sync()
            enhancement_ms = (clock() - enhancement_start) / 1_000_000
        else:
            enhancement_ms = 0.0
        sync()
        detector_start = clock()
        detector(image, batch=BATCH, imgsz=IMGSZ)
        sync()
        detector_ms = (clock() - detector_start) / 1_000_000
        sync()
        total_ms = (clock() - total_start) / 1_000_000
        if total_ms < enhancement_ms + detector_ms or total_ms <= 0:
            raise ValueError("invalid timing boundaries/clock")
        samples.append(dict(enhancement_ms=enhancement_ms, detector_ms=detector_ms, end_to_end_ms=total_ms))
    stats = {key: summarize(s[key] for s in samples) for key in samples[0]}
    return dict(strategy=strategy, protocol=latency_contract(), device=device, hardware=hardware or {"host": host},
                label="OFFICIAL ARMOURY LATENCY — VALIDATION INPUTS ONLY" if host == "ARMOURY" else NON_OFFICIAL,
                official=host == "ARMOURY", samples=samples, summary=stats,
                end_to_end_fps=1000 / stats["end_to_end_ms"]["mean"], timed_iterations=iterations)
