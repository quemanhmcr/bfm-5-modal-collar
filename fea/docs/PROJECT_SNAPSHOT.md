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

## 8. Post-snapshot negative audit: adaptive deadline calibration

A frozen 32-episode controller-in-loop audit tested a direction-aware,
one-sided bounded-drift slew envelope as a possible next stage. The mathematical
bound was sound in the declared ensemble: zero lower-bound violations, 100%
feasibility recall, 2.20% median conservatism, and 3/3 representative dynamic
certificates passed.

The direction was nevertheless **rejected**. Frozen TCZ-1H and its existing
EWMA baseline also produced zero false-safe deadlines because the true worst
minimum-plus-reserve was only about 0.260 s against the 0.46 s task. The new
warm replanner also missed its 0.25 s p95 gate at 0.382 s. Thresholds and drift
were not changed after seeing the result.

Therefore the next bottleneck is not another synthetic calibrator or a larger
candidate bank. It is measured-plant/HIL identification of route/sign slew,
lag and hysteresis, plus deployment-hardware latency in a predeclared active
deadline regime. See
[`POST_TCZ1H_ADAPTIVE_DEADLINE_DECISION_MEMO.md`](POST_TCZ1H_ADAPTIVE_DEADLINE_DECISION_MEMO.md).

## 9. Accepted pre-HIL identification gate

The slew-only adaptive audit was followed by a frozen route/sign/reversal
identification protocol that includes plateau slew, first-order lag, deadtime,
temperature and load. The safety-side dynamic state is

\[
(s_-,	au_+,d_+),
\]

and route travel time is obtained by inverting

\[
|\Delta q|=s\left[u-	au(1-e^{-u/	au})
ight],\qquad T=d+u.
\]

On the declared nonlinear shadow rig, all predeclared gates passed:

- 816 total traces, including 288 untouched holdout traces;
- zero lower-slew, upper-lag or upper-deadtime holdout violations;
- median conservatism: 1.415% slew, 7.505% lag, 3.408 ms deadtime;
- correct reversal-effect sign in all 6 route/sign groups for all three
  quantities;
- frozen nominal model: 140 false-safe deadline-grid cases;
- calibrated bound: zero false-safe cases and 93.28% feasible recall;
- maximum active false-safe window: 214.04 ms;
- bound query p95: 0.352 ms;
- numerical regression: 105 passed.

This is accepted only as a measurement and analysis protocol. It does not alter
TCZ-1H, `design_laws_v8`, or the accepted tag. The next evidence step is to run
the frozen acquisition matrix on hardware/HIL, verify the same holdout gates,
replay the unchanged candidate bank on the measured plant, and measure
end-to-end deployment latency. See
[`POST_TCZ1H_HIL_IDENTIFICATION_GATE_DECISION_MEMO.md`](POST_TCZ1H_HIL_IDENTIFICATION_GATE_DECISION_MEMO.md)
and [`TCZ1H_HIL_MEASUREMENT_PROTOCOL.md`](TCZ1H_HIL_MEASUREMENT_PROTOCOL.md).

## 10. Qualified measured-waveform campaign capsule

The next methodological gap was closed without changing TCZ-1H. A three-phase
campaign transaction now freezes the protocol, fits only train/calibration raw
waveforms, seals the model artifact, and opens holdout without refitting:

```text
freeze -> fit -> seal -> open holdout
```

Position is the primary identification channel for the integrated first-order
response

\[
x(t)=s\left[u-\tau(1-e^{-u/\tau})\right],
\qquad u=\max(t-d,0),
\]

while measured velocity is retained as an independent coherence check. Raw keys
containing truth or oracle labels are rejected.

On the frozen 816-trace shadow qualification:

