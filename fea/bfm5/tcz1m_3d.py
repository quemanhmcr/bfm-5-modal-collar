"""Pure event-root and certification mathematics for TCZ-1M."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping
import numpy as np


def relative(a, b) -> float:
    x=np.asarray(a,dtype=float); y=np.asarray(b,dtype=float)
    return float(np.linalg.norm(x-y)/(np.linalg.norm(x)+np.finfo(float).tiny))


def event_flags(*, volume: float, differential_ratio: float, port: float, power: float, locality: float, gates: Mapping) -> dict:
    sat=gates['saturation']; dark=gates['strong_dark']
    saturation=(float(volume)>=float(sat['minimum_any_core_volume_fraction_above_1p62T']) and
                float(differential_ratio)<=float(sat['maximum_directional_differential_to_secant_ratio']))
    strong=(float(port)<=float(dark['maximum_port_leakage']) and
            float(power)<=float(dark['maximum_power_ratio']) and
            float(locality)<=float(dark['maximum_route_locality_residual']))
    return {'saturation':bool(saturation),'strong_dark':bool(strong),'dark_failure':not bool(strong)}


def event_margins(*, volume: float, differential_ratio: float, port: float, power: float, locality: float, gates: Mapping) -> dict:
    sat=gates['saturation']; dark=gates['strong_dark']
    return {
        'saturation_volume':float(volume)/float(sat['minimum_any_core_volume_fraction_above_1p62T'])-1.0,
        'saturation_differential':float(sat['maximum_directional_differential_to_secant_ratio'])/(float(differential_ratio)+np.finfo(float).tiny)-1.0,
        'strong_dark_port':1.0-float(port)/float(dark['maximum_port_leakage']),
        'strong_dark_power':1.0-float(power)/float(dark['maximum_power_ratio']),
        'strong_dark_locality':1.0-float(locality)/float(dark['maximum_route_locality_residual']),
    }


@dataclass(frozen=True)
class BooleanBracket:
    lo: float
    hi: float
    lo_flag: bool
    hi_flag: bool

    @property
    def width(self) -> float:
        return float(self.hi-self.lo)

    @property
    def midpoint(self) -> float:
        return float(0.5*(self.lo+self.hi))


def validate_transition_bracket(bracket: BooleanBracket, *, rising: bool) -> None:
    if not bracket.lo < bracket.hi:
        raise ValueError('root bracket must be ordered')
    expected=(False,True) if rising else (True,False)
    if (bool(bracket.lo_flag),bool(bracket.hi_flag)) != expected:
        raise ValueError(f'invalid {"rising" if rising else "falling"} bracket flags')


def update_transition_bracket(bracket: BooleanBracket, scale: float, flag: bool, *, rising: bool) -> BooleanBracket:
    validate_transition_bracket(bracket,rising=rising)
    x=float(scale)
    if not bracket.lo < x < bracket.hi:
        raise ValueError('new sample must lie strictly inside bracket')
    # Preserve the two Boolean endpoint classes for both rising and falling roots.
    # A sample replaces the endpoint that has the same Boolean class.
    if bool(flag)==bool(bracket.lo_flag):
        out=BooleanBracket(x,bracket.hi,bool(flag),bracket.hi_flag)
    elif bool(flag)==bool(bracket.hi_flag):
        out=BooleanBracket(bracket.lo,x,bracket.lo_flag,bool(flag))
    else:
        raise ValueError('sample flag does not match either bracket endpoint class')
    validate_transition_bracket(out,rising=rising)
    return out


def certified_event_margin_bounds(saturation: BooleanBracket, dark: BooleanBracket) -> tuple[float,float]:
    """Bounds on s_dark-s_sat from transition brackets."""
    validate_transition_bracket(saturation,rising=True)
    validate_transition_bracket(dark,rising=False)
    return float(dark.lo-saturation.hi), float(dark.hi-saturation.lo)


def root_midpoint(bracket: BooleanBracket) -> float:
    return bracket.midpoint
