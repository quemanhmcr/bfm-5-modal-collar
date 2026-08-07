from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from ngsolve import InnerProduct, Norm, TaskManager, solvers

from bfm5.tcz1k_3d import dark_metrics, directional_differential_to_secant, topology_metrics
from bfm5.tcz1l_3d import relative, strict_overlap_flags

ROOT=Path(__file__).resolve().parents[1]
CONFIG_PATH=ROOT/'config'/'tcz1l_3d_saturation_critical_surface.yml'
CONFIG=yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8'))
CAMPAIGN_SHA=hashlib.sha256(json.dumps(CONFIG,sort_keys=True,separators=(',',':')).encode()).hexdigest()

PINS={
    ROOT/'config'/'tcz1k_3d_nonlinear_holdout.yml': CONFIG['frozen_parent']['tcz1k_config_sha256'],
    ROOT/'scripts'/'run_tcz1k_3d_nonlinear_holdout.py': CONFIG['frozen_parent']['tcz1k_runner_sha256'],
    ROOT/'config'/'tcz1kq_3d_numerical_qualification.yml': CONFIG['frozen_parent']['tcz1kq_config_sha256'],
    ROOT/'scripts'/'run_tcz1kq_3d_qualification.py': CONFIG['frozen_parent']['tcz1kq_runner_sha256'],
}
for _path,_expected in PINS.items():
    _actual=hashlib.sha256(_path.read_bytes()).hexdigest()
    if _actual != _expected:
        raise RuntimeError(f'frozen parent source drift: {_path} {_actual} != {_expected}')

PARENT_PATH=ROOT/'scripts'/'run_tcz1k_3d_nonlinear_holdout.py'
spec=importlib.util.spec_from_file_location('tcz1k_parent',PARENT_PATH)
parent=importlib.util.module_from_spec(spec); spec.loader.exec_module(parent)

GRID=CONFIG['fixed_model']
LADDER=CONFIG['critical_surface_ladder']
GATES=CONFIG['acceptance_gates']
RAYS={x['id']:np.asarray(x['base_current_A'],dtype=float) for x in LADDER['rays']}
if not np.array_equal(np.asarray(GRID['calibration_matrix_C'],dtype=float), parent.C_CAL):
    raise RuntimeError('TCZ-1L calibration differs from frozen TCZ-1K calibration')


