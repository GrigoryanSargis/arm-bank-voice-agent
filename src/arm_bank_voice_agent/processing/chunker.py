from __future__ import annotations

from arm_bank_voice_agent.models.chunk import DocumentChunk
from arm_bank_voice_agent.models.schema import BankDocument


class DocumentChunker:
    def __init__(self, max_chars: int = 1200, overlap_chars: int = 120) -> None:
        if overlap_chars >= max_chars:
            raise ValueError("overlap_chars must be smaller than max_chars")
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk_documents(self, documents: list[BankDocument]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for document in documents:
            chunks.extend(self.chunk_document(document))
        return chunks

    def chunk_document(self, document: BankDocument) -> list[DocumentChunk]:
        paragraphs = self._prepare_paragraphs(document.content)
        windows = self._build_windows(paragraphs)
        output: list[DocumentChunk] = []
        for idx, text in enumerate(windows):
            chunk_id = DocumentChunk.make_chunk_id(
                bank=document.bank,
                topic=document.topic,
                source_url=str(document.source_url),
                chunk_index=idx,
                text=text,
            )
            output.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    bank=document.bank,
                    topic=document.topic,
                    subtopic=document.subtopic,
                    language=document.language,
                    source_url=document.source_url,
                    page_title=document.page_title,
                    section_path=document.section_path,
                    chunk_index=idx,
                    text=text,
                    token_estimate=max(1, len(text) // 4),
                )
            )
        return output

    def _prepare_paragraphs(self, content: str) -> list[str]:
        raw_parts = [p.strip() for p in content.splitlines() if p.strip()]
        if not raw_parts:
            raw_parts = [content.strip()] if content.strip() else []
        prepared: list[str] = []
        for part in raw_parts:
            if len(part) <= self.max_chars:
                prepared.append(part)
                continue
            start = 0
            step = self.max_chars - self.overlap_chars
            while start < len(part):
                prepared.append(part[start : start + self.max_chars])
                start += max(1, step)
        return prepared

    def _build_windows(self, paragraphs: list[str]) -> list[str]:
        if not paragraphs:
            return []
        windows: list[str] = []
        current: list[str] = []
        current_len = 0
        for paragraph in paragraphs:
            paragraph_len = len(paragraph)
            if current and current_len + 1 + paragraph_len > self.max_chars:
                windows.append("\n".join(current))
                overlap_block = self._tail_overlap("\n".join(current))
                current = [overlap_block, paragraph] if overlap_block else [paragraph]
                current_len = sum(len(item) for item in current) + max(len(current) - 1, 0)
                continue
            current.append(paragraph)
            current_len += paragraph_len + (1 if current_len else 0)
        if current:
            windows.append("\n".join(current))
        return windows

    def _tail_overlap(self, text: str) -> str:
        if len(text) <= self.overlap_chars:
            return text
        return text[-self.overlap_chars :].lstrip()