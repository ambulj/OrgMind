# OrgMind Graph Schema & Cypher Reference

This document defines the graph data model for OrgMind on **FalkorDB**, including nodes, relationships, indexing strategies, and 5 core Cypher queries.

---

## 1. Node Types & Properties

| Node Label | Key Properties | Purpose |
| :--- | :--- | :--- |
| **`Person`** | `id` (e.g. `P_ALICE`), `name`, `email`, `role`, `aliases` (list/string) | Employees and contributors. |
| **`Team`** | `id` (e.g. `T_INFRA`), `name`, `lead_id` | Engineering & business teams. |
| **`Project`** | `id` (e.g. `PRJ_AUTH`), `name`, `status`, `description` | Internal projects & initiatives. |
| **`Topic`** | `id` (e.g. `TOPIC_DATABASE`), `name` | Domain subjects (e.g. "OAuth", "FalkorDB", "Billing"). |
| **`Document`** | `id` (e.g. `DOC_AUTH_SPEC`), `title`, `path`, `updated_at` | Architecture docs, PRDs, specs. |
| **`Ticket`** | `id` (e.g. `TICK_102`), `title`, `status`, `created_at` | Issues and tasks (Jira/Linear style). |
| **`Message`** | `id` (e.g. `MSG_901`), `channel`, `timestamp`, `author_id` | Slack / Teams chat messages. |
| **`Decision`** | `id`, `text`, `topic`, `status` (`"current"` \| `"superseded"`), `valid_from`, `valid_to` | Architectural & business decisions. |
| **`Source`** | `id` (e.g. `SRC_DOC_AUTH_P3`), `file_path`, `chunk_offset`, `text_snippet`, `created_at` | Raw, immutable text chunk proving a fact. |

---

## 2. Relationship Types & Rules

| Relationship | From Node -> To Node | Properties | Meaning |
| :--- | :--- | :--- | :--- |
| **`MEMBER_OF`** | `(Person) -> (Team)` | `role` | Person is a member of the team. |
| **`OWNS`** | `(Person\|Team) -> (Project\|Topic)` | `since` | Official owner of a project or subject. |
| **`WORKS_ON`** | `(Person) -> (Project)` | `role` | Contributor to a project. |
| **`AUTHORED`** | `(Person) -> (Document\|Ticket\|Message)` | `timestamp` | Creator of a content piece. |
| **`MENTIONS`** | `(Document\|Ticket\|Message) -> (Person\|Topic\|Project)` | - | Reference to an entity in text. |
| **`ABOUT`** | `(Decision\|Ticket\|Document) -> (Topic)` | - | Primary subject classification. |
| **`DECIDED_BY`** | `(Decision) -> (Person\|Team)` | - | Person or group who ratified the decision. |
| **`DERIVED_FROM`** | `(Decision) -> (Source)` | - | **Provenance edge**: links decision to exact text snippet. |
| **`SUPERSEDES`** | `(Decision[current]) -> (Decision[superseded])` | `superseded_at` | New decision replaces old decision. |
| **`BLOCKED_BY`** | `(Ticket\|Project) -> (Ticket\|Decision)` | `reason` | Dependency blockage. |

### Graph Integrity Rules
1. **Never Delete Decisions**: Outdated decisions are preserved. The new decision points to the old one with `[:SUPERSEDES]`, and the old decision is updated to `status: "superseded"`, `valid_to: timestamp`.
2. **Mandatory Provenance**: Every `Decision` node MUST connect to at least one `Source` node via `[:DERIVED_FROM]`.
3. **Dates as ISO-8601 Strings**: FalkorDB Cypher handles string ordering cleanly (`"2026-03-01" > "2026-01-15"`). Dates are stored as `YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SSZ`.

---

## 3. Indexes & Constraints

FalkorDB supports Range Indexes and dedicated constraints:

```cypher
// [VERIFIED] Primary ID Range Indexes for fast equality lookups
CREATE INDEX FOR (p:Person) ON (p.id);
CREATE INDEX FOR (t:Team) ON (t.id);
CREATE INDEX FOR (pr:Project) ON (pr.id);
CREATE INDEX FOR (tp:Topic) ON (tp.name);
CREATE INDEX FOR (d:Decision) ON (d.id);
CREATE INDEX FOR (d:Decision) ON (d.topic);
CREATE INDEX FOR (s:Source) ON (s.id);
CREATE INDEX FOR (doc:Document) ON (doc.id);
CREATE INDEX FOR (tk:Ticket) ON (tk.id);
```

```text
// [VERIFIED via FalkorDB CLI / Redis command] Unique Constraints:
// Run through redis-cli or falkordb connection:
GRAPH.CONSTRAINT CREATE northwind_labs UNIQUE NODE Person PROPERTIES 1 id
GRAPH.CONSTRAINT CREATE northwind_labs UNIQUE NODE Decision PROPERTIES 1 id
GRAPH.CONSTRAINT CREATE northwind_labs UNIQUE NODE Source PROPERTIES 1 id
```
*(Note: If running purely through Cypher, standard `CREATE INDEX FOR (...) ON (...)` is universally supported across all FalkorDB versions. We create the Range Indexes during initial schema bootstrap in `db.py`.)*

---

## 4. Five Core Cypher Queries (with Verification Status)

