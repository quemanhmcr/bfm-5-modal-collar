# TCZ-1F directional-witness continuation

The full derivative witness costs one baseline plus six gap perturbations per
state. It is retained as the anchor and acceptance audit, but it is wasteful at
every nearby continuation point.

For root finding, the third equation needs only

\[
r=b^Td=\frac{dW'(q+sd)}{ds}\bigg|_{s=0},
\]

which is measured by two directional coenergy solves. The two flux equations
are measured by one baseline solve. Between full anchors, transport the port
Jacobian with the minimum-Frobenius Broyden update

\[
K^+=K+\frac{(\Delta\psi-K\Delta q)\Delta q^T}{\Delta q^T\Delta q}.
\]

Thus a predicted continuation point needs three solves before corrections,
instead of seven. A full witness refresh is mandatory when transport age,
relative Jacobian update, port condition, flux-secant residual, or fold risk
crosses a declared threshold.

This is not a replacement for FEA derivatives. It is a certified transport
layer between full derivative anchors. Every accepted atlas region retains
full-witness points for convergence and bias auditing.
