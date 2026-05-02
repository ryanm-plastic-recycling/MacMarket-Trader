from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select

import macmarket_trader.llm.registry as llm_registry
from macmarket_trader.api.main import app
from macmarket_trader.api.routes import admin as admin_routes
from macmarket_trader.config import Settings
from macmarket_trader.domain.models import AppUserModel
from macmarket_trader.domain.schemas import (
    Bar,
    BetterElsewhereCandidate,
    LLMEventFields,
    OpportunityCandidateSummary,
    OpportunityComparisonMemo,
    PortfolioSnapshot,
    TradeRecommendation,
)
from macmarket_trader.llm.base import LLMClient, LLM_PROMPT_VERSION
from macmarket_trader.llm.mock_extractor import MockLLMClient
from macmarket_trader.service import RecommendationService
from macmarket_trader.storage.db import SessionLocal


client = TestClient(app)
_USER_AUTH = {"Authorization": "Bearer user-token"}


def _bars() -> list[Bar]:
    base = date(2026, 1, 1)
    return [
        Bar(
            date=base + timedelta(days=i),
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=1_000_000 + i * 10_000,
            rel_volume=1.1,
        )
        for i in range(25)
    ]


def _seed_approved_user() -> int:
    resp = client.get("/user/me", headers=_USER_AUTH)
    assert resp.status_code == 200, resp.text
    with SessionLocal() as session:
        user = session.execute(
            select(AppUserModel).where(AppUserModel.external_auth_user_id == "clerk_user")
        ).scalar_one()
        user.approval_status = "approved"
        session.commit()
        return user.id


class MalformedLLMClient(LLMClient):
    provider_name = "broken-test"
    model = "broken"
    prompt_version = LLM_PROMPT_VERSION

    def summarize_event_text(self, *, symbol: str, text: str) -> str:
        return ""

    def extract_event_fields(self, *, symbol: str, text: str) -> LLMEventFields:
        return {"entry": 123}  # type: ignore[return-value]

    def explain_recommendation(self, *, recommendation: TradeRecommendation):
        return {"summary": "bad", "entry": 123}

    def generate_counter_thesis(self, *, recommendation: TradeRecommendation) -> list[str]:
        return ["bad"]

    def compare_candidates(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ):
        return {
            "best_deterministic_candidate_id": "rec_not_supplied",
            "best_deterministic_symbol": "ZZZZ",
            "market_desk_memo": "Malformed memo tries to invent an unscanned symbol.",
            "comparison_rows": [{"candidate_id": "rec_not_supplied", "symbol": "ZZZZ"}],
            "counter_thesis_by_candidate": {"rec_not_supplied": ["bad"]},
            "better_elsewhere": [
                {
                    "symbol": "ZZZZ",
                    "reason": "Invented by malformed provider output.",
                    "source": "deterministic_scan",
                    "verified_by_scan": True,
                }
            ],
            "not_good_enough_warning": None,
            "missing_data": [],
            "deterministic_engine_owns": [
                "approved",
                "side",
                "entry",
                "invalidation",
                "targets",
                "shares",
                "sizing",
                "order_status",
                "paper_position_status",
            ],
            "explanation_only": True,
        }

    def generate_market_context_memo(self, *, candidates: list[OpportunityCandidateSummary]) -> str:
        return "bad"

    def generate_better_elsewhere_memo(
        self,
        *,
        candidates: list[OpportunityCandidateSummary],
        better_elsewhere: list[BetterElsewhereCandidate],
    ) -> str:
        return "bad"


def _decision_snapshot(payload: dict[str, object]) -> dict[str, object]:
    return {
        "entry": payload["entry"],
        "invalidation": payload["invalidation"],
        "targets": payload["targets"],
        "sizing": payload["sizing"],
        "approved": payload["approved"],
        "outcome": payload["outcome"],
    }


def _seed_two_recommendations(monkeypatch) -> tuple[str, str]:
    _seed_approved_user()
    monkeypatch.setattr("macmarket_trader.service.settings.llm_enabled", False)
    monkeypatch.setattr("macmarket_trader.service.settings.llm_provider", "mock")
    monkeypatch.setattr(
        admin_routes,
        "recommendation_service",
        RecommendationService(llm_client=MockLLMClient()),
    )
    first = client.post(
        "/user/recommendations/generate",
        headers=_USER_AUTH,
        json={"symbol": "AAPL", "event_text": "AAPL earnings beat with strong guidance"},
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/user/recommendations/generate",
        headers=_USER_AUTH,
        json={"symbol": "MSFT", "event_text": "MSFT cloud demand improves after enterprise event"},
    )
    assert second.status_code == 200, second.text
    return first.json()["recommendation_id"], second.json()["recommendation_id"]


