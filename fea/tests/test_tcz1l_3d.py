from pathlib import Path
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
