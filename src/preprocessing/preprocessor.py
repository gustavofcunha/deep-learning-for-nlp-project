import os
import re
import sys
import json
import time
import argparse
import unicodedata
from typing import Dict, Any, List, Optional

#regex patterns for text preprocessing and shortcut masking
RE_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
RE_STANDALONE_ACCENTS = re.compile(r"[\u00b4\u02c7\u02c6\u02dc\u02d8\u02da\u02dd\u02db\u02c9`]")
RE_MINUS_UNICODE = re.compile(r"[\u2212]")
RE_DEHYPHEN = re.compile(r"(\b\w+)\s*[-‐‑⁃]\s*\n\s*(\w+\b)")
RE_UNGLUE_URL = re.compile(r"(\b\w+?)(https?|ftp|www\.)", re.IGNORECASE)
RE_SPACED_PROTOCOL = re.compile(
    r"(?:\b|\()https?\s*:\s*/\s*/\s*|(?:\b|\()https?\s*:\s*//|(?:\b|\()https?\s*/\s*/\s*|\bhttp\s*:\s*//",
    re.IGNORECASE,
)
RE_PROTOCOL_LINEBREAK = re.compile(r"\b(https?://|ftp://|www\.)\s*\n\s*", re.IGNORECASE)
RE_URL = re.compile(
    r"\b(?:https?://|ftp://|www\.)[^\s\(\)\[\]\{\}<>\"']+(?:/[^\s\(\)\[\]\{\}<>\"']*)*"
    r"|\b(?:https?://|ftp://|www\.)\S+"
    r"|\b10\.\d{4,9}/\S+",
    re.IGNORECASE,
)
RE_BARE_DOMAIN = re.compile(
    r"\b(?<!@)(?:[a-zA-Z0-9\-]+\.)+(?:com|org|edu|gov|io|net|ai|info|me|de|uk|cn|fr|nl|jp|ru)(?=[/:\s\)\],;\"\'<>]|$)(?:[/:][^\s\)\],;\"\'<>\*]*)*",
    re.IGNORECASE,
)
RE_ORPHAN_PROTOCOL = re.compile(
    r"['\"]?https?(?:\([sS]\))?(?:\s*:\s*/\s*/|\s*:\s*//|\s*://|\s*:\s*|\([sS]\))[^\s\)\],;]*",
    re.IGNORECASE,
)
RE_CONSECUTIVE_URL = re.compile(r"(\s*\[URL\]\s*)+")
RE_FOOTNOTE_BEFORE_URL = re.compile(r"(?<=\s)\d{1,2}\s+(?=\[URL\])")

#latex blocks inline dollar math unicode math operators and raw latex commands
RE_MATH_BLOCK = re.compile(r"\$\$[\s\S]*?\$\$|\\begin\{(?:equation|align|gather|flalign|multline)\*?\}[\s\S]*?\\end\{(?:equation|align|gather|flalign|multline)\*?\}", re.IGNORECASE)
RE_MATH_INLINE = re.compile(r"(?<!\\)\$[^$\n]+\$")
RE_MATH_SYMBOLS = re.compile(r"\s*[∈∉⊆⊂∪∩≤≥≠≈±∇∑∏∫√∀∃⊤⊥∥|→←↔⇒]\s*")
RE_GREEK_SYMBOLS = re.compile(r"[\u0370-\u03ff]")
RE_MATH_EQUATIONS = re.compile(r"(?:\b[A-Za-z0-9_α-ωΑ-Ω]+\s*[\+\-\*/×·]\s*)?[A-Za-z0-9_α-ωΑ-Ω]+\s*[=><≤≥≠≈~]\s*[\+\-]?[A-Za-z0-9_α-ωΑ-Ω]+")
RE_MATH_OPTIM = re.compile(r"\b(?:arg\s*min|arg\s*max)\b[^\n,;\.]*")
RE_LATEX_CMD = re.compile(r"\\[A-Za-z]+(?:\{[^}]*\})*")
RE_CONSECUTIVE_MATH = re.compile(r"(\s*\[MATH\]\s*)+")

