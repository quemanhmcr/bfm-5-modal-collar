from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from ngsolve import InnerProduct, Integrate, Norm, TaskManager, curl, sqrt, solvers

from bfm5.tcz1m_3d import (
    BooleanBracket,
    certified_event_margin_bounds,
    event_flags,
    event_margins,
    relative,
    update_transition_bracket,
    validate_transition_bracket,
)

ROOT=Path(__file__).resolve().parents[1]
CONFIG_PATH=ROOT/'config'/'tcz1m_directional_event_root.yml'
CONFIG=yaml.safe_load(CONFIG_PATH.read_text(encoding='utf-8'))
CAMPAIGN_SHA=hashlib.sha256(json.dumps(CONFIG,sort_keys=True,separators=(',',':')).encode()).hexdigest()

PINS={
    ROOT/'config'/'tcz1l_3d_saturation_critical_surface.yml':CONFIG['frozen_parent']['tcz1l_config_sha256'],
    ROOT/'scripts'/'run_tcz1l_3d_critical_surface.py':CONFIG['frozen_parent']['tcz1l_runner_sha256'],
    ROOT/'bfm5'/'tcz1l_3d.py':CONFIG['frozen_parent']['tcz1l_math_sha256'],
    ROOT/'config'/'tcz1k_3d_nonlinear_holdout.yml':CONFIG['frozen_parent']['tcz1k_config_sha256'],
    ROOT/'scripts'/'run_tcz1k_3d_nonlinear_holdout.py':CONFIG['frozen_parent']['tcz1k_runner_sha256'],
}
for _p,_expected in PINS.items():
    _actual=hashlib.sha256(_p.read_bytes()).hexdigest()
    if _actual != _expected:
        raise RuntimeError(f'frozen parent source drift: {_p} {_actual} != {_expected}')

L_PATH=ROOT/'scripts'/'run_tcz1l_3d_critical_surface.py'
spec=importlib.util.spec_from_file_location('tcz1l_parent',L_PATH)
tcz1l=importlib.util.module_from_spec(spec); spec.loader.exec_module(tcz1l)
parent=tcz1l.parent
FIXED=CONFIG['fixed_physics']; GATES=CONFIG['acceptance_gates']; EST=CONFIG['implicit_shape_estimator']; ALG=CONFIG['root_algorithm']
BASE_CURRENT=np.asarray(FIXED['target_ray']['base_current_A'],dtype=float)
C=np.asarray(FIXED['calibration_matrix_C'],dtype=float)
if not np.array_equal(C,parent.C_CAL):
    raise RuntimeError('TCZ-1M calibration differs from frozen TCZ-1K/1L calibration')


def dump(path:Path,data:Any)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True)+'\n',encoding='utf-8')


def model_for(boundary_scale:float):
    return parent.NonlinearModel(float(FIXED['physical_depth_mm'])*1e-3,float(FIXED['mesh_scale']),float(boundary_scale))


def current_at(scale:float)->np.ndarray:
    return BASE_CURRENT*float(scale)


def restore_nominal(model,current:np.ndarray,vector)->np.ndarray:
    model._set_deformation(np.zeros(3))
    raw=model._set_parameters(current,np.ones(3),1.0,1.0)
    model.gf.vec.data=vector
    return raw


def free_residual_vector(model):
    residual=model.gf.vec.CreateVector()
    model.energy_form.Apply(model.gf.vec,residual)
    for dof in range(len(residual)):
        if not model.free[dof]: residual[dof]=0.0
    return residual


def fixed_state_residual(model,current:np.ndarray,baseline_vector,gap_delta_mm:np.ndarray):
    model._set_deformation(np.asarray(gap_delta_mm,dtype=float))
    model._set_parameters(current,np.ones(3),1.0,1.0)
    model.gf.vec.data=baseline_vector
    return free_residual_vector(model)


