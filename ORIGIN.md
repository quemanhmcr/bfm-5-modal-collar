# ORIGIN — BFM-5 SOMA Team Board

**Canonical artifact:** `ORIGIN.png` — bản PNG team board được cung cấp trong project chat.

- Kích thước nguồn: `1536 × 1024`.
- SHA-256 nguồn: `e4e128f01947e8e92b95509f04b286763c36b81e34c196299851736076e83673`.
- Quy tắc: lưu nguyên byte, không crop, không annotate, không thay ảnh bằng bản vẽ phát triển.

> Local Git Bash không nhìn thấy binary upload của chat; khi `ORIGIN.png` được đặt vào root, hash trên là phép kiểm tra duy nhất.

**Trạng thái:** nguồn gốc bất biến của project. Mọi toán học và geometry mới là phát triển nối tiếp, không thay thế lịch sử này.

## O1 — Thesis gốc

BFM-5 chuyển bài toán từ sáu phase sang các mode trực giao:

\[
(\alpha,\beta,x,y,z_1,z_2).
\]

Không thiết kế sáu cuộn cảm độc lập. Thiết kế eigenvectors và eigenvalues của một magnetic network sáu cổng.

## O2 — Chuỗi hệ thống gốc

```text
Dual three-phase inverters
→ six-port modal collar
→ dual spectral current-mat, offset δe
→ double-sided Halbach membrane rotor
```

Các phần tích hợp trên board:

- power-module ring;
- DC-link capacitor ring;
- six-port modal collar;
- current-mat A/B;
- double-sided Halbach membrane;
- nonmagnetic rotor hub;
- air-gap không back iron;
- segmented cold shell;
- bearing cartridge.

## O3 — Collar gốc

Ba họ flux path:

1. **Torque \(\alpha\beta\):** null path; traction current gần như không từ hóa collar.
2. **Harmonic \(xy\):** gapped path; tích trữ ripple energy và tuyến tính hóa inductance.
3. **Zero/common mode \(z\):** outer toroidal path; tổng ampere-turn cùng chiều cộng lại.

Mục tiêu modal ban đầu:

\[
\mathbf L_m=\operatorname{diag}(L_t,L_t,L_h,L_h,L_z,L_z),
\qquad L_z>L_h\gg L_t.
\]

Và:

\[
\mathbf L_{physical}=\mathbf T^T\mathbf L_m\mathbf T.
\]

## O4 — Spectral current-mat gốc

Hai bộ ba pha có offset điện \(\delta_e\), candidate chính khoảng \(30^\circ\).

Mục tiêu:

- fundamental cộng;
- selected harmonics triệt hoặc giảm;
- chia dòng;
- fault partition;
- PWM interleaving.

## O5 — PWM thesis gốc

Modulator giữ đúng điện áp trung bình trong torque plane và đẩy phần lớn switching error vào các mode có inductance lớn.

Phương trình dòng đúng dùng trong phát triển:

\[
\Delta\mathbf i_m\approx\mathbf L_m^{-1}\widetilde{\mathbf v}_m\Delta t.
\]

## O6 — Team targets ban đầu

Các số dưới đây là **TEAM TARGET — UNVALIDATED**, không phải specification đã phát hành:

| Claim trên board | Giá trị gốc |
|---|---:|
| Power example | 60 kW |
| \(L_t\) | khoảng 20–40 µH |
| \(L_h/L_t\) | ≥ 10 |
| \(L_z/L_t\) | ≥ 20 |
| \(I_{xy}/I_{\alpha\beta}\) | < 3% |
| CM current | giảm ≥ 10 dB so với BFM-4 |
| Torque ripple p-p | < 2% rated torque |
| PM eddy loss | giảm ≥ 15% |
| Fault torque fraction | 0.25–0.50 rated |

## O7 — Verification gốc

- **Rig A:** six-port inductance matrix.
- **Rig B:** modulation–collar loop.
- **Rig C:** spectral current-mat và rotor loss.
- **Rig D:** common-mode, shell và bearing voltage.

## O8 — Nguyên tắc truy vết

Mỗi phát triển dùng ID:

```text
O#  claim gốc
P#  định lý/kết quả toán
D#  quyết định geometry/control
T#  phép thử có thể bác bỏ
```

Ví dụ:

```text
O3 → P2 → D1 → T1
fixed modal collar → bất khả thi limp-home → shared gate → Rig A
```
