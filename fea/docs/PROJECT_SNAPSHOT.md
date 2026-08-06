# BFM-5 / TCZ research snapshot

**Trạng thái:** TCZ-1H được chấp nhận trong miền cục bộ đã kiểm chứng.  
**Nguồn máy đọc:** [`../config/project_state.yml`](../config/project_state.yml).  
**Luật chi tiết hiện hành:** [`../config/design_laws_v8.yml`](../config/design_laws_v8.yml).

## 1. Hạt nhân topology

Hai electrical ports điều khiển ba magnetic branches qua Mercedes tight frame

\[
N=\begin{bmatrix}
1&0\\
-\tfrac12&\tfrac{\sqrt3}{2}\\
-\tfrac12&-\tfrac{\sqrt3}{2}
\end{bmatrix},
\qquad N^T\mathbf1=0,
\qquad N^TN=\tfrac32I.
\]

Branch space tách thành:

\[
\mathbb R^3=\operatorname{im}N\oplus\operatorname{span}(1,1,1).
\]

Electrical ports nhìn thấy balanced plane và không nhìn thấy zero-sequence line. Dark channel vì vậy là một carrier vật lý trong branch space, không phải nullspace tình cờ.

## 2. Điều kiện strong-dark đầy đủ

Với

\[
K_q=\frac{\partial\psi}{\partial q},
\qquad b=\nabla_qW',
\]

một hướng strong-dark phải thỏa đồng thời

\[
K_qd=0,
\qquad b^Td=0.
\]

State được condition theo dòng điện bằng nghiệm

\[
F(q;i)=
\begin{bmatrix}
\psi(i,q)-\psi_{\rm ref}(i)\\
b(i,q)^Td(i,q)
\end{bmatrix}=0.
\]

Route-local invariant

\[
\Xi=\sum_r\frac{b_r}{a_r}
\]

là search surrogate tốt; acceptance cuối luôn dùng full-system residual \(b^Td\).

## 3. Chuỗi kết quả đã chấp nhận

### TCZ-1B — symmetric saturation firewall

Geometry cân bằng được chọn:

- core thickness: **17.0 mm**;
- controlled gap: **1.75 mm**;
- matched planar depth: **22.83813 mm**.

Biên \(\chi_{\rm SD}=5\%\) tăng từ **2.203** lên **3.752** lần current scale, tức **+70.3%**. Trade-off: authority còn **57.4%**, active magnetic volume **1.80×**.

### TCZ-1C — static asymmetry

Static route precompensation tăng sector boundary **11.39%**, nhưng làm isotropic worst-direction boundary giảm **18.37%**. Kết luận: static asymmetry chỉ hợp workload sector, không phải universal improvement.

### TCZ-1D — dark self-conditioning

Trên cùng iso-flux manifold, full-system root

\[
q^\dagger=(2.002667,\ 1.160716,\ 1.553365)\ {\rm mm}
\]

giảm strong-dark residual **99.80%** so với symmetric state. Root phải được schedule theo current state: \(q=q^\star(i)\), không được đóng băng theo góc dòng.

### TCZ-1E — dynamic root tracking

Terminal-matched tracker đạt so với minimum-effort chord:

- RMS strong-dark residual: **−82.15%**;
- integrated metric-power squared: **−22.36%**;
- actuator effort: **+14.66%**.

Manifold-consistent voltage law được chấp nhận; cộng trực tiếp \(K_q\dot q\) gây double compensation và làm current error tăng **2.624×**.

### TCZ-1F — root-sheet geometry

Miền đã kiểm chứng:

\[
0.95\le\rho\le1.05,
\qquad -2^\circ\le\theta\le2^\circ.
\]

Root sheet là intrinsic saddle:

\[
K=-2.0832\ {\rm mm}^{-2},
\qquad k_1=-1.5287,
\qquad k_2=1.3628\ {\rm mm}^{-1}.
\]

Quadratic patch được xác nhận độc lập với max gap error **1.640 µm**. Không cần thêm FEA bên trong patch này nếu fold, interpolation hoặc quality gates chưa bị kích hoạt.

### TCZ-1G — dynamic path geometry

Không có universal path winner:

- geodesic: giảm electrical disturbance;
- slew-polytope: giảm minimum transition time;
- straight path: giảm actual actuator effort và là fallback trung tính.

Fixed nominal polytope path bị từ chối khi route-slew mismatch tăng; deadline path phải replan theo slew đã hiệu chuẩn.

### TCZ-1H — certified Pareto navigator

Kiến trúc được chấp nhận:

```text
learned proposal
      → exact local-physics correction
      → exact reduced-nonlinear replay of declared bank
      → three-corner dynamic certificate
      → winner
```

Oracle chỉ đề xuất, warm-start và xếp hàng. Nó không được chọn winner hoặc cấp safety certificate.

Candidate bank gồm 7 Pareto anchors, task shaping, continuous in-distribution proposal, straight fallback và fastest candidate. Claim chỉ là:

> exact optimum within the declared finite candidate bank.

Kết quả chính:

| Task | Winner | Objective ratio vs straight |
|---|---|---:|
| Metric-power weighted | `anchor_6` | **0.958007** |
| Actuator-voltage | `straight_fallback` | **1.000000** |
| Actuator-effort | `straight_fallback` | **1.000000** |
| Balanced | `straight_fallback` | **1.000000** |
| Deadline-balanced, 0.46 s | `oracle_continuous` | **0.873612** |

Deadline winner đồng thời giảm:

- metric-power squared: **23.03%**;
- actuator-voltage squared: **5.82%**;
- actuator effort: **9.06%**.

Mọi winner qua nominal, slow/delayed và fast-observer dynamic corners.

## 4. Execution policy

- **Không chạy FEMM trên workstation.**
- Linux MCP là control/analysis plane.
- FEMM chỉ chạy trên SHA-pinned GitHub Windows shards.
- TCZ-1G/H là solver-free và dùng immutable identified model data.
- Artifact phải có manifest và SHA-256 trước khi được dùng làm evidence.

## 5. Evidence quyết định

TCZ-1H remote cross-check:

- GitHub run: `31089597294`;
- evidence head: `adae6f09a20314a847a860e8d3e934ef7b199109`;
- `summary.json`: `a9a9da5937b703e55bf00a14079cec208ad45543223875c361419859983d4db1`;
- `artifact_manifest.json`: `2364ea2c5914bc90e61c943d50070b95753d00dfb68783c53c67d58cb88357e5`;
- local/remote winner and metric drift: **0**;
- final numerical regression: **97 passed**.

## 6. Giới hạn claim

Chưa được tuyên bố:

- global continuous optimum;
- validity ngoài TCZ-1F patch;
- hard-real-time oracle-only control;
- 3D end-effect equivalence;
- hardware actuator energy in joules khi chưa có actuator model/measurement;
- production readiness.

## 7. Bước được phép tiếp theo

Ưu tiên tiếp theo là hardware-calibrated/HIL navigation:

1. đo route-specific slew, lag và hysteresis;
2. cập nhật online calibration confidence;
3. replay candidate bank trên measured plant;
4. chỉ mở rộng FEA atlas khi fold, quality, interpolation hoặc domain gate yêu cầu.

Tài liệu chi tiết vẫn được giữ trong `docs/TCZ1*.md`; file này là entry point duy nhất để đọc nhanh trạng thái dự án.