#citation patterns covering narrative parenthetical bracketed and alphanumeric styles
RE_DIGIT_GLUED_AUTHOR = re.compile(r"(\b|[a-z])\d+([A-Z][a-zA-Z])")
RE_SPACED_AUTHOR_ET_AL = re.compile(r"\b([A-Z][a-z]+)\s+([a-z])(?:\s+([a-z]))?\s+et[\.\s]+al", re.IGNORECASE)
RE_LIST_ET_AL = re.compile(r"(\[CITE\](?:\s*,\s*|\s+))et[\.\s]+al\.?", re.IGNORECASE)
RE_ORPHAN_PAREN_ET_AL = re.compile(
    r"\(?\s*et[\.\s]+al\.?,?\s*(?:19|20)\d{2}[a-z]?(?:[;,]\s*(?:19|20)?\d{2}[a-z]?)*\)?",
    re.IGNORECASE
)
RE_ORPHAN_UNOPENED_CITE = re.compile(
    r"(?m)(?:\A|^|[;\.\s])et[\.\s]*al\.?,?\s*(?:19|20)\d{2}[a-z]?(?:[;,]\s*(?:19|20)?\d{2}[a-z]?)*[;\)]"
)
RE_GENERIC_ORPHAN_ET_AL = re.compile(
    r"(?:\.\.\.\s*|\b)et[\.\s]*al\.?\)?",
    re.IGNORECASE
)

RE_BRACKET_NUMERIC = re.compile(r"\[(?:\d{1,3}(?:\s*[\-,\u2013]\s*\d{1,3})*(?:,\s*)?)+\]")
RE_BRACKET_ALPHA_KEY = re.compile(r"\[(?!(?:CITE|MATH|URL)\])[A-Z][A-Za-z0-9\+\*\-]{1,10}\]")
RE_PAREN_BLOCK = re.compile(r"\(([^()]+)\)")
RE_UNCLOSED_PAREN_CITE = re.compile(r"\([A-Z][a-zA-Z\u00C0-\u017F\.\-]+(?:\s+(?:and|&)\s+[A-Z][a-zA-Z\u00C0-\u017F\.\-]+|\s+et\s+al\.?)?,\s*(?:19|20)\d{2}[a-z]?[;,]")
RE_HAS_YEAR = re.compile(r"\b(?:19|20)\d{2}[a-z]?\b")

RE_NARRATIVE_ET_AL = re.compile(
    r"\b(?:[A-Z]\.\s*)*[A-Z][a-zA-Z\u00C0-\u017F\u00B4\.\'\-\*]*(?:\s*\'s)?\s*,?\s*et[\.\s]*al\.?,?(?:\s*\'s)?\s*"
    r"(?:\((?:19|20)\d{2}[a-z]?(?:[;,]\s*(?:(?:19|20)?\d{2})?[a-z]?)*\)|\((?:e\.g\.,?\s*)?(?:19|20)\d{2}[a-z]?\)|\[\d{1,3}(?:\s*[\-,\u2013]\s*\d{1,3})*(?:,\s*\d{1,3})*\]|\[CITE\]|\(\s*\[CITE\]\s*\))?",
    re.IGNORECASE
)

RE_NARRATIVE_MULTI_AUTH = re.compile(
    r"\b(?:[A-Z]\.\s*)*[A-Z][a-zA-Z\u00C0-\u017F\u00B4\.\'\-]+(?:\s*,\s*(?:[A-Z]\.\s*)*[A-Z][a-zA-Z\u00C0-\u017F\u00B4\.\'\-]+)*\s+(?:and|&)\s+(?:[A-Z]\.\s*)*[A-Z][a-zA-Z\u00C0-\u017F\u00B4\.\'\-]+(?:\s*\'s)?\s*"
    r"(?:\((?:19|20)\d{2}[a-z]?(?:[;,]\s*(?:(?:19|20)?\d{2})?[a-z]?)*\)|\((?:e\.g\.,?\s*)?(?:19|20)\d{2}[a-z]?\)|\[\d{1,3}(?:\s*[\-,\u2013]\s*\d{1,3})*(?:,\s*\d{1,3})*\]|\[CITE\]|\(\s*\[CITE\]\s*\))"
)

NON_AUTHOR_NOUNS = {
    "Figure", "Fig", "Table", "Tab", "Section", "Sec", "Equation", "Eq",
    "Theorem", "Lemma", "Definition", "Algorithm", "Appendix", "Step",
    "Model", "Dataset", "Case", "Phase", "Level", "Stage", "Group",
    "Class", "Order", "Type", "Task", "Part", "Day", "Year", "Month",
    "Grade", "Score", "Sample", "Example", "Rule", "Method", "Approach",
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
    "Conference", "Workshop", "Proceedings"
}

RE_SINGLE_AUTHOR = re.compile(
    r"\b([A-Z][a-zA-Z\u00C0-\u017F\'\-]+)(?:\'s)?\s*(\((?:19|20)\d{2}[a-z]?(?:[;,]\s*(?:(?:19|20)?\d{2})?[a-z]?)*\)|\[\d{1,3}(?:\s*[\-,\u2013]\s*\d{1,3})*(?:,\s*\d{1,3})*\]|\[CITE\]|\(\s*\[CITE\]\s*\))"
)

