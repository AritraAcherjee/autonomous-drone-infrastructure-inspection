"""Manifest binding, immutable experiment directories and frozen gate."""
import hashlib
import importlib.metadata
import json
from copy import deepcopy
from pathlib import Path
import platform
import subprocess

from .schema import require, validate_manifest


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def object_hash(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def read_json_with_hash(path):
    """Hash exactly the immutable byte snapshot that is parsed and scored."""
    payload = Path(path).read_bytes()
    return json.loads(payload.decode('utf-8')), hashlib.sha256(payload).hexdigest()



def derive_runtime_manifest(portable_path, repo, checkpoint):
    """Bind a committed portable contract to clean current HEAD and checkpoint."""
    from .damsegment_runtime import (
        PORTABLE_KIND,
        RUNTIME_KIND,
    )

    portable_path = Path(portable_path).resolve()
    repo = Path(repo).resolve()
    checkpoint = Path(checkpoint).resolve()

    portable, portable_file_sha = read_json_with_hash(
        portable_path
    )

    validate_manifest(portable)

    require(
        portable.get('manifest_kind') == PORTABLE_KIND,
        'Expected portable scientific contract',
    )
    require(
        portable_path.is_relative_to(repo),
        'Portable contract must be inside evaluation repository',
    )

    dirty = subprocess.check_output(
        ['git', 'status', '--porcelain'],
        cwd=repo,
        text=True,
    )

    require(
        not dirty.strip(),
        'Runtime manifest requires a clean worktree',
    )

    head = subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'],
        cwd=repo,
        text=True,
    ).strip()

    require(
        file_hash(checkpoint)
        == portable['checkpoint_sha256'],
        'Checkpoint hash mismatch before runtime derivation',
    )

    runtime = deepcopy(portable)
    runtime['manifest_kind'] = RUNTIME_KIND
    runtime['evaluation_git_sha'] = head
    runtime['checkpoint_path'] = str(checkpoint)
    runtime['portable_contract_sha256'] = object_hash(
        portable
    )
    runtime['portable_contract_file_sha256'] = (
        portable_file_sha
    )
    runtime['runtime_bindings'] = {
        'portable_contract_path': portable_path
        .relative_to(repo)
        .as_posix(),
        'evaluation_git_sha': head,
        'portable_checkpoint_path': portable[
            'checkpoint_path'
        ],
        'checkpoint_path': str(checkpoint),
    }

    validate_manifest(runtime, scientific=True)

    return runtime


def environment():
    return dict(python=platform.python_version(), platform=platform.platform(),
                packages={d.metadata['Name']: d.version for d in importlib.metadata.distributions() if d.metadata['Name']})


def experiment_name(m):
    validate_manifest(m)
    return m['experiment_id'] + '--' + object_hash(m)[:16]


def reserve(root, m):
    """Atomic mkdir refuses same experiment ID even when manifest changes."""
    validate_manifest(m)
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    directory = root / m['experiment_id']
    directory.mkdir(exist_ok=False)
    (directory / 'manifest.json').write_bytes(canonical(m) + b'\n')
    (directory / 'status.json').write_bytes(canonical({'status': 'INCOMPLETE', 'run_name': experiment_name(m)}) + b'\n')
    return directory


def frozen_gate(m, repo, ontology, protocol):
    """Validate metadata before opening checkpoint or any scoring payload."""
    validate_manifest(m, scientific=True)
    require(object_hash(ontology) == m['ontology_sha256'] and ontology['version'] == m['ontology_version'], 'Ontology binding mismatch')
    require(object_hash(protocol) == m['protocol_sha256'], 'Protocol binding mismatch')
    repo = Path(repo).resolve()
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip()
    require(sha == m['evaluation_git_sha'], 'Evaluation Git SHA mismatch')
    dirty = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=no'], cwd=repo, text=True)
    require(not dirty.strip(), 'Tracked evaluation tree is dirty')
    source_status = subprocess.check_output(['git', 'status', '--porcelain', '--', 'src', 'scripts', 'configs', 'requirements'], cwd=repo, text=True)
    require(not source_status.strip(), 'Evaluation source/configuration tree is dirty')
    if m['dataset']['identity'] == 'GYU-DET':
        version = read_json(repo / 'data/manifests/gyu_det_v3_baseline_v1/VERSION.json')
        require(m['dataset']['source_manifest_sha256'] == version['manifest_sha256']['test'], 'Approved split binding mismatch')
    checkpoint = Path(m['checkpoint_path'])
    require(checkpoint.is_absolute(), 'Checkpoint path must be absolute')
    require(file_hash(checkpoint) == m['checkpoint_sha256'], 'Checkpoint hash mismatch')


def validate_bundle(bundle, m):
    require(bundle.get('manifest_sha256') == object_hash(m), 'Prediction export belongs to a different experiment')
    require(bundle.get('dataset') == m['dataset'], 'Dataset export mismatch')
    require(bundle.get('inference_config') == m['resolved_inference_config'], 'Inference export mismatch')
    require(object_hash({'images': bundle.get('images'), 'regions': bundle.get('regions')}) == m['dataset']['sha256'],
            'Normalized image inventory/region hash mismatch')
