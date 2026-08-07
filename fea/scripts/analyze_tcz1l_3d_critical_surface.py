from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any
import numpy as np, yaml
from bfm5.tcz1l_3d import relative, sampled_event_order, strict_overlap_flags

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config/tcz1l_3d_saturation_critical_surface.yml').read_text())
SHA=hashlib.sha256(json.dumps(CFG,sort_keys=True,separators=(',',':')).encode()).hexdigest()
G=CFG['acceptance_gates']; SCALES=[float(x) for x in CFG['critical_surface_ladder']['scale_factors']]
RAYS=[x['id'] for x in CFG['critical_surface_ladder']['rays']]


def load_shards(root:Path):
    rows=[]
    for p in root.rglob('shard_summary.json'):
        d=json.loads(p.read_text()); rows.append((p,d))
    return rows


def state_numerical(state:dict[str,Any])->tuple[bool,dict[str,bool]]:
    n=state['numerical']; g=G['numerical']
    checks={
      'stationarity':float(n['max_stationarity_residual'])<=float(g['maximum_stationarity_residual']),
      'gauge':float(n['max_gauge_fraction'])<=float(g['maximum_gauge_fraction']),
      'power_pairing':float(n['max_power_pairing_residual'])<=float(g['maximum_power_pairing_residual']),
      'reciprocity':float(n['exact_tangent_reciprocity_residual'])<=float(g['maximum_reciprocity_residual']),
      'positive_Ld':float(n['exact_tangent_minimum_eigenvalue_H'])>0.0,
      'Ld_condition':float(n['exact_tangent_condition'])<=float(g['maximum_differential_inductance_condition']),
      'linearized_residual':float(n['exact_tangent_max_linearized_residual'])<=float(g['maximum_exact_tangent_linearized_residual']),
    }
    return all(checks.values()),checks


def state_physical(state:dict[str,Any])->dict[str,Any]:
    d=state['dark']; strong_g=G['strong_dark']; sat_g=G['saturation']
    strong={
      'port':float(d['port_leakage'])<=float(strong_g['maximum_port_leakage']),
      'power':float(d['power_ratio'])<=float(strong_g['maximum_power_ratio']),
      'locality':float(d['route_locality_residual'])<=float(strong_g['maximum_route_locality_residual']),
    }
    sat={
      'field_volume':float(state['saturation_volume_fraction_above_1p62T'])>=float(sat_g['minimum_any_core_volume_fraction_above_1p62T']),
      'differential_drop':float(state['directional_differential_to_secant_ratio'])<=float(sat_g['maximum_directional_differential_to_secant_ratio']),
    }
    strict=strict_overlap_flags(volume_above_1p62=float(state['saturation_volume_fraction_above_1p62T']),differential_ratio=float(state['directional_differential_to_secant_ratio']),port=float(d['port_leakage']),power=float(d['power_ratio']),locality=float(d['route_locality_residual']),gates=G['strict_overlap_guard'])
    num,num_checks=state_numerical(state)
    return {'strong_dark':all(strong.values()),'strong_dark_checks':strong,'saturated':all(sat.values()),'saturation_checks':sat,'strict_overlap':bool(strict['accepted']),'strict_checks':strict['checks'],'numerical':num,'numerical_checks':num_checks}


def topology_pass(metrics:dict[str,Any])->tuple[bool,dict[str,bool]]:
    g=G['nonlinear_topology']
    checks={
      'sym2_rank':int(metrics['sym2_rank'])==int(g['required_sym2_rank']),
      'sym2_condition':float(metrics['sym2_condition'])<=float(g['maximum_sym2_condition']),
      'lorentz_signature':list(metrics['lorentz_signature'])==list(g['required_lorentz_signature']),
      'route_rank':max(float(x) for x in metrics['route_rank_defects'])<=float(g['maximum_route_rank_defect']),
      'whitened_tight_frame':float(metrics['maximum_whitened_tight_frame_defect'])<=float(g['maximum_whitened_tight_frame_defect']),
    }
    return all(checks.values()),checks


def raw_case_ok(case:dict[str,Any])->bool:
    g=G['numerical']
    return float(case['relative_stationarity_residual'])<=float(g['maximum_stationarity_residual']) and float(case['gauge_fraction'])<=float(g['maximum_gauge_fraction']) and float(case['power_pairing_residual'])<=float(g['maximum_power_pairing_residual'])