def dump(path:Path,data:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def ray_current(ray:str,scale:float)->np.ndarray:
    if ray not in RAYS: raise KeyError(ray)
    if float(scale) not in [float(x) for x in LADDER['scale_factors']]: raise ValueError(f'unregistered scale {scale}')
    return RAYS[ray]*float(scale)


def model_for(level:str):
    raw=GRID[level]
    return parent.NonlinearModel(float(GRID['physical_depth_mm'])*1e-3,float(raw['mesh_scale']),float(raw['boundary_scale']))


def exact_discrete_current_tangent(model)->tuple[np.ndarray,dict[str,Any]]:
    """Differentiate the discrete stationarity equation instead of differencing current."""
    for form in model.flux_forms: form.Assemble()
    with TaskManager():
        model.energy_form.AssembleLinearization(model.gf.vec)
        model.nonlinear_preconditioner.Update()
    lraw=np.zeros((2,2),dtype=float)
    solve_reports=[]
    for port in range(2):
        rhs=model.flux_forms[port].vec.CreateVector(); rhs.data=model.flux_forms[port].vec
        rhs *= 1.0/parent.base.I0
        for dof in range(len(rhs)):
            if not model.free[dof]: rhs[dof]=0.0
        inv=solvers.CGSolver(model.energy_form.mat,model.nonlinear_preconditioner,tol=1e-11,maxiter=int(parent.SOLVER['maximum_cg_iterations']),printrates=False)
        derivative=model.gf.vec.CreateVector(); derivative.data=inv*rhs
        residual=rhs.CreateVector(); residual.data=rhs-model.energy_form.mat*derivative
        for dof in range(len(residual)):
            if not model.free[dof]: residual[dof]=0.0
        for out in range(2):
            lraw[out,port]=float(InnerProduct(model.flux_forms[out].vec,derivative))/parent.base.I0
        solve_reports.append({'port':port+1,'cg_iterations':int(getattr(inv,'iterations',-1)),'relative_residual':float(Norm(residual)/(Norm(rhs)+1e-300))})
    lcal=parent.C_CAL.T@lraw@parent.C_CAL
    sym=0.5*(lcal+lcal.T)
    report={
        'raw_differential_inductance_H':lraw.tolist(),
        'calibrated_differential_inductance_H':lcal.tolist(),
        'symmetric_differential_inductance_H':sym.tolist(),
        'reciprocity_residual':relative(lcal,lcal.T),
        'eigenvalues_H':np.linalg.eigvalsh(sym).tolist(),
        'condition':float(np.linalg.cond(sym)),
        'linearized_solve_reports':solve_reports,
    }
    return lcal,report


def finite_current_tangent(model,current:np.ndarray,baseline_vector,scenario:dict[str,Any],step_A:float,label:str):
    cols=[]; cases=[]
    for port in range(2):
        d=np.zeros(2); d[port]=step_A
        minus,_=model.solve(current-d,initial_vector=baseline_vector,label=f'{label}_port_{port+1}_minus',**scenario)
        plus,_=model.solve(current+d,initial_vector=baseline_vector,label=f'{label}_port_{port+1}_plus',**scenario)
        cases.extend([minus,plus])
        cols.append((np.asarray(plus['calibrated_flux_linkage_Wb_turn'])-np.asarray(minus['calibrated_flux_linkage_Wb_turn']))/(2*step_A))
    return np.column_stack(cols),cases


def numerical_summary(cases:list[dict[str,Any]],tangent_report:dict[str,Any])->dict[str,Any]:
    return {
        'max_stationarity_residual':max(float(c['relative_stationarity_residual']) for c in cases),
        'max_gauge_fraction':max(float(c['gauge_fraction']) for c in cases),
        'max_power_pairing_residual':max(float(c['power_pairing_residual']) for c in cases),
        'exact_tangent_reciprocity_residual':float(tangent_report['reciprocity_residual']),
        'exact_tangent_minimum_eigenvalue_H':min(float(x) for x in tangent_report['eigenvalues_H']),
        'exact_tangent_condition':float(tangent_report['condition']),
        'exact_tangent_max_linearized_residual':max(float(x['relative_residual']) for x in tangent_report['linearized_solve_reports']),
    }


def adaptive_baseline(model,current:np.ndarray,scenario:dict[str,Any],label:str):
    """Use the parent's linear predictor directly; pay homotopy cost only on failure."""
    efficiency=CONFIG['execution_efficiency']
    try:
        result,vector=model.solve(current,initial_vector=None,label=f'{label}_direct',**scenario)
        return result,vector,[result],{'mode':'direct_linear_initializer','fallback_used':False}
    except RuntimeError as direct_error:
        vector=None; reports=[]
        for factor in efficiency['fallback_continuation_factors']:
            result,vector=model.solve(current*float(factor),initial_vector=vector,label=f'{label}_fallback_{factor:g}',**scenario)
            reports.append(result)
        return reports[-1],vector,reports,{
            'mode':'fallback_homotopy',
            'fallback_used':True,
            'direct_failure_type':type(direct_error).__name__,
            'direct_failure_message':str(direct_error),
        }


def _restore_saved_state(model,current:np.ndarray,vector,gap_delta_mm:np.ndarray,scenario:dict[str,Any])->None:
    base_gaps=np.asarray(scenario.get('gap_delta_mm',np.zeros(3)),dtype=float)
    gains=np.asarray(scenario.get('route_source_gain',np.ones(3)),dtype=float)
    h_scale=float(scenario.get('h_scale',1.0)); b_knee_scale=float(scenario.get('b_knee_scale',1.0))
    model._set_deformation(base_gaps+np.asarray(gap_delta_mm,dtype=float))
    model._set_parameters(current,gains,h_scale,b_knee_scale)
    model.gf.vec.data=vector


def topology_from_gap_states(model,current:np.ndarray,baseline_ld:np.ndarray,gap_vectors:dict[int,tuple[Any,Any]],scenario:dict[str,Any],step_mm:float)->dict[str,Any]:
    """Differentiate exact current tangents at already-solved +/- gap states; no duplicate nonlinear solves."""
    sensitivities=[]; tangent_reports=[]
    for route in range(3):
        pair=[]
        for sign,name,vector in ((-1.0,'minus',gap_vectors[route][0]),(1.0,'plus',gap_vectors[route][1])):
            delta=np.zeros(3); delta[route]=sign*step_mm
            _restore_saved_state(model,current,vector,delta,scenario)
            ld,tr=exact_discrete_current_tangent(model)
            pair.append(0.5*(ld+ld.T))
            tangent_reports.append({'route':route+1,'side':name,**tr})
        sensitivities.append(-(pair[1]-pair[0])/(2.0*step_mm*1e-3))
    return {
        'reuse_policy':'exact_Newton_Hessian_on_primary_gap_states_no_additional_nonlinear_solve',
        'baseline_Ld_H':baseline_ld.tolist(),
        'sensitivities_H_per_m':[x.tolist() for x in sensitivities],
        'topology':topology_metrics(sensitivities),
        'tangent_reports':tangent_reports,
    }


def state_report(model,current:np.ndarray,*,label:str,scenario:dict[str,Any]|None=None,step_mm:float|None=None,include_topology:bool=False,return_internal:bool=False):
    scenario={} if scenario is None else dict(scenario)
    step=float(GRID['gap_step_primary_mm'] if step_mm is None else step_mm)
    baseline,baseline_vector,continuation_cases,baseline_strategy=adaptive_baseline(model,current,scenario,label)
    ld,tangent_report=exact_discrete_current_tangent(model)
    kq,grad_w,gap_cases,gap_vectors=parent.gap_tangent(model,current,baseline_vector,scenario,step,label)
    dark=dark_metrics(kq,grad_w,parent.FRAME)
    flux=np.asarray(baseline['calibrated_flux_linkage_Wb_turn'],dtype=float)
    sym=0.5*(ld+ld.T)
    diff_ratio=directional_differential_to_secant(current,flux,sym)
    volume=float(baseline['core_saturation_volume_fraction']['above_1p62T'])
    strong={
        'port':float(dark['port_leakage'])<=float(GATES['strong_dark']['maximum_port_leakage']),
        'power':float(dark['power_ratio'])<=float(GATES['strong_dark']['maximum_power_ratio']),
        'locality':float(dark['route_locality_residual'])<=float(GATES['strong_dark']['maximum_route_locality_residual']),
    }
    saturation={
        'field_volume':volume>=float(GATES['saturation']['minimum_any_core_volume_fraction_above_1p62T']),
        'differential_drop':diff_ratio<=float(GATES['saturation']['maximum_directional_differential_to_secant_ratio']),
    }
    strict=strict_overlap_flags(volume_above_1p62=volume,differential_ratio=diff_ratio,port=float(dark['port_leakage']),power=float(dark['power_ratio']),locality=float(dark['route_locality_residual']),gates=GATES['strict_overlap_guard'])
    cases=[*continuation_cases,*gap_cases]
    report={
        'current_A':current.tolist(),'baseline':baseline,'continuation_cases':continuation_cases,'baseline_strategy':baseline_strategy,'gap_step_mm':step,'gap_cases':gap_cases,
        'Kq_Wb_per_m':kq.tolist(),'coenergy_gradient_N':grad_w.tolist(),'dark':dark,
        'exact_tangent':tangent_report,'directional_differential_to_secant_ratio':float(diff_ratio),
        'saturation_volume_fraction_above_1p62T':volume,
        'strong_dark_checks':strong,'strong_dark_accepted':all(strong.values()),
        'saturation_checks':saturation,'saturation_accepted':all(saturation.values()),
        'strict_overlap':strict,
        'numerical':numerical_summary(cases,tangent_report),
        'case_count':len(cases),
    }
    if include_topology:
        report['topology_reuse']=topology_from_gap_states(model,current,ld,gap_vectors,scenario,step)
    if return_internal:
        return report,baseline_vector
    return report


def state_shard(ray:str,scale:float,output:Path)->dict[str,Any]:
    model=model_for('mesh_fine')
    current=ray_current(ray,scale)
    sentinel={(x['ray'],float(x['scale'])) for x in CONFIG['topology_sentinels']}
    state=state_report(model,current,label=f'tcz1l_{ray}_{scale:g}',include_topology=(ray,float(scale)) in sentinel)
    result={'kind':'state','ray':ray,'scale':float(scale),'campaign_sha256':CAMPAIGN_SHA,'state':state}
    dump(output/'state.json',result); return result


def numerical_shard(level:str,output:Path)->dict[str,Any]:
    if level not in ('mesh_mid','mesh_fine','boundary_far'): raise ValueError(level)
    ray=CONFIG['numerical_sentinel']['ray']; scale=float(CONFIG['numerical_sentinel']['scale'])
    model=model_for(level); current=ray_current(ray,scale)
    state,baseline_vector=state_report(model,current,label=f'tcz1l_num_{level}',return_internal=True)
    result={'kind':'numerical','level':level,'campaign_sha256':CAMPAIGN_SHA,'state':state}
    if level=='mesh_fine':
        ld_exact=np.asarray(state['exact_tangent']['calibrated_differential_inductance_H'],dtype=float)
        kq2,grad2,cases2,_=parent.gap_tangent(model,current,baseline_vector,{},float(GRID['gap_step_validation_mm']),'tcz1l_num_fine_h2')
        fd,curr_cases=finite_current_tangent(model,current,baseline_vector,{},float(GRID['finite_current_validation_step_A']),'tcz1l_num_fine_fd')
        result['validation']={
            'baseline':state['baseline'],'continuation_cases':[state['baseline']],
            'baseline_reuse':'primary_mesh_fine_baseline_vector',
            'gap_step_validation_mm':float(GRID['gap_step_validation_mm']),
            'Kq_Wb_per_m':kq2.tolist(),'coenergy_gradient_N':grad2.tolist(),'gap_cases':cases2,
            'finite_current_validation_step_A':float(GRID['finite_current_validation_step_A']),
            'finite_difference_differential_inductance_H':fd.tolist(),'current_cases':curr_cases,
            'exact_differential_inductance_H':ld_exact.tolist(),
            'exact_vs_finite_difference_spread':relative(ld_exact,fd),
            'exact_tangent':state['exact_tangent'],
        }
    dump(output/'numerical.json',result); return result


def topology_shard(ray:str,output:Path)->dict[str,Any]:
    """Manual/debug entry point; production R2 obtains topology from sentinel state shards."""
    scale=float(LADDER['sentinel_scale']); current=ray_current(ray,scale); model=model_for('mesh_fine')
    state=state_report(model,current,label=f'tcz1l_topology_debug_{ray}',include_topology=True)
    result={'kind':'topology','ray':ray,'scale':scale,'campaign_sha256':CAMPAIGN_SHA,'state':state,'topology_reuse':state['topology_reuse']}
    dump(output/'topology.json',result); return result


def uncertainty_shard(identifier:str,output:Path)->dict[str,Any]:
    allowed=CONFIG['saturation_targeted_uncertainty']['scenario_ids']
    if identifier not in allowed: raise ValueError(identifier)
    raw=next(x for x in parent.CONFIG['uncertainty_holdout']['scenarios'] if x['id']==identifier)
    scenario=parent.scenario_kwargs(raw)
    ray=CONFIG['saturation_targeted_uncertainty']['ray']; scale=float(CONFIG['saturation_targeted_uncertainty']['scale'])
    model=model_for('mesh_fine'); current=ray_current(ray,scale)
    state=state_report(model,current,label=f'tcz1l_uncertainty_{identifier}',scenario=scenario)
    result={'kind':'uncertainty','scenario_id':identifier,'ray':ray,'scale':scale,'campaign_sha256':CAMPAIGN_SHA,'state':state}
    dump(output/'uncertainty.json',result); return result

def smoke_shard(output:Path)->dict[str,Any]:
    model=parent.NonlinearModel(float(GRID['physical_depth_mm'])*1e-3,1.55,1.0)
    current=np.array([180.0,67.5])
    baseline,vec=model.solve(current,label='tcz1l_smoke_baseline')
    exact,tr=exact_discrete_current_tangent(model)
    fd,cases=finite_current_tangent(model,current,vec,{},4.0,'tcz1l_smoke_fd')
    result={'kind':'smoke','campaign_sha256':CAMPAIGN_SHA,'baseline':baseline,'exact_tangent':tr,'exact_H':exact.tolist(),'finite_H':fd.tolist(),'relative_spread':relative(exact,fd),'cases':cases}
    dump(output/'smoke.json',result); return result


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--kind',choices=('state','numerical','topology','uncertainty','smoke'),required=True); ap.add_argument('--ray',default=''); ap.add_argument('--scale',type=float,default=0.0); ap.add_argument('--case',default=''); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    lock={'schema':CONFIG['schema'],'campaign_sha256':CAMPAIGN_SHA,'config':CONFIG,'kind':a.kind,'ray':a.ray,'scale':a.scale,'case':a.case}
    dump(out/'campaign_lock.json',lock)
    if a.kind=='state': result=state_shard(a.ray,a.scale,out)
    elif a.kind=='numerical': result=numerical_shard(a.case,out)
    elif a.kind=='topology': result=topology_shard(a.ray,out)
    elif a.kind=='uncertainty': result=uncertainty_shard(a.case,out)
    else: result=smoke_shard(out)
    dump(out/'shard_summary.json',result)
    print('BFM5_TCZ1L_SHARD='+json.dumps({'kind':a.kind,'ray':a.ray,'scale':a.scale,'case':a.case,'campaign_sha256':CAMPAIGN_SHA},sort_keys=True))

if __name__=='__main__': main()
