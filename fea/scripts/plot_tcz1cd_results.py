from __future__ import annotations
import json
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'results'/'tcz1d'/'figures';out.mkdir(parents=True,exist_ok=True)

sector=json.loads((ROOT/'results/tcz1c/full_sector_validation/summary.json').read_text())
iso=json.loads((ROOT/'results/tcz1c/isotropic_penalty/summary.json').read_text())
labels=['Sector worst','Isotropic worst']
sym=[next(x for x in sector['designs'] if x['name']=='symmetric')['validated_sector_boundary_scale'], next(x for x in iso['designs'] if x['name']=='symmetric')['crossing']['scale']]
pre=[next(x for x in sector['designs'] if x['name']=='sector_precompensated')['validated_sector_boundary_scale'], next(x for x in iso['designs'] if x['name']=='sector_precompensated')['crossing']['scale']]
x=np.arange(2);w=.35
fig,ax=plt.subplots(figsize=(7,4.5));ax.bar(x-w/2,sym,w,label='Symmetric');ax.bar(x+w/2,pre,w,label='Static precompensated');ax.set_xticks(x,labels);ax.set_ylabel('5% strong-dark boundary scale');ax.legend();ax.grid(axis='y',alpha=.25);fig.tight_layout();fig.savefig(out/'static_precomp_tradeoff.png',dpi=180);plt.close(fig)

scan=json.loads((ROOT/'results/tcz1d/initial_dark_scan/summary.json').read_text())
a=np.array([p['alpha_mm'] for p in scan['points']]);chi=np.array([p['normalized_power_leakage'] for p in scan['points']]);drift=np.array([p['flux_drift_normalized'] for p in scan['points']])
fig,ax=plt.subplots(figsize=(7,4.5));ax.plot(a,chi,'o-',label='Strong-dark discriminant');ax.plot(a,drift,'s-',label='Flux drift');ax.set_xlabel('Initial dark-tangent displacement (mm)');ax.set_ylabel('Normalized residual');ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/'dark_predictor_scan.png',dpi=180);plt.close(fig)

sched=json.loads((ROOT/'results/tcz1d/scheduled_angle_roots/summary.json').read_text())
angles=np.array([p['offset_deg'] for p in sched['schedule']]);gaps=np.array([p['gaps_mm'] for p in sched['schedule']]);chis=np.array([p['strong_dark_discriminant'] for p in sched['schedule']])
fig,ax=plt.subplots(figsize=(7,4.5));
for r in range(3):ax.plot(angles,gaps[:,r],'o-',label=f'gap {r+1}')
ax.set_xlabel('Current-angle offset (deg)');ax.set_ylabel('Scheduled gap (mm)');ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(out/'scheduled_root_gaps.png',dpi=180);plt.close(fig)
fig,ax=plt.subplots(figsize=(7,4.5));ax.plot(angles,chis,'o-');ax.set_xlabel('Current-angle offset (deg)');ax.set_ylabel('Strong-dark discriminant');ax.grid(alpha=.25);fig.tight_layout();fig.savefig(out/'scheduled_root_quality.png',dpi=180);plt.close(fig)
print(out)
