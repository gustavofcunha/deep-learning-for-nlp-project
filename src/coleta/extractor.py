import re
from typing import Dict, Any, Optional
import pymupdf

RUNNING_HEADER_PATTERNS = [
    r"Published as a conference paper at ICLR \d{4}",
    r"Under review as a conference paper at ICLR \d{4}",
    r"Proceedings of the .* Conference .*",
    r"Proceedings of the \d+th .*",
    r"Advances in Neural Information Processing Systems .*",
    r"\d+th Conference on Neural Information Processing Systems .*",
    r"arXiv:\d{4}\.\d{4,5}(?:v\d+)?.*",
]

STOP_TERMS = [
    r"Acknowledgments?",
    r"Acknowledgements?",
    r"Funding(?:\s+and\s+Acknowledgments?)?",
    r"Author\s+Contributions?",
    r"Authors\?\'?\s+Contributions?",
    r"Limitations?(?:\s+and\s+(?:Future\s+Work|Societal\s+Impacts?))?",
    r"Ethic(?:s|\s+Statement|\s+Considerations)?(?:\s+and\s+Reproducibility)?",
    r"Reproducibility(?:\s+Statement)?",
    r"Broader\s+Impacts?(?:\s+Statement)?",
    r"Societal\s+Impacts?",
    r"Impact\s+Statement",
    r"Checklist",
    r"NeurIPS\s+Paper\s+Checklist",
    r"References",
    r"Bibliography",
    r"Literature\s+Cited",
    r"Works\s+Cited",
    r"Appendix(?:\s+[A-Z0-9]+)?",
    r"Appendices",
    r"Supplementary\s+Materials?",
    r"Supplemental\s+Materials?",
    r"Technical\s+Appendix",
]

SEC2_HEADINGS = [
    r"Related\s+Works?",
    r"Prior\s+Works?",
    r"Previous\s+Works?",
    r"Background(?:\s+and\s+Related\s+Works?)?",
    r"Preliminaries",
    r"Problem\s+(?:Formulation|Statement|Setup|Definition)",
    r"Overview",
    r"Methods?",
    r"Methodology",
    r"Approach",
    r"Framework",
    r"Proposed\s+Method",
    r"Model(?:\s+Architecture)?",
]

CONCLUSION_HEADINGS = [
    r"Conclusions?",
    r"Concluding\s+Remarks(?:\s+and\s+Future\s+Work)?",
    r"Conclusion\s+and\s+Future\s+(?:Work|Directions)",
    r"Conclusions?\s+and\s+(?:Discussion|Future\s+Work)",
    r"Discussion\s+and\s+Conclusions?",
    r"Summary\s+and\s+Conclusions?",
    r"Summary\s+and\s+Future\s+Work",
    r"Summary",
]


