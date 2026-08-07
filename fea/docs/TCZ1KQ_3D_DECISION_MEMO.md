# TCZ-1KQ 3D Numerical Qualification Decision Memo

GitHub Actions run `31145999028` on `814d0587a658fc328eb44a55667d244bec81340c` completed successfully. The immutable qualification hash is `eb0e50b825f6700d4ff886d91655cf48cef9e818d6d832a6f0e995d84312439f`.

## Decision

- Numerical qualification: **PASS**.
- Fine-grid nonlinear intrinsic topology: **PASS**.
- Fine-grid operating strong-dark holdout: **PASS (5/5)**.
- Fine-grid uncertainty holdout: **PASS (6/6)**.
- Material saturation occupancy on the frozen operating set: **FAIL** under the predeclared >1.62 T volume gate.
- Frozen affine depth law: **FAIL**; maximum holdout error 10.965846%.
- Overall qualified nonlinear saturated holdout: **NOT ACCEPTED**, solely because the frozen operating set did not materially occupy the >1.62 T core volume threshold.

The finer qualification closed the previous numerical defects without changing any TCZ-1K gate: derivative mesh spread 3.170728%, remote-boundary spread 4.226725%, and derivative-step spread 0.108965%.

## Scientific consequence

TCZ-1KQ supports nonlinear anhysteretic 3D strong-dark topology on the declared fine-grid operating and uncertainty sets, but it does not support a deep-saturation claim. The next admissible test must target saturation before looking at results and compare the ordering of saturation, dark-loss, and rank-loss events.

## Integrity

The repository freeze contains 71 artifact files; the Actions manifest covers 70 evidence records and 9 source records. Canonical artifact tree SHA-256: `cae5cad39ff22ecf55f9f5013560800b0fc03ba36ab7b66077a88027fd84ba1e`.
