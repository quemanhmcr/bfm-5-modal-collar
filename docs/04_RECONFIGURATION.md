# Reconfiguration and Fault Safety

## 1. State equation

Use a common fault configuration:

\[
\mathbf L(q)=
\mathbf L_\sigma+
\mathbf L_Z+
\eta(q)\mathbf L_\Delta,
\]

with

\[
\eta(N)=1,
\qquad
0\le\eta(F)\ll1.
\]

The physical gate changes reluctance; \(\eta\) is an identified equivalent parameter.

## 2. Valid states

| State | Keeper | Inverter condition | Allowed torque |
|---|---|---|---|
| N | Seated | Both sets healthy | Rated envelope |
| PREPARE_F | Seated | Fault isolated; \(i_\Delta\) controlled down | Transient only |
| DISCHARGE | Seated/moving | Clamp or DC-link path active | Transient only |
| F | Withdrawn | One healthy set | \(\rho T_{rated}\) target |
| PREPARE_N | Withdrawn | Both sets verified; low \(i_\Delta\) | Transient only |

No uncontrolled intermediate state is valid.

## 3. Normal-to-fault transition

```text
FAULT DETECTED
  → isolate failed inverter/winding set
  → command differential-current reduction
  → verify |iΔ| ≤ IΔ,open
  → arm energy sink
  → release keeper to high-reluctance state
  → verify position
  → identify/check fault-state impedance
  → enter derated torque-speed envelope
```

If \(|i_\Delta|\) cannot be reduced, the controller shall use the emergency energy path and prohibit re-closing.

## 4. Energy requirement

At the state boundary:

\[
E_{\rm release}=
\frac12\mathbf i^T
(\mathbf L_N-\mathbf L_F)
\mathbf i.
\]

Required capacity:

\[
E_{\rm sink,rated}
\ge
E_{\rm release,max}
\times K_E,
\]

where \(K_E\) is a design margin stored in the parameter ledger.

Permitted sinks:

- controlled inverter return to DC link;
- brake chopper;
- active clamp;
- dedicated snubber;
- resistive dissipation path.

Mechanical motion is not an energy sink.

## 5. Saturation during motion

For all allowed keeper positions \(q\in Q_{tr}\):

\[
B_{\max}(q,\mathbf i)<B_{\rm allow}.
\]

Opening direction should monotonically increase reluctance:

\[
\frac{d\mathcal R_\Delta}{dq}\ge0.
\]

This makes flux non-increasing at fixed current. Closing is allowed only below \(I_{\Delta,close}\).

## 6. Single-fault classification

| Failure | Electrical consequence | Required system response |
|---|---|---|
| Actuator open circuit | Keeper falls to F | Continue derated; report loss of filtering |
| Actuator short circuit | Position may be frozen | Isolate actuator supply; use sensed position |
| Keeper stuck N | Excess limp-home inductance | Reduce speed/current to voltage budget |
| Keeper stuck F | No healthy differential filtering | Continue with alternate PWM/current limit |
| Position sensor open | State unknown | Treat as F; identify impedance before torque |
| Position sensor short | State unknown | Treat as F; identify impedance before torque |
| Keeper fracture | Reluctance uncertain | Enter minimum torque envelope; inspect matrix |
| One core crack | Modal asymmetry/loss | Detect by matrix or flux sensors; derate |

## 7. No-short proof obligation

Model the conductive assembly as graph \(G_E=(V,E)\).

**Invariant:** every collar edge connects nodes belonging to one phase label only.

The keeper and core are excluded from \(E\) by insulation and clearance. Therefore changing magnetic state cannot create a graph path between:

\[
U\leftrightarrow V,
\quad V\leftrightarrow W,
\quad W\leftrightarrow U,
\quad DC^+\leftrightarrow DC^-.
\]

This invariant must be checked against every drawing revision and FMEA row.

## 8. Limp-home envelope

Torque requirement:

\[
T_{fault}\ge\rho T_{rated},
\qquad 0.25\le\rho\le0.5.
\]

Approximate voltage constraint:

\[
E_{back}(\omega_e)
+
R_s\rho I_{rated}
+
\omega_e\Lambda_{\max}\rho I_{rated}
\le V_{phase,max}.
\]

The fault envelope is therefore a torque-speed region, not one scalar torque claim.

## 9. Recovery to normal

Normal re-entry requires:

1. both winding sets electrically verified;
2. keeper and core temperatures within limits;
3. \(|i_\Delta|\le I_{\Delta,close}\);
4. DC-link energy path available;
5. keeper seated and position verified;
6. measured/identified \(\mathbf L_N\) within limits.

Automatic re-entry after a hard winding fault is prohibited.
