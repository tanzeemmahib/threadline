from __future__ import annotations

import json
from typing import Any

from app.prompts import load_prompt
from app.providers.base import ModelProvider
from app.providers.openai_compatible import _format_schema_for_prompt
from app.schemas.models import AnalyzeRequest, ProviderResult
from app.schemas.reverie_evaluation import ReverieOneShotModelOutput
from app.services.field_key_normalizer import format_canonical_keys_for_prompt


async def run_reverie_one_shot(
    request: AnalyzeRequest,
    provider: ModelProvider[Any],
) -> ProviderResult:
    """Run the preregistered, citation-capable one-call Reverie baseline."""

    template = load_prompt("reverie_one_shot", "v1")
    schema_block = _format_schema_for_prompt(ReverieOneShotModelOutput.model_json_schema())
    system_prompt = "\n\n".join(
        [template.content, format_canonical_keys_for_prompt(), schema_block]
    )
    incident = request.incident.model_dump(mode="json")
    evidence_chunks = [
        "<incident_context>\n"
        f"{json.dumps(incident, ensure_ascii=False, sort_keys=True)}\n"
        "</incident_context>"
    ]
    for record in request.records:
        metadata = record.model_dump(mode="json")
        metadata.pop("text", None)
        evidence_chunks.append(
            f"<untrusted_evidence record_id={record.record_id!r}>\n"
            f"<record_metadata>{json.dumps(metadata, ensure_ascii=False, sort_keys=True)}</record_metadata>\n"
            f"<record_text>\n{record.text}\n</record_text>\n"
            "</untrusted_evidence>"
        )
    return await provider.generate_structured(
        template_id=template.template_id,
        template_version=template.version,
        system_prompt=system_prompt,
        user_prompt="\n".join(evidence_chunks),
        response_model=ReverieOneShotModelOutput,
        mock_payload={},
    )
