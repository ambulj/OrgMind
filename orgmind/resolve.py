"""Entity Resolution Module.

Technical Terms:
- Entity Resolution: Matching different text mentions, usernames, or abbreviations
  (e.g., '@alice', 'Alice Chen', 'achen') to a single canonical Person ID (P_ALICE).
- Canonical Entity: The authoritative, primary identity record in the database.
"""

from typing import Dict, Optional, List, Any
import csv
import os
import difflib


class EntityResolver:
    """Maintains an in-memory lookup table of aliases, handles, and emails mapping to canonical Person IDs."""

    def __init__(self, people_csv_path: str = "data/people.csv"):
        self.people_csv_path = people_csv_path
        self.alias_to_id: Dict[str, str] = {}
        self.id_to_person: Dict[str, Dict[str, str]] = {}
        self.flagged_unknowns: List[Dict[str, Any]] = []
        self.load_people()

    def load_people(self) -> None:
        """Parses the master people.csv and builds bidirectional lookup dictionaries."""
        if not os.path.exists(self.people_csv_path):
            print(f"[Resolver] Warning: {self.people_csv_path} not found.")
            return

        with open(self.people_csv_path, mode="r", encoding="utf-8") as f:
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

    def resolve_with_status(self, raw_mention: str, fuzzy_threshold: float = 0.8) -> Dict[str, Any]:
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
        close_matches = difflib.get_close_matches(clean_no_at, candidates, n=1, cutoff=fuzzy_threshold)
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

    def resolve_person(self, raw_mention: str, allow_fuzzy: bool = True, fuzzy_threshold: float = 0.8) -> Optional[str]:
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

    def get_flagged_unknowns(self) -> List[Dict[str, Any]]:
        """Returns the list of author handles/mentions flagged for review."""
        return list(self.flagged_unknowns)

    def get_person_details(self, person_id: str) -> Optional[Dict[str, str]]:
        """Retrieves canonical metadata for a person."""
        return self.id_to_person.get(person_id)


# Global singleton instance for easy import across modules
resolver = EntityResolver()
