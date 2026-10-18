import os

from app import create_app, db

app = create_app()

# Middleware sencillo para desarrollo local que establece SCRIPT_NAME
class PrefixMiddleware:
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix

    def __call__(self, environ, start_response):
        path = environ.get('PATH_INFO', '')
        if path.startswith(self.prefix):
            environ['SCRIPT_NAME'] = self.prefix
            environ['PATH_INFO'] = path[len(self.prefix):] or '/'
            return self.app(environ, start_response)
        # si no comienza con el prefijo devolvemos 404 (evita mezclar rutas)
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']

# Solo para testing local — no usar en producción
#app.wsgi_app = PrefixMiddleware(app.wsgi_app, '/riftbound')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    # Solo para desarrollo local (SESS-2): bind a loopback y debug apagado por
    # defecto. El debugger de Werkzeug solo se activa con FLASK_DEBUG=1 (y
    # create_app lo rechaza en produccion); ampliar el bind requiere RB_HOST.
    app.run(
        host=os.environ.get('RB_HOST', '127.0.0.1'),
        port=int(os.environ.get('RB_PORT', '5000')),
        debug=app.debug,
    )
