# wsgi.py
from app import create_app

application = create_app()
# `gunicorn wsgi:application` y `wsgi:app` apuntan al mismo objeto.
app = application
