from __future__ import annotations

from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

Topic = Literal["credit", "deposit", "branch"]


class DocumentChunk(BaseModel):
    chunk_id: str
    bank: str
    topic: Topic
    subtopic: str | None = None
    language: str = "hy"
    source_url: HttpUrl
    page_title: str
    section_path: list[str] = Field(default_factory=list)
    chunk_index: int
    text: str
    token_estimate: int = 0

    @staticmethod
    def make_chunk_id(*, bank: str, topic: str, source_url: str, chunk_index: int, text: str) -> str:
        payload = f"{bank}|{topic}|{source_url}|{chunk_index}|{text}"
        return sha256(payload.encode("utf-8")).hexdigest()