def tangent_report_ok(report:dict[str,Any])->bool:
    g=G['numerical']
    return float(report['reciprocity_residual'])<=float(g['maximum_reciprocity_residual']) and min(float(x) for x in report['eigenvalues_H'])>0 and float(report['condition'])<=float(g['maximum_differential_inductance_condition']) and max(float(x['relative_residual']) for x in report['linearized_solve_reports'])<=float(g['maximum_exact_tangent_linearized_residual'])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--evidence',type=Path,required=True); args=ap.parse_args(); root=args.evidence.resolve()
    shards=load_shards(root)
    if not shards: raise SystemExit('no shard summaries')
    hashes={d.get('campaign_sha256') for _,d in shards};
    if hashes!={SHA}: raise SystemExit(f'campaign hash mismatch: {hashes} expected {SHA}')
    states={}; numerical={}; topologies={}; uncertainties={}
    for p,d in shards:
        k=d['kind']
        if k=='state': states[(d['ray'],float(d['scale']))]=d
        elif k=='numerical': numerical[d['level']]=d
        elif k=='topology': topologies[d['ray']]=d
        elif k=='uncertainty': uncertainties[d['scenario_id']]=d
        else: raise SystemExit(f'unexpected shard kind {k}: {p}')
    expected_states={(r,s) for r in RAYS for s in SCALES}
    if set(states)!=expected_states: raise SystemExit(f'state set mismatch missing={expected_states-set(states)} extra={set(states)-expected_states}')
    if set(numerical)!={'mesh_mid','mesh_fine','boundary_far'}: raise SystemExit('numerical sentinel set mismatch')
    expected_top={x['ray'] for x in CFG['topology_sentinels']}
    if set(topologies)!=expected_top: raise SystemExit('topology sentinel set mismatch')
    expected_unc=set(CFG['saturation_targeted_uncertainty']['scenario_ids'])
    if set(uncertainties)!=expected_unc: raise SystemExit('uncertainty set mismatch')

    # Numerical qualification at the frozen saturated sentinel.
    mid=numerical['mesh_mid']['state']; fine=numerical['mesh_fine']['state']; far=numerical['boundary_far']['state']; val=numerical['mesh_fine']['validation']
    def arr(s,key): return np.asarray(s[key],dtype=float)
    mesh_gap=max(relative(arr(fine,'Kq_Wb_per_m'),arr(mid,'Kq_Wb_per_m')),relative(arr(fine,'coenergy_gradient_N'),arr(mid,'coenergy_gradient_N')))
    boundary_gap=max(relative(arr(fine,'Kq_Wb_per_m'),arr(far,'Kq_Wb_per_m')),relative(arr(fine,'coenergy_gradient_N'),arr(far,'coenergy_gradient_N')))
    step_gap=max(relative(arr(fine,'Kq_Wb_per_m'),np.asarray(val['Kq_Wb_per_m'])),relative(arr(fine,'coenergy_gradient_N'),np.asarray(val['coenergy_gradient_N'])))
    ld_mid=np.asarray(mid['exact_tangent']['calibrated_differential_inductance_H']); ld_fine=np.asarray(fine['exact_tangent']['calibrated_differential_inductance_H']); ld_far=np.asarray(far['exact_tangent']['calibrated_differential_inductance_H'])
    ld_mesh=relative(ld_fine,ld_mid); ld_boundary=relative(ld_fine,ld_far); exact_fd=float(val['exact_vs_finite_difference_spread'])
    sentinel_state_checks={level:state_numerical(numerical[level]['state'])[0] for level in numerical}
    current_validation_ok=all(raw_case_ok(x) for x in val['current_cases'])
    validation_path_ok=all(raw_case_ok(x) for x in [*val['continuation_cases'],*val['gap_cases']])
    ng=G['numerical']
    numerical_checks={
      'all_sentinel_states':all(sentinel_state_checks.values()),
      'current_validation_cases':current_validation_ok,
      'gap_step_validation_cases':validation_path_ok,
      'gap_derivative_mesh':mesh_gap<=float(ng['maximum_gap_derivative_mesh_spread']),
      'gap_derivative_boundary':boundary_gap<=float(ng['maximum_remote_boundary_spread']),
      'gap_derivative_step':step_gap<=float(ng['maximum_gap_derivative_step_spread']),
      'Ld_mesh':ld_mesh<=float(ng['maximum_Ld_mesh_spread']),
      'Ld_boundary':ld_boundary<=float(ng['maximum_Ld_remote_boundary_spread']),
      'exact_tangent_validation':exact_fd<=float(ng['maximum_exact_tangent_vs_finite_difference_spread']),
    }
    numerical_qualified=all(numerical_checks.values())

    # Ordered critical-surface samples.
    state_rows=[]; ray_reports={}; all_state_num=True
    for ray in RAYS:
        sat=[]; dark=[]; strict=[]
        for scale in SCALES:
            state=states[(ray,scale)]['state']; phys=state_physical(state); all_state_num &= phys['numerical']
            d=state['dark']
            row={'ray':ray,'scale':scale,'current_A':state['current_A'],'current_norm_A':float(np.linalg.norm(state['current_A'])),'numerical':phys['numerical'],'strong_dark':phys['strong_dark'],'saturated':phys['saturated'],'strict_overlap':phys['strict_overlap'],'port_leakage':float(d['port_leakage']),'power_ratio':float(d['power_ratio']),'route_locality_residual':float(d['route_locality_residual']),'volume_above_1p62T':float(state['saturation_volume_fraction_above_1p62T']),'differential_to_secant_ratio':float(state['directional_differential_to_secant_ratio']),'core_B_p16_T':float(state['baseline']['core_B_p16_T']),'Ld_min_H':min(state['exact_tangent']['eigenvalues_H']),'Ld_condition':float(state['exact_tangent']['condition'])}
            state_rows.append(row); sat.append(phys['saturated']); dark.append(phys['strong_dark']); strict.append(phys['strict_overlap'])
        report=sampled_event_order(SCALES,sat,dark,strict)
        if report['first_saturated_scale'] is not None:
            j=SCALES.index(report['first_saturated_scale']); report['saturation_bracket']=[SCALES[j-1] if j>0 else None,SCALES[j]]
        else: report['saturation_bracket']=None
        if report['first_strong_dark_failure_scale'] is None: report['strong_dark_survival_lower_bound_scale']=SCALES[-1]
        ray_reports[ray]=report
    ray_overlap=all(x['strict_local_overlap_certified'] for x in ray_reports.values())
    event_order=all(x['saturation_precedes_sampled_dark_failure'] for x in ray_reports.values())

    # Topology survival at two angularly distinct deep-saturation states.
    topology_rows=[]; topology_survival=True
    sentinel_scale=float(CFG['critical_surface_ladder']['sentinel_scale'])
    for ray,d in topologies.items():
        metrics=d['topology']; passed,checks=topology_pass(metrics)
        assoc=state_physical(states[(ray,sentinel_scale)]['state'])
        case_num=all(raw_case_ok(x) for x in [*d['continuation_cases'],*d['state_reports']]) and tangent_report_ok(d['baseline_exact_tangent']) and all(tangent_report_ok(x) for x in d['tangent_reports'])
        accepted=passed and assoc['numerical'] and assoc['saturated'] and assoc['strong_dark'] and case_num
        topology_survival &= accepted
        topology_rows.append({'ray':ray,'scale':sentinel_scale,'accepted':accepted,'topology_checks':checks,'state_saturated':assoc['saturated'],'state_strong_dark':assoc['strong_dark'],'state_numerical':assoc['numerical'],'internal_cases_numerical':case_num,'metrics':metrics})

    uncertainty_rows=[]; uncertainty_survival=True
    for ident,d in uncertainties.items():
        phys=state_physical(d['state']); accepted=phys['numerical'] and phys['saturated'] and phys['strong_dark']; uncertainty_survival &= accepted
        uncertainty_rows.append({'scenario_id':ident,'accepted':accepted,'numerical':phys['numerical'],'saturated':phys['saturated'],'strong_dark':phys['strong_dark'],'strict_overlap':phys['strict_overlap'],'power_ratio':float(d['state']['dark']['power_ratio']),'port_leakage':float(d['state']['dark']['port_leakage']),'route_locality_residual':float(d['state']['dark']['route_locality_residual']),'volume_above_1p62T':float(d['state']['saturation_volume_fraction_above_1p62T']),'differential_to_secant_ratio':float(d['state']['directional_differential_to_secant_ratio'])})

    decisions={
      'numerical_sentinel_qualified':numerical_qualified,
      'all_state_numerical_admissible':bool(all_state_num),
      'all_ray_overlap_certificates':ray_overlap,
      'all_sampled_event_orders':event_order,
      'topology_survival':bool(topology_survival),
      'saturated_uncertainty_survival':bool(uncertainty_survival),
    }
    overall=all(decisions.values())
    summary={
      'schema':'bfm5_tcz1l_saturation_critical_surface_summary_v1','campaign_sha256':SHA,'parent_qualification_sha256':CFG['frozen_parent']['tcz1kq_qualification_sha256'],
      'overall_saturation_critical_surface_accepted':overall,'partitioned_decision':decisions,
      'numerical_qualification':{'accepted':numerical_qualified,'checks':numerical_checks,'sentinel_state_checks':sentinel_state_checks,'metrics':{'gap_derivative_mesh_spread':mesh_gap,'gap_derivative_boundary_spread':boundary_gap,'gap_derivative_step_spread':step_gap,'Ld_mesh_spread':ld_mesh,'Ld_boundary_spread':ld_boundary,'exact_tangent_vs_finite_difference_spread':exact_fd}},
      'ray_event_reports':ray_reports,'state_rows':state_rows,'topology_rows':topology_rows,'uncertainty_rows':uncertainty_rows,
      'continuity_argument':'The discrete energy is monotone/regularized and the exact Newton Hessian is nonsingular at accepted states. A strict saturated strong-dark sample therefore implies, by continuity/implicit-function regularity, a nonempty local interval retaining both strict inequalities.',
      'claim_scope':CFG['mathematical_claim_boundary'],
    }
    (root/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print('BFM5_TCZ1L_SUMMARY='+json.dumps(decisions,sort_keys=True)); print(json.dumps({'overall':overall,'numerical':summary['numerical_qualification'],'ray_event_reports':ray_reports,'topology':topology_rows,'uncertainty':uncertainty_rows},indent=2))

if __name__=='__main__': main()
