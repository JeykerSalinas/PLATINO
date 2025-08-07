# Platino Backend

Este backend usa [FastAPI](https://fastapi.tiangolo.com/) para exponer una API y un websocket que permiten integrar un LLM y subir archivos para RAG (Retrieval Augmented Generation).

## Instalación

```bash
pip install -r requirements.txt
```

Por defecto la configuración usa una base de datos PostgreSQL que se levanta
mediante Docker. Las tablas se crean automáticamente cuando se inicia la
aplicación.

### Base de datos con Docker

Desde la raíz del repositorio puedes iniciar la base de datos con:

```bash
docker compose -f docker-compose.db.yml up -d
```

El backend se conecta por defecto a `postgresql://postgres:postgres@localhost:5432/platino`.
Si deseas cambiarlo puedes definir la variable de entorno `DATABASE_URL` antes
de ejecutar el servidor.

Para detener el contenedor:

```bash
docker compose -f docker-compose.db.yml down
```

## Uso

```bash
uvicorn app.main:app --reload
```

El websocket está disponible en `/ws/chat` y los endpoints para manejo de archivos en `/api/files`.
El endpoint `/api/split_pdf` permite enviar un PDF y recibir los textos divididos en chunks utilizando LlamaIndex.

Puedes consultar la documentación automática (Swagger UI) en `http://localhost:8000/docs` cuando la aplicación esté en marcha.
