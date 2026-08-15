from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import Settings
from app.evaluation.v1_evidence import build_v1_evaluation


async def main() -> None:
    artifact = await build_v1_evaluation(Settings(provider_mode="mock"))
    destination = (
        Path(__file__).resolve().parents[2] / "shared" / "evaluation" / "threadline-v1.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(artifact.model_dump_json(indent=2), encoding="utf-8")
    print(destination)
    print(
        f"holdout_cases={artifact.holdout.case_count} "
        f"unsafe_releases={artifact.risk_bound.observed_unsafe_releases} "
        "conditional_negative_wilson_upper_percent="
        f"{artifact.risk_bound.conditional_negative_upper_bound_percent} "
        f"all_case_wilson_upper_percent={artifact.risk_bound.all_case_upper_bound_percent} "
        f"target_status={artifact.risk_bound.target_status}"
    )


if __name__ == "__main__":
    asyncio.run(main())
