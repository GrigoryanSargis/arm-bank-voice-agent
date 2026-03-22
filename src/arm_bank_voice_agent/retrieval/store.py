from __future__ import annotations

import json
from pathlib import Path

from arm_bank_voice_agent.models.chunk import DocumentChunk


class ChunkStore:
    def save(self, chunks: list[DocumentChunk], output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [chunk.model_dump(mode="json") for chunk in chunks]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def load(self, input_path: str | Path) -> list[DocumentChunk]:
        path = Path(input_path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        return [DocumentChunk.model_validate(item) for item in payload]