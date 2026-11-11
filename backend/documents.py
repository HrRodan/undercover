"""Document section parser, section lookup, keyword search, and instruction queries."""

import re
import threading

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import (
    ClaimsManualRecord,
    InstructionsRecord,
    PolicyWordingRecord,
)
from backend.schemas import (
    ClaimsManualResponse,
    DocumentSectionDetail,
    DocumentSectionSummary,
    InstructionsResponse,
    PolicyWordingResponse,
)
from backend.seed import (
    CLAIM_INSTRUCTIONS,
    QUEUE_INSTRUCTIONS,
    sync_docs_and_instructions,
)

_DOC_ALIASES: dict[str, str] = {
    "policy_wording": "policy_wording",
    "wording": "policy_wording",
    "policy": "policy_wording",
    "claims_manual": "claims_manual",
    "manual": "claims_manual",
}
_MIN_SEARCH_TERM_LEN = 2


def get_policy_wording_doc(
    session: Session, write_lock: threading.RLock
) -> PolicyWordingResponse:
    """Return the active contractual policy wording."""
    sync_docs_and_instructions(session, write_lock)
    wording = session.scalar(select(PolicyWordingRecord))
    if wording is None:
        raise HTTPException(status_code=404, detail="Policy wording not found")
    return PolicyWordingResponse(version=wording.version, content=wording.content)


def get_claims_manual_doc(
    session: Session, write_lock: threading.RLock
) -> ClaimsManualResponse:
    """Return the active internal claims handling manual."""
    sync_docs_and_instructions(session, write_lock)
    manual = session.scalar(select(ClaimsManualRecord))
    if manual is None:
        raise HTTPException(status_code=404, detail="Claims manual not found")
    return ClaimsManualResponse(version=manual.version, content=manual.content)


def get_instructions_doc(
    session: Session, write_lock: threading.RLock
) -> InstructionsResponse:
    """Return the read-only system prompts for the UnderCover Agent."""
    sync_docs_and_instructions(session, write_lock)
    record = session.scalar(
        select(InstructionsRecord).where(InstructionsRecord.id == 1)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Instructions not found")
    return InstructionsResponse(
        instructions=record.instructions,
        queue_instructions=record.queue_instructions or QUEUE_INSTRUCTIONS,
        claim_instructions=record.claim_instructions or CLAIM_INSTRUCTIONS,
    )


def _normalize_doc_name(doc_name: str) -> str:
    """Normalize a document identifier to policy_wording or claims_manual."""
    key = doc_name.strip().lower().replace("-", "_").replace(" ", "_")
    resolved = _DOC_ALIASES.get(key)
    if resolved is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Document {doc_name} not found. Use policy_wording or claims_manual."
            ),
        )
    return resolved


def _parse_markdown_sections(
    doc_name: str, markdown_text: str
) -> list[DocumentSectionDetail]:
    """Split a markdown document by level-2 headings into addressable sections."""
    lines = markdown_text.splitlines()
    sections: list[DocumentSectionDetail] = []
    current_title: str | None = None
    current_id: str | None = None
    current_lines: list[str] = []
    sec_counter = 0

    for line in lines:
        if line.startswith("## "):
            if current_title is not None and current_id is not None:
                sections.append(
                    DocumentSectionDetail(
                        doc_name=doc_name,
                        section_id=current_id,
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                    )
                )
            sec_counter += 1
            heading = line[3:].strip()
            match = re.match(r"^(\d+)\.\s+(.*)$", heading)
            current_id = match.group(1) if match else str(sec_counter)
            current_title = heading
            current_lines = [line]
        elif current_title is not None:
            current_lines.append(line)

    if current_title is not None and current_id is not None:
        sections.append(
            DocumentSectionDetail(
                doc_name=doc_name,
                section_id=current_id,
                title=current_title,
                content="\n".join(current_lines).strip(),
            )
        )
    return sections


def _load_doc_sections(
    session: Session, doc_name: str, write_lock: threading.RLock
) -> list[DocumentSectionDetail]:
    """Load and parse all sections for policy_wording or claims_manual."""
    canonical = _normalize_doc_name(doc_name)
    if canonical == "policy_wording":
        content = get_policy_wording_doc(session, write_lock).content
    else:
        content = get_claims_manual_doc(session, write_lock).content
    return _parse_markdown_sections(canonical, content)


def list_document_sections(
    session: Session, doc_name: str, write_lock: threading.RLock
) -> list[DocumentSectionSummary]:
    """Return section summaries (IDs and titles) for the given document."""
    sections = _load_doc_sections(session, doc_name, write_lock)
    return [
        DocumentSectionSummary(
            doc_name=s.doc_name,
            section_id=s.section_id,
            title=s.title,
        )
        for s in sections
    ]


def _slugify(value: str) -> str:
    """Normalize a string for case-insensitive section matching."""
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def get_document_section(
    session: Session, doc_name: str, section_id: str, write_lock: threading.RLock
) -> DocumentSectionDetail:
    """Return a single section from policy_wording or claims_manual by ID or title."""
    sections = _load_doc_sections(session, doc_name, write_lock)
    needle = section_id.strip()
    needle_slug = _slugify(needle)
    needle_num_match = re.match(r"^(?:section\s+)?(\d+)$", needle.lower())
    needle_num = needle_num_match.group(1) if needle_num_match else None

    for sec in sections:
        if (
            sec.section_id.lower() == needle.lower()
            or (needle_num is not None and sec.section_id == needle_num)
            or _slugify(sec.title) == needle_slug
        ):
            return sec

    for sec in sections:
        if needle_slug and needle_slug in _slugify(sec.title):
            return sec

    raise HTTPException(
        status_code=404,
        detail=f"Section '{section_id}' not found in {doc_name}",
    )


def search_document_sections(
    session: Session, query: str, write_lock: threading.RLock
) -> list[DocumentSectionDetail]:
    """Search across both policy_wording and claims_manual for matching sections."""
    all_sections = _load_doc_sections(
        session, "policy_wording", write_lock
    ) + _load_doc_sections(session, "claims_manual", write_lock)
    terms = [t for t in _slugify(query).split() if len(t) >= _MIN_SEARCH_TERM_LEN]
    if not terms:
        return all_sections[:5]

    scored: list[tuple[int, DocumentSectionDetail]] = []
    for sec in all_sections:
        haystack_title = _slugify(sec.title)
        haystack_body = _slugify(sec.content)
        score = 0
        for term in terms:
            if term in haystack_title:
                score += 3
            if term in haystack_body:
                score += 1
        if score > 0:
            scored.append((score, sec))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [sec for _, sec in scored[:8]]