def clean_section_text(raw_text: str) -> str:
    #remove standalone page numbers running headers and excessive whitespace
    lines = raw_text.splitlines()
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        #skip page numbers
        if re.match(r"^\d+$", stripped):
            continue
        #skip running conference headers
        if any(re.match(pat, stripped, re.IGNORECASE) for pat in RUNNING_HEADER_PATTERNS):
            continue
        filtered_lines.append(stripped)
    text = "\n".join(filtered_lines)
    #normalize repeated blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_sections_from_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    #extract abstract introduction and conclusion from pdf bytes
    result = {
        "abstract": "",
        "introduction": "",
        "conclusion": "",
        "section_lengths": {
            "abstract_words": 0,
            "intro_words": 0,
            "conclusion_words": 0,
            "total_words": 0,
        },
        "is_valid": False,
    }

    try:
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    except Exception:
        #failed to open pdf document
        return result

    full_text_pages = []
    for page in doc:
        full_text_pages.append(page.get_text("text"))
    full_text = "\n".join(full_text_pages)
    doc.close()

    if not full_text.strip():
        #empty pdf text stream
        return result

    #compile boundary stop regex patterns
    stop_regex = "|".join(STOP_TERMS)
    stop_pattern = rf"(?:\n|\A)\s*(?:(?:\d{{1,2}}\.?|[IVXLCDM]+\.?)\s+)?(?:{stop_regex})\b"

    sec2_regex = "|".join(SEC2_HEADINGS)
    sec2_pattern = rf"(?:\n|\A)\s*(?:(?:2\.?\s+|2\s+|II\.?\s+)(?:{sec2_regex}|[A-Z][A-Za-z\s]{{2,30}}\n)|(?:{sec2_regex})\s*\n)"

    conc_regex = "|".join(CONCLUSION_HEADINGS)

    #abstract extraction requiring standalone heading or separator
    abstract_text = ""
    abs_match = re.search(
        r"(?:\n|\A)\s*(?:Abstract|ABSTRACT)\s*(?:\n|[:\-\.]\s+)(.*?)(?=\n\s*(?:(?:1|I)\.?\s+|1\s+)?(?:Introduction|INTRODUCTION)|\n\s*1\s+[A-Z])",
        full_text,
        re.DOTALL,
    )
    if abs_match:
        abstract_text = clean_section_text(abs_match.group(1))
    else:
        #fallback pattern for abstract
        abs_fallback = re.search(
            r"\b(?:Abstract|ABSTRACT)\b\s*[:\-\.]?\s*(.*?)(?=\n\s*(?:[A-Z0-9\.\s]{2,30}\n))",
            full_text[:4000],
            re.DOTALL,
        )
        if abs_fallback:
            abstract_text = clean_section_text(abs_fallback.group(1))

    #introduction extraction avoiding lowercase list item collisions
    intro_text = ""
    intro_match = re.search(
        rf"\n\s*(?:(?:1|I)\.?\s+|1\s+)?(?:Introduction|INTRODUCTION)\s*[:\.]?\s*\n(.*?)(?={sec2_pattern})",
        full_text,
        re.DOTALL,
    )
    if intro_match:
        intro_text = clean_section_text(intro_match.group(1))
    else:
        #fallback pattern for introduction with generic section 2
        intro_fallback = re.search(
            r"\n\s*(?:(?:1|I)\.?\s+|1\s+)?(?:Introduction|INTRODUCTION)\s*[:\.]?\s*\n(.*?)(?=\n\s*2\.?\s+[A-Z])",
            full_text,
            re.DOTALL,
        )
        if intro_fallback:
            intro_text = clean_section_text(intro_fallback.group(1))

    #conclusion extraction with comprehensive stop boundaries
    conclusion_text = ""
    conc_match = re.search(
        rf"\n\s*(?:(?:\d{{1,2}}\.?|[IVXLCDM]+\.?)\s+)?(?:{conc_regex})\b\s*[:\.]?\s*\n(.*?)(?={stop_pattern})",
        full_text,
        re.DOTALL | re.IGNORECASE,
    )
    if conc_match:
        conclusion_text = clean_section_text(conc_match.group(1))
    else:
        #fallback pattern targeting discussion when conclusion is absent
        conc_fallback = re.search(
            rf"\n\s*(?:(?:\d{{1,2}}\.?|[IVXLCDM]+\.?)\s+)?Discussions?\b\s*[:\.]?\s*\n(.*?)(?={stop_pattern})",
            full_text,
            re.DOTALL | re.IGNORECASE,
        )
        if conc_fallback:
            conclusion_text = clean_section_text(conc_fallback.group(1))

    abs_words = len(abstract_text.split())
    intro_words = len(intro_text.split())
    conc_words = len(conclusion_text.split())
    total_words = abs_words + intro_words + conc_words

    #quality threshold validation across all mandatory sections
    is_valid = (abs_words >= 50) and (intro_words >= 200) and (conc_words >= 50)

    result["abstract"] = abstract_text
    result["introduction"] = intro_text
    result["conclusion"] = conclusion_text
    result["section_lengths"] = {
        "abstract_words": abs_words,
        "intro_words": intro_words,
        "conclusion_words": conc_words,
        "total_words": total_words,
    }
    result["is_valid"] = is_valid
    return result
