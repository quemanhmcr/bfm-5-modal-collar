from __future__ import annotations

import json
from pathlib import Path

import gmsh

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "gmsh_smoke"
OUT.mkdir(parents=True, exist_ok=True)


def main() -> None:
    gmsh.initialize()
    try:
        gmsh.option.setNumber("General.Terminal", 1)
        gmsh.model.add("bfm5_gmsh_smoke")
        box = gmsh.model.occ.addBox(0.0, 0.0, 0.0, 0.02, 0.01, 0.005)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [box], 1)
        gmsh.model.setPhysicalName(3, 1, "magnetic_domain")
        gmsh.option.setNumber("Mesh.CharacteristicLengthMin", 0.001)
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.003)
        gmsh.model.mesh.generate(3)
        node_tags, _, _ = gmsh.model.mesh.getNodes()
        element_types, element_tags, _ = gmsh.model.mesh.getElements(3)
        element_count = sum(len(tags) for tags in element_tags)
        mesh_path = OUT / "box.msh"
        gmsh.write(str(mesh_path))
        report = {
            "node_count": int(len(node_tags)),
            "volume_element_count": int(element_count),
            "element_types": [int(v) for v in element_types],
            "mesh": str(mesh_path),
        }
        if report["node_count"] <= 0 or report["volume_element_count"] <= 0:
            raise RuntimeError(f"Invalid Gmsh mesh report: {report}")
        (OUT / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
    finally:
        gmsh.finalize()


if __name__ == "__main__":
    main()