def test_llm_settings_mock_defaults_require_no_key(monkeypatch) -> None:
    for key in (
        "LLM_ENABLED",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "OPENAI_API_KEY",
        "LLM_API_KEY",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_OUTPUT_TOKENS",
        "LLM_TEMPERATURE",
    ):
        monkeypatch.delenv(key, raising=False)

    cfg = Settings(_env_file=None)

    assert cfg.llm_enabled is False
    assert cfg.llm_provider == "mock"
    assert cfg.llm_model == ""
    assert cfg.llm_api_key == ""


def test_llm_settings_prefers_openai_api_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("LLM_API_KEY", "sk-legacy-test")

    cfg = Settings(_env_file=None)

    assert cfg.llm_api_key == "sk-openai-test"


def test_llm_settings_uses_legacy_key_when_openai_key_is_blank(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("LLM_API_KEY", "sk-legacy-test")

    cfg = Settings(_env_file=None)

    assert cfg.llm_api_key == "sk-legacy-test"


def test_llm_disabled_openai_provider_does_not_require_key(monkeypatch) -> None:
    monkeypatch.setattr(llm_registry.settings, "llm_enabled", False)
    monkeypatch.setattr(llm_registry.settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_registry.settings, "llm_model", "gpt-5.1")
    monkeypatch.setattr(llm_registry.settings, "llm_api_key", "")

    client = llm_registry.build_llm_client()

    assert isinstance(client, MockLLMClient)
    assert client.model == "gpt-5.1"


def test_openai_llm_client_reads_configured_env_values(monkeypatch) -> None:
    monkeypatch.setattr(llm_registry.settings, "llm_enabled", True)
    monkeypatch.setattr(llm_registry.settings, "llm_provider", "openai")
    monkeypatch.setattr(llm_registry.settings, "llm_model", "gpt-5.1")
    monkeypatch.setattr(llm_registry.settings, "llm_api_key", "sk-openai-test")
    monkeypatch.setattr(llm_registry.settings, "llm_timeout_seconds", 20.0)
    monkeypatch.setattr(llm_registry.settings, "llm_max_output_tokens", 1200)
    monkeypatch.setattr(llm_registry.settings, "llm_temperature", 0.2)

    client = llm_registry.build_llm_client()

    assert client.provider_name == "openai"
    assert client.model == "gpt-5.1"
    assert getattr(client, "api_key") == "sk-openai-test"
    assert getattr(client, "timeout_seconds") == 20.0
    assert getattr(client, "max_output_tokens") == 1200
    assert getattr(client, "temperature") == 0.2


def test_mock_llm_provider_returns_structured_explanation_and_event_fields() -> None:
    llm = MockLLMClient()
    event_fields = llm.extract_event_fields(symbol="AAPL", text="AAPL earnings beat with strong guidance")
    assert event_fields.source_type.value == "corporate"
    assert event_fields.summary
    assert -1.0 <= event_fields.sentiment_score <= 1.0

    rec = RecommendationService(persist_audit=False, llm_client=llm).generate(
        symbol="AAPL",
        bars=_bars(),
        event_text="AAPL earnings beat with strong guidance",
        event=None,
        portfolio=PortfolioSnapshot(),
        user_is_approved=True,
    )
    assert rec.ai_explanation is not None
    assert rec.ai_explanation.explanation_only is True
    assert set(rec.ai_explanation.deterministic_engine_owns) == {
        "entry",
        "stop",
        "target",
        "sizing",
        "approval",
        "order_routing",
    }
    assert rec.llm_provenance is not None
    assert rec.llm_provenance.provider == "mock"


def test_malformed_llm_output_falls_back_to_deterministic_mock_explanation(monkeypatch) -> None:
    monkeypatch.setattr("macmarket_trader.service.settings.llm_enabled", True)
    monkeypatch.setattr("macmarket_trader.service.settings.llm_provider", "openai")
    service = RecommendationService(persist_audit=False, llm_client=MalformedLLMClient())

    rec = service.generate(
        symbol="AAPL",
        bars=_bars(),
        event_text="AAPL earnings beat with strong guidance",
        event=None,
        portfolio=PortfolioSnapshot(),
        user_is_approved=True,
    )

    assert rec.ai_explanation is not None
    assert rec.llm_provenance is not None
    assert rec.llm_provenance.provider == "mock"
    assert rec.llm_provenance.fallback_used is True
    assert rec.llm_provenance.validation_errors
    assert rec.entry.zone_low > 0
    assert rec.sizing.shares > 0


def test_api_llm_explanation_does_not_change_deterministic_recommendation_values(monkeypatch) -> None:
    _seed_approved_user()

    monkeypatch.setattr("macmarket_trader.service.settings.llm_enabled", False)
    monkeypatch.setattr("macmarket_trader.service.settings.llm_provider", "mock")
    monkeypatch.setattr(
        admin_routes,
        "recommendation_service",
        RecommendationService(llm_client=MockLLMClient()),
    )
    first = client.post(
        "/user/recommendations/generate",
        headers=_USER_AUTH,
        json={"symbol": "AAPL", "event_text": "AAPL earnings beat with strong guidance"},
    )
    assert first.status_code == 200, first.text

    monkeypatch.setattr("macmarket_trader.service.settings.llm_enabled", True)
    monkeypatch.setattr(
        admin_routes,
        "recommendation_service",
        RecommendationService(llm_client=MockLLMClient()),
    )
    second = client.post(
        "/user/recommendations/generate",
        headers=_USER_AUTH,
        json={"symbol": "AAPL", "event_text": "AAPL earnings beat with strong guidance"},
    )
    assert second.status_code == 200, second.text

    rows = client.get("/user/recommendations", headers=_USER_AUTH)
    assert rows.status_code == 200, rows.text
    by_uid = {row["recommendation_id"]: row["payload"] for row in rows.json()}
    first_payload = by_uid[first.json()["recommendation_id"]]
    second_payload = by_uid[second.json()["recommendation_id"]]

    assert _decision_snapshot(first_payload) == _decision_snapshot(second_payload)
    assert second_payload["ai_explanation"]["explanation_only"] is True
    assert set(second_payload["ai_explanation"]["deterministic_engine_owns"]) == {
        "entry",
        "stop",
        "target",
        "sizing",
        "approval",
        "order_routing",
    }


def test_opportunity_intelligence_falls_back_when_llm_disabled(monkeypatch) -> None:
    first_id, second_id = _seed_two_recommendations(monkeypatch)

    response = client.post(
        "/user/recommendations/opportunity-intelligence",
        headers=_USER_AUTH,
        json={
            "selected_recommendation_ids": [first_id, second_id],
            "include_better_elsewhere": True,
            "max_candidates": 4,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["explanation_only"] is True
    assert payload["provenance"]["fallback_used"] is True
    assert set(payload["provenance"]["candidate_ids"]) == {first_id, second_id}
    assert "approved" in payload["deterministic_engine_owns"]
    assert "entry" in payload["deterministic_engine_owns"]


def test_opportunity_intelligence_does_not_change_trade_fields(monkeypatch) -> None:
    first_id, second_id = _seed_two_recommendations(monkeypatch)
    before = client.get("/user/recommendations", headers=_USER_AUTH)
    assert before.status_code == 200, before.text
    before_by_id = {row["recommendation_id"]: _decision_snapshot(row["payload"]) for row in before.json()}

    response = client.post(
        "/user/recommendations/opportunity-intelligence",
        headers=_USER_AUTH,
        json={"selected_recommendation_ids": [first_id, second_id], "include_better_elsewhere": False},
    )
    assert response.status_code == 200, response.text

    after = client.get("/user/recommendations", headers=_USER_AUTH)
    assert after.status_code == 200, after.text
    after_by_id = {row["recommendation_id"]: _decision_snapshot(row["payload"]) for row in after.json()}
    assert before_by_id[first_id] == after_by_id[first_id]
    assert before_by_id[second_id] == after_by_id[second_id]


def test_opportunity_intelligence_rejects_unscanned_llm_symbols(monkeypatch) -> None:
    first_id, second_id = _seed_two_recommendations(monkeypatch)
    monkeypatch.setattr("macmarket_trader.service.settings.llm_enabled", True)
    monkeypatch.setattr("macmarket_trader.service.settings.llm_provider", "openai")
    monkeypatch.setattr(
        admin_routes,
        "recommendation_service",
        RecommendationService(llm_client=MalformedLLMClient()),
    )

    response = client.post(
        "/user/recommendations/opportunity-intelligence",
        headers=_USER_AUTH,
        json={
            "selected_recommendation_ids": [first_id, second_id],
            "include_better_elsewhere": False,
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provenance"]["provider"] == "mock"
    assert payload["provenance"]["fallback_used"] is True
    assert payload["provenance"]["validation_errors"]
    assert "ZZZZ" not in {candidate["symbol"] for candidate in payload["better_elsewhere"]}
    assert payload["best_deterministic_symbol"] in {"AAPL", "MSFT"}
