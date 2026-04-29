"""Options helpers for read-only research and replay math."""

from .paper_close import OptionPaperCloseError, close_paper_option_structure
from .paper_contracts import OptionPaperContractError, PreparedOptionPaperStructure, prepare_option_paper_structure
from .paper_open import open_paper_option_structure
from .payoff import (
    OptionLegInput,
    OptionLegPayoff,
    OptionPayoffPoint,
    OptionPayoffResult,
    analyze_iron_condor,
    analyze_option_structure,
    analyze_vertical_debit_spread,
    calculate_option_leg_payoff,
)

__all__ = [
    "OptionPaperCloseError",
    "OptionPaperContractError",
    "PreparedOptionPaperStructure",
    "OptionLegInput",
    "OptionLegPayoff",
    "OptionPayoffPoint",
    "OptionPayoffResult",
    "analyze_iron_condor",
    "analyze_option_structure",
    "analyze_vertical_debit_spread",
    "calculate_option_leg_payoff",
    "close_paper_option_structure",
    "open_paper_option_structure",
    "prepare_option_paper_structure",
]
