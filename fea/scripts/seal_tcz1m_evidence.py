from __future__ import annotations
import argparse,hashlib,json,os,platform
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[1]
CFG_PATH=ROOT/'config/tcz1m_directional_event_root.yml'; CFG=yaml.safe_load(CFG_PATH.read_text())
SHA=hashlib.sha256(json.dumps(CFG,sort_keys=True,separators=(',',':')).encode()).hexdigest()
SOURCES=[
 'fea/config/tcz1m_directional_event_root.yml','fea/bfm5/tcz1m_3d.py','fea/scripts/run_tcz1m_directional_event_root.py','fea/scripts/analyze_tcz1m_directional_event_root.py','fea/scripts/seal_tcz1m_evidence.py','fea/tests/test_tcz1m_3d.py','fea/docs/TCZ1M_3D_DIRECTIONAL_EVENT_ROOT.md','.github/workflows/tcz1m-3d-event-root.yml',
 'fea/requirements-tcz1l-core.txt','fea/requirements-tcz1l-validation.txt','fea/requirements-tcz1l-analysis.txt','.github/actions/setup-fea3d/action.yml','fea/config/tcz1l_3d_saturation_critical_surface.yml','fea/scripts/run_tcz1l_3d_critical_surface.py','fea/bfm5/tcz1l_3d.py','fea/config/tcz1k_3d_nonlinear_holdout.yml','fea/scripts/run_tcz1k_3d_nonlinear_holdout.py']

def rec(p:Path,base:Path): return {'path':p.relative_to(base).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--evidence',type=Path,required=True); a=ap.parse_args(); evroot=a.evidence.resolve(); summary=json.loads((evroot/'summary.json').read_text())
 if summary.get('campaign_sha256')!=SHA: raise SystemExit('summary campaign hash mismatch')
 evidence=[]
 for p in sorted(x for x in evroot.rglob('*') if x.is_file() and x.name!='artifact_manifest.json'): evidence.append(rec(p,evroot))
 source=[]; errors=[]; repo=ROOT.parent
 for rel in SOURCES:
  p=repo/rel
  if not p.is_file(): errors.append('missing source '+rel); continue
  source.append(rec(p,repo))
 manifest={'schema':'bfm5_tcz1m_evidence_manifest_v1','campaign_sha256':SHA,'scientific_contract_sha256':CFG['integrity']['scientific_contract_sha256'],'github_run_id':os.getenv('GITHUB_RUN_ID',''),'git_sha':os.getenv('GITHUB_SHA',''),'platform':platform.platform(),'overall_directional_event_root_accepted':summary['overall_directional_event_root_accepted'],'partitioned_decision':summary['partitioned_decision'],'evidence_files':evidence,'source_files':source,'errors':errors}
 (evroot/'artifact_manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
 print('BFM5_TCZ1M_EVIDENCE='+('PASS' if not errors else 'FAIL')+' '+json.dumps({'evidence_files':len(evidence),'source_files':len(source),'campaign_sha256':SHA,'errors':errors},sort_keys=True))
 if errors: raise SystemExit('evidence source sealing failed')
 if not summary['overall_directional_event_root_accepted']: raise SystemExit('TCZ-1M directional event-root gate rejected by preregistered decision')

if __name__=='__main__': main()
