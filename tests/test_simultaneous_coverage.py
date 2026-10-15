import numpy as np
import pandas as pd
import pytest

from vibefinance.evaluation.forecast_followup import simultaneous_coverage


def test_partial_security_groups_cannot_inflate_joint_coverage():
    rows=pd.DataFrame({'as_of':pd.to_datetime(['2024-01-01']*2+['2024-04-01','2024-07-01']),
        'ticker':['A','B','A','B']})
    score=simultaneous_coverage(rows,np.array([1,0,1,1]),['A','B'])
    assert score['coverage']==0
    assert score['complete_forecast_dates']==1
    assert score['excluded_partial_forecast_dates']==2
    assert score['calendar_quarters']==1


def test_no_complete_universe_means_joint_coverage_unavailable():
    rows=pd.DataFrame({'as_of':pd.to_datetime(['2024-01-01']), 'ticker':['A']})
    score=simultaneous_coverage(rows,[1],['A','B'])
    assert score['coverage'] is None and score['complete_forecast_dates']==0


@pytest.mark.parametrize('defect',['duplicate','unknown','nan'])
def test_invalid_joint_records_are_rejected(defect):
    rows=pd.DataFrame({'as_of':pd.to_datetime(['2024-01-01']*2), 'ticker':['A','B']})
    values=np.array([1.,1.])
    if defect=='duplicate':rows.loc[1,'ticker']='A'
    elif defect=='unknown':rows.loc[1,'ticker']='C'
    else:values[0]=np.nan
    with pytest.raises(ValueError):simultaneous_coverage(rows,values,['A','B'])
