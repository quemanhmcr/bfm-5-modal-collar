# TCZ-1F: remote current-state root atlas

TCZ-1F moves every FEMM solve off the workstation. Linux MCP is the control
plane; GitHub-hosted Windows runners are the FEMM data plane. A workflow run is
split into independently retryable operating-point shards and a Linux
aggregation stage.

## Root map

For current coordinates `(rho, theta)`, solve

\[
F(q;\rho,\theta)=
\begin{bmatrix}
\psi(i,q)-\psi_{ref}(i)\\
b(i,q)^T d(i,q)
\end{bmatrix}=0,
\qquad K_qd=0.
\]

The atlas stores `q*(rho,theta)`, dark axis, strong-dark residual, flux drift,
field stress, route locality and root-existence margins.

## Fold diagnostic without wasteful finite differences

Writing the root Jacobian as

\[
F_q=\begin{bmatrix}K_q\\c^T\end{bmatrix},
\]

and letting `d` span `ker(K_q)`, local root existence requires

\[
\sigma_2(K_q)>0,
\qquad c^Td\ne0.
\]

The second scalar is the derivative of signed dark-power coupling along the
iso-flux dark continuation. It is already identified by the corrected secant
bracket. Therefore TCZ-1F detects folds using port-rank and dark
transversality, rather than spending six additional seven-solve derivative
blocks at every root.

## Remote protocol

1. Ubuntu planner emits a JSON matrix from `config/tcz1f_grid.yml`.
2. Each Windows shard installs a SHA-pinned FEMM stable build and solves one
   full-system root.
3. A shard uploads JSON only, with a SHA-256 manifest. Large `.ans` and `.fem`
   files remain ephemeral unless a later forensic profile requests them.
4. Ubuntu aggregation verifies checksums, builds the atlas, estimates the root
   connection and reports gaps, failed roots and fold proximity.

No local FEMM invocation is part of this protocol.

## Induced geometry and root sheets

For a regular root sheet, the implicit connection is

\[
A(i)=-F_q^{-1}F_i=\frac{\partial q^\star}{\partial i}.
\]

An actuator effort metric `Gq` induces

\[
G_I=A^TG_qA
\]

on current-state space. This turns electrical path design into a geodesic
problem: two paths with identical endpoints can have very different actuator
cost even when both remain strong-dark.

The discriminant set is where either port rank is lost or dark
transversality vanishes. On a single regular graph sheet, closed continuation
must return to the same root. A branch permutation after a closed loop is not
ordinary curvature; it is evidence of multiple sheets or monodromy around the
discriminant. TCZ-1F aggregation therefore retains root identity and will later
run closed-cell continuation audits.

## Linux MCP submission

`ci/linux_orchestrate_tcz1f.sh PROFILE` is the durable control-plane entry
point. It updates a nonce-bearing request file, pushes the research branch,
locates the exact run by commit SHA, watches it, downloads all artifacts and
rejects aggregate output with checksum errors or failed shards. Expensive FEMM
runs are triggered only by changes to the workflow or request file; ordinary
code/documentation pushes are inert.

### Coordinate normalization

The raw condition number of `G_I` depends on the current-state coordinates:
current magnitude scale is dimensionless while angle is represented in
radians. Every atlas must therefore report both the raw tensor and a
workload-normalized tensor

\[
\bar G_I=D^TG_ID,
\qquad
D=\operatorname{diag}(\Delta\rho_c,\Delta\theta_c),
\]

for declared characteristic steps. Raw and normalized metrics answer different
questions and their condition numbers must not be conflated.
