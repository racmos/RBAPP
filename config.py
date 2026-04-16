import os

def _engine_options(db_uri: str) -> dict:
    """Return engine options appropriate for the database backend.
    SQLite (used in tests) does not accept client_encoding."""
    if db_uri.startswith('sqlite'):
        return {'pool_pre_ping': True}
    return {
        'connect_args': {'client_encoding': 'utf8'},
        'pool_pre_ping': True,
    }

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    # PostgreSQL connection string with psycopg driver
    # Format: postgresql+psycopg://user:password@host:port/database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql+psycopg://postgres:abcd1234@192.168.1.33:5432/postgres?client_encoding=utf8'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = _engine_options(
        os.environ.get('DATABASE_URL') or
        'postgresql+psycopg://postgres:abcd1234@192.168.1.33:5432/postgres'
    )
