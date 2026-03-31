"""Audit trail recorder for recommendation payloads."""

from macmarket_trader.domain.schemas import AuditRecord, TradeRecommendation


class AuditEngine:
    """In-memory audit recorder suitable for testing and local development."""

    def __init__(self) -> None:
        self.records: list[AuditRecord] = []

    def record(self, recommendation: TradeRecommendation) -> AuditRecord:
        record = AuditRecord(
            recommendation_id=recommendation.recommendation_id,
            payload=recommendation.model_dump(mode="json"),
        )
        self.records.append(record)
        return record
