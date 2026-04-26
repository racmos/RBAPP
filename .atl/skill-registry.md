# Skill Registry — rbapp (Riftbound Manager)

**Generated**: 2026-04-26
**Mode**: engram
**SDD Strict TDD**: enabled ✅

---

## User Skills (Auto-resolved from `~/.config/opencode/skills/`)

| Skill | Description | Trigger |
|-------|-------------|---------|
| `sdd-explore` | Investigate ideas before committing to a change | `/sdd-explore <topic>` |
| `sdd-propose` | Create change proposal | `/sdd-propose <change-name>` |
| `sdd-spec` | Write delta specs (Given/When/Then) | `/sdd-spec <change>` |
| `sdd-design` | Technical design document | `/sdd-design <change>` |
| `sdd-tasks` | Break down change into tasks | `/sdd-tasks <change>` |
| `sdd-apply` | Implement tasks from change | `/sdd-apply <change>` |
| `sdd-verify` | Validate implementation vs specs | `/sdd-verify <change>` |
| `sdd-archive` | Archive completed change | `/sdd-archive <change>` |
| `branch-pr` | PR creation workflow | When creating a pull request |
| `issue-creation` | GitHub issue creation | When reporting a bug or feature |
| `judgment-day` | Adversarial dual-review protocol | "judgment day" / "juzgar" |
| `skill-creator` | Create new AI skills | When adding agent instructions |
| `skill-registry` | Update this registry | "update skills" / "skill registry" |

## Project Skills (Local — `.agent/skills/`)

_No project-level skills directory found._

---

## Skill Resolution Matrix

| Code Context | Task Context | Skills to Inject |
|--------------|--------------|------------------|
| `*.py` | Writing Python | `python-pro` (user preference) |
| `app/routes/domains/*.py` | New endpoint | Review `app/schemas/validators.py` first |
| `app/models/*.py` | New model | Follow `rb` prefix convention |
| `tests/test_*.py` | Writing tests | pytest + SQLite in-memory fixtures pattern |
| Any | SDD workflow | Load appropriate `sdd-*` skill |

---

## Project Conventions (Compact Rules)

### Stack
- Flask 3.1.0, Python 3.13, SQLAlchemy 2.0.36, Pydantic 2.10.5
- PostgreSQL (prod) / SQLite in-memory (tests)
- Gunicorn + Nginx — all routes prefixed `/riftbound`

### DB Naming
```
Tables: rbusers, rbset, rbcards, rbcollection, rbdecks, rbcardmarket
Schema: riftbound
Columns: snake_case with table prefix — rbcar_name, rbcol_quantity, rbdck_snapshot
Models: Rb prefix — RbCard, RbSet, RbCollection, RbDeck
```

### Route Pattern
```python
from app.schemas.validators import MySchema
from app.schemas.validation import validate_json

@bp.route('/endpoint', methods=['POST'])
@login_required
@validate_json(MySchema)
def endpoint():
    data = request.validated_data  # validated Pydantic model
    ...
    return jsonify({'success': True, 'data': result})
```

### Testing Pattern
```python
# Use fixtures from conftest.py
def test_something(authenticated_client, sample_card):
    resp = authenticated_client.post('/riftbound/endpoint', json={...})
    assert resp.status_code == 200
    assert resp.json['success'] is True
```

### Test Command
```bash
source venv/bin/activate && pytest -vv --tb=long --cov=app
```

---

## Convention Sources

| File | Role |
|------|------|
| `AGENTS.md` | Full project conventions — read before any code |
| `app/schemas/validators.py` | All Pydantic schemas — check before adding validation |
| `app/routes/domains/` | Existing route patterns — follow these |
| `app/models/` | Model definitions — follow `rb` prefix |
| `tests/conftest.py` | All test fixtures |
| `pytest.ini` | Test runner config |
| `requirements.txt` | Exact pinned dependency versions |
