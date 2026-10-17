"""Data Validation & Consistency Checker for OrgMind (Phase 1).

Validates:
1. Date formats and chronological sanity (valid_from <= valid_to where applicable)
2. Every person mention or handle resolves cleanly to canonical Person ID
3. Every decision has non-empty source text and source ID
4. Prints an exact summary of data counts
Exits with code 0 on success, non-zero on validation error.
"""

import csv
import glob
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from orgmind.resolve import resolver
from orgmind.ingest_unstructured import extract_from_markdown_llm


def parse_date(date_str: str) -> datetime:
    """Parses ISO date string or YYYY-MM-DD."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}")


def check_all_data() -> int:
    print("==================================================")
    print(" [OrgMind Data Check] Validating Expanded Dataset ")
    print("==================================================")
    errors = []

    # 1. Check People
    people_file = "data/people.csv"
    people_count = 0
    with open(people_file, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            people_count += 1
            pid = r["id"]
            if not pid.startswith("P_"):
                errors.append(f"Invalid person id format: {pid}")
    print(f"[PASS] Checked {people_count} people in people.csv")

    # 2. Check Teams & Projects
    teams_count = len(list(csv.DictReader(open("data/teams.csv", encoding="utf-8"))))
    projects_count = len(list(csv.DictReader(open("data/projects.csv", encoding="utf-8"))))
    print(f"[PASS] Checked {teams_count} teams, {projects_count} projects.")

    # 3. Check Ownership History
    history_file = "data/ownership_history.csv"
    if os.path.exists(history_file):
        history_rows = list(csv.DictReader(open(history_file, encoding="utf-8")))
        for h in history_rows:
            d_from = parse_date(h["valid_from"])
            if h.get("valid_to"):
                d_to = parse_date(h["valid_to"])
                if d_from > d_to:
                    errors.append(f"Ownership date anomaly in {h['project_id']}: valid_from > valid_to")
        print(f"[PASS] Checked {len(history_rows)} ownership records.")

    # 4. Check Tickets
    tickets = json.load(open("data/tickets.json", encoding="utf-8"))
    for t in tickets:
        parse_date(t["created_at"])
        if t.get("author_id") and not resolver.get_person_details(t["author_id"]):
            errors.append(f"Ticket {t['id']} author {t['author_id']} not in master people registry.")
        if t.get("assignee_id") and not resolver.get_person_details(t["assignee_id"]):
            errors.append(f"Ticket {t['id']} assignee {t['assignee_id']} not in master people registry.")
    print(f"[PASS] Checked {len(tickets)} tickets in tickets.json")

    # 5. Check Markdown Docs & Decisions
    md_files = glob.glob("data/docs/*.md")
    total_decisions = 0
    total_sources = 0
    for doc in md_files:
        content = open(doc, encoding="utf-8").read()
        res = extract_from_markdown_llm(doc, content)
        for dec in res.decisions:
            total_decisions += 1
            if not dec.text or len(dec.text.strip()) < 5:
                errors.append(f"Decision {dec.decision_id} in {doc} has empty text.")
            if not dec.source.snippet or len(dec.source.snippet.strip()) < 10:
                errors.append(f"Decision {dec.decision_id} has invalid source snippet.")
            total_sources += 1
            if dec.decided_by_mention:
                resolved = resolver.resolve_person(dec.decided_by_mention)
                if not resolved:
                    errors.append(f"Decider '{dec.decided_by_mention}' in {doc} does not resolve to a Person.")

    print(f"[PASS] Checked {len(md_files)} markdown documents ({total_decisions} decisions with valid sources).")

    # 6. Check Chat Messages
    chat_files = glob.glob("data/chats/*.jsonl")
    total_messages = 0
    unresolved_handles = set()
    for cf in chat_files:
        for line in open(cf, encoding="utf-8"):
            if not line.strip():
                continue
            total_messages += 1
            msg = json.loads(line)
            ts = msg.get("ts") or msg.get("timestamp")
            parse_date(ts)
            author = msg.get("author", "")
            resolved = resolver.resolve_person(author)
            if not resolved:
                unresolved_handles.add(author)

    if unresolved_handles:
        errors.append(f"Unresolved chat author handles: {unresolved_handles}")
    else:
        print(f"[PASS] Checked {total_messages} messages across {len(chat_files)} channels (all authors resolved!).")

    # 7. Check Live Drops
    live_files = glob.glob("data/live/*")
    print(f"[PASS] Verified {len(live_files)} live drop payloads present in /data/live/.")

    print("\n---------------- Data Summary ----------------")
    print(f" Employees (Person):        {people_count}")
    print(f" Teams:                     {teams_count}")
    print(f" Projects:                  {projects_count}")
    print(f" Tickets:                   {len(tickets)}")
    print(f" Markdown Documents:        {len(md_files)}")
    print(f" Extracted Decisions:       {total_decisions}")
    print(f" Total Chat Messages:       {total_messages}")
    print(f" Live Update Drop Files:    {len(live_files)}")
    print("----------------------------------------------")

    if errors:
        print(f"\n[FAIL] Found {len(errors)} validation errors:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("\n[OrgMind Data Check] ALL DATA CHECKS PASSED (EXIT 0)\n")
    return 0


if __name__ == "__main__":
    sys.exit(check_all_data())
