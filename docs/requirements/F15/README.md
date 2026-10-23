# F15: Rules app — phase spec (outline)

Status: planned, **outline only — specified when the phase starts** · Depends on: F12 (production; the phase runs after it), F2 (catalog and card search) · Source: `docs/knowledge/decisions-2026-10-22.md` ("Rules app", "Agreed order") · Phase IDs are identifiers, not order; the order lives in `docs/knowledge/roadmap.md`.

## Goal

A user selects cards that interact and asks how they resolve; the app answers only from the official rule
documents (Core Rules, Tournament Rules, FAQ), showing where the answer comes from. Earlier answers are
stored and returned when the same question is asked again.

## Current state

Nothing exists: no rule documents in the repository, no AI service, no vector search. The card catalog
(`rbcards`, F2 search and `CardCombobox`) is the only building block in place.

## Scope

In (outline): ingesting the official rule documents, selecting cards, asking a question, an answer
grounded in those documents with references, stored queries reused on repeat, semantic (vector) search,
Obsidian-like links between rules, cards and answers.

Out (outline): rules from unofficial sources; deck building advice; judging tournaments.

## Decisions already taken

- The Rules app is a new phase after production and before events (owner, 2026-10-22).
- The user selects cards that interact; the answer comes only from the official rule documents: Core
  Rules, Tournament Rules, FAQ (owner, 2026-10-22).
- Previous queries are stored and returned when repeated (owner, 2026-10-22).
- It needs an AI service paid per query and semantic (vector) search, with Obsidian-like linking (owner,
  2026-10-22).
- It is specified when the phase starts (owner, 2026-10-22).

## Requirements

Outline; IDs are placeholders until the phase is specified.

- **F15-R1** The official documents are ingested into a searchable store with their version and date; a
  new version can replace an old one.
- **F15-R2** A query is a set of selected cards plus an optional question; the answer cites the rule
  sections it is based on and says so when the documents do not cover the case.
- **F15-R3** A repeated query returns the stored answer without calling the AI service (D-F15-5).
- **F15-R4** Calls to the paid AI service are bounded (D-F15-3) and its key lives only in environment
  variables.
- **F15-R5** Rules, cards and answers are linked to each other and navigable (D-F15-7).

## Data model changes

To be specified. Expected: rule documents and their sections with embeddings, stored queries and answers,
links between them (D-F15-2).

## API

To be specified. Expected under `/riftbound/api/v1/rules/`: ask, list/read stored answers, read a rule
section; admin endpoints to ingest documents.

## UI

To be specified. Expected: card picker (F2 `CardCombobox`), question box, answer with cited sections,
linked rules view; mobile, desktop and wide layouts like every screen.

## Units

To be defined when the phase is specified.

## Open decisions

| ID | Question | Options | Recommendation | Blocks |
|---|---|---|---|---|
| D-F15-1 | AI service | hosted API (per-query cost) / self-hosted model | A hosted API with per-query billing, chosen when the phase starts by cost and quality on a sample of real rule questions | Phase start |
| D-F15-2 | Vector store | `pgvector` in the existing PostgreSQL / external service | `pgvector` in PostgreSQL (no new server; backups already cover it) | Phase start |
| D-F15-3 | Cost control | per-user limit / global monthly budget / admin only | Per-user daily limit plus a global monthly budget with a kill switch; stored answers do not count | Phase start |
| D-F15-4 | Who can use it | every signed-in user / admin only at first | Admin only during a trial, then every signed-in user | Phase start |
| D-F15-5 | When two queries are "the same" | same card set + same normalised question / semantic match | Exact match on the sorted card set and the normalised question; semantic matches shown as "preguntas parecidas", not reused silently | Phase start |
| D-F15-6 | Languages | documents in English, answers in the user's language / English only | Answers in the user's language (es/en) with quotes of the English source text | Phase start |
| D-F15-7 | Meaning of "Obsidian-like linking" | backlinks between rule sections, cards and answers / graph view | Backlinks and a list of related items first; a graph view only if the owner asks for it | Phase start |
| D-F15-8 | How the official documents arrive and are updated | owner uploads files / scraped from the official site | Owner provides the files; the admin ingests a new version from the admin panel | Phase start |
| D-F15-9 | Stored answers after a new rules version | keep / mark outdated / recompute | Mark them outdated and recompute on the next request | Phase start |

## Risks and notes

- **Cost**: every new question costs money; caching and limits (D-F15-3, D-F15-5) are part of the first
  unit, not an afterthought.
- **Wrong answers**: the answer must cite its sources and say when the documents do not cover a case; it
  is not an official ruling.
- **Licensing**: storing and quoting Riot's rule documents needs the same fan-content review as the rest of
  the app (F11 disclaimer, F12 licensing).
- **Secrets**: the AI service key is an environment variable, never logged or sent to the frontend.