def lean_observables(model,current:np.ndarray,vector,gap_delta_mm:np.ndarray)->dict[str,Any]:
    model._set_deformation(np.asarray(gap_delta_mm,dtype=float))
    raw_current=model._set_parameters(current,np.ones(3),1.0,1.0)
    model.gf.vec.data=vector
    for form in model.flux_forms: form.Assemble()
    raw_flux=np.asarray([float(InnerProduct(form.vec,model.gf.vec))/parent.base.I0 for form in model.flux_forms],dtype=float)
    flux=parent.calibrated_flux(parent.C_CAL,raw_flux)
    source_work=float(raw_current@raw_flux)
    field=curl(model.gf); field_sq=InnerProduct(field,field); field_abs=sqrt(field_sq+1e-18)
    scaled_abs=field_abs/model.b_knee_scale
    core_energy=model.h_scale*model.b_knee_scale*parent.energy_cf(scaled_abs)
    air_energy=0.5/parent.MU0*field_sq
    density=model.core_indicator*core_energy+(1.0-model.core_indicator)*air_energy
    with TaskManager(): magnetic_energy=float(Integrate(density,model.mesh,order=5))
    model.load.Assemble(); residual=free_residual_vector(model)
    rel_res=float(Norm(residual)/(Norm(model.load.vec)+1e-300))
    return {
        'raw_flux_linkage_Wb_turn':raw_flux.tolist(),
        'calibrated_flux_linkage_Wb_turn':np.asarray(flux,dtype=float).tolist(),
        'magnetic_energy_J':magnetic_energy,
        'magnetic_coenergy_J':float(source_work-magnetic_energy),
        'relative_stationarity_residual':rel_res,
    }


def solve_hessian(model,rhs,label:str)->tuple[Any,dict[str,Any]]:
    inv=solvers.CGSolver(model.energy_form.mat,model.nonlinear_preconditioner,tol=1e-11,maxiter=int(parent.SOLVER['maximum_cg_iterations']),printrates=False)
    out=model.gf.vec.CreateVector(); out.data=inv*rhs
    residual=rhs.CreateVector(); residual.data=rhs-model.energy_form.mat*out
    for dof in range(len(residual)):
        if not model.free[dof]: residual[dof]=0.0
    report={'label':label,'cg_iterations':int(getattr(inv,'iterations',-1)),'relative_residual':float(Norm(residual)/(Norm(rhs)+1e-300))}
    return out,report


