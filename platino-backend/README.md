# Platino Backend

Este backend usa [FastAPI](https://fastapi.tiangolo.com/) para exponer una API y un websocket que permiten integrar un LLM y subir archivos para RAG (Retrieval Augmented Generation).

## Instalación

```bash
pip install -r requirements.txt
```

Por defecto se usa una base de datos SQLite (`platino.db`). Las tablas se
crean automáticamente cuando se inicia la aplicación.

## Uso

```bash
uvicorn app.main:app --reload
```

El websocket está disponible en `/ws/chat` y los endpoints para manejo de archivos en `/api/files`.

Puedes consultar la documentación automática (Swagger UI) en `http://localhost:8000/docs` cuando la aplicación esté en marcha.
