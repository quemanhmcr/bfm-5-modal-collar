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
| [`PROOFS.md`](PROOFS.md) | Các định lý đã chứng minh | Không chứa geometry suy đoán |
| [`DESIGN.md`](DESIGN.md) | Cấu trúc hiện hành sau toán học | Chỉ một phương án đang sống |
| [`TEST.md`](TEST.md) | Thí nghiệm và kill criteria | Không có tiêu chí thì không chế tạo |

## Current truth

- **Gốc:** BFM-5 SOMA — dual three-phase, six-port modal collar, shifted current-mat, double-sided Halbach membrane.
- **Đã chứng minh:** fixed-collar limp-home impossibility; healthy minimum là 4 path khi offset lattice-compatible, nhưng exact-null one-pass tại 30° là vô nghiệm.
- **Thiết kế đang sống:** outer Z/CM path cố định + inner two-axis differential path có một shared rank-2 gate.
- **Chưa chứng minh:** gate rank-2 chế tạo được, loss, tolerance, transition energy, lợi ích rotor và PWM ở cấp hệ thống.
- **Next kill test:** đo hai ma trận complex six-port ở trạng thái normal/fault trên Rig A.

## Luật ghi chép

1. Bản gốc không bị viết lại bởi phát triển mới.
2. Mọi phát triển phải trỏ về claim gốc và định lý tạo ra nó.
3. Số gốc chỉ nằm trong `ORIGIN.md`; số thiết kế hiện hành chỉ nằm trong bảng tham số của `DESIGN.md`.
4. `TBD` tốt hơn số bịa.
5. Phương án cũ nằm trong Git, không để trong tài liệu hiện hành.
