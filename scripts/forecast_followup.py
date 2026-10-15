"""Freeze revised methodology, then evaluate a fresh period exactly once."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vibefinance.data.historical import load, read_manifest
from vibefinance.evaluation.forecast import fingerprint
from vibefinance.evaluation.forecast_followup import FollowupProtocol, evaluate_followup, prepare_followup


EVALUATION_LEDGER=Path('.runtime/forecast-followup/evaluation-2024-2025-started.json')


def implementation_hashes():
    root=Path(__file__).resolve().parent.parent
    paths=("vibefinance/data/historical.py","vibefinance/evaluation/forecast.py",
           "vibefinance/evaluation/forecast_selection.py","vibefinance/evaluation/uncertainty.py",
           "vibefinance/evaluation/forecast_followup.py","scripts/forecast_followup.py")
    return {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in paths}


def current_runtime():
    import numpy as np
    import pandas as pd
    import pyarrow
    return {"python":sys.version.split()[0],"numpy":np.__version__,"pandas":pd.__version__,"pyarrow":pyarrow.__version__}


def assert_originals(hashes):
    for name,expected in hashes.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=expected:
            raise ValueError("Original frozen experiment artifact changed")


def write_new(path,value):
    with Path(path).open("x") as handle:
        json.dump(value,handle,indent=2,allow_nan=False)
        handle.write("\n")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("prepare","test"))
    parser.add_argument("--manifest",default="data/forecast_followup_manifest.json")
    parser.add_argument("--protocol",default="data/forecast_followup_protocol.json")
    parser.add_argument("--data-dir",default=".runtime/forecast/data")
    parser.add_argument("--run-dir",default=".runtime/forecast-followup/fresh")
    args=parser.parse_args()
    directory=Path(args.run_dir);directory.mkdir(parents=True,exist_ok=True)
    if args.stage=="prepare":
        if (directory/"selection.json").exists() or (directory/"report.json").exists():
            raise ValueError("Revised experiment already frozen/spent; preserve the run")
        manifest=read_manifest(args.manifest)
        frames,metadata=load(manifest,args.data_dir)
        legacy_path=Path('.runtime/forecast/selection.json')
        legacy=json.loads(legacy_path.read_text())
        hashes=json.loads(Path('.runtime/forecast-followup/original-artifact-hashes.json').read_text())
        assert_originals(hashes)
        frozen=prepare_followup(frames,metadata,legacy,FollowupProtocol(**json.loads(Path(args.protocol).read_text())))
        frozen.update(source_manifest=manifest,data_directory=str(Path(args.data_dir).resolve()),
            original_artifact_hashes=hashes,original_selection_id=legacy['selection_id'],
            created_at_utc=datetime.now(timezone.utc).isoformat(),implementation_sha256=implementation_hashes(),
            runtime=current_runtime())
        frozen['selection_id']=fingerprint(frozen)
        write_new(directory/'selection.json',frozen)
        print(json.dumps({"selection_id":frozen['selection_id'],"selection":frozen['selection'],
            "calibration_rows":frozen['calibration']['sample_size'],
            "calibration_shared_dates":frozen['calibration']['shared_dates'],
            "scale_floor":frozen['calibration']['scale_floor'],"period_status":frozen['period_status']},indent=2))
        return
    if (directory/'report.json').exists():
        raise ValueError("Fresh period already reported and now spent; no repeated test tuning")
    if EVALUATION_LEDGER.exists():
        raise ValueError("2024-2025 evaluation already started/spent; another run directory cannot restore independence")
    frozen=json.loads((directory/'selection.json').read_text())
    identity=frozen.pop('selection_id')
    if (fingerprint(frozen)!=identity or implementation_hashes()!=frozen['implementation_sha256']
            or current_runtime()!=frozen['runtime']):
        raise ValueError("Frozen methodology or implementation changed")
    assert_originals(frozen['original_artifact_hashes'])
    frames,_=load(frozen['source_manifest'],frozen['data_directory'])
    # Persist before consuming fresh labels, including on interrupted/failed runs.
    # This is shared across run directories; never erase it to call a retry fresh.
    EVALUATION_LEDGER.parent.mkdir(parents=True,exist_ok=True)
    write_new(EVALUATION_LEDGER,{"selection_id":identity,"period":[frozen['protocol']['test_start'],frozen['protocol']['test_end']],
        "status":"evaluation started; period is now spent even if interrupted",
        "started_at_utc":datetime.now(timezone.utc).isoformat(),"run_directory":str(directory.resolve())})
    report=evaluate_followup(frames,frozen)
    report.update(selection_id=identity,original_selection_id=frozen['original_selection_id'],
        original_artifact_hashes=frozen['original_artifact_hashes'],runtime=frozen['runtime'],
        evaluated_at_utc=datetime.now(timezone.utc).isoformat())
    write_new(directory/'report.json',report)
    print(json.dumps({"selection":report['selection'],"test_count":report['test']['sample_size'],
        "metrics":report['test']['metrics'],"primary_interval":report['test']['interval'],
        "period_status":report['period_status']},indent=2))


if __name__=='__main__':
    main()
