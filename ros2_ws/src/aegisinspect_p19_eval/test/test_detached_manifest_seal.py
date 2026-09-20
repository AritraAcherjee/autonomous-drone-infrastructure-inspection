from pathlib import Path

import pytest

from aegisinspect_p19_eval.contracts import (
    ContractError, sha256_bytes, verify_detached_seal, write_detached_seal,
)


def produce(tmp_path: Path, payload: bytes = b'{"frozen":true}\n'):
    tmp_path.mkdir(parents=True, exist_ok=True)
    manifest = tmp_path / "manifest.json"
    seal = tmp_path / "manifest.sha256"
    manifest.write_bytes(payload)
    digest = write_detached_seal(manifest, seal)
    return manifest, seal, digest


def test_real_producer_writes_bare_lowercase_digest(tmp_path):
    manifest, seal, digest = produce(tmp_path)
    assert seal.read_bytes() == digest.encode("ascii") + b"\n"
    assert digest == sha256_bytes(manifest.read_bytes())


def test_real_producer_output_crosses_real_verifier_boundary(tmp_path):
    manifest, seal, _ = produce(tmp_path)
    verify_detached_seal(manifest.read_bytes(), seal.read_text(encoding="utf-8"))


def test_producer_uses_one_terminal_lf_and_no_filename(tmp_path):
    _, seal, digest = produce(tmp_path)
    assert seal.read_text(encoding="utf-8") == f"{digest}\n"
    assert seal.read_bytes().count(b"\n") == 1


def test_identical_manifest_produces_deterministic_seal(tmp_path):
    first_manifest, first_seal, first_digest = produce(tmp_path / "first")
    second_manifest, second_seal, second_digest = produce(tmp_path / "second")
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert first_digest == second_digest
    assert first_seal.read_bytes() == second_seal.read_bytes()


def test_mutated_manifest_is_rejected(tmp_path):
    manifest, seal, _ = produce(tmp_path)
    manifest.write_bytes(manifest.read_bytes() + b" ")
    with pytest.raises(ContractError, match="changed after sealing"):
        verify_detached_seal(manifest.read_bytes(), seal.read_text(encoding="utf-8"))


def reject(tmp_path, invalid):
    manifest, _, digest = produce(tmp_path)
    with pytest.raises(ContractError):
        verify_detached_seal(manifest.read_bytes(), invalid(digest))


def test_gnu_sha256sum_record_is_rejected(tmp_path):
    reject(tmp_path, lambda d: f"{d}  PRE_START_MANIFEST.normal_host.json\n")


def test_uppercase_digest_is_rejected(tmp_path):
    reject(tmp_path, lambda d: d.upper() + "\n")


def test_non_64_hex_digest_is_rejected(tmp_path):
    reject(tmp_path, lambda d: d[:-1] + "\n")


def test_malformed_text_is_rejected(tmp_path):
    reject(tmp_path, lambda _: "not-a-digest\n")


def test_explanatory_text_is_rejected(tmp_path):
    reject(tmp_path, lambda d: f"sha256: {d}\n")


def test_non_hex_digest_is_rejected(tmp_path):
    reject(tmp_path, lambda _: "g" * 64 + "\n")


def test_wrong_digest_is_rejected(tmp_path):
    reject(tmp_path, lambda _: "0" * 64 + "\n")
