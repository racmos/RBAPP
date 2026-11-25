# F10-CM-l: Matching workbench — fewer tabs, in workflow order

| Field | Value |
|---|---|
| Phase / unit | F10 / CM-l (Cardmarket admin, owner feedback 2026-11-24) |
| Branch | `feat/cm-matching-tabs` (from up-to-date `origin/main`) |
| Depends on | CM-a…CM-k (all deployed) |
| Size forecast | ~450 authored lines (frontend only) |
| Risk | `Risk: none` (no API, no data; old `?tab=` URLs keep working through aliases) |
| TDD | ON (strict). Runner: `cd frontend && npx vitest run` |
| Sources | Owner message 2026-11-24: "hay como muchas pestañas y alguna creo que carecen de utilidad o se pueden unificar" |

## Objective

The Matching screen (`/admin/cardmarket/matching`) has seven tabs (To link, Linked, Conflicts, Ignored,
Auto-match, Expansions, Missing cards). Several are rarely used or are one step of the same job. Reduce them
to four, ordered as the owner works through a reset or a new set: prepare, auto-match, link by hand, review.

## Read first

- `frontend/src/admin/cardmarket/matching/MatchingPage.tsx` (tab state in `?tab=`, `Counters()`), `format.ts`
  (`TABS`, `parseTab`, shared filter params `q type category set foil match_type reason page`).
- The panels: `ToLinkPanel`, `LinkedPanel` (also exports `ConflictsPanel`), `IgnoredPanel`,
  `AutoMatchPanel`, `ExpansionsPanel`, `MissingCardsPanel`; strings `admin.json` `matching.tabs.*`.
- `docs/knowledge/product.md` (owner decisions) and `docs/frontend.md` (matching screen).

## Scope

In: the tab bar, the URL contract, the merged panels' filters and counters, tests, `docs/frontend.md`,
`docs/knowledge/state.md`, `AGENTS.md` structure line.
Out: any API change, any change to how products are matched, the Create card / Link dialogs.

## Specs

- **S1 Four tabs.** The tab bar is `Prepare | Auto-match | To link | Linked`, in that order (the workflow
  order of the reset). Default tab is `To link` (as today).
- **S2 Prepare** merges Expansions and Missing cards behind a two-option segmented control
  (`Expansions | Missing cards`), URL `?tab=prepare&view=expansions|missing` (`view` default `expansions`;
  `set=` keeps working for Missing cards). Both panels are used unchanged.
- **S3 To link** merges the Ignored list: a segmented control `To link | Ignored` (`?view=ignored`), with the
  ignored count in its label. The Ignored panel (Restore) is used unchanged.
- **S4 Linked** merges Conflicts: a segmented control `All links | Conflicts` (`?view=conflicts`); the
  Conflicts label carries its count and a warning tone when it is above zero, so a conflict is never hidden.
  A tab-level badge is not added (the page counters stay where they are).
- **S5 Old URLs keep working.** `?tab=conflicts` → `linked` + `view=conflicts`; `?tab=ignored` → `link` +
  `view=ignored`; `?tab=expansions` → `prepare` + `view=expansions`; `?tab=missing` → `prepare` +
  `view=missing` (keeps `set`); `?tab=auto` and `?tab=linked` unchanged; an unknown value falls back to
  `link`. The alias rewrites the URL with `replace` (no history entry). The "unmapped expansions" counter link
  and `onOpenLink` (`?tab=linked&q=<id>`) are updated to the new contract.
- **S6 Filters survive.** Changing tab drops the filters that do not belong to the target tab (as today);
  changing only `view` inside a tab keeps `q`, `set`, `category` and drops `page`.
- **S7 Accessibility.** Tabs keep arrow/Home/End keys and `matching-tab-<name>` / `matching-panel-<name>` ids;
  the segmented controls are a radio group (`role="radiogroup"`) with visible focus, label and count read
  by screen readers; axe is clean on all four tabs and on a phone viewport (the four tabs fit without
  horizontal scrolling at 360 px).
- **S8 No lost function.** Every action of the seven old tabs stays reachable in two clicks or fewer
  (Relink/Unlink, Restore, Ignore, preview/apply, map expansion, create missing cards, "View products").
- **S9 Strings** in the `admin` namespace (catalog check green); no Spanish text.

## UI

Desktop (≥ 860 px): the tab bar on one row; the segmented control sits at the left of each merged panel's
toolbar. Phone: the tabs scroll inside their bar only if they do not fit; the segmented control wraps under
the tab bar. The page counters (unmatched, unmapped expansions) stay above the tabs.

## Acceptance criteria

1. Four tabs render, in order, on desktop and phone; each old panel is reachable.
2. Every alias of S5 lands on the right tab/view with the same filters, and the address bar shows the new
   form after a `replace`.
3. Conflicts and Ignored counts show in their control labels; the Conflicts label is in warning tone with
   conflicts present.
4. Existing panel tests keep passing; new tests cover S1–S7. Whole frontend lane green.

## Delivery

One commit, one PR (frontend only; deploy = pull + frontend build, no restart).
`docs/frontend.md`, `docs/knowledge/state.md` row "CM-l matching tabs", `AGENTS.md` matching structure line.

## Open questions

- None. Owner confirmed 2026-11-24: `Prepare | Auto-match | To link | Linked`, default tab `To link`.

## Log

- 2026-11-24 — requirement written from the owner's feedback; proposals marked above.
- 2026-11-25 — built on `feat/cm-matching-tabs` (frontend only; implemented, not deployed).
