from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path
import numpy as np,yaml
from bfm5.tcz1m_3d import relative

ROOT=Path(__file__).resolve().parents[1]
CFG=yaml.safe_load((ROOT/'config/tcz1m_directional_event_root.yml').read_text(encoding='utf-8'))
SHA=hashlib.sha256(json.dumps(CFG,sort_keys=True,separators=(',',':')).encode()).hexdigest()
G=CFG['acceptance_gates']; EXPECTED=[float(x) for x in CFG['fixed_physics']['exterior_boundary_scales']]


def load(root:Path):
    rows=[]
    for p in root.rglob('shard_summary.json'):
        d=json.loads(p.read_text()); rows.append((p,d))
    return rows


def state_at(root:dict,scale:float):
    rows=[x for x in root['evaluations'] if abs(float(x['scale'])-float(scale))<1e-10]
    if len(rows)!=1: raise ValueError(f'expected common state {scale} once at boundary {root["boundary_scale"]}, got {len(rows)}')
    return rows[0]


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--evidence',type=Path,required=True); a=ap.parse_args(); root=a.evidence.resolve()
    shards=load(root)
    if not shards: raise SystemExit('no TCZ-1M shard summaries')
    hashes={d.get('campaign_sha256') for _,d in shards}
    if hashes!={SHA}: raise SystemExit(f'campaign hash mismatch {hashes} != {SHA}')
    estimators=[d for _,d in shards if d.get('kind')=='estimator_validation']
    roots={float(d['boundary_scale']):d for _,d in shards if d.get('kind')=='root_boundary'}
    if len(estimators)!=1: raise SystemExit(f'estimator shard count {len(estimators)} != 1')
    estimator=estimators[0]; estimator_ok=bool(estimator['accepted'])
    roots_complete=set(roots)==set(EXPECTED)

    root_rows=[]; all_localized=roots_complete
    maxw=float(G['event_root']['maximum_final_bracket_width_scale'])
    if roots_complete:
        for b in EXPECTED:
            r=roots[b]; sat=r['saturation_bracket']; dark=r['strong_dark_bracket']
            localized=bool(r['bracket_valid'] and r['all_states_numerical'] and sat and dark and float(sat['width'])<=maxw and float(dark['width'])<=maxw)
            all_localized &= localized
            root_rows.append({'boundary_scale':b,'localized':localized,'saturation_bracket':sat,'strong_dark_bracket':dark,'event_margin_bounds_scale':r['event_margin_bounds_scale'],'unique_state_evaluations':r['unique_state_evaluations'],'all_states_numerical':r['all_states_numerical']})

    prod=float(CFG['fixed_physics']['production_boundary_scale']); positive=False
    if prod in roots and roots[prod]['saturation_bracket'] and roots[prod]['strong_dark_bracket']:
        positive=float(roots[prod]['event_margin_bounds_scale'][0])>0.0

    b1,b2=[float(x) for x in CFG['fixed_physics']['exterior_convergence_pair']]
    sat_shift=dark_shift=float('inf'); exterior_roots=False; route2_spread=float('inf'); route2_ok=False
    if b1 in roots and b2 in roots and roots[b1]['saturation_bracket'] and roots[b2]['saturation_bracket'] and roots[b1]['strong_dark_bracket'] and roots[b2]['strong_dark_bracket']:
        sat_shift=abs(float(roots[b1]['saturation_bracket']['midpoint'])-float(roots[b2]['saturation_bracket']['midpoint']))
        dark_shift=abs(float(roots[b1]['strong_dark_bracket']['midpoint'])-float(roots[b2]['strong_dark_bracket']['midpoint']))
        exterior_roots=max(sat_shift,dark_shift)<=float(G['exterior']['maximum_root_midpoint_shift_scale'])
        common=float(CFG['root_algorithm']['common_diagnostic_scale'])
        s1=state_at(roots[b1],common); s2=state_at(roots[b2],common)
        k1=np.asarray(s1['implicit']['Kq_Wb_per_m'],dtype=float)[:,1]; k2=np.asarray(s2['implicit']['Kq_Wb_per_m'],dtype=float)[:,1]
        route2_spread=relative(k1,k2)
        route2_ok=route2_spread<=float(G['exterior']['route_2_Kq_column_relative_spread_at_common_midpoint'])

    decisions={
        'implicit_shape_estimator_validated':estimator_ok,
        'all_boundary_roots_localized':bool(all_localized),
        'production_positive_certified_event_margin':bool(positive),
        'exterior_root_stability':bool(exterior_roots),
        'route_2_exterior_Kq_stability':bool(route2_ok),
    }
    overall=all(decisions.values())
    summary={
        'schema':'bfm5_tcz1m_directional_event_root_summary_v1','campaign_sha256':SHA,
        'scientific_contract_sha256':CFG['integrity']['scientific_contract_sha256'],
        'overall_directional_event_root_accepted':overall,'partitioned_decision':decisions,
        'estimator_validation':estimator,
        'roots_complete':roots_complete,'root_rows':root_rows,
        'production_boundary_scale':prod,
        'production_event_margin_bounds_scale':roots.get(prod,{}).get('event_margin_bounds_scale'),
        'exterior':{'pair':[b1,b2],'saturation_root_midpoint_shift_scale':sat_shift,'strong_dark_root_midpoint_shift_scale':dark_shift,'route_2_Kq_column_relative_spread_at_common_midpoint':route2_spread,'common_diagnostic_scale':float(CFG['root_algorithm']['common_diagnostic_scale'])},
        'claim_scope':CFG['claim_scope'],
    }
    (root/'summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print('BFM5_TCZ1M_SUMMARY='+json.dumps(decisions,sort_keys=True))
    print(json.dumps({'overall':overall,'decisions':decisions,'production_margin':summary['production_event_margin_bounds_scale'],'exterior':summary['exterior'],'roots':root_rows},indent=2))

if __name__=='__main__': main()
