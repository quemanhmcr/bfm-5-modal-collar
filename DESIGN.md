# DESIGN — Cấu trúc hiện hành

**Revision:** D1. Đây là phát triển nối tiếp từ bản gốc O3, không phải bản gốc mới.

## D1 — Geometry đang sống

Nguồn:

```text
O3 fixed three-path collar
→ P2 fixed-collar impossibility
→ P5 rank change ≥ 2
→ D1 reconfigurable differential block
```

```text
SIX PHASE CONDUCTORS
        │
        ├── PERMANENT OUTER Z/CM PATH
        │      balanced torque → net MMF ≈ 0
        │      z+/common mode  → L high
        │
        └── SWITCHABLE INNER DIFFERENTIAL BLOCK
               αΔ gapped limb
               βΔ gapped limb
               one shared return keeper
```

## Hai trạng thái

| State | Keeper | Differential block | Outer Z/CM |
|---|---|---|---|
| Normal | seated | \(L_\Delta\) cao | active |
| Fault | withdrawn | gần leakage | active |

Một fault state dùng cho cả winding-set 1 và 2.

## Geometry rules

1. Sáu phase là sáu conductor liên tục và cách điện; keeper không nối điện phase.
2. Outer toroid không bị bypass.
3. Inner core có hai đường từ đối xứng \(\alpha_\Delta,\beta_\Delta\).
4. Một keeper chỉ được gọi là “one switch” nếu một bề mặt hỏng đơn thay đổi cả hai eigenvalues.
5. Mất nguồn actuator phải về fault/high-reluctance.
6. Mở keeper phải tăng reluctance và không làm \(B_{max}\) tăng.
7. Đóng keeper bị cấm khi \(|i_\Delta|\) vượt giới hạn.

## State operator

\[
\mathbf L_N=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_\Delta,
\]

\[
\mathbf L_F=\mathbf L_\sigma+\mathbf L_Z+\mathbf L_{\Delta,F}.
\]

Mục tiêu:

\[
\|\mathbf L_{\Delta,F}\|_2\ll\|\mathbf L_\Delta\|_2.
\]

## Transition

```text
fault detect
→ isolate failed set
→ reduce |iΔ|
→ arm DC-link/clamp energy path
→ withdraw keeper
→ verify position and measured modal state
→ derated limp-home
```

Năng lượng phải có nơi đi:

\[
E_{release}=\frac12\mathbf i^T(\mathbf L_N-\mathbf L_F)\mathbf i.
\]

## Parameter ledger — nguồn số duy nhất

| Symbol | Meaning | Current value | Status |
|---|---|---:|---|
| \(\rho\) | Fault torque fraction | O6 | TEAM TARGET |
| \(\gamma\) | Normal differential inductance floor | TBD | SYSTEM INPUT |
| \(\Lambda_{max}\) | Fault torque-plane inductance ceiling | TBD | SYSTEM INPUT |
| \(L_{z+}\) | Retained common-sum inductance | TBD | SYSTEM INPUT |
| \(\varepsilon_L=L_{\Delta,F}/L_{\Delta,N}\) | Residual ratio | TBD | TARGET |
| \(g_\alpha,g_\beta\) | Energy-storage gaps | TBD | FEA |
| \(g_K\) | Withdrawn keeper gap | TBD | FEA |
| \(A_\alpha,A_\beta,A_K\) | Effective areas | TBD | CAD/FEA |
| \(N_\alpha,N_\beta\) | Effective modal turns | TBD | ROUTING |
| \(B_{allow}\) | Flux-density ceiling | TBD | MATERIAL |
| \(I_{\Delta,open}\) | Max current before opening | TBD | TEST |
| \(E_{sink,rated}\) | Available transition-energy sink | TBD | INVERTER |
| \(\delta_e\) | Current-mat offset | O4/O6 | UNVALIDATED |

## Open decisions, theo thứ tự

1. Shared keeper có thật sự tạo rank-2 change dưới tolerance không?
2. Có cần path riêng cho \(z-\) không?
3. Magnetic keeper hay electrical bypass có mass/loss/reliability thấp hơn?
4. \(\delta_e^*\) cho rotor và current-mat cụ thể là bao nhiêu?
5. Các target 60 kW của team có sống qua voltage, loss và thermal budget không?
