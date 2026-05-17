"""
PDF Extraction Module for Bursa Malaysia IPO Prospectuses.

Targets key sections: Financial Information, Risk Factors, IPO Details.
Uses pdfplumber as primary extractor (pure Python, no C build tools needed),
with PyPDF2 as fallback.
"""

import re
import pdfplumber
from typing import Optional

try:
    from PyPDF2 import PdfReader
    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

# ── Section anchors commonly found in Malaysian prospectuses ──
SECTION_PATTERNS = {
    "financial": re.compile(
        r"(?:financial\s+(?:information|statements|performance|highlights)|"
        r"profit\s+(?:and\s+loss|before\s+tax)|"
        r"balance\s+sheet|"
        r"cash\s+flow\s+statement|"
        r"dividend\s+(?:policy|history)|"
        r"historical\s+financial)",
        re.IGNORECASE
    ),
    "risk": re.compile(
        r"(?:risk\s+factors?|key\s+risks?|principal\s+risks?|"
        r"risk\s+associated|risk\s+related|material\s+risks?)",
        re.IGNORECASE
    ),
    "ipo_details": re.compile(
        r"(?:details?\s+of\s+(?:the\s+)?(?:offer|listing|ipo)|"
        r"offer\s+(?:price|for\s+sale)|"
        r"utilization\s+of\s+proceeds|"
        r"proceeds?\s+from\s+(?:the\s+)?(?:offer|listing|ipo)|"
        r"investment\s+overview|"
        r"basis\s+of\s+(?:offer|listing)|"
        r"share\s+capital\s+and\s+voting\s+rights|"
        r"dividend\s+(?:policy|yield)|"
        r"listing\s+statistics|"
        r"enlarged\s+share\s+capital|"
        r"expected\s+timetable)",
        re.IGNORECASE
    ),
}

MAX_CHARS_PER_SECTION = 8000


def extract_prospectus_data(file_path: str) -> dict:
    """
    Extract key sections from a Malaysian IPO prospectus PDF.

    Returns:
        dict with keys: 'financial', 'risk', 'ipo_details', 'full_text_sample'
    """
    result = {
        "financial": "",
        "risk": "",
        "ipo_details": "",
        "full_text_sample": "",
    }

    # ── Phase 1: Extract all text ──
    full_text = _extract_with_pdfplumber(file_path)

    if not full_text.strip() and HAS_PYPDF2:
        full_text = _extract_with_pypdf2(file_path)

    if not full_text.strip():
        raise ValueError(
            "Could not extract any text from the PDF. "
            "It may be a scanned image PDF or password-protected."
        )

    # Store a sample for context
    result["full_text_sample"] = full_text[:3000]

    # ── Phase 2: Locate and extract key sections ──
    sections = _split_into_sections(full_text)

    for section_name, pattern in SECTION_PATTERNS.items():
        best_match = _find_best_section(sections, pattern)
        if best_match:
            result[section_name] = best_match[:MAX_CHARS_PER_SECTION]

    # ── Phase 3: If section-based extraction found little, use keyword proximity ──
    for key in ["financial", "risk", "ipo_details"]:
        if not result[key]:
            result[key] = _keyword_proximity_extract(full_text, key)

    return result


def _extract_with_pdfplumber(file_path: str) -> str:
    """Extract text using pdfplumber — pure Python, good with tables."""
    pages = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            # Also extract tables as text for financial data
            tables = page.extract_tables() or []
            for table in tables:
                for row in table:
                    text += "\n" + " | ".join(str(cell) or "" for cell in row)
            pages.append(text)
    return "\n\n".join(pages)


def _extract_with_pypdf2(file_path: str) -> str:
    """Fallback extraction with PyPDF2 — simple but reliable."""
    reader = PdfReader(file_path)
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n\n".join(pages)


def _split_into_sections(text: str) -> list[tuple[str, str]]:
    """Split full text into rough sections based on heading-like lines."""
    lines = text.split("\n")
    sections = []
    current_heading = "Preamble"
    current_body = []

    for line in lines:
        stripped = line.strip()
        if len(stripped) > 4 and len(stripped) < 120:
            is_heading = (
                stripped.isupper()
                or stripped.istitle()
                or re.match(r"^[\d]+\.\s+[A-Z]", stripped)
                or re.match(r"^(?:SECTION|PART)\s+[\dIVX]+", stripped, re.IGNORECASE)
            )
            if is_heading:
                if current_body:
                    sections.append((current_heading, "\n".join(current_body)))
                current_heading = stripped
                current_body = []
                continue

        current_body.append(line)

    if current_body:
        sections.append((current_heading, "\n".join(current_body)))

    return sections


def _find_best_section(sections: list[tuple[str, str]], pattern: re.Pattern) -> str:
    """Find the section whose heading best matches the given pattern."""
    matches = []
    for heading, body in sections:
        if pattern.search(heading):
            matches.append(body)

    if matches:
        return max(matches, key=len)
    return ""


def _keyword_proximity_extract(text: str, section_key: str) -> str:
    """Last-resort extraction: find keyword anchors and grab surrounding text."""
    anchors = {
        "financial": [
            "revenue", "profit after tax", "PATAMI", "earnings per share",
            "dividend", "gearing", "net cash", "financial year", "EBITDA",
            "cash flow from operations"
        ],
        "risk": [
            "risk factor", "key risk", "concentration risk", "reliance on",
            "dependent on", "may be adversely", "cannot assure", "fluctuation",
            "regulatory risk", "competition"
        ],
        "ipo_details": [
            "offer price", "proceeds", "utilization of proceeds", "public issue",
            "offer for sale", "listing", "IPO", "enlarged share capital",
            "market capitalisation", "expected listing"
        ],
    }

    keywords = anchors.get(section_key, [])
    collected = []

    for kw in keywords:
        idx = text.lower().find(kw.lower())
        if idx != -1:
            start = max(0, idx - 500)
            end = min(len(text), idx + 1500)
            snippet = text[start:end]
            collected.append(snippet)

    if collected:
        merged = "\n\n---\n\n".join(collected)
        return merged[:MAX_CHARS_PER_SECTION]

    return ""


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_processor.py <path_to_pdf>")
        sys.exit(1)

    data = extract_prospectus_data(sys.argv[1])
    for key, val in data.items():
        print(f"\n{'='*60}")
        print(f"SECTION: {key}")
        print(f"{'='*60}")
        print(val[:500] if val else "(empty)")