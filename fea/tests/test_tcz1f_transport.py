import numpy as np
import pytest

from bfm5.tcz1f_transport import (
    broyden_port_update,
    dark_axis,
    directional_coenergy_force,
    refresh_required,
)


def test_directional_force_is_exact_for_quadratic_along_line() -> None:
    # W(s)=3+2s+5s^2, derivative at zero is 2.
    h=0.03
    minus=3-2*h+5*h*h
    plus=3+2*h+5*h*h
    assert np.isclose(directional_coenergy_force(minus,plus,h),2.0)


def test_broyden_update_enforces_flux_secant_exactly() -> None:
    k=np.array([[1.0,0.0,0.0],[0.0,1.0,0.0]])
    dq=np.array([0.1,-0.2,0.3])
    dpsi=np.array([0.15,-0.25])
    updated,health=broyden_port_update(k,dq,dpsi)
    assert np.allclose(updated@dq,dpsi)
    assert health.secant_residual_after < 1e-14
    assert np.isfinite(health.port_condition)


def test_dark_axis_remains_null_and_oriented() -> None:
    k=np.array([[1.0,0.0,-1.0],[0.0,1.0,-1.0]])
    reference=np.array([1.0,1.0,1.0])
    d=dark_axis(k,reference)
    assert np.linalg.norm(k@d)<1e-12
    assert d@reference>0


def test_refresh_policy_detects_old_or_large_updates() -> None:
    k=np.array([[1.0,0.0,0.0],[0.0,1.0,0.0]])
    _,health=broyden_port_update(k,[0.1,0.0,0.1],[0.1,0.0])
    assert not refresh_required(health,age=0,max_age=4,max_relative_update=1.0,max_secant_residual=1.0)
    assert refresh_required(health,age=4,max_age=4,max_relative_update=1.0,max_secant_residual=1.0)


def test_tiny_transport_step_is_rejected() -> None:
    with pytest.raises(ValueError):
        broyden_port_update(np.ones((2,3)),[0,0,0],[0,0])
