# PLATINO

Este proyecto incluye un backend FastAPI, un frontend Vite/Vue y servicios auxiliares como Ollama, PostgreSQL y Qdrant.

## Levantar todo con Docker Compose

Requiere [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/).

```bash
docker compose up -d --build
```

Esto inicia los servicios:

- **ollama**: servidor de modelos LLM. Descarga automáticamente el modelo `llama3` si no está presente.
- **db**: base de datos PostgreSQL
- **qdrant**: base de datos vectorial
- **backend**: API FastAPI
- **frontend**: interfaz web Vite

El frontend queda disponible en `http://localhost:5173` (puerto configurable con `FRONTEND_PORT`).

Para detener todos los servicios:

```bash
docker compose down
```

## Desarrollo manual en local

Para desarrollar sin levantar todo con Docker, solo se usa un contenedor para la base de datos SQL. Los demás servicios se ejecutan directamente en el host.

1. **Base de datos**

   ```bash
   docker compose -f docker-compose.db.yml up -d
   ```

2. **Qdrant**

   Instala Qdrant localmente siguiendo la [documentación oficial](https://qdrant.tech/documentation/).
   Luego inicia el servicio:

   ```bash
   qdrant
   ```

3. **Ollama**

   Instala [Ollama](https://ollama.com/download) y ejecuta el servidor:

   ```bash
   ollama serve
   ```

4. **Backend**

   ```bash
   cd platino-backend
   pip install -r requirements.txt
   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/platino
   export QDRANT_URL=http://localhost:6333
   uvicorn app.main:app --reload
   ```

5. **Frontend**

   ```bash
   cd platino-frontend
   cp .env.example .env
   npm install
   npm run dev
   ```

   El frontend se conecta al backend mediante la variable `VITE_API_URL` y a Ollama mediante `VITE_OLLAMA_URL`, ambas definidas en `.env`.

Con estos pasos tendrás todos los servicios funcionando en tu entorno local.
