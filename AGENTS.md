# Riftbound - Agent Instructions

## Project Overview

**Riftbound Manager** es una aplicación web para gestionar el juego de cartas coleccionables Riftbound. Permite a los usuarios:
- Autenticación y perfiles de usuario
- Gestión de sets de cartas
- Gestión individual de cartas
- Seguimiento de colección personal
- Construcción y gestión de mazos
- Generación de precios

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python Flask 3.0.0 |
| Database | PostgreSQL (schema: `riftbound`) |
| ORM | SQLAlchemy 2.0.23 |
| Auth | Flask-Login 0.6.3 |
| Validation | Pydantic 2.5.3 |
| Testing | pytest 7.4.3 |
| Server | Gunicorn + Nginx |

## Project Structure

```
riftbound/
├── app/
│   ├── __init__.py          # Flask app factory + blueprint registration
│   ├── errors.py            # Error handlers (404, 500, etc)
│   ├── models/              # SQLAlchemy models
│   │   ├── user.py          # User (rbusers)
│   │   ├── set.py           # RbSet (rbset)
│   │   ├── card.py          # RbCard (rbcards)
│   │   ├── collection.py    # RbCollection (rbcollection)
│   │   ├── deck.py          # RbDeck (rbdecks)
│   │   └── market.py        # RbCardMarket (rbcardmarket)
│   ├── routes/
│   │   ├── auth.py          # Auth routes (login/register/logout)
│   │   ├── routes.py        # Main blueprint + domain imports
│   │   └── domains/         # Domain-specific routes
│   │       ├── sets.py      # Sets CRUD
│   │       ├── cards.py     # Cards CRUD + upload
│   │       ├── collection.py # Collection management
│   │       ├── deck.py      # Deck endpoints
│   │       ├── price.py     # Price generation
│   │       └── profile.py   # Profile updates
│   ├── schemas/             # Pydantic validation schemas
│   │   ├── validators.py    # Request validation schemas
│   │   └── validation.py    # @validate_json decorator
│   ├── templates/           # Jinja2 templates (11 files)
│   │   └── errors/          # Error page templates
│   └── static/              # CSS, images
├── tests/
│   ├── conftest.py          # pytest fixtures
│   └── test_routes.py       # Route tests (~40 test cases)
├── docs/                    # 39 documentation files
├── pytest.ini               # pytest configuration
├── config.py                # Flask configuration
├── run.py                   # Entry point
└── requirements.txt         # Python dependencies
```

## Conventions

### Database Naming
- Tablas: `rbusers`, `rbset`, `rbcards`, `rbcollection`, `rbdecks`, `rbcardmarket`
- Schema: `riftbound`
- Prefijo en modelos: `rb` (de Riftbound)

### Column Naming Convention
- Todas las columnas usan snake_case con prefijo de tabla
- Ejemplo: `rbcar_name`, `rbcol_quantity`, `rbdck_snapshot`

### URL Routes
- Todas las rutas usan el prefijo `/riftbound` (para Nginx reverse proxy)
- Rutas de API devuelven JSON con `jsonify()`

### Blueprints
El proyecto usa blueprints por dominio:
- `main_bp` — Dashboard
- `auth_bp` — Login/Register/Logout
- `sets_bp` — Sets management
- `cards_bp` — Cards management
- `collection_bp` — Collection management
- `deck_bp` — Deck management
- `price_bp` — Price generation
- `profile_bp` — Profile management

### Color Scheme (Dark Teal Theme)
| Element | Color | Hex |
|---------|-------|-----|
| Background | Dark Teal | #013951 |
| Hover | Deep Teal | #1a4c62 |
| Accent (buttons) | Cyan | #00b2cf |
| Active/Hover | Orange | #ef7d21 |
| Menu | Black | #111111 |

## Development Guidelines

### Before Writing Code
1. Read the existing patterns in `app/routes/domains/`
2. Check the schemas in `app/schemas/validators.py`
3. Check the models in `app/models/` for the data structure
4. Review templates in `app/templates/` for UI patterns

### Code Style
- Follow PEP 8 for Python
- Use type hints where appropriate
- Document complex SQL queries
- Use `db.session.commit()` after database operations
- Use Pydantic schemas for all JSON request validation

### Request Validation
Todos los endpoints que reciben JSON deben usar `@validate_json`:
```python
from app.schemas.validators import SetCreate
from app.schemas.validation import validate_json

@sets_bp.route('/add', methods=['POST'])
@login_required
@validate_json(SetCreate)
def add_set():
    data = request.validated_data  # Validated Pydantic model
    ...
```

### Testing
```bash
# Install test dependencies
pip install pytest pytest-cov pytest-flask

# Run tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html
```

### Security
- Passwords are hashed with Werkzeug's `generate_password_hash`
- All routes except login/register require `@login_required`
- Environment variables for secrets (`SECRET_KEY`, `DATABASE_URL`)
- Pydantic validation on all JSON endpoints

## Database Operations

### Common Patterns
```python
# Query with filters
cards = RbCard.query.filter(RbCard.rbcar_name.ilike(f'%{search}%')).all()

# Pagination
pagination = query.paginate(page=page, per_page=per_page, error_out=False)

# Join query
query = db.session.query(RbCollection, RbCard).join(
    RbCard, 
    (RbCollection.rbcol_rbset_id == RbCard.rbcar_rbset_id) & 
    (RbCollection.rbcol_rbcar_id == RbCard.rbcar_id)
)
```

### Running Locally
```bash
python run.py
# Access at http://localhost:5000/riftbound
```

### Production
```bash
gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app
```

## Error Handling

El proyecto tiene handlers para errores HTTP:
- `404` — Página no encontrada
- `500` — Error interno del servidor
- `403` — Acceso denegado
- `401` — No autorizado
- `400` — Solicitud inválida

Los errores de API devuelven JSON con formato:
```json
{
  "success": false,
  "error": "Error Type",
  "message": "Description"
}
```

## Project Skills

The following skills are available in `.agent/skills/`:
- `python-pro/` — Python best practices
- `fastapi-pro/` — FastAPI patterns (not used in this project)
- `python-performance-optimization/` — Performance tips

## Common Tasks

### Adding a New Model
1. Create file in `app/models/` (e.g., `player.py`)
2. Define class with `db.Model`, `__tablename__`, schema
3. Import in `app/models/__init__.py`
4. Add route in `app/routes/domains/`

### Adding a New Route
1. Create or update file in `app/routes/domains/`
2. Add `@blueprint_name.route()` with `@login_required` and `@validate_json(schema)`
3. Add template in `app/templates/`
4. Add nav link in `app/templates/base.html`

### Adding Request Validation
1. Define schema in `app/schemas/validators.py`
2. Use `@validate_json(SchemaClass)` decorator
3. Access validated data via `request.validated_data`

## Troubleshooting

### Database Connection Issues
- Check `config.py` for DATABASE_URL format
- Ensure PostgreSQL is running
- Verify credentials and database exists

### Template Not Found
- Check template exists in `app/templates/`
- Verify Flask is looking in correct static/template folders

### Validation Errors
- Check Pydantic schema definitions in `app/schemas/validators.py`
- Error details returned in JSON response under `details` key
