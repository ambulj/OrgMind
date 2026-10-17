"""Entity Resolution Module.

Technical Terms:
- Entity Resolution: Matching different text mentions, usernames, or abbreviations
  (e.g., '@alice', 'Alice Chen', 'achen') to a single canonical Person ID (P_ALICE).
- Canonical Entity: The authoritative, primary identity record in the database.
"""

import csv
import difflib
import os
from pathlib import Path
from typing import Any


class EntityResolver:
    """Maintains an in-memory lookup table of aliases, handles, and emails mapping to canonical Person IDs."""

    def __init__(self, people_csv_path: str = "data/people.csv"):
        self.people_csv_path = people_csv_path
        self.alias_to_id: dict[str, str] = {}
        self.id_to_person: dict[str, dict[str, str]] = {}
        self.flagged_unknowns: list[dict[str, Any]] = []
        self.load_people()

    def load_people(self) -> None:
        """Parses the master people.csv and builds bidirectional lookup dictionaries."""
        if not os.path.exists(self.people_csv_path):
            repo_root = Path(__file__).resolve().parent.parent.parent.parent
            alt_path = repo_root / self.people_csv_path
            if alt_path.exists():
                self.people_csv_path = str(alt_path)
            else:
                print(f"[Resolver] Warning: {self.people_csv_path} not found.")
                return

        with open(self.people_csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                pid = row["id"].strip()
                name = row["name"].strip()
                email = row["email"].strip()
                aliases = [a.strip() for a in row.get("aliases", "").split(",") if a.strip()]

                self.id_to_person[pid] = {
                    "id": pid,
                    "name": name,
                    "email": email,
                    "role": row.get("role", "").strip(),
                }

                # Register exact variations
                self.alias_to_id[pid.lower()] = pid
                self.alias_to_id[name.lower()] = pid
                self.alias_to_id[email.lower()] = pid

                for alias in aliases:
                    clean_alias = alias.lower()
                    self.alias_to_id[clean_alias] = pid
                    if clean_alias.startswith("@"):
                        self.alias_to_id[clean_alias.lstrip("@")] = pid

    def resolve_with_status(self, raw_mention: str, fuzzy_threshold: float = 0.8) -> dict[str, Any]:
        """Resolves a raw text mention or handle to a canonical Person ID with status metadata.

        Returns dict with keys:
            - resolved_id: Canonical Person ID or None
            - status: 'exact', 'fuzzy', or 'unknown'
            - original: raw_mention
            - match_key: alias or closest string matched
            - confidence: float score (1.0 for exact, 0.0-1.0 for fuzzy/unknown)
            - flag_for_review: True if status == 'unknown'
        """
        if not raw_mention or not str(raw_mention).strip():
            return {
                "resolved_id": None,
                "status": "unknown",
                "original": raw_mention,
                "match_key": None,
                "confidence": 0.0,
                "flag_for_review": False,
            }

        clean = str(raw_mention).strip().lower()
        clean_no_at = clean.lstrip("@")

        # 1. Exact match
        if clean in self.alias_to_id:
            return {
                "resolved_id": self.alias_to_id[clean],
                "status": "exact",
                "original": raw_mention,
                "match_key": clean,
                "confidence": 1.0,
                "flag_for_review": False,
            }

        if clean_no_at in self.alias_to_id:
            return {
                "resolved_id": self.alias_to_id[clean_no_at],
                "status": "exact",
                "original": raw_mention,
                "match_key": clean_no_at,
                "confidence": 1.0,
                "flag_for_review": False,
            }

        # 2. Fuzzy match fallback
        candidates = list(self.alias_to_id.keys())
        close_matches = difflib.get_close_matches(
            clean_no_at, candidates, n=1, cutoff=fuzzy_threshold
        )
        if close_matches:
            best_match = close_matches[0]
            ratio = difflib.SequenceMatcher(None, clean_no_at, best_match).ratio()
            return {
                "resolved_id": self.alias_to_id[best_match],
                "status": "fuzzy",
                "original": raw_mention,
                "match_key": best_match,
                "confidence": round(ratio, 2),
                "flag_for_review": False,
            }

        # 3. Unknown handle - Flag for human review instead of creating phantom node
        flag_entry = {
            "mention": raw_mention,
            "status": "unknown",
            "reason": "No exact or fuzzy alias match in company directory",
        }
        self.flagged_unknowns.append(flag_entry)

        return {
            "resolved_id": None,
            "status": "unknown",
            "original": raw_mention,
            "match_key": None,
            "confidence": 0.0,
            "flag_for_review": True,
        }

    def resolve_person(
        self, raw_mention: str, allow_fuzzy: bool = True, fuzzy_threshold: float = 0.8
    ) -> str | None:
        """Resolves a raw text mention or handle to a canonical Person ID.

        Args:
            raw_mention: E.g., '@alice', 'bob.m@northwind.io', 'David Kim', 'pri'
            allow_fuzzy: If True, uses difflib fallback for slight typos.
            fuzzy_threshold: Minimum similarity cutoff (default 0.8).

        Returns:
            Canonical Person ID (e.g. 'P_ALICE') or None if unknown.
        """
        res = self.resolve_with_status(raw_mention, fuzzy_threshold=fuzzy_threshold)
        if res["status"] in ("exact", "fuzzy") if allow_fuzzy else (res["status"] == "exact"):
            return res["resolved_id"]
        return None

    def get_flagged_unknowns(self) -> list[dict[str, Any]]:
        """Returns the list of author handles/mentions flagged for review."""
        return list(self.flagged_unknowns)

    def suggest_merge_candidates(self, raw_mention: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Identifies candidate canonical identities for an ambiguous or unrecognized mention.
        Rule: NEVER merge silently. Presents candidates for human-in-the-loop review.
        """
        clean = str(raw_mention).strip().lower().lstrip("@")
        candidates = list(self.alias_to_id.keys())
        matches = difflib.get_close_matches(clean, candidates, n=top_k, cutoff=0.5)

        results = []
        seen_pids = set()
        for m in matches:
            pid = self.alias_to_id[m]
            if pid in seen_pids:
                continue
            seen_pids.add(pid)
            ratio = round(difflib.SequenceMatcher(None, clean, m).ratio(), 2)
            person = self.id_to_person.get(pid, {})
            results.append({
                "raw_mention": raw_mention,
                "matched_alias": m,
                "suggested_id": pid,
                "suggested_name": person.get("name", "Unknown"),
                "similarity_score": ratio,
                "review_action": "requires_human_approval",
            })
        return results

    def get_person_details(self, person_id: str) -> dict[str, str] | None:
        """Retrieves canonical metadata for a person."""
        return self.id_to_person.get(person_id)


# Global singleton instance for easy import across modules
resolver = EntityResolver()
