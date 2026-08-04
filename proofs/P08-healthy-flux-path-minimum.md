[← Proof index](../PROOFS.md) · [Notation](P00-notation.md)

# P8 — Healthy flux-path minimum

Phạm vi: healthy cố định; không bypass, switch, keeper hoặc fault topology.

Với \(\mathbf R\succ0\):

\[
\ker(\mathbf N^T\mathbf R^{-1}\mathbf N)=\ker\mathbf N.
\]

Do \(\dim T_\Sigma^\perp=4\), mọi nghiệm cần \(m\ge4\).

## P8.1 — Cản trở số học của offset

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

## P8.2 — Construction \(m=4\) khi lattice-compatible

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

## P8.3 — Nếu ép các path độc lập

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
