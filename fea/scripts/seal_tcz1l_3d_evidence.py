from __future__ import annotations
import argparse, hashlib, json, os, platform
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parents[1]
CFG_PATH=ROOT/'config'/'tcz1l_3d_saturation_critical_surface.yml'
CFG=yaml.safe_load(CFG_PATH.read_text())
SHA=hashlib.sha256(json.dumps(CFG,sort_keys=True,separators=(',',':')).encode()).hexdigest()
SOURCES=[
 'fea/config/tcz1l_3d_saturation_critical_surface.yml','fea/bfm5/tcz1l_3d.py','fea/scripts/run_tcz1l_3d_critical_surface.py','fea/scripts/analyze_tcz1l_3d_critical_surface.py','fea/scripts/seal_tcz1l_3d_evidence.py','fea/tests/test_tcz1l_3d.py','.github/workflows/tcz1l-3d-saturation.yml','fea/config/tcz1k_3d_nonlinear_holdout.yml','fea/scripts/run_tcz1k_3d_nonlinear_holdout.py']

def rec(p:Path,base:Path): return {'path':p.relative_to(base).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--evidence',type=Path,required=True); a=ap.parse_args(); root=a.evidence.resolve()
 summary=json.loads((root/'summary.json').read_text())
 if summary['campaign_sha256']!=SHA: raise SystemExit('campaign hash mismatch')
 ev=[rec(p,root) for p in sorted(root.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json']
 source=[]; errors=[]
 repo=ROOT.parent
 for rel in SOURCES:
  p=repo/rel
  if not p.is_file(): errors.append('missing source '+rel); continue
  source.append({'path':rel,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 manifest={'schema':'bfm5_tcz1l_evidence_manifest_v1','campaign_sha256':SHA,'github_run_id':os.getenv('GITHUB_RUN_ID',''),'git_sha':os.getenv('GITHUB_SHA',''),'platform':platform.platform(),'overall_saturation_critical_surface_accepted':summary['overall_saturation_critical_surface_accepted'],'partitioned_decision':summary['partitioned_decision'],'evidence_files':ev,'source_files':source,'errors':errors}
 (root/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 if errors: raise SystemExit('; '.join(errors))
 if not summary['overall_saturation_critical_surface_accepted']: raise SystemExit('TCZ-1L saturation critical-surface holdout rejected by preregistered gate')
 print('BFM5_TCZ1L_EVIDENCE=PASS '+json.dumps({'campaign_sha256':SHA,'evidence_files':len(ev),'source_files':len(source)}))
if __name__=='__main__': main()
