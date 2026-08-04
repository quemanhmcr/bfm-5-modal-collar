[← Proof index](../PROOFS.md) · [Notation](P00-notation.md)

# P5 — Minimal reconfiguration rank bound

Giả sử normal matrix:

\[
\ker\mathbf L_N=T_\Sigma,
\]

và:

\[
x^T\mathbf L_Nx\ge\gamma\|x\|^2,
\qquad x\in T_\Sigma^\perp.
\]

Với \(a=(x,0)\in T_1\), phân rã:

\[
a=\frac12(x,R_\delta x)+\frac12(x,-R_\delta x).
\]

Suy ra:

\[
a^T\mathbf L_Na\ge\frac\gamma2\|a\|^2.
\]

Nếu fault requirement là:

\[
a^T\mathbf L_Fa\le\Lambda_{max}\|a\|^2,
\qquad \Lambda_{max}<\frac\gamma2,
\]

thì trên không gian hai chiều \(T_1\):

\[
\mathbf L_N-\mathbf L_F\succ0.
\]

Do đó:

\[
\boxed{\operatorname{rank}(\mathbf L_N-\mathbf L_F)\ge2.}
\]

Nếu một phần tử vật lý thay đổi ma trận với hạng tối đa \(r_{max}\), thì:

\[
\boxed{s_{min}\ge\left\lceil\frac2{r_{max}}\right\rceil.}
\]

**Hệ quả:** một cơ cấu là tối thiểu chỉ khi chính cơ cấu đó thay đổi đồng thời cả hai differential axes.
