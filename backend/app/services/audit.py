from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.schemas.models import AuditEvent


class AuditBuilder:
    def __init__(self, *, mock_mode: bool) -> None:
        self.mock_mode = mock_mode
        self.events: list[AuditEvent] = []
        self.base = datetime(2026, 4, 18, 22, 2, tzinfo=UTC) if mock_mode else datetime.now(UTC)

    def add(
        self,
        event_type: str,
        actor: str,
        record_ids: list[str],
        before: str,
        after: str,
        reason: str,
        *,
        prompt_version: str | None = None,
        human: bool = False,
    ) -> None:
        timestamp = (
            self.base + timedelta(seconds=len(self.events) * 3)
            if self.mock_mode
            else datetime.now(UTC)
        )
        origin = "human" if human else "machine"
        self.events.append(
            AuditEvent(
                event_id=f"AUDIT-{len(self.events) + 1:04d}",
                timestamp=timestamp,
                event_type=event_type,
                actor=actor,
                action=event_type,
                detail=reason,
                workflow_version="threadline-workflow/1.0.0",
                prompt_version=prompt_version,
                source_record_ids=record_ids,
                before=before,
                after=after,
                before_value=before,
                after_value=after,
                reason=reason,
                machine_or_human=origin,
                origin=origin,
                synthetic_mode=True,
            )
        )
