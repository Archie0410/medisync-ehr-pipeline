"""Patient document extraction pipeline.

Flow:
  1. Resolve patient by MRN
  2. Load all orders (sorted by order_date) with their documents
  3. Extract raw text from each PDF via PyMuPDF
  4. Build a timeline bundle
  5. Send to LLM for structured extraction
  6. Persist result to patient_extractions + markdown file
"""

import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.patient import Patient
from app.models.order import Order
from app.models.document import Document
from app.models.extraction import PatientExtraction
from app.services import llm_client

logger = logging.getLogger("medisync.extraction")

SYSTEM_PROMPT = """\
You are a clinical data analyst. You will receive text extracted from healthcare \
documents (PDFs) for a single patient, presented in chronological order.

Your task: Analyze ALL documents and produce a single comprehensive structured JSON object \
that merges and organizes the clinical information.

Return ONLY valid JSON (no markdown fences, no explanation). Use this schema:

{
  "patient_summary": {
    "dob": "string",
    "primary_diagnosis": "string",
    "additional_diagnoses": ["string"]
  },
  "timeline": [
    {
      "date": "YYYY-MM-DD",
      "document_type": "string",
      "clinician": "string or null",
      "key_findings": ["string"],
      "vitals": {
        "bp": "string or null",
        "hr": "string or null",
        "temp": "string or null",
        "weight": "string or null",
        "o2_sat": "string or null"
      },
      "medications_mentioned": ["string"],
      "interventions": ["string"],
      "goals_or_plan": ["string"],
      "status_or_outcome": "string or null"
    }
  ],
  "medications_across_visits": ["string"],
  "allergies": "string or null",
  "overall_clinical_summary": "string (2-4 sentences summarizing the patient's care trajectory)",
  "flags_or_concerns": ["string (any clinical red flags, missing info, or inconsistencies)"]
}

Rules:
- If a field is not found in any document, use null or empty array.
- Dates should be ISO format (YYYY-MM-DD) when possible.
- timeline entries should be ordered chronologically.
- Merge duplicate medication names.
- Be precise — do NOT hallucinate information not in the source text.
"""


async def run_extraction(db: AsyncSession, mrn: str) -> PatientExtraction:
    """Run the full extraction pipeline for a patient."""
    settings = get_settings()

    result = await db.execute(select(Patient).where(Patient.mrn == mrn))
    patient = result.scalar_one_or_none()
    if not patient:
        raise PatientNotFoundError(f"Patient MRN={mrn} not found")

    extraction = PatientExtraction(
        patient_id=patient.id,
        status="processing",
        provider=settings.extraction_provider,
        model_name=settings.extraction_model,
    )
    db.add(extraction)
    await db.flush()

    try:
        orders = await _load_patient_orders_with_docs(db, patient.id)

        if not orders:
            extraction.status = "completed"
            extraction.documents_processed = 0
            extraction.structured_data = {"message": "No orders/documents found for this patient"}
            extraction.markdown = "# No documents found\n\nThis patient has no orders with attached documents."
            extraction.completed_at = datetime.now(timezone.utc)
            await db.flush()
            return extraction

        doc_timeline = _build_document_timeline(orders)
        total_docs = len(doc_timeline)

        user_prompt = _build_llm_prompt(patient, doc_timeline)

        logger.info(
            "Sending %d documents to %s/%s for patient MRN=%s",
            total_docs, settings.extraction_provider, settings.extraction_model, mrn,
        )

        structured = await llm_client.complete_json(SYSTEM_PROMPT, user_prompt)

        markdown = _structured_to_markdown(patient, structured)

        md_dir = Path(settings.extractions_path)
        md_dir.mkdir(parents=True, exist_ok=True)
        md_path = md_dir / f"{mrn}_{extraction.id}.md"
        md_path.write_text(markdown, encoding="utf-8")

        extraction.status = "completed"
        extraction.documents_processed = total_docs
        extraction.structured_data = structured
        extraction.markdown = markdown
        extraction.markdown_path = str(md_path)
        extraction.completed_at = datetime.now(timezone.utc)

        for entry in doc_timeline:
            doc_obj = entry["_doc_obj"]
            doc_obj.extracted_data = {
                "text_length": len(entry["text"]),
                "extraction_id": extraction.id,
                "extracted_at": datetime.now(timezone.utc).isoformat(),
            }

        await db.flush()
        logger.info("Extraction %d completed: %d docs processed", extraction.id, total_docs)
        return extraction

    except Exception as e:
        logger.error("Extraction failed for MRN=%s: %s", mrn, e)
        extraction.status = "failed"
        extraction.error_message = str(e)
        extraction.completed_at = datetime.now(timezone.utc)
        await db.flush()
        return extraction


async def get_extractions_for_patient(db: AsyncSession, patient_id: int) -> list[PatientExtraction]:
    result = await db.execute(
        select(PatientExtraction)
        .where(PatientExtraction.patient_id == patient_id)
        .order_by(PatientExtraction.created_at.desc())
    )
    return list(result.scalars().all())


async def get_extraction_by_id(db: AsyncSession, extraction_id: int) -> PatientExtraction | None:
    result = await db.execute(
        select(PatientExtraction).where(PatientExtraction.id == extraction_id)
    )
    return result.scalar_one_or_none()


# ---- Internal helpers ----

async def _load_patient_orders_with_docs(db: AsyncSession, patient_id: int) -> list[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.patient_id == patient_id)
        .options(selectinload(Order.documents))
        .order_by(Order.order_date.asc(), Order.created_at.asc())
    )
    return list(result.scalars().all())


