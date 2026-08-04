# BFM-5

**Mục tiêu:** chứng minh hoặc giết nhanh kiến trúc BFM-5 bằng vật lý, không bằng slide.

## Một luồng duy nhất

```text
ORIGIN.md  →  PROOFS.md  →  DESIGN.md  →  TEST.md
bản gốc       cái đúng       cái đang làm    cách giết nó
```

| Tệp | Chức năng | Quy tắc |
|---|---|---|
| [`ORIGIN.md`](ORIGIN.md) | Bản vẽ và ý tưởng gốc của team | Bất biến; chỉ sửa lỗi chép |
| [`PROOFS.md`](PROOFS.md) | Chỉ mục kết quả đã chứng minh | Toán chi tiết nằm trong `proofs/` |
| [`DESIGN.md`](DESIGN.md) | Cấu trúc hiện hành sau toán học | Chỉ một phương án đang sống |
| [`TEST.md`](TEST.md) | Thí nghiệm và kill criteria | Không có tiêu chí thì không chế tạo |

## Current truth

- **Gốc:** BFM-5 SOMA — dual three-phase, six-port modal collar, shifted current-mat, double-sided Halbach membrane.
- **Đã chứng minh:** exact synthesis là finite-cone LP; H5 là universal ở frame lattice-compatible; exact torque null được bảo vệ bởi winding incidence; linkage ký sinh và sai số synthesis cùng tiêu thụ một tolerance budget định lượng từ P10.
- **Thiết kế đang sống:** H5 — ba differential branches chuyển cùng nhau + hai path z+/z− cố định; shifted current-mat giữ lại, torque null tại gần 30° là bài toán tối ưu xấp xỉ.
- **Chưa chứng minh:** gate rank-2 chế tạo được, loss, tolerance, transition energy, lợi ích rotor và PWM ở cấp hệ thống.
- **Next kill test:** tối ưu routing xấp xỉ theo góc lệch, rồi đo ma trận complex six-port H5 ở normal/fault trên Rig A.

## Luật ghi chép

1. Bản gốc không bị viết lại bởi phát triển mới.
2. Mọi phát triển phải trỏ về claim gốc và định lý tạo ra nó.
3. Số gốc chỉ nằm trong `ORIGIN.md`; số thiết kế hiện hành chỉ nằm trong bảng tham số của `DESIGN.md`.
4. `TBD` tốt hơn số bịa.
5. Phương án cũ nằm trong Git, không để trong tài liệu hiện hành.
