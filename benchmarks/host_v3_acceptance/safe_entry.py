"""Post-run entry: reject this consumed study before credentials or models.

Added after the run; the original frozen runner remains unchanged as evidence.
New generation requires a separately registered study, not deleting a marker.
"""
import json
from pathlib import Path
import runpy

HERE=Path(__file__).parent


def refuse_consumed():
    manifest=HERE/'ARCHIVES.json'
    if manifest.exists() and json.loads(manifest.read_bytes()).get('consumed'):
        raise RuntimeError('CONSUMED_STUDY_NO_REPLAY_REGISTER_A_NEW_STUDY')


if __name__=='__main__':
    refuse_consumed()
    runpy.run_module('benchmarks.host_v3_acceptance.runner',run_name='__main__')
