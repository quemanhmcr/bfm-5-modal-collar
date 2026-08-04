# PROOFS — Chỉ mục

Toán chi tiết chỉ mở khi cần kiểm tra. [Notation](proofs/P00-notation.md).

| # | Chứng minh | Đóng góp cho BFM-5 | Chi tiết |
|---:|---|---|---|
| 1 | \(L=L_\sigma+N^T\mathcal R^{-1}N\). | Routing chọn modal directions; magnetic geometry chọn modal levels. | [P1](proofs/P01-magnetic-synthesis.md) |
| 2 | Fixed collar không thể vừa null hai single-set torque spaces vừa giữ differential selectivity. | Bắt buộc có reconfiguration cho limp-home. | [P2](proofs/P02-fixed-collar-impossibility.md) |
| 3 | \(L_\Delta\le2L_{limp}\) với collar thụ động cố định. | Limp-home luôn trả giá bằng differential selectivity. | [P3](proofs/P03-passive-approximate-bound.md) |
| 4 | Một common toroid chỉ tạo rank-one \(z+\). | \(z-\) cần path riêng hoặc coupling khác. | [P4](proofs/P04-common-toroid-rank-one.md) |
| 5 | \(\operatorname{rank}(L_N-L_F)\ge2\). | Một cơ cấu fault phải đổi đồng thời hai differential axes. | [P5](proofs/P05-minimum-reconfiguration-rank.md) |
| 6 | Có thể dùng một operator fault chung cho lỗi của cả hai winding set. | Không cần hai bypass độc lập. | [P6](proofs/P06-common-fault-state.md) |
| 7 | \(\Delta i_m\approx L_m^{-1}\widetilde v_m\Delta t\). | Cơ sở toán của PWM error steering. | [P7](proofs/P07-pwm-modal-ripple.md) |
| 8 | Healthy exact synthesis: 4 path khi lattice-compatible; literal \(30^\circ\) one-turn exact-null là vô nghiệm. | Loại topology vô ích; xác định H4/H5 candidates. | [P8](proofs/P08-healthy-flux-path-minimum.md) |
| 9 | Exact one-turn realizability tương đương membership trong finite cone; H5 là universal ở frame lattice-compatible. | Có compiler \(L^*\to N,R\) và dual certificate trước CAD. | [P9](proofs/P09-exact-modal-realizability.md) |
| 10 | \(\sin\Theta\le\varepsilon/(\gamma-\varepsilon)\); với fixed \(N\), \(\ker(N^TGN)=\ker N\). | Tolerance phải chặn parasitic modal linkage, không phải ép mọi kích thước chính xác như nhau. | [P10](proofs/P10-torque-null-tolerance.md) |

## Chưa chứng minh

Geometry/routing thực, rank-2 gate dưới tolerance, transition safety, rotor/PWM benefit và system loss vẫn phải qua [`TEST.md`](TEST.md).
