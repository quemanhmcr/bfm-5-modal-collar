from pathlib import Path
import hashlib
import json
import yaml
import numpy as np
from bfm5.tcz1l_3d import first_true_scale, sampled_event_order, strict_overlap_flags, relative

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config/tcz1l_3d_saturation_critical_surface.yml').read_text())

def test_frozen_rays_and_scales():
    ladder=CFG['critical_surface_ladder']
    assert [x['id'] for x in ladder['rays']]==['high_skew','rotated_a','rotated_b']
    assert ladder['scale_factors']==[1.0,1.35,1.8,2.4,3.2]
    assert ladder['sentinel_scale']==3.2

def test_no_refit_and_parent_hashes():
    f=CFG['frozen_parent']
    assert f['refit_forbidden'] is True
    assert f['tcz1kq_freeze_git_sha']=='9d344195a5d459f850ce6d850620cbd565fa0395'
    assert f['tcz1kq_qualification_sha256']=='eb0e50b825f6700d4ff886d91655cf48cef9e818d6d832a6f0e995d84312439f'

def test_event_order_logic():
    scales=[1,1.35,1.8,2.4,3.2]
    r=sampled_event_order(scales,[False,False,True,True,True],[True,True,True,True,False],[False,False,True,True,False])
    assert r['first_saturated_scale']==1.8
    assert r['first_strong_dark_failure_scale']==3.2
    assert r['strict_local_overlap_certified']
    assert r['saturation_precedes_sampled_dark_failure']

def test_strict_guard():
    g=CFG['acceptance_gates']['strict_overlap_guard']
    good=strict_overlap_flags(volume_above_1p62=1e-3,differential_ratio=.90,port=1e-7,power=.01,locality=.01,gates=g)
    assert good['accepted']
    bad=strict_overlap_flags(volume_above_1p62=1e-5,differential_ratio=.90,port=1e-7,power=.01,locality=.01,gates=g)
    assert not bad['accepted']

def test_relative():
    assert relative(np.eye(2),np.eye(2))==0.0


def test_execution_r2_cannot_refit_scientific_contract():
    e=CFG['execution_efficiency']
    keys=['frozen_parent','fixed_model','critical_surface_ladder','saturation_targeted_uncertainty','topology_sentinels','numerical_sentinel','acceptance_gates','decision_rules','mathematical_claim_boundary']
    payload={k:CFG[k] for k in keys}
    actual=hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    assert actual==e['scientific_contract_sha256']=='5d5a24a45941344f7a2fdbf9288ee43ebdb50488479613ca4c677fa817b062b8'
    assert e['physical_model_rays_material_uncertainty_and_acceptance_gates_unchanged'] is True
    assert e['baseline_strategy']=='direct_Newton_from_linear_initializer_then_fallback_homotopy_only_on_failure'
    assert e['topology_reuses_primary_gap_states_via_exact_Newton_Hessian'] is True


def test_actions_matrix_fits_runner_concurrency_and_uses_core_runtime():
    workflow=(ROOT.parent/'.github/workflows/tcz1l-3d-saturation.yml').read_text()
    assert workflow.count('- {label:')==20
    assert 'max-parallel: 20' in workflow
    assert 'topology-high_skew' not in workflow and 'topology-rotated_a' not in workflow
    assert 'requirements-file: fea/requirements-tcz1l-core.txt' in workflow
    assert "install-getdp: 'false'" in workflow


def test_minimal_runtime_lock_is_exact():
    req=(ROOT/'requirements-tcz1l-core.txt').read_text().splitlines()
    assert req==['numpy==2.5.1','scipy==1.18.0','PyYAML==6.0.3','ngsolve==6.2.2606']
