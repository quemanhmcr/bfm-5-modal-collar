# BFM-5 open-source FEA workspace

Installed stack:

- FEMM 4.2 stable at `C:\femm42\bin\femm.exe`;
- pyFEMM in the local Python virtual environment;
- Gmsh 4.15.2 CLI and Python API;
- GetDP 3.5.0 at `C:\project\fea-tools\getdp-3.5.0\getdp-3.5.0-Windows64\getdp.exe`;
- NumPy, SciPy, pandas, Matplotlib, meshio, pytest and JupyterLab.

## Run validation

From Git Bash:

```bash
cd /c/project/liqi_match/bfm5_fea
./run_smoke_tests.sh
```

From PowerShell:

```powershell
cd C:\project\liqi_match\bfm5_fea
.\run_smoke_tests.ps1
```

## Start JupyterLab

```bash
./.venv/Scripts/python.exe -m jupyterlab
```

The FEMM smoke test builds and solves a nonlinear axisymmetric magnetic model and records current, flux linkage, inductance and core flux density under `results/femm_smoke/`.

## Pre-FEA topology authority

Before any BFM-5 CAD is accepted, read and enforce:

- `docs/TOPOLOGY_CHARTER.md` — mathematical and physical definition;
- `config/topology_v1.yml` — machine-readable contract and acceptance gates;
- `bfm5/topology.py` — invariant metrics and dark-channel primitives;
- `scripts/validate_topology.py` — ideal-topology reference report.

The central design is a Mercedes tight-frame winding incidence: the two
electrical ports observe the balanced plane of a three-branch magnetic space,
while the common/zero-sequence branch line is hidden. FEA geometry must realize
this decomposition with low route-locality and nonlinear-compatibility error;
it must not redefine the topology after the fact.

## Accepted symmetric reference: TCZ-1B-knee

The gauge-reduced FEA optimizer selected a 17 mm core thickness, 1.75 mm
controlled gap and 22.838 mm matched planar depth. Its converged 5% strong-dark
boundary is 3.752x the base current, versus 2.203x for TCZ-1. Frozen-command
tolerance replay passes for +/-0.03 mm gap errors and +/-0.2 mm core-thickness
errors. See `docs/TCZ1B_DECISION_MEMO.md` and
`config/geometry_tcz1b_winner.yml`.

## TCZ-1C / TCZ-1D results

- `docs/TCZ1C_DECISION_MEMO.md`: static workload-aware precompensation and its isotropic penalty.
- `docs/TCZ1D_DARK_SELF_CONDITIONING.md`: iso-flux strong-dark root and local scheduled-root manifold.
- `config/tcz1d_scheduled_root.yml`: machine-readable root schedule around the nominal current direction.
- `scripts/solve_full_strong_dark_root.py`: solves the full residual `b^T d = 0`, not only route-local `Xi = 0`.

## TCZ-1E dynamic root tracking

The accepted dynamic workflow is documented in
`docs/TCZ1E_DYNAMIC_ROOT_TRACKING.md`. The machine-readable policies are in
`config/tcz1e_policies.yml`, dynamic laws in `config/design_laws_v4.yml`, and
final results in `results/tcz1e/final_benchmark/summary.json`.

## Remote-only FEMM policy

From TCZ-1F onward, workstation FEMM execution is disabled by project policy.
Use the private GitHub Actions workflow `TCZ-1F Remote Root Atlas`. Linux MCP
acts as the orchestration and artifact-analysis plane; FEMM runs only on
SHA-pinned GitHub-hosted Windows shards. See `docs/TCZ1F_REMOTE_ROOT_ATLAS.md`.

## TCZ-1F status

The local current-state root sheet on magnitude scale `[0.95, 1.05]` and angle
`[-2 deg, 2 deg]` is independently validated. It is an intrinsic saddle and is
represented by an accepted quadratic root patch. See
`docs/TCZ1F_DECISION_MEMO.md` and `config/tcz1f_local_patch.yml`. No further
FEA is authorized inside this patch before the TCZ-1G dynamic geodesic test.
