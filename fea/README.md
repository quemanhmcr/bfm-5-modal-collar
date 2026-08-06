# BFM-5 FEA and strong-dark control

Đọc nhanh trạng thái hiện tại:

1. [`docs/PROJECT_SNAPSHOT.md`](docs/PROJECT_SNAPSHOT.md) — kết luận cô đọng.
2. [`config/project_state.yml`](config/project_state.yml) — trạng thái máy đọc.
3. [`config/design_laws_v8.yml`](config/design_laws_v8.yml) — luật và evidence TCZ-1H đầy đủ.
4. [`docs/TOPOLOGY_CHARTER.md`](docs/TOPOLOGY_CHARTER.md) — định nghĩa topology bất biến.

## Current accepted state

- Mercedes tight-frame topology với zero-sequence dark carrier.
- TCZ-1B symmetric geometry là hardware reference.
- TCZ-1D strong-dark root được schedule theo current state.
- TCZ-1F quadratic root patch đã được FEA xác nhận trong
  `rho=[0.95,1.05]`, `theta=[-2°,2°]`.
- TCZ-1H là navigator hiện hành: learned proposal, exact physics correction,
  exact candidate-bank replay và dynamic certificate.

## Execution policy

- Không chạy FEMM trên workstation.
- Linux MCP điều phối và phân tích.
- FEMM chỉ chạy trên SHA-pinned GitHub Windows shards.
- TCZ-1G/H là solver-free và dùng immutable identified model data.

## Validation

Numerical regression:

```bash
cd fea
python -m pytest -q tests
```

TCZ-1H benchmark:

```bash
cd fea
python scripts/run_tcz1h_benchmark.py \
  --output-root results_ci/tcz1h \
  --workers 4 \
  --latency-profile local_reference
```

Chi tiết lịch sử và failure analyses vẫn nằm trong `docs/TCZ1*.md` và
`config/design_laws_v*.yml`; không cần đọc chúng để nắm trạng thái hiện hành.
