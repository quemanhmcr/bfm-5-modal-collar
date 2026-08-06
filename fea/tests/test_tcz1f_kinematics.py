import numpy as np
from bfm5.tcz1f_kinematics import connection_velocity_polytope, directional_rate_bound


def test_three_route_connection_creates_bounded_central_polygon() -> None:
    a=np.array([[1.0,0.0],[0.0,1.0],[1.0,1.0]])
    report=connection_velocity_polytope(a,1.0)
    vertices=np.asarray(report['vertices'])
    assert report['vertex_count']==6
    assert np.all(np.abs(a@vertices.T)<=1.0+1e-10)
    assert np.allclose(np.mean(vertices,axis=0),0.0)
    assert report['area_coordinate2_per_s2']>0


def test_directional_and_pure_bounds_agree() -> None:
    a=np.array([[2.0,0.0],[0.0,3.0],[1.0,1.0]])
    report=connection_velocity_polytope(a,0.6)
    assert np.isclose(report['pure_coordinate_rate_bounds_per_s'][0],0.3)
    assert np.isclose(report['pure_coordinate_rate_bounds_per_s'][1],0.2)
    assert np.isclose(directional_rate_bound(a,[1,0],0.6),0.3)
