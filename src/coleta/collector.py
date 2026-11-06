import argparse
import io
import json
import os
import random
import sys
import time
from typing import List, Dict, Any, Set, Optional
import requests

from src.coleta.extractor import extract_sections_from_pdf
from src.coleta.sources import fetch_candidates_for_stratum

DEFAULT_PRE_2020_QUOTA = 350
DEFAULT_POST_2020_QUOTA = 200
TARGET_TOTAL_PAPERS = 11800
CONFERENCES = ["NeurIPS", "ACL", "ICML", "ICLR"]
YEARS = list(range(2015, 2026))

OUTPUT_RAW_PATH = os.path.join("data", "raw", "collected_corpus.jsonl")
FAILED_LOG_PATH = os.path.join("data", "raw", "failed_downloads.log")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 (Research Collector; mailto:student@university.edu)"
}

ENGLISH_STOPWORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
}


def is_english_text(text: str) -> bool:
    #verify english language using stopword density
    words = [w.lower() for w in text.split() if w.isalpha()]
    if not words:
        return False
    stopword_count = sum(1 for w in words if w in ENGLISH_STOPWORDS)
    ratio = stopword_count / len(words)
    return ratio >= 0.05


def load_collected_paper_ids(output_path: str) -> Set[str]:
    #load existing paper identifiers from output file
    collected_ids: Set[str] = set()
    if not os.path.exists(output_path):
        return collected_ids

    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                paper_id = record.get("paper_id")
                if paper_id:
                    collected_ids.add(paper_id)
            except Exception:
                continue
    return collected_ids


def append_record(output_path: str, record: Dict[str, Any]) -> None:
    #append single json record to output file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_failure(log_path: str, paper_id: str, url: str, reason: str) -> None:
    #record failed download event for auditing
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{paper_id}\t{url}\t{reason}\n")


def download_pdf_with_backoff(url: str, max_retries: int = 5) -> Optional[bytes]:
    #download pdf stream using exponential backoff with jitter
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=HTTP_HEADERS, timeout=25, stream=True)
            if response.status_code == 200:
                #validate pdf mime or magic bytes
                content = response.content
                if b"%PDF" in content[:1024]:
                    return content
                else:
                    return None
            elif response.status_code in (429, 500, 502, 503, 504):
                #server busy or rate limited apply backoff
                retry_after = response.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    wait_time = float(retry_after)
                else:
                    wait_time = min(45.0, (2.0 ** attempt) + random.uniform(0.5, 1.5))
                time.sleep(wait_time)
            elif response.status_code == 404:
                #document not found
                return None
            else:
                return None
        except (requests.exceptions.RequestException, TimeoutError):
            wait_time = min(45.0, (2.0 ** attempt) + random.uniform(0.5, 1.5))
            time.sleep(wait_time)
    return None


def assign_provenance(year: int, position_in_stratum: int) -> tuple[str, Optional[int]]:
    #assign provenance category and supervised label
    if year <= 2019:
        if position_in_stratum < 75:
            return "seed_discarded", None
        elif position_in_stratum < 150:
            return "human_ground_truth", 0
        else:
            return "human_temporal_blind", 0
    else:
        return "longitudinal_unlabeled", None


