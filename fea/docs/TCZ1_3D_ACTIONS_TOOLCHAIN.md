# TCZ-1 3D Actions toolchain

The reusable Linux layer is defined by:

- `fea/requirements-tcz1-3d.txt`: exact CPython 3.12 wheel closure;
- `fea/ci/install_getdp_linux.sh`: checksum-pinned GetDP 3.5.0 installer;
- `.github/actions/setup-fea3d/action.yml`: reusable setup and GitHub cache adapter;
- `.github/workflows/tcz1-3d-toolchain.yml`: cache prewarm and reuse proof;
- `fea/scripts/fea3d_toolchain_smoke.py`: functional 3D solver/data-stack gate.

Future 3D workflows should use the local action after checkout:

```yaml
- uses: ./.github/actions/setup-fea3d
  with:
    python-version: '3.12'
    cache-generation: v1
```

The action creates `.venv-fea3d`, restores or builds the complete binary
wheelhouse, installs from that wheelhouse with `--no-index`, restores GetDP,
and exports `GETDP`, `GETDP_ROOT`, `VIRTUAL_ENV` and the virtual-environment
`bin` directory for subsequent steps.

The prewarm workflow is not accepted merely because downloads succeed. It must
pass Gmsh tetrahedral meshing, meshio import, NGSolve finite-element-space
construction, a real GetDP magnetostatic solve, OpenTURNS/PyVista/HDF5/xarray
smokes, and then prove in a second job that both caches are hits.
