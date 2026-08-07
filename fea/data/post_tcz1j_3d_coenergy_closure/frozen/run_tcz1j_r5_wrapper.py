from __future__ import annotations
import hashlib, json, os, pathlib, subprocess, tarfile, time
base=pathlib.Path('/content/bfm5')
out=base/'tcz1j-same-mesh-r5'
env=os.environ.copy()
env.update({
    'BFM5_TCZ1J_OUT':str(out),
    'BFM5_TCZ1J_BASE_SCRIPT':str(base/'run_tcz1j_full_campaign.py'),
    'OMP_NUM_THREADS':'2',
    'OPENBLAS_NUM_THREADS':'2',
    'MKL_NUM_THREADS':'2',
    'NUMBA_NUM_THREADS':'2',
})
t0=time.perf_counter()
p=subprocess.run([str(base/'venv/bin/python'),str(base/'run_tcz1j_same_mesh_closure.py')],env=env,text=True,capture_output=True,timeout=7000)
print(p.stdout)
if p.stderr: print(p.stderr)
if p.returncode: raise SystemExit(p.returncode)
summary=json.loads((out/'summary.json').read_text())
runtime={
    'schema':'bfm5_tcz1j_colab_r5_runtime_v1',
    'wall_s':time.perf_counter()-t0,
    'cpu_count':os.cpu_count(),
    'thread_env':{k:env[k] for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMBA_NUM_THREADS')},
    'base_script_sha256':hashlib.sha256((base/'run_tcz1j_full_campaign.py').read_bytes()).hexdigest(),
    'closure_script_sha256':hashlib.sha256((base/'run_tcz1j_same_mesh_closure.py').read_bytes()).hexdigest(),
    'campaign_sha256':summary['campaign_sha256'],
    'topology_closure_accepted':summary['topology_closure_accepted'],
    'planar_depth_gauge_accepted':summary['planar_depth_gauge_accepted'],
}
(out/'runtime_r5.json').write_text(json.dumps(runtime,indent=2,sort_keys=True)+'\n')
tar_path=base/'tcz1j-same-mesh-r5-evidence.tar.gz'
with tarfile.open(tar_path,'w:gz') as tf: tf.add(out,arcname=out.name)
h=hashlib.sha256(tar_path.read_bytes()).hexdigest()
print('BFM5_TCZ1J_R5='+json.dumps({'runtime':runtime,'tar_bytes':tar_path.stat().st_size,'tar_sha256':h},sort_keys=True))
