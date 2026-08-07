"""Functional smoke and immutable manifest for the Linux 3D FEA toolchain."""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

import gmsh
import h5py
import meshio
import ngsolve
import numpy as np
import openturns as ot
import pyvista as pv
import xarray as xr
from netgen.occ import Box, Pnt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results_ci" / "fea3d_toolchain"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_versions() -> dict[str, str]:
    names = [
        "gmsh", "ngsolve", "netgen-mesher", "openturns", "pyvista", "vtk",
        "SALib", "meshio", "numpy", "scipy", "pandas", "PyYAML", "h5py",
        "xarray", "scikit-learn", "scikit-optimize", "matplotlib", "psutil",
        "pytest",
    ]
    return {name: importlib.metadata.version(name) for name in names}


def gmsh_mesh_smoke(tmp: Path) -> dict[str, int]:
    mesh_path = tmp / "box.msh"
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.model.add("bfm5_fea3d_toolchain")
        volume = gmsh.model.occ.addBox(0.0, 0.0, 0.0, 0.02, 0.01, 0.005)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [volume], 1)
        gmsh.model.setPhysicalName(3, 1, "magnetic_domain")
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", 0.001)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.003)
        gmsh.model.mesh.generate(3)
        nodes, _, _ = gmsh.model.mesh.getNodes()
        _, element_tags, _ = gmsh.model.mesh.getElements(3)
        volume_elements = sum(len(tags) for tags in element_tags)
        gmsh.write(str(mesh_path))
    finally:
        gmsh.finalize()
    imported = meshio.read(mesh_path)
    if len(imported.cells) == 0:
        raise RuntimeError("meshio did not recover any Gmsh cells")
    return {
        "nodes": int(len(nodes)),
        "volume_elements": int(volume_elements),
        "meshio_cell_blocks": int(len(imported.cells)),
    }


def ngsolve_smoke() -> dict[str, int]:
    generated = Box(Pnt(0, 0, 0), Pnt(1, 1, 1)).GenerateMesh(maxh=0.55)
    try:
        fes = ngsolve.H1(generated, order=1)
        mesh = generated
    except TypeError:
        mesh = ngsolve.Mesh(generated)
        fes = ngsolve.H1(mesh, order=1)
    return {"elements": int(mesh.ne), "h1_ndof": int(fes.ndof)}


def getdp_smoke(tmp: Path) -> dict[str, object]:
    executable = Path(os.environ.get("GETDP", shutil.which("getdp") or ""))
    if not executable.is_file():
        raise RuntimeError(f"GetDP executable not found: {executable}")
    version = subprocess.run(
        [str(executable), "-version"], check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    ).stdout.strip()
    root = executable.parent.parent
    doc_root = root / "share" / "doc" / "getdp"
    sandbox = tmp / "getdp-doc"
    shutil.copytree(doc_root, sandbox)
    work = sandbox / "examples"
    subprocess.run(
        [str(executable), "magnet.pro", "-solve", "Magnetostatics_phi", "-pos", "phi"],
        cwd=work, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    result = work / "phi.pos"
    if not result.is_file() or result.stat().st_size == 0:
        raise RuntimeError("GetDP magnetostatic example produced no phi.pos")
    return {
        "version_output": version,
        "binary_sha256": sha256(executable),
        "magnetostatic_result_bytes": int(result.stat().st_size),
        "magnetostatic_result_sha256": sha256(result),
    }


def data_stack_smoke(tmp: Path) -> dict[str, object]:
    h5_path = tmp / "field.h5"
    values = np.arange(12, dtype=float).reshape(3, 4)
    with h5py.File(h5_path, "w") as handle:
        handle.create_dataset("B", data=values)
    with h5py.File(h5_path, "r") as handle:
        recovered = np.asarray(handle["B"])
    if not np.array_equal(values, recovered):
        raise RuntimeError("HDF5 round-trip mismatch")
    data = xr.DataArray(values, dims=("route", "sample"))
    sphere = pv.Sphere(theta_resolution=8, phi_resolution=8)
    distribution = ot.Normal(3)
    return {
        "hdf5_sha256": sha256(h5_path),
        "xarray_shape": list(data.shape),
        "pyvista_cells": int(sphere.n_cells),
        "openturns_dimension": int(distribution.getDimension()),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="bfm5-fea3d-") as directory:
        tmp = Path(directory)
        report = {
            "schema": "bfm5_fea3d_toolchain_smoke_v1",
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "packages": package_versions(),
            "gmsh": gmsh_mesh_smoke(tmp),
            "ngsolve": ngsolve_smoke(),
            "getdp": getdp_smoke(tmp),
            "data_stack": data_stack_smoke(tmp),
        }
    output = OUT / "toolchain_manifest.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("BFM5_FEA3D_TOOLCHAIN=PASS")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
