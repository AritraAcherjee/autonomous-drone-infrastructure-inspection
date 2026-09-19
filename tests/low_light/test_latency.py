"""Deterministic fake clocks/detectors; no actual Laptop timing evidence."""

import numpy as np
import pytest

from src.low_light import latency as l
from src.low_light import evaluation as e


def run(strategy=e.STRATEGIES[0], **overrides):
    ticks = iter(range(0, 1000_000_000, 1_000_000))
    calls = []
    def detector(image, **kwargs):
        calls.append(kwargs)
    kwargs = dict(strategy=strategy, images=[np.zeros((8, 8, 3), np.uint8)], detector=detector,
                  iterations=3, clock=lambda: next(ticks))
    kwargs.update(overrides)
    return l.measure(**kwargs), calls


def test_summary_statistics():
    summary = l.summarize([1., 2., 3., 4., 100.])
    assert summary["mean"] == 22
    assert summary["median"] == 3
    assert summary["p95"] == pytest.approx(80.8)
    assert l.summarize([7]) == dict(mean=7, median=7, p95=7)


@pytest.mark.parametrize("samples", [[], [-1], [float("nan")], [float("inf")], [True]])
def test_invalid_samples_rejected(samples):
    with pytest.raises(ValueError):
        l.summarize(samples)


@pytest.mark.parametrize("key,value", [("warmups", 49), ("warmups", 51), ("batch", 2), ("imgsz", 320),
                                      ("batch", True), ("warmups", 50.0), ("iterations", 0)])
def test_frozen_latency_settings(key, value):
    with pytest.raises(ValueError):
        run(**{key: value})


@pytest.mark.parametrize("strategy", e.STRATEGIES)
def test_warmups_and_detector_arguments(strategy):
    report, calls = run(strategy)
    assert len(calls) == 50 + 3
    assert all(c == dict(batch=1, imgsz=640) for c in calls)
    assert report["protocol"]["warmups"] == 50
    assert len(report["samples"]) == 3
    assert report["end_to_end_fps"] == 1000 / report["summary"]["end_to_end_ms"]["mean"]
    assert report["label"] == e.NON_OFFICIAL
    assert report["official"] is False
    if strategy != e.STRATEGIES[1]:
        assert all(s["enhancement_ms"] == 0.0 for s in report["samples"])
    else:
        assert all(s["enhancement_ms"] == 1.0 for s in report["samples"])


def test_cuda_requires_synchronization():
    with pytest.raises(ValueError, match="synchronization"):
        run(device="cuda:0")


@pytest.mark.parametrize("strategy,syncs", [(e.STRATEGIES[0], 13), (e.STRATEGIES[1], 19)])
def test_explicit_cuda_timing_boundaries(strategy, syncs):
    events = []
    ticks = iter(range(0, 1000_000_000, 1_000_000))
    def clock():
        events.append("clock")
        return next(ticks)
    run(strategy, device="cuda:0", synchronize=lambda: events.append("sync"), clock=clock)
    assert events.count("sync") == syncs
    # Every timestamp is immediately preceded by explicit synchronization.
    assert all(events[i-1] == "sync" for i, event in enumerate(events) if event == "clock")


def test_warmups_are_untimed():
    events = []
    ticks = iter(range(0, 1000_000_000, 1_000_000))
    l.measure(strategy=e.STRATEGIES[0], images=[np.zeros((8, 8, 3), np.uint8)], iterations=1,
              detector=lambda *a, **k: events.append("detector"),
              clock=lambda: (events.append("clock"), next(ticks))[1])
    assert events[:50] == ["detector"] * 50
    assert events[50] == "clock"


def test_official_cpu_claim_rejected():
    with pytest.raises(ValueError, match="CUDA"):
        run(host="ARMOURY", hardware={"gpu": "synthetic"})


def test_laptop_cannot_claim_official_by_argument(monkeypatch):
    monkeypatch.setattr(l.platform, "node", lambda: "Laptop1")
    with pytest.raises(ValueError, match="different machine"):
        run(host="ARMOURY", hardware={"gpu": "synthetic"}, device="cuda:0", synchronize=lambda: None)
