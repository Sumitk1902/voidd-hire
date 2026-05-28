"""FastAPI ASGI wrapper that delegates ALL requests to the Flask app.

Supervisor runs `uvicorn server:app --host 0.0.0.0 --port 8001`.
This entry point keeps that contract while letting us serve a pure Flask app.
"""
from a2wsgi import WSGIMiddleware
from app import flask_app

# Expose as ASGI for uvicorn
app = WSGIMiddleware(flask_app)