- clean raw validation errors: **0**;
- declared fault injections detected: **7/7**;
- literal holdout IDs in the sealed model: **0**;
- measured-estimate holdout violations for slew/lag/deadtime: **0/0/0**;
- shadow-oracle bound violations: **0/0/0**;
- median conservatism: **1.237%** slew, **6.053%** lag, **3.048 ms** deadtime;
- deterministic raw bundle and protocol hashes reproduced exactly;
- forbidden truth-generating imports in the measured analyzer: **0**;
- numerical regression: **110 passed**.

This accepts the campaign capsule as evidence infrastructure only. It does not
create TCZ-1I, hardware evidence, or a new design law. The next decisive step is
to acquire real HIL/actuator traces with the same lock and gates, then replay the
unchanged candidate bank and measure target-controller latency. See
[`POST_TCZ1H_MEASURED_CAMPAIGN_CAPSULE_DECISION_MEMO.md`](POST_TCZ1H_MEASURED_CAMPAIGN_CAPSULE_DECISION_MEMO.md)
and [`TCZ1H_MEASURED_CAMPAIGN_CAPSULE.md`](TCZ1H_MEASURED_CAMPAIGN_CAPSULE.md).

## 11. Local deployment gate: correct causality, rejected preparation time

A local Windows-only deployment audit qualified the monotone safety lattice

```text
HOLD -> certified straight fallback -> exact finite-bank winner
```

Snapshot mismatch and expiry returned HOLD; incomplete but valid evidence used
the straight fallback; a complete bank selected the exact finite-bank winner.
All integrity and request-time latency gates passed, with decision p99 about
0.3 microseconds even under CPU stress. The audit was nevertheless rejected:
preparing the exact straight-fallback certificate took **2.3498 s**, above its
frozen 1.0 s gate. Profiling placed **2.3794 s** in exact nonlinear replay and
only **6.5 ms** in straight-path construction.

The failure established the correct time-scale split: exact replay belongs to
the slow temperature/load calibration plane, not the fast request path. See
[`POST_TCZ1H_LOCAL_DEPLOYMENT_GATE_DECISION_MEMO.md`](POST_TCZ1H_LOCAL_DEPLOYMENT_GATE_DECISION_MEMO.md).

## 12. Accepted local exact fallback certificate atlas

The follow-up retained exact nonlinear replay but moved it offline onto a
frozen 5x5 temperature-load grid. Runtime adds sensor reserves, selects an upper
ceiling node, verifies its snapshot and bundle, and returns FALLBACK or HOLD.
No optimizer or nonlinear simulator lies on this fast path.

All 10 predeclared gates passed:

- 25 exact nodes, 15 certified and 10 explicitly rejected;
- active reserved node `45.5 C / 0.51 load` certified;
- offline build: **62.772 s**;
- lookup+arm+decision p99: **35.901 us** baseline and **77.301 us** under CPU stress;
- out-of-domain state returned HOLD;
- corrupted atlas was detected;
- all published nodes passed exact dynamic replay;
- local numerical regression: **117 passed**.

Every rejected node failed only the strong-dark discriminant. The finite-node
frontier was load 1.00 at 20 C, 0.75 at 35 C, 0.51 at 45.5 C, 0.25 at 55 C and
0 at 70 C. This suggests, but does not establish, the exploratory severity
coordinate

\[
\zeta=(T-20)/50+L.
\]

All sampled nodes with `zeta <= 1.05` passed and all with `zeta >= 1.21` failed;
the fitted gate crossing was about 1.165. This is a pre-registered HIL
hypothesis, not a design law or continuous physical certificate.

The atlas is accepted only as local deployment evidence infrastructure. TCZ-1H,
`design_laws_v8`, and the accepted tag remain unchanged. See
[`POST_TCZ1H_LOCAL_FALLBACK_ATLAS_DECISION_MEMO.md`](POST_TCZ1H_LOCAL_FALLBACK_ATLAS_DECISION_MEMO.md)
and [`TCZ1H_LOCAL_FALLBACK_CERTIFICATE_ATLAS.md`](TCZ1H_LOCAL_FALLBACK_CERTIFICATE_ATLAS.md).