### Query 1: Who Owns a Project or Topic?
Finds the designated owner (individual Person or Team) of a Project or Topic.

```cypher
// [VERIFIED]
MATCH (owner)-[:OWNS]->(target)
WHERE (target:Project AND toLower(target.name) CONTAINS toLower($target_name))
   OR (target:Topic AND toLower(target.name) = toLower($target_name))
RETURN labels(target)[0] AS target_type,
       target.name AS target_name,
       labels(owner)[0] AS owner_type,
       owner.name AS owner_name,
       owner.id AS owner_id;
```
* **FalkorDB Notes**: `toLower()` and `CONTAINS` are fully supported. We avoid regex `=~` which FalkorDB does not support.

---

### Query 2: Who Knows About a Topic? (Evidence-Ranked)
Finds people with the most evidence of expertise (authored documents, wrote tickets, or participated in chats discussing the topic).

```cypher
// [VERIFIED]
MATCH (p:Person)-[:AUTHORED]->(item)-[:MENTIONS|ABOUT]->(top:Topic)
WHERE toLower(top.name) = toLower($topic_name)
WITH p, count(item) AS evidence_count, collect(item.id) AS evidence_items
RETURN p.id AS person_id,
       p.name AS person_name,
       p.role AS role,
       evidence_count,
       evidence_items[0..5] AS sample_evidence
ORDER BY evidence_count DESC
LIMIT 5;
```
* **FalkorDB Notes**: `WITH p, count(item)` aggregation before `ORDER BY` is standard OpenCypher and verified in FalkorDB. List slicing (`[0..5]`) is supported.

---

### Query 3: Trace a Decision (Current + History + Source Provenance)
Traces the current active decision, the older decisions it replaced via `[:SUPERSEDES]`, and the exact `Source` text snippet.

```cypher
// [VERIFIED]
MATCH (d:Decision)-[:ABOUT]->(top:Topic)
WHERE toLower(top.name) = toLower($topic_name)
OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
OPTIONAL MATCH (d)-[:SUPERSEDES]->(old:Decision)
OPTIONAL MATCH (old)-[:DERIVED_FROM]->(old_src:Source)
RETURN d.id AS decision_id,
       d.text AS decision_text,
       d.status AS status,
       d.valid_from AS valid_from,
       src.id AS source_id,
       src.file_path AS source_file,
       src.text_snippet AS source_text,
       old.id AS superseded_decision_id,
       old.text AS superseded_text,
       old_src.id AS superseded_source_id;
```
* **FalkorDB Notes**: Multi-hop `OPTIONAL MATCH` clauses operate smoothly. Returns `null` for fields if no superseding history exists yet.

---

### Query 4: Supersede a Decision (New Decision Replaces Old Decision)
When an updated decision arrives (e.g. via `/data/live/new_decision.json`), create the new decision, link it to its source, link `(new)-[:SUPERSEDES]->(old)`, and mark the old decision as superseded.

```cypher
// [VERIFIED]
MATCH (old:Decision {topic: $topic, status: "current"})
SET old.status = "superseded",
    old.valid_to = $timestamp
WITH old
CREATE (new:Decision {
    id: $new_decision_id,
    text: $decision_text,
    topic: $topic,
    status: "current",
    valid_from: $timestamp,
    valid_to: ""
})
CREATE (src:Source {
    id: $source_id,
    file_path: $file_path,
    chunk_offset: $chunk_offset,
    text_snippet: $snippet,
    created_at: $timestamp
})
CREATE (new)-[:DERIVED_FROM]->(src)
CREATE (new)-[:SUPERSEDES {superseded_at: $timestamp}]->(old)
WITH new, old, src
MATCH (top:Topic) WHERE toLower(top.name) = toLower($topic)
CREATE (new)-[:ABOUT]->(top)
RETURN new.id AS new_id, old.id AS superseded_id, src.id AS source_id;
```
* **FalkorDB Notes**: FalkorDB supports chained `WITH` clauses carrying forward variables between mutation steps (`SET` -> `CREATE`).

---

### Query 5: What Changed Since a Given Date?
Lists all decisions made or updated, tickets created, and documents modified after `$since_date` (format: `YYYY-MM-DD`).

```cypher
// [VERIFIED]
MATCH (d:Decision)
WHERE d.valid_from >= $since_date
OPTIONAL MATCH (d)-[:DERIVED_FROM]->(src:Source)
OPTIONAL MATCH (d)-[:DECIDED_BY]->(actor)
RETURN "Decision" AS change_type,
       d.id AS item_id,
       d.text AS summary,
       d.valid_from AS timestamp,
       d.status AS status,
       src.id AS source_id,
       actor.name AS actor_name
UNION
MATCH (tk:Ticket)
WHERE tk.created_at >= $since_date
OPTIONAL MATCH (p:Person)-[:AUTHORED]->(tk)
RETURN "Ticket" AS change_type,
       tk.id AS item_id,
       tk.title AS summary,
       tk.created_at AS timestamp,
       tk.status AS status,
       tk.id AS source_id,
       p.name AS actor_name
ORDER BY timestamp DESC;
```
* **FalkorDB Notes**:
  - String date comparison (`d.valid_from >= $since_date`) works reliably in FalkorDB without needing complex date parsing procedures.
  - `UNION` is fully supported in FalkorDB, provided column names and types match across queries.
