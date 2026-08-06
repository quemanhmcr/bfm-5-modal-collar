from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bfm5.topology import euler_compatibility_report


def spread(values):
    a=np.asarray(values,float)
    return float((a.max()-a.min())/(np.mean(np.abs(a))+1e-30))


def main():
    path=ROOT/'results'/'tcz1b'/'winner_validation'/'summary.json'
    d=json.loads(path.read_text())
    for group in ('step_points','mesh_points'):
        for p in d[group]:
            p['euler_compatibility']=euler_compatibility_report(
                p['branch_mmf'],p['route_response_a_Wb_per_mm'],p['coenergy_gradient_J_per_mm']
            )
    steps=d['step_points']; meshes=d['mesh_points']
    conv={
        'step_chi_relative_spread':spread([p['normalized_power_leakage'] for p in steps[:2]]),
        'step_Xi_relative_spread':spread([p['Xi_normalized'] for p in steps[:2]]),
        'step_euler_defect_norm_relative_spread':spread([
            p['euler_compatibility']['euler_defect_norm_normalized'] for p in steps[:2]
        ]),
        'mesh_chi_relative_spread':spread([p['normalized_power_leakage'] for p in meshes]),
        'mesh_Xi_relative_spread':spread([p['Xi_normalized'] for p in meshes]),
        'mesh_Gamma_relative_spread':spread([p['gap_coenergy_fraction'] for p in meshes]),
    }
    checks={k:v<=0.05 for k,v in conv.items()}
    d['convergence']=conv
    d['convergence_checks']=checks
    d['passed']=bool(all(checks.values()) and all(d['tolerance_checks'].values()))
    path.write_text(json.dumps(d,indent=2),encoding='utf-8')
    print(json.dumps({'convergence':conv,'checks':checks,'tolerance':d['tolerance_metrics'],'passed':d['passed']},indent=2))

if __name__=='__main__':
    main()
