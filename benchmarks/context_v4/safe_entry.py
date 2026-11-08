"""Post-run guard, added after generation; no consumed-freeze replay."""
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
    runpy.run_module('benchmarks.context_v4.runner',run_name='__main__')
