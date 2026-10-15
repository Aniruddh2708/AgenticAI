"""Correct joint denominators from saved predictions; no refit or fresh scoring."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vibefinance.data.historical import load
from vibefinance.evaluation.forecast_followup import simultaneous_coverage


def main():
    source=Path('.runtime/forecast-followup/fresh/report.json')
    report=json.loads(source.read_text())
    corrected=copy.deepcopy(report)
    rows=pd.DataFrame(report['test_rows'])
    rows['as_of']=pd.to_datetime(rows['as_of'])
    securities=[entry['ticker'] for entry in report['data']]
    changes={}
    for point,methods in corrected['test']['intervals'].items():
        for method,metrics in methods.items():
            if method=='frozen_2018_absolute':
                continue
            lower=np.array([row['intervals'][point][method]['lower'] for row in report['test_rows']])
            upper=np.array([row['intervals'][point][method]['upper'] for row in report['test_rows']])
            target=rows.forward_return.to_numpy(float)
            joint=simultaneous_coverage(rows,(target>=lower)&(target<=upper),securities)
            before=metrics['simultaneous_security_coverage']
            metrics['simultaneous_security_coverage']=joint['coverage']
            metrics['simultaneous_coverage_details']=joint
            changes[point+'__'+method]={'previous_available_group_value':before,'corrected':joint}
    corrected['test']['interval']=corrected['test']['intervals']['selected']['security_vol_scaled']
    frozen=json.loads(Path('.runtime/forecast-followup/fresh/selection.json').read_text())
    _,quality=load(frozen['source_manifest'],frozen['data_directory'])
    corrected['data_quality']={'excluded_zero_volume_dates':{
        entry['ticker']:entry['excluded_zero_volume_dates'] for entry in quality},
        'finding':'Four securities contain stale zero-volume vendor rows on 2025-03-18 while ITC traded. Exclusion makes vendor-row calendars security-specific; do not realign the spent test.',
        'independent_exchange_verification':False}
    corrected['analysis_status']='Exploratory correction derived from already inspected saved predictions; no refit, new radii or row changes'
    corrected['period_status']='2024-2025 is spent; this derived report corrects joint denominators only'
    corrected['correction']={'source_report_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'method':'Complete declared five-security origins only; partial groups excluded and counted',
        'changes':changes}
    corrected['limitations'].append('Only ten complete five-security origins remain, across five quarters, for joint coverage; they do not represent all of 2025.')
    target=Path('.runtime/forecast-followup/exploratory-report.json')
    with target.open('x') as handle:
        json.dump(corrected,handle,indent=2,allow_nan=False);handle.write('\n')
    print(json.dumps({'analysis_status':corrected['analysis_status'],
        'marginal_coverage_unchanged':corrected['test']['interval']['coverage'],
        'primary_joint':corrected['test']['interval']['simultaneous_coverage_details'],
        'joint_method':corrected['test']['intervals']['selected']['joint_vol_scaled']['simultaneous_coverage_details']},indent=2))


if __name__=='__main__':
    main()
