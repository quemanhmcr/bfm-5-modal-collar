# TCZ-1KQ nonlinear 3D numerical qualification

TCZ-1KQ is an independent finer-grid replay of the frozen TCZ-1K physics. It
exists because run `31143771001` missed the predeclared mesh and remote-boundary
limits by 0.72 and 1.88 percentage points, respectively.

The qualification does not relax a threshold and does not refit the TCZ-1J
calibration matrix, B-H law, current set, uncertainty set or affine depth law.
It freezes three new discretization levels before solving any field:

| Level | Mesh scale | Boundary scale | Preflight elements |
|---|---:|---:|---:|
| mesh-mid | 1.30 | 1.55 | 62,372 |
| mesh-fine / replay | 1.10 | 1.55 | 74,680 |
| boundary-far | 1.10 | 1.85 | 96,277 |

The same 5% convergence gates are applied between mesh-mid and mesh-fine, and
between mesh-fine and boundary-far. The fine grid then replays all five
operating points, all six uncertainty cases, both unseen depths and the full
nonlinear actuator-to-`Sym(2)` tangent.

The affine depth law remains a separate hypothesis. A depth-law failure does
not erase a qualified topology result, and no new depth coefficients are fit in
this stage.
