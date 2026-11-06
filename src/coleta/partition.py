import os
import json
import random
from collections import defaultdict
from typing import Dict, List, Tuple, Any

#stratified allocation constants
TARGET_PRE_2020_SEEDS = 1500
TARGET_PRE_2020_HUMAN_TRAIN = 1500
CORPUS_PATH = os.path.join("data", "raw", "collected_corpus.jsonl")
BACKUP_PATH = os.path.join("data", "raw", "collected_corpus_unpartitioned.jsonl")

def compute_stratum_allocations(pre_strata: Dict[Tuple[str, int], List[Dict[str, Any]]]) -> Dict[Tuple[str, int], int]:
    #compute balanced allocations where seeds equal human train
    allocations: Dict[Tuple[str, int], int] = {}
    for (conf, y), paper_list in pre_strata.items():
        n = len(paper_list)
        allocations[(conf, y)] = min(75, int(n * 0.425))

    current_total = sum(allocations.values())
    deficit = TARGET_PRE_2020_SEEDS - current_total

    #prioritize strata with largest remaining capacity
    candidates = list(pre_strata.keys())
    while deficit > 0:
        candidates.sort(key=lambda k: len(pre_strata[k]) - 2 * allocations[k], reverse=True)
        allocations[candidates[0]] += 1
        deficit -= 1

    return allocations

def partition_corpus(input_path: str = CORPUS_PATH, backup_path: str = BACKUP_PATH, random_seed: int = 42) -> Dict[str, Any]:
    #partition dataset into experimental subsets
    print(f"Reading corpus from {input_path}...")
    records: List[Dict[str, Any]] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    #create safety backup of unpartitioned corpus
    if not os.path.exists(backup_path):
        print(f"Creating safety backup at {backup_path}...")
        with open(backup_path, "w", encoding="utf-8") as f:
            for r in records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    pre_strata: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)
    post_strata: Dict[Tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)

    for r in records:
        conf = r["conference"]
        year = r["publication_year"]
        if year <= 2019:
            pre_strata[(conf, year)].append(r)
        else:
            post_strata[(conf, year)].append(r)

    #calculate exact balanced stratum allocations
    allocations = compute_stratum_allocations(pre_strata)

    partitioned_records: List[Dict[str, Any]] = []
    seed_count = 0
    human_train_count = 0
    temporal_blind_count = 0

    #process pre-2020 strata
    for (conf, y), paper_list in sorted(pre_strata.items()):
        rng = random.Random(random_seed + y + hash(conf) % 1000)
        rng.shuffle(paper_list)

        k = allocations[(conf, y)]
        for i, paper in enumerate(paper_list):
            if i < k:
                paper["provenance_type"] = "seed_discarded"
                paper["label"] = None
                seed_count += 1
            elif i < 2 * k:
                paper["provenance_type"] = "human_ground_truth"
                paper["label"] = 0
                human_train_count += 1
            else:
                paper["provenance_type"] = "human_temporal_blind"
                paper["label"] = 0
                temporal_blind_count += 1
            partitioned_records.append(paper)

    #process post-2020 strata
    post_count = 0
    for (conf, y), paper_list in sorted(post_strata.items()):
        for paper in paper_list:
            paper["provenance_type"] = "longitudinal_unlabeled"
            paper["label"] = None
            post_count += 1
            partitioned_records.append(paper)

    #write back partitioned records to corpus path
    print(f"Writing {len(partitioned_records)} partitioned records to {input_path}...")
    with open(input_path, "w", encoding="utf-8") as f:
        for r in partitioned_records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    summary = {
        "total_records": len(partitioned_records),
        "seed_discarded": seed_count,
        "human_ground_truth": human_train_count,
        "human_temporal_blind": temporal_blind_count,
        "longitudinal_unlabeled": post_count,
        "allocations": {f"{c}_{y}": allocations[(c, y)] for (c, y) in sorted(allocations.keys())},
    }

    print("\n" + "=" * 60)
    print("PARTITIONING SUMMARY COMPLETED")
    print(f"Total Records: {summary['total_records']}")
    print(f"Seeds Discarded (AI Seeds): {summary['seed_discarded']}")
    print(f"Human Ground Truth (Modeling): {summary['human_ground_truth']}")
    print(f"Human Temporal Blind (<=2019 Control): {summary['human_temporal_blind']}")
    print(f"Longitudinal Unlabeled (>=2020 Evaluation): {summary['longitudinal_unlabeled']}")
    print("=" * 60 + "\n")

    return summary

if __name__ == "__main__":
    partition_corpus()

