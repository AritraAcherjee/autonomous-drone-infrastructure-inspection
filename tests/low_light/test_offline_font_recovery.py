"""Synthetic, no-network checks for the deterministic offline validator-font stage."""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))
from detection.training import provenance as p


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def font_source(tmp_path):
    source = tmp_path/'source'/'Arial.ttf'
    source.parent.mkdir()
    source.write_bytes(b'synthetic-font-bytes')
    return source, digest(b'synthetic-font-bytes')


def destination(root: Path) -> Path:
    return p.runtime_ultralytics_dir(root)/'Arial.ttf'


def test_stages_verified_source_to_effective_ultralytics_path(tmp_path, font_source):
    source, approved = font_source
    result = p.stage_offline_arial_font(tmp_path, source=source, approved_sha256=approved)
    target = destination(tmp_path)
    assert result['destination_path'] == str(target)
    assert result['source_sha256'] == result['destination_sha256'] == approved
    assert result['source_destination_byte_equal'] is True
    assert target.read_bytes() == source.read_bytes()


def test_correct_existing_destination_is_accepted_without_replacement(tmp_path, font_source, monkeypatch):
    source, approved = font_source
    target = destination(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(source.read_bytes())
    before = target.stat().st_mtime_ns
    monkeypatch.setattr(p.shutil, 'copyfile', lambda *a: pytest.fail('correct destination replaced'))
    result = p.stage_offline_arial_font(tmp_path, source=source, approved_sha256=approved)
    assert result['already_staged'] is True
    assert target.stat().st_mtime_ns == before


def test_missing_source_fails_closed(tmp_path):
    with pytest.raises(ValueError, match='source'):
        p.stage_offline_arial_font(tmp_path, source=tmp_path/'missing'/'Arial.ttf', approved_sha256='0'*64)


def test_symlink_source_fails_closed(tmp_path, font_source):
    source, approved = font_source
    linked = tmp_path/'linked'/'Arial.ttf'
    linked.parent.mkdir()
    linked.symlink_to(source)
    with pytest.raises(ValueError, match='non-symlink'):
        p.stage_offline_arial_font(tmp_path, source=linked, approved_sha256=approved)


def test_source_hash_mismatch_fails_closed(tmp_path, font_source):
    source, _ = font_source
    with pytest.raises(ValueError, match='source SHA'):
        p.stage_offline_arial_font(tmp_path, source=source, approved_sha256='0'*64)


def test_different_existing_destination_fails_without_overwrite(tmp_path, font_source):
    source, approved = font_source
    target = destination(tmp_path)
    target.parent.mkdir(parents=True)
    target.write_bytes(b'unexpected-font')
    with pytest.raises(ValueError, match='existing'):
        p.stage_offline_arial_font(tmp_path, source=source, approved_sha256=approved)
    assert target.read_bytes() == b'unexpected-font'


def test_corrupt_copy_fails_closed(tmp_path, font_source, monkeypatch):
    source, approved = font_source
    def corrupt_copy(_source, target):
        Path(target).write_bytes(b'corrupt')
        return str(target)
    monkeypatch.setattr(p.shutil, 'copyfile', corrupt_copy)
    with pytest.raises(ValueError, match='destination SHA'):
        p.stage_offline_arial_font(tmp_path, source=source, approved_sha256=approved)


def test_staging_has_no_download_dependency_and_smoke_guard_remains(tmp_path, font_source):
    source, approved = font_source
    p.stage_offline_arial_font(tmp_path, source=source, approved_sha256=approved)
    helper_source = Path(p.__file__).read_text(encoding='utf-8')
    smoke_source = (ROOT/'scripts/low_light/prepare_desktop_handoff.py').read_text(encoding='utf-8')
    assert 'safe_download' not in helper_source
    assert 'patch(\n                    "ultralytics.utils.downloads.safe_download"' in smoke_source


def test_smoke_stages_font_after_runtime_routing_and_before_ultralytics_import():
    smoke_source = (ROOT/'scripts/low_light/prepare_desktop_handoff.py').read_text(encoding='utf-8')
    routed = smoke_source.index('configure_runtime(repo)')
    staged = smoke_source.index('font_staging = stage_offline_arial_font(repo)')
    ultralytics = smoke_source.index('from ultralytics.utils import callbacks, LOGGER')
    guard = smoke_source.index('"ultralytics.utils.downloads.safe_download"')
    assert routed < staged < ultralytics < guard
