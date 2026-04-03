from datetime import date

from macmarket_trader.domain.enums import InstrumentType, MarketMode, TradingSessionModel
from macmarket_trader.domain.schemas import (
    CryptoMarketContext,
    InstrumentIdentity,
    OptionContractContext,
    OptionStructureContext,
    OptionStructureLeg,
    RecommendationGenerateRequest,
    ReplayRunRequest,
)
from macmarket_trader.strategy_registry import list_strategies


def test_market_mode_enums_exist() -> None:
    assert MarketMode.EQUITIES.value == "equities"
    assert InstrumentType.OPTION_CONTRACT.value == "option_contract"
    assert TradingSessionModel.CRYPTO_24_7.value == "crypto_24_7"


def test_market_aware_contracts_validate() -> None:
    instrument = InstrumentIdentity(
        market_mode=MarketMode.OPTIONS,
        instrument_type=InstrumentType.OPTION_CONTRACT,
        symbol="SPY_20260515C00500000",
        underlying_symbol="SPY",
        quote_currency="USD",
        trading_session_model=TradingSessionModel.US_OPTIONS_REGULAR_HOURS,
    )
    option_contract = OptionContractContext(
        expiration=date(2026, 5, 15),
        strike=500.0,
        option_right="call",
        days_to_expiration=42,
    )
    option_structure = OptionStructureContext(
        strategy_id="iron_condor",
        strategy_legs=[
            OptionStructureLeg(action="buy", option_right="put", strike=190.0),
            OptionStructureLeg(action="sell", option_right="put", strike=195.0),
            OptionStructureLeg(action="sell", option_right="call", strike=210.0),
            OptionStructureLeg(action="buy", option_right="call", strike=215.0),
        ],
        net_debit_credit=1.35,
        max_profit=135.0,
        max_loss=365.0,
        breakeven_low=193.65,
        breakeven_high=211.35,
    )
    crypto = CryptoMarketContext(venue="preview", quote_currency="USD", liquidation_buffer_pct=6.2)

    assert instrument.market_mode == MarketMode.OPTIONS
    assert option_contract.multiplier == 100
    assert option_structure.strategy_legs[0].action == "buy"
    assert crypto.venue == "preview"


def test_market_mode_on_request_contracts() -> None:
    rec_req = RecommendationGenerateRequest(symbol="AAPL", bars=[], market_mode=MarketMode.EQUITIES)
    replay_req = ReplayRunRequest(symbol="AAPL", event_texts=[], bars=[], market_mode=MarketMode.CRYPTO)
    assert rec_req.market_mode == MarketMode.EQUITIES
    assert replay_req.market_mode == MarketMode.CRYPTO


def test_strategy_registry_by_market_mode() -> None:
    equities = list_strategies(MarketMode.EQUITIES)
    options = list_strategies(MarketMode.OPTIONS)
    crypto = list_strategies(MarketMode.CRYPTO)

    assert any(item.display_name == "Event Continuation" for item in equities)
    assert any(item.strategy_id == "iron_condor" for item in options)
    assert all(item.market_mode == MarketMode.CRYPTO for item in crypto)
    assert any(item.strategy_id == "crypto_basis_carry" for item in crypto)