def implicit_linearized_state(model,current:np.ndarray,baseline:dict[str,Any],baseline_vector,step_mm:float)->dict[str,Any]:
    """One nonlinear baseline + discrete implicit-function sensitivities.

    F(A,q)=0 => A_q=-F_A^{-1}F_q. F_q is central-differenced at fixed A,
    while the state response is solved with the exact Newton Hessian F_A.
    """
    h_m=float(step_mm)*1e-3
    fq=[]
    for route in range(3):
        d=np.zeros(3); d[route]=float(step_mm)
        minus=fixed_state_residual(model,current,baseline_vector,-d)
        plus=fixed_state_residual(model,current,baseline_vector,d)
        deriv=plus.CreateVector(); deriv.data=plus-minus; deriv*=1.0/(2.0*h_m)
        fq.append(deriv)

    restore_nominal(model,current,baseline_vector)
    for form in model.flux_forms: form.Assemble()
    with TaskManager():
        model.energy_form.AssembleLinearization(model.gf.vec)
        model.nonlinear_preconditioner.Update()

    # Current tangent: two Hessian solves at the same baseline factorization/preconditioner.
    lraw=np.zeros((2,2),dtype=float); current_solve_reports=[]
    for port in range(2):
        rhs=model.flux_forms[port].vec.CreateVector(); rhs.data=model.flux_forms[port].vec; rhs*=1.0/parent.base.I0
        for dof in range(len(rhs)):
            if not model.free[dof]: rhs[dof]=0.0
        derivative,sr=solve_hessian(model,rhs,f'current_port_{port+1}')
        for out in range(2): lraw[out,port]=float(InnerProduct(model.flux_forms[out].vec,derivative))/parent.base.I0
        current_solve_reports.append(sr)
    lcal=parent.C_CAL.T@lraw@parent.C_CAL; sym=0.5*(lcal+lcal.T)

    kq_cols=[]; grad=[]; shape_solve_reports=[]; prediction_reports=[]
    for route in range(3):
        rhs=fq[route].CreateVector(); rhs.data=fq[route]; rhs*=-1.0
        aq,sr=solve_hessian(model,rhs,f'shape_route_{route+1}')
        shape_solve_reports.append(sr)
        pair=[]
        for sign,name in ((-1.0,'minus'),(1.0,'plus')):
            d=np.zeros(3); d[route]=sign*float(step_mm)
            predicted=baseline_vector.CreateVector(); predicted.data=baseline_vector; predicted.data += sign*h_m*aq
            obs=lean_observables(model,current,predicted,d)
            pair.append(obs)
            prediction_reports.append({'route':route+1,'side':name,**obs})
        kq_cols.append((np.asarray(pair[1]['calibrated_flux_linkage_Wb_turn'])-np.asarray(pair[0]['calibrated_flux_linkage_Wb_turn']))/(2.0*h_m))
        grad.append((float(pair[1]['magnetic_coenergy_J'])-float(pair[0]['magnetic_coenergy_J']))/(2.0*h_m))

    restore_nominal(model,current,baseline_vector)
    kq=np.column_stack(kq_cols); grad=np.asarray(grad,dtype=float)
    dark=parent.dark_metrics(kq,grad,parent.FRAME)
    flux=np.asarray(baseline['calibrated_flux_linkage_Wb_turn'],dtype=float)
    diff=parent.directional_differential_to_secant(current,flux,sym)
    volume=float(baseline['core_saturation_volume_fraction']['above_1p62T'])
    flags=event_flags(volume=volume,differential_ratio=diff,port=float(dark['port_leakage']),power=float(dark['power_ratio']),locality=float(dark['route_locality_residual']),gates=GATES)
    margins=event_margins(volume=volume,differential_ratio=diff,port=float(dark['port_leakage']),power=float(dark['power_ratio']),locality=float(dark['route_locality_residual']),gates=GATES)
    return {
        'method':EST['method'],
        'gap_step_mm':float(step_mm),
        'Kq_Wb_per_m':kq.tolist(),
        'coenergy_gradient_N':grad.tolist(),
        'dark':dark,
        'calibrated_differential_inductance_H':lcal.tolist(),
        'symmetric_differential_inductance_H':sym.tolist(),
        'tangent_reciprocity_residual':relative(lcal,lcal.T),
        'tangent_eigenvalues_H':np.linalg.eigvalsh(sym).tolist(),
        'tangent_condition':float(np.linalg.cond(sym)),
        'directional_differential_to_secant_ratio':float(diff),
        'saturation_volume_fraction_above_1p62T':volume,
        'event_flags':flags,
        'event_margins':margins,
        'current_solve_reports':current_solve_reports,
        'shape_solve_reports':shape_solve_reports,
        'prediction_reports':prediction_reports,
        'maximum_linearized_solve_residual':max([x['relative_residual'] for x in current_solve_reports+shape_solve_reports]),
        'maximum_prediction_stationarity_residual':max(x['relative_stationarity_residual'] for x in prediction_reports),
    }


def baseline_numerical_ok(state:dict[str,Any],implicit:dict[str,Any])->tuple[bool,dict[str,bool]]:
    g=GATES['numerical']; eig=implicit['tangent_eigenvalues_H']
    checks={
        'stationarity':float(state['relative_stationarity_residual'])<=float(g['maximum_stationarity_residual']),
        'gauge':float(state['gauge_fraction'])<=float(g['maximum_gauge_fraction']),
        'power_pairing':float(state['power_pairing_residual'])<=float(g['maximum_power_pairing_residual']),
        'reciprocity':float(implicit['tangent_reciprocity_residual'])<=float(g['maximum_tangent_reciprocity_residual']),
        'positive_Ld':min(float(x) for x in eig)>0.0,
        'Ld_condition':float(implicit['tangent_condition'])<=float(g['maximum_differential_inductance_condition']),
        'linearized_solve':float(implicit['maximum_linearized_solve_residual'])<=float(g['maximum_linearized_solve_residual']),
    }
    return all(checks.values()),checks


