import numpy as np
from bfm5.tcz1f_curvature import root_patch_curvature


def test_quadratic_root_sheet_is_recovered_exactly() -> None:
    points=[]
    for s in [0.95,1.0,1.05]:
        for a in [-2.0,0.0,2.0]:
            x=s-1.0
            q=np.array([
                2.0 + 0.2*x - 0.03*a + 0.5*x*x + 0.04*x*a + 0.002*a*a,
                1.2 + 0.8*x + 0.001*a - 0.2*x*x,
                1.5 + 0.1*x + 0.02*a - 0.03*x*a,
            ])
            points.append({
                'status':'passed','point_id':f'{s}_{a}',
                'input':{'magnitude_scale':s,'angle_offset_deg':a},
                'root':{'gaps_mm':q.tolist()},
            })
    report=root_patch_curvature({'points':points})
    assert np.allclose(report['first_derivatives']['dq_dscale_mm'], [0.2,0.8,0.1])
    assert np.allclose(report['first_derivatives']['dq_dangle_mm_per_deg'], [-0.03,0.001,0.02])
    assert report['max_quadratic_corner_error_um'] < 1e-9
    assert report['max_additive_corner_error_um'] > 0.0


def test_incomplete_patch_is_rejected() -> None:
    try:
        root_patch_curvature({'points':[]})
    except ValueError as error:
        assert 'Incomplete' in str(error)
    else:
        raise AssertionError('Expected incomplete patch rejection')
