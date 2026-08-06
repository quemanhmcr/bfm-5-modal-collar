from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "tcz1b" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

screen=json.loads((ROOT/'results/tcz1b/screening/summary.json').read_text())
rows=[r for r in screen['screening_rows'] if r['feasible']]
plt.figure(figsize=(8,5.5))
for r in rows:
    marker='o' if not r['pareto'] else 's'
    size=45+80*r['active_volume_ratio']
    plt.scatter(r['authority_ratio'],r['predicted_boundary_scale'],s=size,marker=marker,alpha=0.75)
    if r['selected_for_refinement']:
        plt.annotate(r['slug'],(r['authority_ratio'],r['predicted_boundary_scale']),xytext=(4,4),textcoords='offset points',fontsize=8)
plt.xlabel('Per-mm actuator authority / TCZ-1')
plt.ylabel('Predicted 5% boundary scale')
plt.title('TCZ-1B coarse FEA frontier (marker size = active volume ratio)')
plt.grid(True,alpha=0.25)
plt.tight_layout()
plt.savefig(OUT/'screening_frontier.png',dpi=180)
plt.close()

ref=json.loads((ROOT/'results/tcz1b/refinement/summary.json').read_text())
knee=json.loads((ROOT/'results/tcz1b/knee_refinement/summary.json').read_text())
plt.figure(figsize=(8,5.5))
plt.scatter([1.0],[ref['reference_tcz1_boundary_scale']],s=120,marker='o',label='TCZ-1')
for c in ref['candidate_summaries']:
    plt.scatter(c['screening']['authority_ratio'],c['boundary_scale'],s=80,marker='s')
    plt.annotate(c['slug'],(c['screening']['authority_ratio'],c['boundary_scale']),xytext=(4,4),textcoords='offset points',fontsize=8)
for c in knee['summaries']:
    plt.scatter(c['design']['authority_ratio'],c['boundary_scale'],s=95,marker='^')
    plt.annotate(c['slug'],(c['design']['authority_ratio'],c['boundary_scale']),xytext=(4,4),textcoords='offset points',fontsize=8)
plt.xlabel('Per-mm actuator authority / TCZ-1')
plt.ylabel('Converged strong-dark 5% boundary scale')
plt.title('Actual boundary–authority trade-off')
plt.grid(True,alpha=0.25)
plt.tight_layout()
plt.savefig(OUT/'boundary_authority_tradeoff.png',dpi=180)
plt.close()

winner=next(x for x in knee['summaries'] if x['slug']==knee['winner_slug'])
headroom=next(x for x in ref['candidate_summaries'] if x['slug']=='t15_g2_n1')
baseline=json.loads((ROOT/'results/tcz1/strong_dark_boundary/summary.json').read_text())
plt.figure(figsize=(8,5.5))
plt.plot([p['scale'] for p in baseline['merged_phase_curve']],[p['power_leakage'] for p in baseline['merged_phase_curve']],marker='o',label='TCZ-1')
plt.plot([p['scale'] for p in winner['phase_curve']],[p['strong_dark_discriminant'] for p in winner['phase_curve']],marker='s',label='TCZ-1B knee')
plt.plot([p['scale'] for p in headroom['phase_curve']],[p['strong_dark_discriminant'] for p in headroom['phase_curve']],marker='^',label='TCZ-1B headroom extreme')
plt.axhline(0.05,linestyle='--',label='5% gate')
plt.xlabel('Canonical current scale')
plt.ylabel('Strong-dark discriminant')
plt.title('Strong-dark phase boundary')
plt.yscale('log')
plt.grid(True,alpha=0.25)
plt.legend()
plt.tight_layout()
plt.savefig(OUT/'strong_dark_phase_comparison.png',dpi=180)
plt.close()

plt.figure(figsize=(8,5.5))
plt.plot([p['scale'] for p in winner['phase_curve']],[p['Xi_normalized'] for p in winner['phase_curve']],marker='o',label='Normalized Xi')
plt.plot([p['scale'] for p in winner['phase_curve']],[p['homogeneity_ratio_spread'] for p in winner['phase_curve']],marker='s',label='Homogeneity-ratio spread')
plt.xlabel('Canonical current scale')
plt.ylabel('Constitutive mismatch metric')
plt.title('TCZ-1B knee: route constitutive mismatch growth')
plt.grid(True,alpha=0.25)
plt.legend()
plt.tight_layout()
plt.savefig(OUT/'constitutive_mismatch_growth.png',dpi=180)
plt.close()

print(OUT)
