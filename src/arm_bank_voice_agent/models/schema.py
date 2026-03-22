from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


Topic = Literal["credit", "deposit", "branch"]


class StructuredData(BaseModel):
    currency: list[str] = Field(default_factory=list)
    interest_rates: list[str] = Field(default_factory=list)
    term_range: str | None = None
    fees: list[str] = Field(default_factory=list)
    eligibility: list[str] = Field(default_factory=list)
    documents: list[str] = Field(default_factory=list)
    address: str | None = None
    working_hours: str | None = None
    phone: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class BankDocument(BaseModel):
    bank: str
    topic: Topic
    subtopic: str | None = None
    language: str = "hy"
    page_title: str
    source_url: HttpUrl
    source_type: Literal["html"] = "html"
    section_path: list[str] = Field(default_factory=list)
    content: str
    structured_data: StructuredData = Field(default_factory=StructuredData)
    scraped_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_hash: str | None = None
    is_active: bool = True

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("document content must not be empty")
        return normalized

    def with_hash(self) -> "BankDocument":
        payload = "|".join(
            [
                self.bank,
                self.topic,
                str(self.source_url),
                self.page_title,
                self.content,
            ]
        )
        self.content_hash = sha256(payload.encode("utf-8")).hexdigest()
        return self