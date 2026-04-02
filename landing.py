from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc):
    return HTMLResponse(
        status_code=404,
        content=f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>404 - No Encontrado (Landing)</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background-color: #1a1a1a;
                    color: #f0f0f0;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    margin: 0;
                    text-align: center;
                }}
                .container {{
                    background-color: #2a2a2a;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                    max-width: 600px;
                    width: 90%;
                }}
                h1 {{ color: #e74c3c; margin-bottom: 20px; }}
                p {{ margin-bottom: 20px; line-height: 1.6; }}
                code {{ background-color: #333; padding: 2px 6px; border-radius: 4px; color: #e74c3c; }}
                .btn {{
                    display: inline-block;
                    background-color: #4a90e2;
                    color: white;
                    padding: 12px 24px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    transition: background-color 0.3s;
                    margin-top: 20px;
                }}
                .btn:hover {{ background-color: #357abd; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>404 - Recurso No Encontrado</h1>
                <p>El recurso que buscas no se encuentra en la <strong>Landing Page</strong> (Puerto 8000).</p>
                <p><strong>URL Solicitada:</strong> <code>{request.url.path}</code></p>
                <p>Es posible que faltara el prefijo <code>/riftbound/</code> en la solicitud.</p>
                <a href="/riftbound/" class="btn">Ir a la Aplicación Principal</a>
            </div>
        </body>
        </html>
        """
    )

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Riftbound Manager</title>
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #1a1a1a;
                color: #f0f0f0;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                height: 100vh;
                margin: 0;
            }
            .container {
                text-align: center;
                background-color: #2a2a2a;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                max-width: 600px;
                width: 90%;
            }
            h1 {
                color: #4a90e2;
                margin-bottom: 20px;
            }
            p {
                margin-bottom: 30px;
                line-height: 1.6;
            }
            .btn {
                display: inline-block;
                background-color: #4a90e2;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 5px;
                font-weight: bold;
                transition: background-color 0.3s;
            }
            .btn:hover {
                background-color: #357abd;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Bienvenido a Riftbound Manager</h1>
            <p>La herramienta definitiva para gestionar tu colección de cartas, mazos y precios de Riftbound.</p>
            <a href="/riftbound/" class="btn">Ir a la Aplicación</a>
        </div>
    </body>
    </html>
    """
    return html_content