def run_collection(
    output_path: str = OUTPUT_RAW_PATH,
    pre_2020_quota: int = DEFAULT_PRE_2020_QUOTA,
    post_2020_quota: int = DEFAULT_POST_2020_QUOTA,
    smoke_test: bool = False,
    smoke_sample_count: int = 1,
) -> Dict[str, Any]:
    #orchestrate balanced stratified collection across all strata
    random.seed(42)
    collected_ids = load_collected_paper_ids(output_path)
    total_target = (len(CONFERENCES) * 5 * pre_2020_quota) + (len(CONFERENCES) * 6 * post_2020_quota)
    if smoke_test:
        total_target = len(CONFERENCES) * smoke_sample_count

    print("=" * 70)
    print("STARTING SCIENTIFIC PAPER COLLECTION PIPELINE")
    print(f"Target Conferences: {', '.join(CONFERENCES)}")
    print(f"Target Years: {YEARS[0]} to {YEARS[-1]} ({len(YEARS)} years)")
    print(f"Pre-2020 Target per Stratum: {pre_2020_quota} papers (75 seeds, 75 train, {pre_2020_quota - 150} temporal)")
    print(f"Post-2020 Target per Stratum: {post_2020_quota} papers (longitudinal unlabeled)")
    print(f"Global Target: {total_target} papers")
    print(f"Already Collected in Output: {len(collected_ids)} papers")
    print(f"Output File: {output_path}")
    print("=" * 70)

    total_valid_collected = len(collected_ids)
    strata_stats: Dict[str, int] = {}

    target_conferences = CONFERENCES
    target_years = [2023] if smoke_test else YEARS

    for year in target_years:
        for conf in target_conferences:
            stratum_key = f"{conf}_{year}"
            strata_stats[stratum_key] = 0

            #quota for current stratum based on temporal partition
            base_quota = pre_2020_quota if year <= 2019 else post_2020_quota
            stratum_quota = smoke_sample_count if smoke_test else base_quota

            #discover candidate papers
            print(f"\n>>> Querying candidates for {conf} {year}...", flush=True)
            candidates = fetch_candidates_for_stratum(conf, year)
            print(f"    Found {len(candidates)} candidates.", flush=True)

            if not candidates:
                continue

            #reproducible shuffle for uniform sampling
            random.seed(42 + year + hash(conf) % 1000)
            random.shuffle(candidates)

            collected_in_stratum = 0
            candidate_attempts = 0
            for candidate in candidates:
                if collected_in_stratum >= stratum_quota:
                    break

                candidate_attempts += 1
                paper_id = candidate["paper_id"]
                if paper_id in collected_ids:
                    #already collected
                    collected_in_stratum += 1
                    continue

                pdf_url = candidate.get("url", "")
                if not pdf_url:
                    continue

                #polite request delay
                time.sleep(0.5)

                #download stream
                pdf_bytes = download_pdf_with_backoff(pdf_url)
                if not pdf_bytes:
                    log_failure(FAILED_LOG_PATH, paper_id, pdf_url, "download_failed_or_non_pdf")
                    continue

                #extract target sections
                extracted = extract_sections_from_pdf(pdf_bytes)
                if not extracted["is_valid"]:
                    log_failure(FAILED_LOG_PATH, paper_id, pdf_url, "quality_threshold_not_met")
                    continue

                #verify english language
                sample_text = extracted["abstract"] + " " + extracted["introduction"][:500]
                if not is_english_text(sample_text):
                    log_failure(FAILED_LOG_PATH, paper_id, pdf_url, "non_english_text")
                    continue

                #assign provenance category
                provenance_type, label = assign_provenance(year, collected_in_stratum)

                #assemble complete record
                record: Dict[str, Any] = {
                    "paper_id": paper_id,
                    "doi": candidate.get("doi"),
                    "title": candidate.get("title", ""),
                    "authors": candidate.get("authors", []),
                    "publication_year": year,
                    "conference": conf,
                    "url": pdf_url,
                    "abstract": extracted["abstract"],
                    "introduction": extracted["introduction"],
                    "conclusion": extracted["conclusion"],
                    "section_lengths": extracted["section_lengths"],
                    "provenance_type": provenance_type,
                    "label": label,
                    "generator_metadata": None,
                }

                #persist to storage
                append_record(output_path, record)
                collected_ids.add(paper_id)
                collected_in_stratum += 1
                total_valid_collected += 1
                strata_stats[stratum_key] = collected_in_stratum

                #progress reporting in terminal
                progress_pct = (total_valid_collected / total_target) * 100.0
                short_title = record["title"][:45] + ("..." if len(record["title"]) > 45 else "")
                print(
                    f"[{total_valid_collected:4d}/{total_target:4d}] "
                    f"({progress_pct:6.2f}%) | "
                    f"{conf} {year}: {collected_in_stratum:3d}/{stratum_quota:3d} | "
                    f"{short_title}",
                    flush=True,
                )

            print(f"Finished stratum {conf} {year}: {collected_in_stratum}/{stratum_quota} collected.", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("COLLECTION RUN COMPLETED", flush=True)
    print(f"Total Papers in Database: {total_valid_collected}", flush=True)
    print(f"Database File: {output_path}", flush=True)
    print("=" * 70, flush=True)

    return {
        "total_collected": total_valid_collected,
        "strata_stats": strata_stats,
    }


def main():
    parser = argparse.ArgumentParser(description="Scientific paper collection pipeline")
    parser.add_argument("--output", type=str, default=OUTPUT_RAW_PATH, help="Output JSONL path")
    parser.add_argument("--pre_quota", type=int, default=DEFAULT_PRE_2020_QUOTA, help="Quota per stratum for years <= 2019")
    parser.add_argument("--post_quota", type=int, default=DEFAULT_POST_2020_QUOTA, help="Quota per stratum for years >= 2020")
    parser.add_argument("--smoke_test", action="store_true", help="Run fast verification test")
    parser.add_argument("--smoke_sample_count", type=int, default=1, help="Samples per venue in smoke test")
    args = parser.parse_args()

    run_collection(
        output_path=args.output,
        pre_2020_quota=args.pre_quota,
        post_2020_quota=args.post_quota,
        smoke_test=args.smoke_test,
        smoke_sample_count=args.smoke_sample_count,
    )


if __name__ == "__main__":
    main()