RE_NESTED_PAREN_CITE = re.compile(r"\((?:see|e\.g\.,?|cf\.|i\.e\.,?|also)?\s*\[CITE\](?:\s*,\s*\[CITE\])*\s*\)", re.IGNORECASE)
RE_ORPHAN_ET_AL = re.compile(r"\b[A-Z][a-zA-Z\u00C0-\u017F\u00B4\.\-]+(?:\s*\'s)?\s*,?\s*et[\.\s]*al\.?,?", re.IGNORECASE)
RE_APOSTROPHE_ORPHAN = re.compile(r"\b[A-Z]\'\s*\[CITE\]")
RE_CONSECUTIVE_CITE = re.compile(r"(\s*\[CITE\]\s*)+")
RE_CONSECUTIVE_CITE_SEMI = re.compile(r"\[CITE\](?:\s*[;,]\s*\[CITE\])+")

RE_CONFERENCE_HEADER = re.compile(
    r"(?im)^[^\n]*(?:"
    r"under review as a conference paper at iclr|"
    r"accepted as a conference paper at iclr|"
    r"published in|proceedings of the|appearing in proceedings of|"
    r"neurips \d{4}|icml \d{4}|acl \d{4}|iclr \d{4}|"
    r"annual meeting of the association for computational linguistics|"
    r"learning,\s+[a-z\s]+,\s+[a-z]+,\s+\d{4}\.?\s*jmlr|"
    r"jmlr:\s*w&cp\s+volume\s+\d+|"
    r"copyright\s+\d{4}\s+by\s+the\s+author\(s\)|"
    r"pmlr\s+\d+(?::\d+-\d+)?,\s+\d{4}|"
    r"volume\s+\d+\.\s*copyright\s+\d{4}\s+by\s+the\s+author\(s\)"
    r")[^\n]*\n?",
    re.MULTILINE
)
RE_PAGE_NUMBER = re.compile(r"^\s*\d+\s*$", re.MULTILINE)
RE_EQUATION_NUMBER = re.compile(r"(?m)^\s*\(\d{1,3}[a-z]?\)\s*$")
RE_EMAIL = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")
RE_AFFILIATION_FOOTNOTE = re.compile(r"(?im)^[^\n]*\b(?:equal contribution|corresponding author|work done while|intern(?:ed|ing)? at|part of this work was done|electronic address:?|e-mail:?|correspondence to:?)[^\n]*$")
RE_FOOTNOTE_URL_LINE = re.compile(r"(?im)^\s*\d+[\.:\s]*(?:https?://|www\.)\S+$")
RE_FIGURE_TABLE_CAPTION = re.compile(r"(?im)^\s*(?:figure|fig\.|table|tab\.)\s+\d+[:\.][\s\S]*?(?:\.\s*(?:\n|$)|(?=\n\s*\n|\Z))")
RE_BULLETS = re.compile(r"(?m)^\s*[•\u2022\u25cf\u25aa\u2023\*]\s*")
RE_GLUED_FOOTNOTE = re.compile(r"\b([a-z]{3,})[1-9](?=[,\.\s\)]|\[|$)")
RE_MULTI_SPACES = re.compile(r"[ \t]+")
RE_MULTI_NEWLINES = re.compile(r"\n{3,}")

#universal boundary stop markers for references appendices and author metadata
RE_BIBLIOGRAPHY_START = re.compile(
    r"(?im)^[ \t]*(?:"
    r"(?:[0-9]{1,2}\.?\s+|[IVXLCDM]+\.?\s+)?(?:references|bibliography|literature cited|works cited)\b[:\.]?"
    r"|impact statement\b[:\.]?"
    r"|broader impacts?(?:\s+statement)?\b[:\.]?"
    r"|ethical considerations?(?:\s+and\s+reproducibility)?\b[:\.]?"
    r"|reproducibility(?:\s+statement)?\b[:\.]?"
    r"|author\s+contributions?\b[:\.]?"
    r"|checklist\b[:\.]?"
    r"|neurips\s+paper\s+checklist\b[:\.]?"
    r"|(?:[0-9]{1,2}\.?\s+|[IVXLCDM]+\.?\s+)?appendix(?:\s+[a-z0-9]+)?\b[:\.]?"
    r"|(?:[0-9]{1,2}\.?\s+|[IVXLCDM]+\.?\s+)?appendices\b[:\.]?"
    r"|supplementary\s+materials?\b[:\.]?"
    r"|supplemental\s+materials?\b[:\.]?"
    r"|technical\s+appendix\b[:\.]?"
    r"|a\.\s+proofs?\b"
    r")[ \t]*$",
    re.MULTILINE
)

