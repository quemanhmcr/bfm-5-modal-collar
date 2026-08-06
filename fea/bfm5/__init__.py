"""BFM-5 open-source FEA automation and topology-analysis package."""

from .topology import (
    TopologyTangentReport,
    best_route_local_factorization,
    compatibility_xi,
    dark_direction,
    determinant_from_lorentz,
    frame_metrics,
    hidden_branch_mode,
    ideal_branch_dark_direction,
    inductance_from_routes,
    inertia_signature,
    lorentz_q,
    mercedes_frame,
    normalized_port_leakage,
    normalized_power_leakage,
    pullback_determinant_form,
    route_projectors,
    tangent_report,
)

__version__ = "0.2.0"

__all__ = [
    "TopologyTangentReport",
    "best_route_local_factorization",
    "compatibility_xi",
    "dark_direction",
    "determinant_from_lorentz",
    "frame_metrics",
    "hidden_branch_mode",
    "ideal_branch_dark_direction",
    "inductance_from_routes",
    "inertia_signature",
    "lorentz_q",
    "mercedes_frame",
    "normalized_port_leakage",
    "normalized_power_leakage",
    "pullback_determinant_form",
    "route_projectors",
    "tangent_report",
]

# TCZ-1B gauge-reduced design utilities are intentionally not imported here;
# keeping the package root light avoids importing FEMM-adjacent configuration
# code during algebra-only tests.

# TCZ-1E dynamic root tracking is implemented in bfm5.tcz1e.