def solve_baseline(model,current:np.ndarray,label:str,initial_vector=None):
    if initial_vector is not None:
        try:
            result,vector=model.solve(current,initial_vector=initial_vector,label=f'{label}_nearest_warm')
            return result,vector,{'mode':'nearest_warm_start','fallback_used':False}
        except RuntimeError as warm_error:
            warm_diag={'warm_failure_type':type(warm_error).__name__,'warm_failure_message':str(warm_error)}
    else:
        warm_diag={}
    try:
        result,vector=model.solve(current,initial_vector=None,label=f'{label}_direct')
        return result,vector,{'mode':'direct_linear_initializer','fallback_used':False,**warm_diag}
    except RuntimeError as direct_error:
        vector=None; reports=[]
        for factor in tcz1l.CONFIG['execution_efficiency']['fallback_continuation_factors']:
            result,vector=model.solve(current*float(factor),initial_vector=vector,label=f'{label}_fallback_{factor:g}')
            reports.append(result)
        return reports[-1],vector,{'mode':'fallback_homotopy','fallback_used':True,'direct_failure_type':type(direct_error).__name__,'direct_failure_message':str(direct_error),**warm_diag}


def evaluate_scale(model,scale:float,label:str,initial_vector=None)->tuple[dict[str,Any],Any]:
    current=current_at(scale)
    baseline,vector,strategy=solve_baseline(model,current,label,initial_vector=initial_vector)
    implicit=implicit_linearized_state(model,current,baseline,vector,float(EST['geometry_residual_step_mm']))
    numerical,checks=baseline_numerical_ok(baseline,implicit)
    report={
        'scale':float(scale),'current_A':current.tolist(),'baseline':baseline,'baseline_strategy':strategy,
        'implicit':implicit,'numerical_accepted':bool(numerical),'numerical_checks':checks,
    }
    return report,vector


def frozen_reference(scale:float)->dict[str,Any]:
    key=f'{float(scale):.2f}'
    path=ROOT.parent/EST['frozen_reference_paths'][key]
    return json.loads(path.read_text(encoding='utf-8'))['state']


def estimator_validation(output:Path)->dict[str,Any]:
    boundary=float(EST['validation_boundary_scale']); model=model_for(boundary)
    rows=[]; previous=None
    for scale in [float(x) for x in EST['validation_scales']]:
        state,vector=evaluate_scale(model,scale,f'tcz1m_estimator_{scale:g}',initial_vector=previous)
        previous=vector
        ref=frozen_reference(scale); imp=state['implicit']
        ref_flags={'saturation':bool(ref['saturation_accepted']),'strong_dark':bool(ref['strong_dark_accepted']),'dark_failure':not bool(ref['strong_dark_accepted'])}
        errors={
            'Kq_relative':relative(ref['Kq_Wb_per_m'],imp['Kq_Wb_per_m']),
            'coenergy_gradient_relative':relative(ref['coenergy_gradient_N'],imp['coenergy_gradient_N']),
            'power_ratio_absolute':abs(float(ref['dark']['power_ratio'])-float(imp['dark']['power_ratio'])),
            'locality_absolute':abs(float(ref['dark']['route_locality_residual'])-float(imp['dark']['route_locality_residual'])),
        }
        a=EST['acceptance']
        checks={
            'Kq':errors['Kq_relative']<=float(a['maximum_Kq_relative_error']),
            'coenergy_gradient':errors['coenergy_gradient_relative']<=float(a['maximum_coenergy_gradient_relative_error']),
            'power_ratio':errors['power_ratio_absolute']<=float(a['maximum_power_ratio_absolute_error']),
            'locality':errors['locality_absolute']<=float(a['maximum_locality_absolute_error']),
            'linearized_residual':float(imp['maximum_linearized_solve_residual'])<=float(a['maximum_linearized_state_residual']),
            'event_classification':imp['event_flags']==ref_flags,
            'baseline_numerical':bool(state['numerical_accepted']),
        }
        rows.append({'scale':scale,'accepted':all(checks.values()),'checks':checks,'errors':errors,'reference_flags':ref_flags,'state':state})
    accepted=all(r['accepted'] for r in rows)
    result={'kind':'estimator_validation','campaign_sha256':CAMPAIGN_SHA,'boundary_scale':boundary,'accepted':accepted,'rows':rows}
    dump(output/'estimator_validation.json',result); return result