RE_SECTION_NUMBERED = re.compile(
    r"(?im)^[ \t]*(?:(?:[2-9]\.?\s+|[IVXLCDM]+\.?\s+)[A-Z][A-Za-z0-9\s,\-:]{2,50})[ \t]*$",
    re.MULTILINE
)

KNOWN_SECTION_HEADINGS = [
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
    r"Proposed\s+(?:Method|Approach|Framework|Model)",
    r"Model(?:\s+Architecture)?",
    r"Data(?:\s+and\s+Methods?)?",
    r"Datasets?",
    r"Experimental\s+(?:Setup|Settings|Design|Results)",
    r"Experiments?",
    r"System\s+Architecture",
    r"Consistency\s+Assumption\s+Veri[fﬁ]cation",
    r"Attitude\s+Identi[fﬁ]cation",
    r"Standard\s+Occupational\s+Classi[fﬁ]cation",
    r"Stage\s+1[:\s]+.*",
    r"Architecture\s+and\s+Experimental\s+Setup",
]
RE_KNOWN_SECTION = re.compile(
    rf"(?im)^[ \t]*(?:{'|'.join(KNOWN_SECTION_HEADINGS)})\b[:\.]?[ \t]*$",
    re.MULTILINE
)

HEADING_STOP_WORDS = {
    "and", "or", "of", "for", "in", "on", "with", "by", "as", "to", "the", "a", "an", "at", "from"
}

DEFAULT_INPUT_PATH = os.path.join("data", "raw", "collected_corpus.jsonl")
DEFAULT_OUTPUT_PATH = os.path.join("data", "processed", "preprocessed_corpus.jsonl")
DEFAULT_SYNTHETIC_INPUT_PATH = os.path.join("data", "raw", "synthetic_ai.jsonl")
DEFAULT_SYNTHETIC_OUTPUT_PATH = os.path.join("data", "processed", "synthetic_corpus.jsonl")
DEFAULT_SEEDS_REFERENCE_PATH = os.path.join("data", "processed", "preprocessed_corpus.jsonl")

def is_title_case_heading(line: str) -> bool:
    #detect title cased section header lines
    cleaned_line = line.strip()
    if not (4 <= len(cleaned_line) <= 45 and cleaned_line[0].isupper()):
        return False
    if cleaned_line.endswith((".", ",", ";", ":", "-", "‐", "?")):
        return False
    tokens = cleaned_line.split()
    if len(tokens) < 2 or len(tokens) > 6:
        return False
    for token in tokens:
        clean_token = re.sub(r"[^A-Za-z]", "", token)
        if not clean_token:
            continue
        if clean_token.lower() in HEADING_STOP_WORDS:
            continue
        if not clean_token[0].isupper():
            return False
    return True

def sanitize_section_boundaries(text: str, is_intro: bool = False) -> str:
    #truncate leaked downstream sections bibliographies and appendices
    if not text:
        return ""
    bibliography_match = RE_BIBLIOGRAPHY_START.search(text)
    if bibliography_match:
        text = text[:bibliography_match.start()]
    if is_intro:
        lines = text.split("\n")
        accumulated_words = 0
        cut_point = None
        for line_index, line in enumerate(lines):
            line_words = len(line.split())
            accumulated_words += line_words
            if accumulated_words >= 200:
                stripped_line = line.strip()
                if (
                    RE_SECTION_NUMBERED.match(stripped_line)
                    or RE_KNOWN_SECTION.match(stripped_line)
                    or is_title_case_heading(stripped_line)
                ):
                    cut_point = line_index
                    break
        if cut_point is not None:
            text = "\n".join(lines[:cut_point])
    return text.strip()

def strip_footnote_blocks(text: str) -> str:
    #remove multi line author affiliation and conference footnote blocks
    lines = text.split("\n")
    cleaned_lines = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()
        is_fn = False
        if re.match(r"^(?:(?:\d{1,2}|[*†‡§])\s*[A-Z]|Correspondence\s+to:?|Electronic\s+address:?|E-mail:?)", stripped, re.IGNORECASE):
            if any(cue in stripped.lower() for cue in ("university", "research", "institute", "laboratory", "department", "deepmind", "google", "meta", "microsoft", "adobe", "@", "correspondence")):
                is_fn = True
        elif any(cue in stripped.lower() for cue in ("equal contribution", "work done while", "internship at", "part of this work was done")):
            is_fn = True
        elif any(cue in stripped.lower() for cue in ("pmlr ", "jmlr", "copyright 20", "copyright 19")):
            is_fn = True

        if is_fn:
            i += 1
            while i < n:
                curr = lines[i].strip()
                if not curr:
                    i += 1
                    continue
                if any(cue in curr.lower() for cue in (
                    "@", "university", "institute", "department", "research", "laboratory",
                    "adobe", "google", "deepmind", "microsoft", "meta", "canada", "usa",
                    "author", "internship", "correspondence", "pmlr", "jmlr", "copyright",
                    "sydney", "lille", "france", "australia", "equal contribution"
                )) or re.match(r"^\d{1,2}[A-Z]", curr):
                    i += 1
                else:
                    break
            continue
        cleaned_lines.append(line)
        i += 1
    return "\n".join(cleaned_lines)

