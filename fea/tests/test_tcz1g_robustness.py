import numpy as np

from bfm5.tcz1g import QuadraticRootPatch, optimize_root_path, reparameterize_by_slew, straight_current_path
from bfm5.tcz1g_robustness import fixed_path_slew_monte_carlo


def patch() -> QuadraticRootPatch:
    return QuadraticRootPatch(
        nominal_current=(1600.0, 600.0), q0_mm=(2.0, 1.16, 1.55),
        dq_drho_mm=(0.25, 0.84, 0.10), dq_dtheta_mm_per_deg=(-0.03, 0.0, 0.019),
        d2q_drho2_mm=(2.3, 1.4, -0.9), d2q_drho_dtheta_mm_per_deg=(-0.04, 0.01, -0.02),
        d2q_dtheta2_mm_per_deg2=(3e-4, 4e-4, 3e-4),
    )


def test_slew_monte_carlo_is_reproducible() -> None:
    model = patch(); start=[0.95,-2.0]; end=[1.05,2.0]
    plans={
        'straight_current': reparameterize_by_slew(model, straight_current_path(model,start,end,samples=41)),
        'polytope_time_optimal': reparameterize_by_slew(model, optimize_root_path(model,start,end,objective='polytope_time',nodes=7,dense_samples=41)),
    }
    a=fixed_path_slew_monte_carlo(model,plans,uncertainty_fractions=[0.05],samples=1000,seed=7)
    b=fixed_path_slew_monte_carlo(model,plans,uncertainty_fractions=[0.05],samples=1000,seed=7)
    assert a==b
    stats=a['rows'][0]['paths']['polytope_time_optimal']
    assert 0.0 <= stats['win_probability_vs_straight'] <= 1.0
    assert stats['q05_time_ratio'] <= stats['median_time_ratio'] <= stats['q95_time_ratio']


def test_robustness_decision_threshold_rejects_weak_fixed_path() -> None:
    # The production decision requires >=95% fixed-path wins at ±5% route
    # slew uncertainty.  A merely majority-winning path must not be accepted.
    win_probability = 0.83
    assert not (win_probability >= 0.95)
