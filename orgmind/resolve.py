"""Entity Resolution Module.

Technical Terms:
- Entity Resolution: Matching different text mentions, usernames, or abbreviations
  (e.g., '@alice', 'Alice Chen', 'achen') to a single canonical Person ID (P_ALICE).
- Canonical Entity: The authoritative, primary identity record in the database.
"""

from typing import Dict, Optional
import csv
import os


class EntityResolver:
    """Maintains an in-memory lookup table of aliases, handles, and emails mapping to canonical Person IDs."""

    def __init__(self, people_csv_path: str = "data/people.csv"):
        self.people_csv_path = people_csv_path
        self.alias_to_id: Dict[str, str] = {}
        self.id_to_person: Dict[str, Dict[str, str]] = {}
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

    def resolve_person(self, raw_mention: str) -> Optional[str]:
        """Resolves a raw text mention or handle to a canonical Person ID.

        Args:
            raw_mention: E.g., '@alice', 'bob.m@northwind.io', 'David Kim'

        Returns:
            Canonical Person ID (e.g. 'P_ALICE') or None if unknown.
        """
        if not raw_mention:
            return None

        clean = raw_mention.strip().lower()
        if clean in self.alias_to_id:
            return self.alias_to_id[clean]

        clean_no_at = clean.lstrip("@")
        if clean_no_at in self.alias_to_id:
            return self.alias_to_id[clean_no_at]

        # TODO (Person A): Add RapidFuzz / Levenshtein distance for fuzzy matching typos (e.g., 'Ailce Chen')
        return None

    def get_person_details(self, person_id: str) -> Optional[Dict[str, str]]:
        """Retrieves canonical metadata for a person."""
        return self.id_to_person.get(person_id)


# Global singleton instance for easy import across modules
resolver = EntityResolver()
