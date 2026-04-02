# Skill Registry - Riftbound Project

**Generated**: 2026-03-31
**Mode**: engram (hybrid)

## Project Skills (Local)

Located in `.agent/skills/`:

| Skill | Description | Trigger |
|-------|-------------|---------|
| `python-pro` | Python best practices and patterns | Writing Python code |
| `fastapi-pro` | FastAPI patterns (not used in this Flask project) | — |
| `python-performance-optimization` | Performance optimization tips | Performance-related tasks |

## User Skills (Auto-resolved)

Skills are resolved from the registry and injected into sub-agent prompts as compact rules. Match by code context (file extensions) and task context.

### Skill Resolution Matrix

| Code Context | Task Context | Skills to Inject |
|--------------|--------------|------------------|
| `*.py` | Writing Python | `python-pro` |
| `*.py` | Testing | `pytest` (if available) |
| `app/routes/*.py` | API design | `django-drf` (Flask equivalent patterns) |
| `app/models/*.py` | Database models | `python-pro` |
| `*.html` | Frontend templates | `tailwind-4` (for styling patterns) |
| `app/__init__.py` | App factory | `python-pro` |

## Project Standards (Compact Rules)

### Python
```python
# Use type hints
def function(param: str) -> dict:
    pass

# Use f-strings
name = f"Hello {user}"

# Use context managers
with db.session.begin():
    db.session.add(obj)

# Query patterns
cards = RbCard.query.filter_by(rbcar_rbset_id=set_id).all()
```

### Database
```python
# Always commit after changes
db.session.add(obj)
db.session.commit()

# Use rollback on error
try:
    db.session.commit()
except:
    db.session.rollback()
    raise

# Filter with ilike for case-insensitive search
query.filter(RbCard.rbcar_name.ilike(f'%{search}%'))
```

### Routes
```python
# Always require auth for protected routes
@main_bp.route('/endpoint')
@login_required
def protected_endpoint():
    pass

# Return JSON for API endpoints
return jsonify({'success': True, 'data': data})
```

### Templates (Jinja2)
```html
<!-- Use url_for for links -->
<a href="{{ url_for('main.cards') }}">Cards</a>

<!-- Pass current_user to templates -->
{{ current_user.username }}
```

## Skills Not Found

The following skills were not found but may be useful:
- `pytest` — No test runner detected
- `tailwind-4` — Project uses vanilla CSS
- `typescript` — No TypeScript in project

## Notes

- This is a Flask project, not Django or FastAPI
- No TypeScript/JavaScript framework detected (vanilla JS only)
- No E2E testing framework detected
- Project uses PostgreSQL with SQLAlchemy ORM
