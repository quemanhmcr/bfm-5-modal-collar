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


## P8 — Healthy flux-path minimum

Phạm vi: healthy cố định; không bypass, switch, keeper hoặc fault topology.

Với \(\mathbf R\succ0\):

\[
\ker(\mathbf N^T\mathbf R^{-1}\mathbf N)=\ker\mathbf N.
\]

Do \(\dim T_\Sigma^\perp=4\), mọi nghiệm cần \(m\ge4\).

### P8.1 — Cản trở số học của offset

Với một row \(n=(a,b)\), \(a,b\in\{-1,0,1\}^3\), đặt

\[
\chi(a)=a_u+\omega a_v+\omega^2a_w,\qquad \omega=e^{2\pi i/3}.
\]

Điều kiện \(n\perp T_\Sigma\) tương đương

\[
\chi(a)+e^{-i\delta}\chi(b)=0.
\]

Với vector ternary, \(|\chi|^2\in\{0,1,3,4\}\); trên mỗi shell khác zero, các hướng chỉ cách nhau bội \(60^\circ\). Vì vậy row có thành phần torque khác zero chỉ tồn tại khi

\[
\boxed{\delta\in60^\circ\mathbb Z.}
\]

Nếu \(\delta=30^\circ\), mọi row null chỉ là zero-sequence; \(\operatorname{rank}N\le2\). Do đó

\[
\boxed{m_{min}=+\infty}
\]

cho exact-null + one-pass ternary routing tại offset \(30^\circ\).

### P8.2 — Construction \(m=4\) khi lattice-compatible

Xét \(\delta=0\); các offset \(k60^\circ\) nhận được bằng signed cyclic relabeling của set 2. Chọn

\[
\mathbf N_4=
\begin{bmatrix}
1&1&0&-1&-1&0\\
0&1&1&0&-1&-1\\
1&0&1&-1&0&-1\\
1&1&1&1&1&1
\end{bmatrix}.
\]

Ba row đầu là một orbit ba pha; row cuối là common-sum path. Từ \(N_4i=0\) suy ra \(i_1=i_2\) và \(\mathbf1^Ti_1=0\), nên

\[
\ker N_4=T_\Sigma.
\]

Trong path space của ba row đầu, đặt

\[
P_0=\frac13\mathbf1\mathbf1^T,\qquad P_2=I-P_0,
\]

\[
\mathbf R^{-1}=
\begin{bmatrix}
g_hP_2+g_-P_0&0\\
0&g_+
\end{bmatrix},\qquad g_h,g_-,g_+>0.
\]

Trong basis \((\alpha_\Sigma,\beta_\Sigma,\alpha_\Delta,\beta_\Delta,z_+,z_-)\):

\[
\boxed{
\mathbf L_m=\operatorname{diag}(0,0,2g_h,2g_h,6g_+,8g_-).
}
\]

Do đó exact torque null, equal \(xy\) eigenvalues và hai zero eigenvalues độc lập đều đạt với bốn path. Kết hợp cận rank:

\[
\boxed{m_{min}=4}
\]

khi offset lattice-compatible và cho phép reluctance matrix coupled, reciprocal.

### P8.3 — Nếu ép các path độc lập

Giả sử topology và reluctance đều C3-symmetric, còn \(\mathbf R\) diagonal. Mọi differential row khác zero có C3 orbit kích thước 3; không có real one-dimensional differential orbit dưới phép quay \(120^\circ\). Vì vậy cần ít nhất ba branch cho equal \(xy\) response.

Với \(m=4\), path còn lại chỉ cho thêm một scalar reluctance. Sau khi cố định gain của orbit để cố định \(L_h\), chỉ còn một continuous knob cho zero subspace; không thể chỉnh độc lập cả \(L_{z+}\) và \(L_{z-}\). Do đó strong independent tuning buộc \(m\ge5\).

Construction bốn path vẫn hoạt động nhưng khóa một quan hệ phổ; với equal gain trên ba branch:

\[
L_{z-}=4L_h.
\]

Nếu \(L_h,L_{z+},L_{z-}\) phải là ba knob độc lập, cần năm path. Một construction là

\[
\mathbf N_5=
\begin{bmatrix}
1&-1&0&-1&1&0\\
0&1&-1&0&-1&1\\
-1&0&1&1&0&-1\\
1&1&1&1&1&1\\
1&1&1&-1&-1&-1
\end{bmatrix}.
\]

Với \(\mathbf R^{-1}=\operatorname{diag}(p,p,p,q_+,q_-)\):

\[
\mathbf L_m=\operatorname{diag}(0,0,6p,6p,6q_+,6q_-).
\]

**Hệ quả thiết kế:** đáp án là 4, 5 hoặc vô nghiệm tùy đúng mô hình vật lý; không được nói “m=4” mà bỏ qua offset và cấu trúc của \(R\).

---

## Proof boundary

Chưa được chứng minh bằng các định lý trên:

- geometry thực đạt đúng \(\mathbf N\) mong muốn;
- một keeper duy nhất tạo rank-2 change dưới tolerance;
- lợi ích \(\delta_e\approx30^\circ\) với rotor cụ thể;
- PM loss, torque ripple, CM current và efficiency targets;
- stability và năng lượng trong chuyển trạng thái thực.
