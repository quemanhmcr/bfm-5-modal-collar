# TCZ-1D: dark self-conditioning and the scheduled strong-dark root manifold

## Root formulation

For each current state define the unconditioned reference flux

\[
\psi_{ref}(i)=\psi(i,q_{sym}).
\]

Let

\[
K_q=\partial_q\psi,
\qquad
K_qd=0,
\qquad
b=\nabla_qW'.
\]

A full-system strong-dark conditioned state solves

\[
F(q;i)=
\begin{bmatrix}
\psi(i,q)-\psi_{ref}(i)\\
b(i,q)^Td(i,q)
\end{bmatrix}=0.
\]

This definition does not require route-local factorization. If the Jacobian

\[
\partial_qF\in\mathbb R^{3\times3}
\]

is nonsingular, the implicit-function theorem gives a local two-dimensional
root manifold

\[
q=q^*(i).
\]

## Nominal FEA root

At canonical current

\[
i=(1600,600)^T,
\]

the unconditioned symmetric gaps give

\[
\chi_{SD}=0.0803883.
\]

Predictor motion along the dark tangent followed by minimum-norm visible
Newton correction produced the full-system root

\[
q^\dagger=(2.002667,1.160716,1.553365)\ \mathrm{mm}.
\]

At this point

\[
\frac{|b^Td|}{\|b\|}=1.6021\times10^{-4},
\]

\[
\frac{\|\psi-\psi_{ref}\|}{\|\psi_{ref}\|}
=1.3377\times10^{-5}.
\]

The strong-dark leakage is reduced by 99.80%. Route-local Xi is not exactly
zero because the FEA route-locality residual is finite; this confirms that
signed full-system coupling is the correct final residual.

## Convergence

Across derivative steps 0.03, 0.06 and 0.12 mm and a refined mesh,

\[
7.08\times10^{-5}\le\chi_{SD}\le9.82\times10^{-4}.
\]

Maximum flux drift is 0.00147 and route-locality residual remains below
0.00470.

## Frozen root versus scheduled root

A frozen root is robust to plus/minus 2% current magnitude and 0.01 mm gap
errors, but not to plus/minus 2 degree current-angle changes. The dark axis
moves by roughly 5.5 to 6.4 degrees.

Solving the conditioned root at angle offsets -2, 0 and +2 degrees gives a
local schedule with maximum

\[
\chi_{SD}=1.1004\times10^{-3},
\]

maximum flux drift below 0.000161, and maximum required gap span 0.1195 mm.
This validates local existence of q*(i), but not yet dynamic tracking.

## Next decisive problem

TCZ-1E must track q*(i(t)) for a rotating current trajectory under actuator
slew, delay and energy constraints. The comparison must be terminal matched
and voltage controlled. The quantity to minimize is integrated electrical
port disturbance plus actuator cost, not instantaneous chi alone.