def _extract_pdf_text(storage_path: str) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    path = Path(storage_path)
    if not path.is_file():
        return f"[File not found: {storage_path}]"
    try:
        doc = fitz.open(str(path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def _build_document_timeline(orders: list[Order]) -> list[dict]:
    """Build a chronologically sorted list of document entries."""
    entries = []
    for order in orders:
        for doc in order.documents:
            if not doc.storage_path:
                continue
            text = _extract_pdf_text(doc.storage_path)
            if not text.strip() or text.startswith("["):
                continue
            entries.append({
                "order_date": order.order_date.isoformat() if order.order_date else "unknown",
                "doc_type": order.doc_type or "Unknown",
                "order_id": order.order_id,
                "filename": doc.filename,
                "text": text,
                "_doc_obj": doc,
            })
    entries.sort(key=lambda e: e["order_date"])
    return entries


MAX_CHARS_PER_DOC = 8000
MAX_TOTAL_CHARS = 80000


def _build_llm_prompt(patient: Patient, timeline: list[dict]) -> str:
    """Build the user prompt with document texts only (no patient identifiers)."""
    header = (
        f"Below are {len(timeline)} clinical documents in chronological order.\n"
        f"Analyze them and return the structured JSON.\n\n"
    )

    sections = []
    total_chars = 0
    for i, entry in enumerate(timeline, 1):
        text = _redact_patient_identifiers(entry["text"], patient)
        if len(text) > MAX_CHARS_PER_DOC:
            text = text[:MAX_CHARS_PER_DOC] + "\n... [truncated]"
        if total_chars + len(text) > MAX_TOTAL_CHARS:
            text = text[:max(500, MAX_TOTAL_CHARS - total_chars)] + "\n... [truncated due to length limit]"

        safe_filename = _redact_patient_identifiers(entry["filename"] or "", patient)

        section = (
            f"--- DOCUMENT {i} ---\n"
            f"Date: {entry['order_date']}\n"
            f"Type: {entry['doc_type']}\n"
            f"File: {safe_filename}\n\n"
            f"{text}\n"
        )
        sections.append(section)
        total_chars += len(text)

    return header + "\n".join(sections)


def _redact_patient_identifiers(value: str, patient: Patient) -> str:
    """Mask direct patient identifiers before sending content to external LLM."""
    text = value or ""

    tokens = {
        patient.mrn,
        patient.first_name,
        patient.last_name,
        f"{patient.first_name} {patient.last_name}",
        f"{patient.last_name}, {patient.first_name}",
    }

    for token in sorted((t for t in tokens if t), key=len, reverse=True):
        pattern = re.compile(re.escape(token), flags=re.IGNORECASE)
        text = pattern.sub("[REDACTED]", text)

    return text


def _structured_to_markdown(patient: Patient, data: dict) -> str:
    """Convert the structured JSON extraction to a Markdown document."""
    lines = [
        f"# Clinical Summary: {patient.last_name}, {patient.first_name}",
        f"**MRN:** {patient.mrn}  ",
        f"**DOB:** {patient.dob}  ",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    summary = data.get("patient_summary", {})
    if summary:
        lines.append("## Patient Summary")
        lines.append(f"- **Primary Diagnosis:** {summary.get('primary_diagnosis', '--')}")
        additional = summary.get("additional_diagnoses", [])
        if additional:
            lines.append(f"- **Additional Diagnoses:** {', '.join(additional)}")
        lines.append("")

    overall = data.get("overall_clinical_summary")
    if overall:
        lines.append("## Overall Clinical Summary")
        lines.append(overall)
        lines.append("")

    timeline = data.get("timeline", [])
    if timeline:
        lines.append("## Visit Timeline")
        lines.append("")
        for entry in timeline:
            date = entry.get("date", "Unknown")
            doc_type = entry.get("document_type", "")
            clinician = entry.get("clinician", "")
            lines.append(f"### {date} — {doc_type}")
            if clinician:
                lines.append(f"**Clinician:** {clinician}")
            findings = entry.get("key_findings", [])
            if findings:
                lines.append("**Key Findings:**")
                for f in findings:
                    lines.append(f"- {f}")
            vitals = entry.get("vitals", {})
            vitals_str = ", ".join(
                f"{k}: {v}" for k, v in (vitals or {}).items() if v
            )
            if vitals_str:
                lines.append(f"**Vitals:** {vitals_str}")
            meds = entry.get("medications_mentioned", [])
            if meds:
                lines.append(f"**Medications:** {', '.join(meds)}")
            interventions = entry.get("interventions", [])
            if interventions:
                lines.append("**Interventions:**")
                for i in interventions:
                    lines.append(f"- {i}")
            goals = entry.get("goals_or_plan", [])
            if goals:
                lines.append("**Goals/Plan:**")
                for g in goals:
                    lines.append(f"- {g}")
            status = entry.get("status_or_outcome")
            if status:
                lines.append(f"**Status:** {status}")
            lines.append("")

    all_meds = data.get("medications_across_visits", [])
    if all_meds:
        lines.append("## All Medications Across Visits")
        for m in all_meds:
            lines.append(f"- {m}")
        lines.append("")

    allergies = data.get("allergies")
    if allergies:
        lines.append(f"## Allergies\n{allergies}")
        lines.append("")

    flags = data.get("flags_or_concerns", [])
    if flags:
        lines.append("## Flags & Concerns")
        for fl in flags:
            lines.append(f"- {fl}")
        lines.append("")

    return "\n".join(lines)


class PatientNotFoundError(ValueError):
    pass