def root_boundary(boundary:float,output:Path)->dict[str,Any]:
    model=model_for(boundary); lo,hi=[float(x) for x in FIXED['root_bracket_scale']]; tol=float(FIXED['root_tolerance_scale'])
    cache:dict[float,tuple[dict[str,Any],Any]]={}

    def get(scale:float):
        key=round(float(scale),12)
        if key in cache: return cache[key]
        nearest=None
        if cache:
            nearest_key=min(cache,key=lambda x:abs(x-key)); nearest=cache[nearest_key][1]
        report,vector=evaluate_scale(model,float(scale),f'tcz1m_b{boundary:g}_s{scale:g}',initial_vector=nearest)
        cache[key]=(report,vector); return report,vector

    lo_state,_=get(lo); hi_state,_=get(hi)
    bracket_valid=(not lo_state['implicit']['event_flags']['saturation'] and hi_state['implicit']['event_flags']['saturation'] and lo_state['implicit']['event_flags']['strong_dark'] and not hi_state['implicit']['event_flags']['strong_dark'])
    sat=None; dark=None
    if bracket_valid:
        sat=BooleanBracket(lo,hi,False,True); dark=BooleanBracket(lo,hi,True,False)
        validate_transition_bracket(sat,rising=True); validate_transition_bracket(dark,rising=False)
        maxeval=int(ALG['maximum_unique_state_evaluations_per_boundary'])
        while (sat.width>tol or dark.width>tol) and len(cache)<maxeval:
            mids=[]
            if sat.width>tol: mids.append(sat.midpoint)
            if dark.width>tol: mids.append(dark.midpoint)
            for scale in sorted(set(round(x,12) for x in mids)):
                state,_=get(scale); flags=state['implicit']['event_flags']
                if sat.lo < scale < sat.hi: sat=update_transition_bracket(sat,scale,bool(flags['saturation']),rising=True)
                if dark.lo < scale < dark.hi: dark=update_transition_bracket(dark,scale,bool(flags['strong_dark']),rising=False)
        margin=certified_event_margin_bounds(sat,dark)
    else:
        margin=(float('-inf'),float('inf'))

    evaluations=[]
    for scale,(state,_) in sorted(cache.items()): evaluations.append(state)
    result={
        'kind':'root_boundary','campaign_sha256':CAMPAIGN_SHA,'boundary_scale':float(boundary),'bracket_valid':bool(bracket_valid),
        'saturation_bracket':None if sat is None else {'lo':sat.lo,'hi':sat.hi,'width':sat.width,'midpoint':sat.midpoint},
        'strong_dark_bracket':None if dark is None else {'lo':dark.lo,'hi':dark.hi,'width':dark.width,'midpoint':dark.midpoint},
        'event_margin_bounds_scale':[float(margin[0]),float(margin[1])],
        'unique_state_evaluations':len(cache),'evaluations':evaluations,
        'all_states_numerical':all(bool(s['numerical_accepted']) for s in evaluations),
    }
    dump(output/'root_boundary.json',result); return result


def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument('--kind',choices=('estimator_validation','root_boundary'),required=True); ap.add_argument('--boundary',type=float,default=0.0); ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); out=a.output.resolve(); out.mkdir(parents=True,exist_ok=True)
    dump(out/'campaign_lock.json',{'schema':CONFIG['schema'],'campaign_sha256':CAMPAIGN_SHA,'config':CONFIG,'kind':a.kind,'boundary':a.boundary})
    result=estimator_validation(out) if a.kind=='estimator_validation' else root_boundary(float(a.boundary),out)
    dump(out/'shard_summary.json',result)
    print('BFM5_TCZ1M_SHARD='+json.dumps({'kind':a.kind,'boundary':a.boundary,'campaign_sha256':CAMPAIGN_SHA,'accepted':result.get('accepted')},sort_keys=True),flush=True)

if __name__=='__main__': main()
