# Delta for collection-quantity

> Tags: `[a]`..`[e]` = delivery unit. `[PG-CI]` = verify in the PostgreSQL CI job; `[MANUAL]` = manual/ops check. Untagged scenarios are pytest-testable on SQLite.

## ADDED Requirements

### Requirement: QTY-1 Integer storage via migration [b]

`rbcol_quantity` MUST be an integer NOT NULL column (model and DB). The quantity revision MUST convert existing text values to integers. Before altering, it MUST abort, changing nothing, if any value is not a whole number in 1..9999 (after trimming), listing the offending `rbcol_id` values. A CHECK `rbcol_quantity >= 1` SHOULD be added. Downgrade MUST restore Text.

_As built (R6, revision `0003_collection_quantity_integer`): pre-flight range 1..9999; the CHECK `rbcollection_quantity_chk` was added and downgrade drops it._

#### Scenario: Data preserved
- GIVEN rows with `rbcol_quantity` `'12'` and `' 3 '` at the previous revision
- WHEN the quantity revision runs
- THEN the rows hold integers 12 and 3

#### Scenario: Pre-flight aborts
- GIVEN rows with quantity `'abc'`, `''`, `'0'` or `'10000'`
- WHEN the revision runs
- THEN it raises an error listing those `rbcol_id`s and the column is still Text with its data

#### Scenario: Downgrade
- GIVEN head
- WHEN the revision is downgraded
- THEN the column is Text and values read `'12'`, `'3'`

#### Scenario: PG cast path [PG-CI]
- GIVEN PostgreSQL with text quantities `'12'`, `'3'`
- WHEN the revision runs and is downgraded
- THEN `ALTER ... USING` succeeds in both directions and values are preserved

### Requirement: QTY-2 Numeric ordering [b]

The collection list sorted by quantity MUST order numerically.

#### Scenario: Ascending and descending
- GIVEN a user with lines of quantity 2, 10 and 3
- WHEN `GET /riftbound/collection?sort_by=quantity&sort_order=asc` (then `desc`) is requested
- THEN the lines appear as 2, 3, 10 (then 10, 3, 2)

### Requirement: QTY-3 Atomic merge on add [b]

Adding to an existing line (same user, set, card, foil) MUST increase the quantity by the added amount in a single database update, not read-modify-write. Quantities MUST be stored and read as integers by add, update, bulk-apply and export.

#### Scenario: Sequential adds
- GIVEN a line with quantity 1
- WHEN `POST /riftbound/collection/add` adds 2 and then 3 to the same line
- THEN one row remains with integer quantity 6

#### Scenario: Concurrent adds [MANUAL]
- GIVEN a line with quantity 1
- WHEN two requests add 2 each concurrently on PostgreSQL
- THEN the final quantity is 5 (no lost update); verified by code review that no read-modify-write remains

#### Scenario: Export arithmetic
- GIVEN a line with quantity 12 and playset 3
- WHEN `POST /riftbound/collection/export_csv` selects it
- THEN the exported quantity is 9

### Requirement: QTY-4 Validated CSV import [b]

`POST /riftbound/collection/import_csv` takes JSON `{"csv_data": "<lines>"}`; each non-blank line is `set;card;foil;quantity`. A line is valid only if foil is `N` or `S`, quantity is an integer 1..9999 (whitespace and `\r` trimmed) and the card exists in `rbcards`. Valid lines MUST be applied to the current user (existing line: quantity overwritten, as today; else created). Invalid lines MUST be skipped and reported by line number and reason. The response MUST keep `success: true` and add `imported` (count) and `skipped` (list). A non-JSON body or missing `csv_data` MUST return 400, not 500.

#### Scenario: Mixed input
- GIVEN card `OGN/1` exists, `OGN/999` does not, and the user has no lines
- WHEN `csv_data` is `"OGN;1;N;3\nOGN;999;N;1\nOGN;1;X;1\nOGN;1;N;abc\nOGN;1;N;0\nOGN;1;S;10000\nbad"`
- THEN `imported == 1`, `skipped` has 6 entries with line numbers 2-7, and exactly one line (quantity 3, foil N) exists

#### Scenario: Overwrite existing
- GIVEN the user has `OGN/1` foil N quantity 5
- WHEN `csv_data` is `"OGN;1;N;2"`
- THEN the line's quantity is integer 2 and no second row is created

#### Scenario: Bad body
- GIVEN an authenticated user
- WHEN `import_csv` is posted with a non-JSON body, or JSON without `csv_data`
- THEN the status is 400 with `{success:false,error,message}`

#### Scenario: Scoped to caller
- GIVEN user B has `OGN/1` foil N
- WHEN user A imports `"OGN;1;N;4"`
- THEN B's line is unchanged
