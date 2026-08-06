# BFM-5 FEA and strong-dark control

Đọc nhanh trạng thái hiện tại:

1. [`docs/PROJECT_SNAPSHOT.md`](docs/PROJECT_SNAPSHOT.md) — kết luận cô đọng.
2. [`config/project_state.yml`](config/project_state.yml) — trạng thái máy đọc.
3. [`config/design_laws_v8.yml`](config/design_laws_v8.yml) — luật và evidence TCZ-1H đầy đủ.
4. [`docs/TOPOLOGY_CHARTER.md`](docs/TOPOLOGY_CHARTER.md) — định nghĩa topology bất biến.
5. [`docs/POST_TCZ1H_ADAPTIVE_DEADLINE_DECISION_MEMO.md`](docs/POST_TCZ1H_ADAPTIVE_DEADLINE_DECISION_MEMO.md) — negative audit sau TCZ-1H.
6. [`docs/POST_TCZ1H_HIL_IDENTIFICATION_GATE_DECISION_MEMO.md`](docs/POST_TCZ1H_HIL_IDENTIFICATION_GATE_DECISION_MEMO.md) — accepted pre-HIL identification gate.
7. [`docs/TCZ1H_HIL_MEASUREMENT_PROTOCOL.md`](docs/TCZ1H_HIL_MEASUREMENT_PROTOCOL.md) — frozen measured-plant acquisition protocol.
8. [`docs/TCZ1H_MEASURED_CAMPAIGN_CAPSULE.md`](docs/TCZ1H_MEASURED_CAMPAIGN_CAPSULE.md) — raw-waveform schema and holdout firewall.
9. [`docs/POST_TCZ1H_MEASURED_CAMPAIGN_CAPSULE_DECISION_MEMO.md`](docs/POST_TCZ1H_MEASURED_CAMPAIGN_CAPSULE_DECISION_MEMO.md) — accepted pipeline qualification.
10. [`docs/POST_TCZ1H_LOCAL_DEPLOYMENT_GATE_DECISION_MEMO.md`](docs/POST_TCZ1H_LOCAL_DEPLOYMENT_GATE_DECISION_MEMO.md) — rejected request-time exact replay.
11. [`docs/TCZ1H_LOCAL_FALLBACK_CERTIFICATE_ATLAS.md`](docs/TCZ1H_LOCAL_FALLBACK_CERTIFICATE_ATLAS.md) — fallback-atlas contract.
12. [`docs/POST_TCZ1H_LOCAL_FALLBACK_ATLAS_DECISION_MEMO.md`](docs/POST_TCZ1H_LOCAL_FALLBACK_ATLAS_DECISION_MEMO.md) — accepted local atlas qualification.

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

## Pre-HIL identification gate

A frozen 816-trace route/sign/reversal protocol has passed on a nonlinear
shadow rig. The accepted safety-side actuator state is now the triplet
`(lower slew, upper lag, upper deadtime)`, conditioned on temperature, load,
and reversal history. On 288 holdout traces it produced zero bound violations,
zero calibrated false-safe deadline cases, and 93.28% feasible recall; the
frozen nominal model produced 140 false-safe grid cases.

This accepts the **measurement protocol only**. It is not hardware or HIL
evidence and does not create TCZ-1I or `design_laws_v9`. The next run must use
real measured traces, replay the unchanged TCZ-1H candidate bank, and measure
target-controller latency.

Run the shadow qualification:

```bash
cd fea
python scripts/run_tcz1h_hil_identification.py \
  --output-root data/post_tcz1h_hil_identification
```

## Measured-waveform campaign capsule

The qualified capsule consumes raw command, position, velocity, time, operating
condition and interlock arrays. Position is the primary fit channel; velocity is
an independent coherence check. The sealed model is created before holdout is
opened and is tied to the protocol and raw-bundle SHA-256 values.

Shadow qualification:

```bash
cd fea
python scripts/run_tcz1h_measured_campaign_qualification.py \
  --output-root data/post_tcz1h_measured_campaign
```

Measured/HIL transaction, using an externally acquired compatible raw bundle:

```bash
cd fea
python scripts/run_tcz1h_measured_campaign.py freeze \
  --campaign-root results_hil/tcz1h_measured
python scripts/run_tcz1h_measured_campaign.py fit \
  --campaign-root results_hil/tcz1h_measured \
  --raw-bundle /path/to/raw_waveforms.npz
python scripts/run_tcz1h_measured_campaign.py evaluate \
  --campaign-root results_hil/tcz1h_measured \
  --raw-bundle /path/to/raw_waveforms.npz
```

Qualification accepts the pipeline only. TCZ-1I remains unauthorized until the
same transaction passes on measured traces and the unchanged candidate bank is
replayed on the measured/HIL plant.

## Local fallback deployment qualification

The first local deployment audit proved the snapshot-bound HOLD/fallback/winner
lattice but rejected request-time exact fallback preparation at 2.35 s. The
accepted follow-up precomputes exact straight-fallback certificates on a finite
temperature-load grid. Only exact-replay passing cells are published; rejected,
missing, stale, corrupted and out-of-domain cells return HOLD.

Run locally without GitHub Actions:

```bash
cd fea
python scripts/run_tcz1h_local_deployment.py \
  --output-root results_local/tcz1h_local_deployment_qualification
python scripts/run_tcz1h_local_fallback_atlas.py \
  --output-root results_local/tcz1h_local_fallback_atlas
```

On the qualified Windows process the 25-node atlas built in 62.77 s. Runtime
lookup, verification, arm and decision had p99 35.9 microseconds baseline and
77.3 microseconds under CPU stress. This is local software evidence, not
hardware/HIL or operating-system hard-real-time evidence.
