from pathlib import Path
import hashlib,json
import numpy as np,yaml
from bfm5.tcz1m_3d import BooleanBracket,certified_event_margin_bounds,event_flags,event_margins,update_transition_bracket
ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config/tcz1m_directional_event_root.yml').read_text())

def test_frozen_target_and_bracket():
 assert CFG['fixed_physics']['target_ray']['id']=='rotated_a'
 assert CFG['fixed_physics']['target_ray']['base_current_A']==[-420.0,520.0]
 assert CFG['fixed_physics']['root_bracket_scale']==[1.35,1.8]
 assert CFG['fixed_physics']['root_tolerance_scale']==0.01
 assert CFG['fixed_physics']['exterior_boundary_scales']==[1.55,1.85,2.15]

def test_parent_is_exact_tcz1l_freeze():
 f=CFG['frozen_parent']; assert f['refit_forbidden'] is True
 assert f['tcz1l_freeze_git_sha']=='91e968378704a8c4204192f4eecab3d5c32b1e2b'
 assert f['tcz1l_actions_run_id']==31155017334

def test_scientific_contract_hash():
 keys=CFG['integrity']['scientific_contract_keys']; payload={k:CFG[k] for k in keys}
 actual=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 assert actual==CFG['integrity']['scientific_contract_sha256']

def test_boolean_bisection_and_margin_bounds():
 sat=BooleanBracket(1.35,1.8,False,True); dark=BooleanBracket(1.35,1.8,True,False)
 sat=update_transition_bracket(sat,1.575,False,rising=True)
 dark=update_transition_bracket(dark,1.575,True,rising=False)
 assert (sat.lo,sat.hi)==(1.575,1.8); assert (dark.lo,dark.hi)==(1.575,1.8)
 lo,hi=certified_event_margin_bounds(BooleanBracket(1.60,1.61,False,True),BooleanBracket(1.70,1.71,True,False))
 assert np.isclose(lo,.09) and np.isclose(hi,.11)

def test_event_flags_use_frozen_thresholds():
 g=CFG['acceptance_gates']; f=event_flags(volume=2e-4,differential_ratio=.9,port=1e-8,power=.05,locality=.05,gates=g)
 assert f=={'saturation':True,'strong_dark':True,'dark_failure':False}
 f2=event_flags(volume=0,differential_ratio=.9,port=1e-8,power=.11,locality=.05,gates=g)
 assert not f2['saturation'] and not f2['strong_dark'] and f2['dark_failure']
 m=event_margins(volume=1e-4,differential_ratio=.97,port=1e-3,power=.1,locality=.1,gates=g)
 assert max(abs(x) for x in m.values())<1e-12

def test_frozen_endpoint_classifications_are_opposite():
 paths=CFG['implicit_shape_estimator']['frozen_reference_paths']; rows=[]
 for key in ('1.35','1.80'):
  d=json.loads((ROOT.parent/paths[key]).read_text())['state']; rows.append((d['saturation_accepted'],d['strong_dark_accepted']))
 assert rows==[(False,True),(True,False)]

def test_workflow_dag_and_matrix():
 w=(ROOT.parent/'.github/workflows/tcz1m-3d-event-root.yml').read_text()
 assert w.count('python -m pytest -q tests/test_tcz1m_3d.py')==1
 assert 'needs: validate-math' in w
 assert 'needs: estimator-validation' in w
 assert w.count('kind: root_boundary')==3
 for b in ('1.55','1.85','2.15'): assert f"boundary: '{b}'" in w
