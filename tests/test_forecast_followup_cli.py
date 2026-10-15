"""The test period becomes spent before scoring, including failed runs."""
import json
import sys

import pytest

from scripts import forecast_followup as cli
from vibefinance.evaluation.forecast import fingerprint


def frozen_run(tmp_path, name="fresh"):
    directory=tmp_path/name
    directory.mkdir()
    frozen={"implementation_sha256":cli.implementation_hashes(),"runtime":cli.current_runtime(),
        "original_artifact_hashes":{},"original_selection_id":"unit-fixture",
        "source_manifest":{},"data_directory":"unit-fixture",
        "protocol":{"test_start":"2024-01-01","test_end":"2025-12-31"}}
    frozen["selection_id"]=fingerprint(frozen)
    (directory/"selection.json").write_text(json.dumps(frozen))
    return directory


def test_evaluation_failure_retains_spent_period_ledger_and_blocks_another_directory(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    directory=frozen_run(tmp_path)
    monkeypatch.setattr(sys,"argv",["forecast_followup","test","--run-dir",str(directory)])
    monkeypatch.setattr(cli,"load",lambda *_:({},[]))
    calls=[]
    def fail_after_start(*_):
        assert cli.EVALUATION_LEDGER.exists()
        calls.append(1)
        raise RuntimeError("Injected scoring interruption")
    monkeypatch.setattr(cli,"evaluate_followup",fail_after_start)
    with pytest.raises(RuntimeError,match="interruption"):
        cli.main()
    assert len(calls)==1 and not (directory/"report.json").exists()
    ledger=json.loads(cli.EVALUATION_LEDGER.read_text())
    assert "spent" in ledger["status"]
    other=frozen_run(tmp_path,"other")
    monkeypatch.setattr(sys,"argv",["forecast_followup","test","--run-dir",str(other)])
    with pytest.raises(ValueError,match="another run directory"):
        cli.main()
    assert len(calls)==1


@pytest.mark.parametrize("change",["implementation","runtime","selection"])
def test_changed_freeze_is_rejected_before_any_scoring_or_spent_ledger(tmp_path,monkeypatch,change):
    monkeypatch.chdir(tmp_path)
    directory=frozen_run(tmp_path)
    path=directory/"selection.json"
    frozen=json.loads(path.read_text())
    if change=="implementation":frozen["implementation_sha256"]={"different":"implementation"}
    elif change=="runtime":frozen["runtime"]={"different":"runtime"}
    else:frozen["data_directory"]="changed snapshot"
    path.write_text(json.dumps(frozen))
    monkeypatch.setattr(sys,"argv",["forecast_followup","test","--run-dir",str(directory)])
    monkeypatch.setattr(cli,"evaluate_followup",lambda *_:pytest.fail("Scoring must not start"))
    with pytest.raises(ValueError,match="Frozen"):
        cli.main()
    assert not cli.EVALUATION_LEDGER.exists()
