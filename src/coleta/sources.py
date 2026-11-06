import hashlib
import re
import urllib.parse
import xml.etree.ElementTree as ElementTree
from typing import List, Dict, Any, Optional
import requests
from bs4 import BeautifulSoup

HTTP_TIMEOUT_SECONDS = 15
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Research Data Collector)"
}

ACL_VOLUME_MAPPING = {
    2015: "P15-1",
    2016: "P16-1",
    2017: "P17-1",
    2018: "P18-1",
    2019: "P19-1",
    2020: "2020.acl-main",
    2021: "2021.acl-long",
    2022: "2022.acl-long",
    2023: "2023.acl-long",
    2024: "2024.acl-long",
    2025: "2025.acl-long",
}

ICML_VOLUME_MAPPING = {
    2015: "v37",
    2016: "v48",
    2017: "v70",
    2018: "v80",
    2019: "v97",
    2020: "v119",
    2021: "v139",
    2022: "v162",
    2023: "v202",
    2024: "v235",
    2025: "v250",
}


def build_fallback_paper_id(conference: str, year: int, title: str) -> str:
    #generate deterministic sha256 identifier
    raw_key = f"{conference.lower()}_{year}_{title.strip().lower()}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]


def fetch_acl_candidates(year: int) -> List[Dict[str, Any]]:
    #fetch acl anthology papers for target year
    candidates: List[Dict[str, Any]] = []
    volume_slug = ACL_VOLUME_MAPPING.get(year, f"{year}.acl-long")
    url = f"https://aclanthology.org/volumes/{volume_slug}/"

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 200:
            #fallback to event page if volume returns non-200
            alt_url = f"https://aclanthology.org/events/acl-{year}/"
            response = requests.get(alt_url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
            if response.status_code != 200:
                return candidates
    except Exception:
        #network exception during candidate discovery
        return candidates

    soup = BeautifulSoup(response.text, "html.parser")
    pdf_anchors = soup.find_all("a", href=lambda href: bool(href and href.endswith(".pdf")))

    seen_urls = set()
    for anchor in pdf_anchors:
        pdf_url = anchor.get("href", "")
        #skip volume index or handbook documents
        if not pdf_url or "handbook" in pdf_url.lower() or pdf_url.endswith(".0.pdf") or re.search(r"-\d000\.pdf$", pdf_url):
            continue
        if pdf_url in seen_urls:
            continue
        seen_urls.add(pdf_url)

        entry_container = anchor.find_parent("div", class_="d-sm-flex") or anchor.find_parent("p") or anchor.parent
        title_tag = entry_container.find("strong") if entry_container else None
        title = title_tag.get_text(strip=True) if title_tag else ""

        if not title:
            continue

        authors = []
        if entry_container:
            for author_tag in entry_container.find_all("a", href=lambda href: bool(href and "/people/" in href)):
                author_name = author_tag.get_text(strip=True)
                if author_name and author_name not in authors:
                    authors.append(author_name)

        #extract doi from link
        doi = None
        doi_tag = entry_container.find("a", href=lambda href: bool(href and "doi.org" in href)) if entry_container else None
        if doi_tag:
            doi_match = re.search(r"10\.\d{4,9}/\S+", doi_tag.get("href", ""))
            if doi_match:
                doi = doi_match.group(0)

        paper_id = doi if doi else build_fallback_paper_id("ACL", year, title)

        candidates.append({
            "paper_id": paper_id,
            "doi": doi,
            "title": title,
            "authors": authors,
            "publication_year": year,
            "conference": "ACL",
            "url": pdf_url,
        })

    return candidates


def fetch_icml_candidates(year: int) -> List[Dict[str, Any]]:
    #fetch icml papers from pmlr for target year
    candidates: List[Dict[str, Any]] = []
    volume_slug = ICML_VOLUME_MAPPING.get(year)
    if not volume_slug:
        return candidates

    url = f"https://proceedings.mlr.press/{volume_slug}/"
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 200:
            return candidates
    except Exception:
        #network exception during candidate discovery
        return candidates

    soup = BeautifulSoup(response.text, "html.parser")
    paper_divs = soup.find_all("div", class_="paper")

    for div in paper_divs:
        title_p = div.find("p", class_="title")
        title = title_p.get_text(strip=True) if title_p else ""
        if not title:
            continue

        authors_span = div.find("span", class_="authors")
        authors_raw = authors_span.get_text(strip=True) if authors_span else ""
        authors = [a.strip() for a in authors_raw.split(",") if a.strip()]

        pdf_anchor = div.find("a", href=lambda href: bool(href and href.endswith(".pdf")))
        pdf_url = pdf_anchor.get("href", "") if pdf_anchor else ""
        if not pdf_url:
            continue

        paper_id = build_fallback_paper_id("ICML", year, title)

        candidates.append({
            "paper_id": paper_id,
            "doi": None,
            "title": title,
            "authors": authors,
            "publication_year": year,
            "conference": "ICML",
            "url": pdf_url,
        })

    return candidates


def fetch_neurips_candidates(year: int) -> List[Dict[str, Any]]:
    #fetch neurips papers from official proceedings for target year
    candidates: List[Dict[str, Any]] = []
    url = f"https://proceedings.neurips.cc/paper_files/paper/{year}"

    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
        if response.status_code != 200:
            #fallback url structure for historic years
            url = f"https://proceedings.neurips.cc/paper/{year}"
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
            if response.status_code != 200:
                return candidates
    except Exception:
        #network exception during candidate discovery
        return candidates

    soup = BeautifulSoup(response.text, "html.parser")
    paper_list = soup.find("ul", class_="paper-list") or soup.find("ul")
    if not paper_list:
        return candidates

    items = paper_list.find_all("li")
    for item in items:
        anchor = item.find("a")
        if not anchor:
            continue
        title = anchor.get_text(strip=True)
        link = anchor.get("href", "")
        if not title or not link:
            continue

        #extract authors from tag
        authors = []
        authors_span = item.find("span", class_="paper-authors")
        if authors_span and authors_span.get_text(strip=True):
            authors = [a.strip() for a in authors_span.get_text(strip=True).split(",") if a.strip()]
        else:
            author_tags = item.find_all("i")
            for at in author_tags:
                authors_text = at.get_text(strip=True)
                authors = [a.strip() for a in authors_text.split(",") if a.strip()]

        #construct direct pdf link
        #transform hash abstract url to file pdf url
        pdf_url = ""
        if "-Abstract-Conference.html" in link:
            pdf_url = link.replace("/hash/", "/file/").replace("-Abstract-Conference.html", "-Paper-Conference.pdf")
        elif "-Abstract.html" in link:
            pdf_url = link.replace("/hash/", "/file/").replace("-Abstract.html", "-Paper.pdf")
        elif "Abstract" in link:
            pdf_url = link.replace("/hash/", "/file/").replace("Abstract", "Paper").replace(".html", ".pdf")
        else:
            #general file url construction
            raw_hash_match = re.search(r"([a-f0-9]{32})", link)
            if raw_hash_match:
                paper_hash = raw_hash_match.group(1)
                suffix = "-Paper-Conference.pdf" if year >= 2022 else "-Paper.pdf"
                pdf_url = f"/paper_files/paper/{year}/file/{paper_hash}{suffix}"

        if not pdf_url:
            continue

        if not pdf_url.startswith("http"):
            pdf_url = f"https://proceedings.neurips.cc{pdf_url}"

        paper_id = build_fallback_paper_id("NeurIPS", year, title)

        candidates.append({
            "paper_id": paper_id,
            "doi": None,
            "title": title,
            "authors": authors,
            "publication_year": year,
            "conference": "NeurIPS",
            "url": pdf_url,
        })

    return candidates


def fetch_iclr_candidates(year: int, max_results: int = 500) -> List[Dict[str, Any]]:
    #fetch iclr papers from open academic archive api with strict submission window
    candidates: List[Dict[str, Any]] = []
    base_url = "http://export.arxiv.org/api/query"
    date_query = f"submittedDate:[{year-1}08010000 TO {year}07312359]"
    topic_query = f'(all:"ICLR {year}" OR all:"ICLR{year}" OR jr:"ICLR {year}" OR jr:"ICLR{year}" OR all:"Learning Representations {year}")'
    query_string = f"{topic_query} AND {date_query}"

    params = {
        "search_query": query_string,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    #query arxiv api with retries to handle rate limits
    root = None
    for attempt in range(4):
        try:
            response = requests.get(base_url, params=params, headers=DEFAULT_HEADERS, timeout=HTTP_TIMEOUT_SECONDS)
            if response.status_code == 200:
                root = ElementTree.fromstring(response.text)
                break
            elif response.status_code in (429, 503):
                #wait before retry
                import time
                time.sleep(4.0 * (attempt + 1))
        except Exception:
            #network exception during candidate discovery
            import time
            time.sleep(3.0 * (attempt + 1))

    if root is None:
        return candidates

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", namespace)

    for entry in entries:
        title_elem = entry.find("atom:title", namespace)
        title = title_elem.text.strip().replace("\n", " ") if title_elem is not None else ""
        if not title:
            continue

        id_elem = entry.find("atom:id", namespace)
        arxiv_url = id_elem.text.strip().replace("http://", "https://") if id_elem is not None else ""

        #validate arxiv submission year to prevent cross conference year leakage
        m = re.search(r"arxiv\.org/abs/(\d{2})(\d{2})\.", arxiv_url)
        if not m:
            continue
        yy = int(m.group(1))
        full_y = 2000 + yy if yy < 50 else 1900 + yy
        if full_y not in (year, year - 1):
            continue

        authors = []
        for author_elem in entry.findall("atom:author", namespace):
            name_elem = author_elem.find("atom:name", namespace)
            if name_elem is not None and name_elem.text:
                authors.append(name_elem.text.strip())

        pdf_url = arxiv_url.replace("/abs/", "/pdf/") if "/abs/" in arxiv_url else ""

        #extract doi if present
        doi_elem = entry.find("{http://arxiv.org/schemas/atom}doi")
        doi = doi_elem.text.strip() if doi_elem is not None else None

        paper_id = doi if doi else build_fallback_paper_id("ICLR", year, title)

        candidates.append({
            "paper_id": paper_id,
            "doi": doi,
            "title": title,
            "authors": authors,
            "publication_year": year,
            "conference": "ICLR",
            "url": pdf_url,
        })

    return candidates


def fetch_candidates_for_stratum(conference: str, year: int) -> List[Dict[str, Any]]:
    #route candidate discovery based on conference identifier
    conf_upper = conference.upper()
    if conf_upper == "ACL":
        return fetch_acl_candidates(year)
    elif conf_upper == "ICML":
        return fetch_icml_candidates(year)
    elif conf_upper == "NEURIPS":
        return fetch_neurips_candidates(year)
    elif conf_upper == "ICLR":
        return fetch_iclr_candidates(year)
    else:
        return []