def dehyphenate(text: str) -> str:
    #reconnect words broken across line endings
    return RE_DEHYPHEN.sub(r"\1\2", text)

def normalize_unicode(text: str) -> str:
    #normalize unicode characters to canonical nfkc form and convert unicode minus
    text = RE_STANDALONE_ACCENTS.sub("", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = unicodedata.normalize("NFKC", text)
    text = RE_MINUS_UNICODE.sub("-", text)
    text = RE_CTRL_CHARS.sub("", text)
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return text

def remove_affiliations_and_emails(text: str) -> str:
    #expurge author affiliation footnotes emails and footnote urls
    cleaned = strip_footnote_blocks(text)
    cleaned = RE_AFFILIATION_FOOTNOTE.sub("", cleaned)
    cleaned = RE_EMAIL.sub("", cleaned)
    cleaned = RE_FOOTNOTE_URL_LINE.sub("", cleaned)
    return cleaned

def clean_footnotes(text: str) -> str:
    #strip trailing footnote index glued to vocabulary words
    return RE_GLUED_FOOTNOTE.sub(r"\1", text)

def remove_captions(text: str) -> str:
    #expurge isolated figure and table caption lines
    return RE_FIGURE_TABLE_CAPTION.sub("", text)

def remove_algorithm_pseudocode(text: str) -> str:
    #expurge algorithm pseudocode listings while preserving surrounding analytical prose
    lines = text.split("\n")
    filtered = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if re.match(r"^\s*Algorithm\s+\d+[:\s]", line, re.IGNORECASE):
            is_algo = False
            for step_idx in range(i + 1, min(i + 4, n)):
                if re.match(r"^\s*(?:1[:\.]|input:|require:|initialize:)", lines[step_idx], re.IGNORECASE):
                    is_algo = True
                    break
            if is_algo:
                j = i + 1
                while j < n:
                    curr = lines[j].strip()
                    if curr.lower().startswith("until meet stopping criterion") or curr.lower().startswith("until stopping"):
                        j += 1
                        break
                    if re.match(r"^\d+:\s*(?:until|return|end)", curr, re.IGNORECASE):
                        j += 1
                        break
                    if re.match(r"^[A-Z][a-z]+.*[a-z]{3,}\s+[a-z]{3,}", curr) and not any(kw in curr.lower() for kw in ("input:", "output:", "initialize", "repeat", "min", "max", "parameter", "matrix", "vector", "multipliers")):
                        break
                    j += 1
                i = j
                continue
        filtered.append(line)
        i += 1
    return "\n".join(filtered)

def remove_boilerplate(text: str) -> str:
    #remove venue boilerplate standalone equation numbers and isolated page numbering
    cleaned = RE_CONFERENCE_HEADER.sub("", text)
    cleaned = RE_PAGE_NUMBER.sub("", cleaned)
    cleaned = RE_EQUATION_NUMBER.sub("", cleaned)
    return cleaned

def mask_citations(text: str) -> str:
    #mask narrative parenthetical and numeric citations comprehensively
    text = RE_DIGIT_GLUED_AUTHOR.sub(r"\1 \2", text)
    text = RE_SPACED_AUTHOR_ET_AL.sub(r"\1\2\3 et al", text)
    text = RE_LIST_ET_AL.sub(r"\1", text)
    text = RE_ORPHAN_PAREN_ET_AL.sub(" [CITE] ", text)
    text = RE_ORPHAN_UNOPENED_CITE.sub(" [CITE] ", text)
    text = RE_NARRATIVE_ET_AL.sub(" [CITE] ", text)
    text = RE_NARRATIVE_MULTI_AUTH.sub(" [CITE] ", text)

    def _replace_single_author(match: re.Match) -> str:
        name = match.group(1)
        if name in NON_AUTHOR_NOUNS:
            return match.group(0)
        return " [CITE] "

    text = RE_SINGLE_AUTHOR.sub(_replace_single_author, text)
    text = RE_BRACKET_ALPHA_KEY.sub(" [CITE] ", text)

    def _replace_bracket_num(match: re.Match) -> str:
        val = match.group(0)
        if "0" in val and ("0," in val or "0 ," in val or "[0" in val):
            return val
        return " [CITE] "

    text = RE_BRACKET_NUMERIC.sub(_replace_bracket_num, text)

    def _replace_paren(match: re.Match) -> str:
        content = " ".join(match.group(1).split())
        if RE_HAS_YEAR.search(content):
            if any(cue in content.lower() for cue in ("et al", "et. al", "et.al", "etal", "&", ";", ", 19", ", 20", "e.g.", "see", "cf.", "i.e.")) or re.search(r"^[A-Z][a-zA-Z]+", content):
                return " [CITE] "
        return match.group(0)

    text = RE_PAREN_BLOCK.sub(_replace_paren, text)
    text = RE_UNCLOSED_PAREN_CITE.sub(" [CITE] ", text)
    text = RE_NESTED_PAREN_CITE.sub(" [CITE] ", text)
    text = RE_ORPHAN_ET_AL.sub(" [CITE] ", text)
    text = RE_GENERIC_ORPHAN_ET_AL.sub(" [CITE] ", text)
    text = RE_APOSTROPHE_ORPHAN.sub(" [CITE] ", text)
    text = RE_CONSECUTIVE_CITE_SEMI.sub(" [CITE] ", text)
    text = RE_CONSECUTIVE_CITE.sub(" [CITE] ", text)
    return text

def mask_math(text: str) -> str:
    #mask block inline latex math unicode operators and raw commands with canonical math token
    text = RE_MATH_BLOCK.sub(" [MATH] ", text)
    text = RE_MATH_INLINE.sub(" [MATH] ", text)
    text = RE_LATEX_CMD.sub(" [MATH] ", text)
    text = RE_MATH_OPTIM.sub(" [MATH] ", text)
    text = RE_MATH_EQUATIONS.sub(" [MATH] ", text)
    text = RE_MATH_SYMBOLS.sub(" [MATH] ", text)
    text = RE_GREEK_SYMBOLS.sub(" [MATH] ", text)
    text = RE_CONSECUTIVE_MATH.sub(" [MATH] ", text)
    return text

def mask_urls(text: str) -> str:
    #unglue tokens reconnect protocols and mask urls domains and orphan protocols
    text = RE_UNGLUE_URL.sub(r"\1 \2", text)
    text = RE_SPACED_PROTOCOL.sub("https://", text)
    text = RE_PROTOCOL_LINEBREAK.sub(r"\1", text)
    text = RE_URL.sub(" [URL] ", text)
    text = RE_BARE_DOMAIN.sub(" [URL] ", text)
    text = RE_ORPHAN_PROTOCOL.sub(" [URL] ", text)
    text = RE_CONSECUTIVE_URL.sub(" [URL] ", text)
    text = RE_FOOTNOTE_BEFORE_URL.sub("", text)
    return text

def normalize_bullets(text: str) -> str:
    #standardize varied bullet point symbols to unified dash
    return RE_BULLETS.sub("- ", text)

def normalize_whitespace(text: str) -> str:
    #collapse intra paragraph line breaks while preserving paragraph boundaries and bullet lists
    if not text:
        return ""
    raw_blocks = re.split(r"\n\s*\n+", text.strip())
    cleaned_blocks = []
    for block in raw_blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if not lines:
            continue
        merged_lines = []
        for line in lines:
            if line.startswith("- "):
                merged_lines.append("\n" + line)
            elif merged_lines and merged_lines[-1].startswith("\n- "):
                merged_lines.append(" " + line)
            else:
                if merged_lines and not merged_lines[-1].startswith("\n- "):
                    merged_lines.append(" " + line)
                else:
                    merged_lines.append(line)
        block_text = "".join(merged_lines)
        block_text = RE_MULTI_SPACES.sub(" ", block_text).strip()
        if block_text:
            cleaned_blocks.append(block_text)
    return "\n\n".join(cleaned_blocks)

def preprocess_text(text: str, title: str = "", is_intro: bool = False) -> str:
    #execute complete text cleaning normalization and masking pipeline
    if not text or not isinstance(text, str):
        return ""
    text = sanitize_section_boundaries(text, is_intro=is_intro)
    text = normalize_unicode(text)
    text = dehyphenate(text)
    if title:
        title_norm = normalize_unicode(title).strip()
        if len(title_norm) > 10:
            title_pat = re.compile(rf"(?im)^\s*{re.escape(title_norm)}\s*$\n?")
            text = title_pat.sub("", text)
    text = remove_affiliations_and_emails(text)
    text = remove_boilerplate(text)
    text = remove_algorithm_pseudocode(text)
    text = remove_captions(text)
    text = mask_urls(text)
    text = mask_math(text)
    text = clean_footnotes(text)
    text = mask_citations(text)
    text = normalize_bullets(text)
    text = normalize_whitespace(text)
    return text

def preprocess_record(record: Dict[str, Any]) -> Dict[str, Any]:
    #clean individual paper record sections and update word metrics
    cleaned_record = dict(record)
    title = record.get("title", "")

    cleaned_abstract = preprocess_text(record.get("abstract", ""), title=title, is_intro=False)
    cleaned_intro = preprocess_text(record.get("introduction", ""), title=title, is_intro=True)
    cleaned_concl = preprocess_text(record.get("conclusion", ""), title=title, is_intro=False)

    cleaned_record["abstract"] = cleaned_abstract
    cleaned_record["introduction"] = cleaned_intro
    cleaned_record["conclusion"] = cleaned_concl

    abs_words = len(cleaned_abstract.split())
    intro_words = len(cleaned_intro.split())
    concl_words = len(cleaned_concl.split())

    cleaned_record["section_lengths"] = {
        "abstract_words": abs_words,
        "intro_words": intro_words,
        "conclusion_words": concl_words,
        "total_words": abs_words + intro_words + concl_words,
    }

    return cleaned_record

def count_total_lines(file_path: str) -> int:
    #count total lines in input file
    count = 0
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count

def load_seeds_reference(reference_path: str = DEFAULT_SEEDS_REFERENCE_PATH) -> Dict[str, Dict[str, Any]]:
    #load metadata lookup dictionary from seed reference dataset
    seeds_map: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(reference_path):
        return seeds_map
    with open(reference_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            rec = json.loads(line_str)
            pid = rec.get("paper_id")
            if pid:
                seeds_map[pid] = {
                    "conference": rec.get("conference") or rec.get("venue"),
                    "publication_year": rec.get("publication_year") or rec.get("year"),
                    "authors": rec.get("authors"),
                    "url": rec.get("url"),
                    "doi": rec.get("doi"),
                    "stratum": rec.get("stratum"),
                    "venue": rec.get("venue") or rec.get("conference"),
                    "year": rec.get("year") or rec.get("publication_year"),
                }
    return seeds_map

def run_preprocessing_pipeline(
    input_path: Optional[str] = None,
    output_path: Optional[str] = None,
    max_records: Optional[int] = None,
    seeds_ref_path: Optional[str] = None,
) -> Dict[str, Any]:
    #orchestrate text preprocessing with real time progress tracking
    resolved_input = input_path or DEFAULT_INPUT_PATH
    if not resolved_input:
        resolved_input = DEFAULT_INPUT_PATH

    if not output_path:
        #safeguard output destination based on input file name
        if "synthetic" in os.path.basename(resolved_input).lower():
            resolved_output = DEFAULT_SYNTHETIC_OUTPUT_PATH
        else:
            resolved_output = DEFAULT_OUTPUT_PATH
    else:
        resolved_output = output_path

    if not os.path.exists(resolved_input):
        raise FileNotFoundError(f"Input file not found: {resolved_input}")

    os.makedirs(os.path.dirname(resolved_output), exist_ok=True)

    print("=" * 70, flush=True)
    print("STARTING SPECIALIZED TEXT PREPROCESSING PIPELINE (STAGE 2 / 3.5)", flush=True)
    print(f"Input File: {resolved_input}", flush=True)
    print(f"Output File: {resolved_output}", flush=True)

    seeds_lookup_path = seeds_ref_path or DEFAULT_SEEDS_REFERENCE_PATH
    seeds_meta = load_seeds_reference(seeds_lookup_path)
    if seeds_meta:
        print(f"Loaded Seeds Reference Metadata: {len(seeds_meta)} entries", flush=True)

    total_target = count_total_lines(resolved_input)
    if max_records and max_records < total_target:
        total_target = max_records

    print(f"Total Papers to Process: {total_target}", flush=True)
    print("Sanitizing: Boundary cuts, bibliography, appendices, and downstream sections", flush=True)
    print("Masking: [CITE] citations, [MATH] equations/operators, [URL] links", flush=True)
    print("Expurging: Figure/Table captions, pseudocode, author emails, affiliation footnotes", flush=True)
    print("Normalization: Unicode NFKC ligatures, minus signs, dehyphenation, bullets", flush=True)
    print("=" * 70, flush=True)

    processed_count = 0
    start_time = time.time()

    with open(resolved_input, "r", encoding="utf-8") as in_f, open(resolved_output, "w", encoding="utf-8") as out_f:
        for line in in_f:
            if not line.strip():
                continue

            doc = json.loads(line)
            cleaned = preprocess_record(doc)

            #recover metadata from seed reference for synthetic papers if missing
            pid = cleaned.get("paper_id", "")
            base_id = pid.replace("synthetic::", "") if pid.startswith("synthetic::") else pid
            if base_id in seeds_meta:
                seed = seeds_meta[base_id]
                if cleaned.get("conference") is None:
                    cleaned["conference"] = seed.get("conference")
                if cleaned.get("publication_year") is None:
                    cleaned["publication_year"] = seed.get("publication_year")
                if cleaned.get("authors") is None:
                    cleaned["authors"] = seed.get("authors")
                if cleaned.get("url") is None:
                    cleaned["url"] = seed.get("url")
                if cleaned.get("doi") is None:
                    cleaned["doi"] = seed.get("doi")
                if cleaned.get("stratum") is None and seed.get("stratum") is not None:
                    cleaned["stratum"] = seed.get("stratum")
                if cleaned.get("venue") is None and seed.get("venue") is not None:
                    cleaned["venue"] = seed.get("venue")
                if cleaned.get("year") is None and seed.get("year") is not None:
                    cleaned["year"] = seed.get("year")

            out_f.write(json.dumps(cleaned, ensure_ascii=False) + "\n")

            processed_count += 1
            progress_pct = (processed_count / total_target) * 100.0

            conf = cleaned.get("conference") or cleaned.get("venue") or "UNKNOWN"
            year = cleaned.get("publication_year") or cleaned.get("year") or 0
            raw_title = cleaned.get("title", "")
            short_title = raw_title[:45] + ("..." if len(raw_title) > 45 else "")

            #real time progress reporting in terminal matching stage 1
            print(
                f"[{processed_count:5d}/{total_target:5d}] "
                f"({progress_pct:6.2f}%) | "
                f"{conf} {year} | "
                f"{short_title}",
                flush=True,
            )

            if max_records and processed_count >= max_records:
                break

    elapsed_time = time.time() - start_time
    avg_speed = processed_count / max(0.001, elapsed_time)

    print("\n" + "=" * 70, flush=True)
    print("PREPROCESSING PIPELINE COMPLETED SUCCESSFULLY", flush=True)
    print(f"Total Papers Processed: {processed_count}", flush=True)
    print(f"Time Elapsed: {elapsed_time:.1f} seconds ({avg_speed:.1f} papers/sec)", flush=True)
    print(f"Processed Corpus File: {resolved_output}", flush=True)
    print("=" * 70, flush=True)

    return {
        "processed_count": processed_count,
        "elapsed_time_sec": elapsed_time,
        "output_path": resolved_output,
    }

def parse_args(cli_args: Optional[List[str]] = None) -> argparse.Namespace:
    #parse command line arguments for preprocessing pipeline
    parser = argparse.ArgumentParser(description="Specialized text preprocessing pipeline with parity masking")
    parser.add_argument(
        "positional_input",
        nargs="?",
        default=None,
        help="Optional positional path to input jsonl file",
    )
    parser.add_argument(
        "-i", "--input", "--input-path",
        dest="input_path",
        default=None,
        help="Path to input JSONL file (default: data/raw/collected_corpus.jsonl or data/raw/synthetic_ai.jsonl)",
    )
    parser.add_argument(
        "-o", "--output", "--output-path",
        dest="output_path",
        default=None,
        help="Path to output JSONL file (default: data/processed/preprocessed_corpus.jsonl or data/processed/synthetic_corpus.jsonl)",
    )
    parser.add_argument(
        "--seeds-ref",
        dest="seeds_ref_path",
        default=DEFAULT_SEEDS_REFERENCE_PATH,
        help="Path to seed reference JSONL file for metadata recovery (default: data/processed/preprocessed_corpus.jsonl)",
    )
    parser.add_argument(
        "--max-records",
        dest="max_records",
        type=int,
        default=None,
        help="Maximum records to process (default: all)",
    )
    parsed = parser.parse_args(cli_args)
    if parsed.positional_input and not parsed.input_path:
        parsed.input_path = parsed.positional_input
    return parsed

def main(cli_args: Optional[List[str]] = None) -> None:
    #cli entry point for executing preprocessing pipeline
    args = parse_args(cli_args)
    run_preprocessing_pipeline(
        input_path=args.input_path,
        output_path=args.output_path,
        max_records=args.max_records,
        seeds_ref_path=args.seeds_ref_path,
    )

if __name__ == "__main__":
    main()
