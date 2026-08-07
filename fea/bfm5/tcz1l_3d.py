"""Pure decision mathematics for TCZ-1L critical-surface holdout."""
from __future__ import annotations
from typing import Sequence
import numpy as np


def relative(a, b) -> float:
    x=np.asarray(a,dtype=float); y=np.asarray(b,dtype=float)
    return float(np.linalg.norm(x-y)/(np.linalg.norm(x)+np.finfo(float).tiny))


def first_true_scale(scales: Sequence[float], flags: Sequence[bool]) -> float | None:
    for scale, flag in zip(scales, flags, strict=True):
        if bool(flag): return float(scale)
    return None


def sampled_event_order(scales: Sequence[float], saturation: Sequence[bool], strong_dark: Sequence[bool], strict_overlap: Sequence[bool]) -> dict:
    if not (len(scales)==len(saturation)==len(strong_dark)==len(strict_overlap)):
        raise ValueError('event arrays must have equal length')
    if any(b <= a for a,b in zip(scales,scales[1:])):
        raise ValueError('scales must be strictly increasing')
    sat=first_true_scale(scales,saturation)
    dark_fail=first_true_scale(scales,[not bool(x) for x in strong_dark])
    overlap=first_true_scale(scales,strict_overlap)
    ordered=bool(sat is not None and (dark_fail is None or sat < dark_fail))
    return {
        'first_saturated_scale':sat,
        'first_strong_dark_failure_scale':dark_fail,
        'first_strict_overlap_scale':overlap,
        'saturation_precedes_sampled_dark_failure':ordered,
        'strict_local_overlap_certified':overlap is not None,
    }


def gate_margin(value: float, maximum: float) -> float:
    if maximum <= 0: raise ValueError('maximum must be positive')
    return float(1.0-value/maximum)


def strict_overlap_flags(*, volume_above_1p62: float, differential_ratio: float, port: float, power: float, locality: float, gates: dict) -> dict:
    checks={
        'volume': volume_above_1p62 >= float(gates['minimum_core_volume_fraction_above_1p62T']),
        'differential_drop': differential_ratio <= float(gates['maximum_directional_differential_to_secant_ratio']),
        'port': port <= float(gates['maximum_port_leakage']),
        'power': power <= float(gates['maximum_power_ratio']),
        'locality': locality <= float(gates['maximum_route_locality_residual']),
    }
    return {'checks':checks,'accepted':all(checks.values())}
