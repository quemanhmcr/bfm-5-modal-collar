import numpy as np
from bfm5.tcz1f_surrogate import validate_patch_surrogates


def make_point(scale,angle,q,d=(-0.5,0.8,0.33)):
    return {
      'point_id':f'{scale}_{angle}','status':'passed',
      'input':{'magnitude_scale':scale,'angle_offset_deg':angle},
      'root':{'gaps_mm':list(q),'dark_direction':list(d),'strong_dark_discriminant':1e-4,'flux_drift_normalized':1e-5},
      'fold_diagnostic':{'root_fold_margin_per_mm':0.1},
    }


def qfun(s,a):
    r=s-1
    return np.array([2+0.2*r-0.03*a+0.5*r*r+0.04*r*a+0.002*a*a,1.2+0.8*r+0.001*a-0.2*r*r,1.5+0.1*r+0.02*a-0.03*r*a])


def test_quadratic_surrogate_validates_exactly() -> None:
    base={'points':[make_point(s,a,qfun(s,a)) for s in [0.95,1,1.05] for a in [-2,0,2]]}
    val={'points':[make_point(s,a,qfun(s,a)) for s in [0.975,1.025] for a in [-1,1]]}
    curvature={
      'first_derivatives':{'dq_dscale_mm':[0.2,0.8,0.1],'dq_dangle_mm_per_deg':[-0.03,0.001,0.02]},
      'second_derivatives':{'d2q_dscale2_mm':[1,-0.4,0],'d2q_dscale_dangle_mm_per_deg':[0.04,0,-0.03],'d2q_dangle2_mm_per_deg2':[0.004,0,0]},
    }
    report=validate_patch_surrogates(base,val,curvature)
    assert report['summary']['max_quadratic_error_um']<1e-9
    assert report['decision']=='accept-quadratic-local-patch'
