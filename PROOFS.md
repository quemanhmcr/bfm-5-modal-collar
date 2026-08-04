# PROOFS — Kết quả đã chứng minh

Chỉ chứa điều đã suy ra từ giả thiết rõ ràng. Geometry nằm trong [`DESIGN.md`](DESIGN.md).

## Notation

\[
T_3=\{x\in\mathbb R^3:\mathbf1^Tx=0\},
\]

\[
T_1=\{(x,0):x\in T_3\},\qquad
T_2=\{(0,y):y\in T_3\},
\]

\[
T_\Sigma=\{(x,R_\delta x):x\in T_3\},\qquad
T_\Delta=\{(x,-R_\delta x):x\in T_3\}.
\]

---

## P1 — Magnetic synthesis

Với effective-turn matrix \(\mathbf N\), reluctance matrix \(\boldsymbol{\mathcal R}\succ0\) và leakage \(\mathbf L_\sigma\succeq0\):

\[
\boxed{\mathbf L=\mathbf L_\sigma+\mathbf N^T\boldsymbol{\mathcal R}^{-1}\mathbf N.}
\]

**Hệ quả:** conductor routing chọn eigenvectors; gaps/core geometry chọn eigenvalues.

---

## P2 — Fixed-collar impossibility

Nếu một toán tử tuyến tính cố định thỏa

\[
\mathbf L_cT_1=0,\qquad \mathbf L_cT_2=0,
\]

thì do tuyến tính:

\[
\mathbf L_c(T_1\oplus T_2)=0.
\]

Mà:

\[
\boxed{T_1\oplus T_2=T_\Sigma\oplus T_\Delta,}
\]

nên:

\[
\boxed{\mathbf L_cT_\Delta=0.}
\]

**Hệ quả:** fixed collar không thể đồng thời vô hình cho hai single-set torque spaces và có inductance lớn trên differential torque space.

---

## P3 — Passive approximate bound

Với \(\mathbf L_c=\mathbf L_c^T\succeq0\), nếu worst-case single-set inductance không vượt \(L_{limp}\), thì Cauchy–Schwarz trong bán chuẩn \(\mathbf L_c\) cho:

\[
\boxed{L_\Delta\le2L_{limp}.}
\]

**Hệ quả:** single-set operation của một ideal differential collar nhìn thấy khoảng \(L_\Delta/2\). Limp-home có thể derate, nhưng không thể “miễn phí”.

---

## P4 — Một common toroid chỉ rank one

Với:

\[
\mathbf u_{z+}=\frac1{\sqrt6}[1,1,1,1,1,1]^T,
\]

một toroid chung đóng góp:

\[
\mathbf L_z=L_z\mathbf u_{z+}\mathbf u_{z+}^T.
\]

Do đó:

\[
\operatorname{rank}(\mathbf L_z)=1.
\]

Nó không tự động tạo inductance lớn cho:

\[
\mathbf u_{z-}=\frac1{\sqrt6}[1,1,1,-1,-1,-1]^T.
\]

**Hệ quả:** claim gốc hai eigenvalue \(z\) lớn cần một flux path độc lập thứ hai hoặc phải thu hẹp thành claim \(z+\).

---

## P5 — Minimal reconfiguration rank bound

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

---

## P6 — Một fault state chung là đủ

Tách:

\[
\mathbf L_N=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_\Delta.
\]

Chọn:

\[
\mathbf L_F=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_{\Delta,F},
\qquad \|\mathbf L_{\Delta,F}\|\ll\|\mathbf L_\Delta\|.
\]

Nếu \(\mathbf L_Z\) triệt tiêu balanced torque current của từng set, cùng một \(\mathbf L_F\) dùng được cho cả hai lỗi:

\[
\boxed{\mathbf L_{F1}=\mathbf L_{F2}=\mathbf L_F.}
\]

**Hệ quả:** không cần hai bypass độc lập theo winding set.

---

## P7 — PWM modal ripple relation

Từ:

\[
\mathbf v_m=\mathbf L_m\frac{d\mathbf i_m}{dt},
\]

trong một switching interval:

\[
\boxed{\Delta\mathbf i_m\approx\mathbf L_m^{-1}\widetilde{\mathbf v}_m\Delta t.}
\]

**Hệ quả:** với cùng voltage error, mode có inductance lớn sinh current ripple nhỏ hơn. Đây là nền toán của PWM error steering trong O5.

---

## Proof boundary

Chưa được chứng minh bằng các định lý trên:

- geometry thực đạt đúng \(\mathbf N\) mong muốn;
- một keeper duy nhất tạo rank-2 change dưới tolerance;
- lợi ích \(\delta_e\approx30^\circ\) với rotor cụ thể;
- PM loss, torque ripple, CM current và efficiency targets;
- stability và năng lượng trong chuyển trạng thái thực.
