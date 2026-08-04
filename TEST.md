# TEST — Kill order

Không tối ưu toàn hệ thống trước khi primitive sống qua test trước đó.


## T0 — Routing and offset certificate

### T0A — Exact feasibility

Reproduce P8 before CAD:

- literal \(30^\circ\), one-pass ternary, exact null: valid-row span = 2 → FAIL;
- lattice-compatible angle: \(N_4\) and \(N_5\) rank 4 → PASS.

### T0B — D2 approximate-null optimizer

Sweep \(\delta_e\) and admissible differential row orbits. Minimize:

\[
J=w_\Sigma\varepsilon_\Sigma^2+w_{Cu}l_{Cu}+w_BB_{\Sigma,pk}^2+w_LL_{split}^2.
\]

Constraints:

1. three differential rows form a C3 orbit;
2. row sum is zero within each winding set;
3. differential rank is two;
4. \(z+\) and \(z-\) rows remain independent;
5. routing is physically embeddable;
6. residual flux and loss stay below budget.

Kill D2 if no point near the rotor-optimal \(\delta_e\) satisfies both differential coupling and residual torque-flux budgets.

## T1 — Rig A: six-port collar

Đo:

\[
\mathbf Z(\omega,I,T,q)=\mathbf R+j\omega\mathbf L,
\qquad q\in\{N,F\}.
\]

Biến đổi:

\[
\mathbf L_m=\mathbf T\frac{\mathbf L+\mathbf L^T}{2}\mathbf T^T.
\]

### Kill criteria

Giết D2 nếu một trong các điều sau xảy ra:

1. normal torque subspace không gần null;
2. hai differential eigenvalues không cùng tăng;
3. \(\operatorname{rank}(\mathbf L_N-\mathbf L_F)<2\) trên noise floor;
4. fault residual vượt \(\Lambda_{max}\);
5. torque residual tại \(\delta_e^*\) vượt flux/loss budget;
6. \(z+\) hoặc \(z-\) bị mất trong fault state;
7. một differential branch stuck tạo modal asymmetry hoặc saturation không chấp nhận được;
8. intermediate state có \(B_{max}\) lớn hơn endpoints;
9. transition energy vượt sink;
10. một lỗi đơn tạo phase short hoặc mất conductor continuity.

### Output tối thiểu

- raw complex \(6\times6\) matrices;
- modal matrices;
- eigenvalues và principal angles;
- \(B(I,q)\), loss \((f,I,T,q)\);
- N→F voltage/energy transient;
- một dòng PASS/FAIL cho từng criterion.

## T2 — Rig B: PWM × collar

Chỉ chạy sau T1.

Kiểm tra O5/P7:

- cùng \(v_{\alpha\beta}^*\), chọn switching state khác nhau;
- đo error allocation trong \(xy,z\);
- so ripple/loss với và không dùng modal cost function.

Kill nếu giảm ripple không bù được extra collar loss hoặc common-mode stress.

## T3 — Rig C: current-mat × rotor

Chỉ chạy sau T2.

Sweep \(\delta_e\), đo hoặc tính:

- fundamental field;
- harmonic 5/7 và các harmonic rotor thực nhạy;
- PM eddy loss;
- torque ripple;
- AC copper loss.

Không đóng băng \(30^\circ\) trước optimum thực.

## T4 — Rig D: common mode

Đo:

- common-mode current;
- shell current;
- bearing voltage/current;
- retained Z/CM impedance ở fault state;
- ảnh hưởng segmented cold shell.

## Research loop

```text
Một câu hỏi
→ một model tối thiểu
→ một test có thể bác bỏ
→ update DESIGN.md
→ commit
```
