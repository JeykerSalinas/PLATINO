from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from io import BytesIO
from pathlib import Path
import os
import tempfile
import traceback
import fitz  # PyMuPDF
import httpx
import requests

# LlamaIndex / Qdrant
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core.node_parser import SentenceSplitter


from llama_index.readers.file import PyMuPDFReader, PDFReader
from llama_index.core.settings import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, Filter, FieldCondition, MatchValue, HnswConfigDiff, PayloadSchemaType
from qdrant_client.http.exceptions import UnexpectedResponse

# Project deps
from ...db.session import get_db
from ...db.models import Document, Topic
from ...core.config import settings as app_settings

# --------------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------------
router = APIRouter()

# --------------------------------------------------------------------------------------
# Global config
# --------------------------------------------------------------------------------------
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# Make LlamaIndex use our embedding model (set once at import)
Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)

# File storage
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Qdrant
QDRANT_URL = app_settings.qdrant_url  # e.g. http://qdrant:6333
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents_384")
QDRANT_DISTANCE = Distance.COSINE
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6"))

# Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")  # single source of truth

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def _safe_filename(name: str) -> str:
    # Drop any directory components (basic traversal mitigation)
    return Path(name).name

def _ensure_qdrant_collection(client: QdrantClient, *, recreate_if_dim_mismatch: bool = True) -> None:
    try:
        info = client.get_collection(QDRANT_COLLECTION)
        size = info.config.params.vectors.size  # type: ignore[attr-defined]
        if recreate_if_dim_mismatch and size != EMBEDDING_DIM:
            # Keep it explicit — you may prefer to raise instead of recreating (data loss!)
            raise ValueError(f"Found collection with dim {size} ≠ {EMBEDDING_DIM}")
    except Exception:
        client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=QDRANT_DISTANCE),
            hnsw_config=HnswConfigDiff(m=16, ef_construct=128),
        )
        client.create_payload_index(QDRANT_COLLECTION, field_name="topic", field_schema=PayloadSchemaType.KEYWORD)
        client.create_payload_index(QDRANT_COLLECTION, field_name="module", field_schema=PayloadSchemaType.KEYWORD)
        client.create_payload_index(QDRANT_COLLECTION, field_name="filename",  field_schema=PayloadSchemaType.KEYWORD)

def _thumbnail_from_pdf(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    try:
        page = doc.load_page(0)
        pix = page.get_pixmap()
        thumb_path = UPLOAD_DIR / f"{pdf_path.name}.png"
        pix.save(thumb_path)
        return str(thumb_path)
    finally:
        doc.close()

def _index_nodes_in_qdrant(nodes, metadata: Dict[str, Any]):
    client = QdrantClient(url=QDRANT_URL)
    _ensure_qdrant_collection(client)

    # Attach metadata to every node before indexing
    for node in nodes:
        md = dict(metadata)
        # Preserve existing metadata if any
        if getattr(node, "metadata", None):
            md.update(node.metadata)
        node.metadata = md

    vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex(nodes, storage_context=storage_context)


# --------------------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------------------
class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = Field(..., example="llama3")
    messages: List[ChatMessage] = Field(..., example=[{"role": "user", "content": "Hola"}])
    stream: bool = True
    options: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def validate_messages(self):
        if not self.messages:
            raise ValueError("messages no puede estar vacío")
        last = self.messages[-1]
        if not isinstance(last, ChatMessage) or not last.content:
            raise ValueError("El último mensaje debe tener 'content'")
        return self


# --------------------------------------------------------------------------------------
# Files API
# --------------------------------------------------------------------------------------
@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    topic_id: Optional[int] = Query(None),
):
    try:
        # Sanitize name and persist file
        raw_name = _safe_filename(file.filename)
        content = await file.read()
        path = UPLOAD_DIR / raw_name
        with open(path, "wb") as f:
            f.write(content)

        thumb_path: Optional[str] = None
        chunks: List[str] = []
        metadata: Dict[str, Any] = {"filename": raw_name, "source": str(path)}
        nodes = None

        # Topic (optional)
        topic = db.get(Topic, topic_id) if topic_id is not None else None
        if topic_id is not None and topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")

        # PDF handling (thumbnail + chunking + prepare nodes)
        if raw_name.lower().endswith(".pdf"):
            # Thumbnail
            thumb_path = _thumbnail_from_pdf(path)

            # Chunking via LlamaIndex
            pdf_reader = PDFReader()
            documents = pdf_reader.load_data(str(path))
            splitter = SentenceSplitter(chunk_size=1000, chunk_overlap=150)  # ≈15% solape

            nodes = splitter.get_nodes_from_documents(documents)
            chunks = [n.get_content() for n in nodes]
            metadata["pages"] = fitz.open(path).page_count  # inexpensive reopen

        # Persist DB row
        doc_db = Document(
            filename=raw_name,
            filepath=str(path),
            thumbnail=thumb_path,
            file_metadata=metadata,
            chunks=chunks,
            topic_id=topic_id,
        )
        db.add(doc_db)
        db.commit()
        db.refresh(doc_db)

        # If we created nodes, attach richer metadata and index
        if nodes is not None:
            for node in nodes:
                node.metadata = {
                    "document_id": doc_db.id,
                    "filename": doc_db.filename,
                    "topic_id": topic.id if topic else None,
                    "module_id": topic.module.id if (topic and topic.module) else None,
                    "topic": topic.title if topic else None,
                    "module": topic.module.title if (topic and topic.module) else None,
                    "page_start": node.metadata.get("page_label") or node.metadata.get("page_start"),
                    "page_end": node.metadata.get("page_label") or node.metadata.get("page_end")
                }
            try:
                _index_nodes_in_qdrant(nodes, metadata={})
            except Exception as e:
                # Do not rollback DB doc if vector indexing fails
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Error indexando en Qdrant: {e}")

        return {
            "id": doc_db.id,
            "filename": doc_db.filename,
            "thumbnail": doc_db.thumbnail,
            "chunks": chunks,
            "metadata": metadata,
            "topic_id": doc_db.topic_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/files")
async def list_files(db: Session = Depends(get_db)):
    docs = db.query(Document).all()
    return {
        "files": [
            {
                "id": d.id,
                "filename": d.filename,
                "thumbnail": d.thumbnail,
                "topic_id": d.topic_id,
            }
            for d in docs
        ]
    }


@router.get("/files/{doc_id}")
async def get_file(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "id": doc.id,
        "filename": doc.filename,
        "filepath": doc.filepath,
        "thumbnail": doc.thumbnail,
        "metadata": doc.file_metadata,
        "chunks": doc.chunks,
        "topic_id": doc.topic_id,
    }


@router.delete("/files/{doc_id}")
async def delete_file(doc_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Remove files on disk (ignore if missing)
    try:
        if doc.filepath and os.path.exists(doc.filepath):
            os.remove(doc.filepath)
        if doc.thumbnail and os.path.exists(doc.thumbnail):
            os.remove(doc.thumbnail)
    except Exception:
        traceback.print_exc()

    # Remove vectors from Qdrant (by filename metadata)
    try:
        client = QdrantClient(url=QDRANT_URL)
        _ensure_qdrant_collection(client, recreate_if_dim_mismatch=False)
        q_filter = Filter(must=[FieldCondition(key="filename", match=MatchValue(value=doc.filename))])
        # Newer clients accept `filter=`; older use `points_selector=`. We'll try filter first, fallback.
        try:
            client.delete(collection_name=QDRANT_COLLECTION, filter=q_filter)  # type: ignore[arg-type]
        except TypeError:
            client.delete(collection_name=QDRANT_COLLECTION, points_selector=q_filter)  # backward compat
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to delete from Qdrant: {e}")

    db.delete(doc)
    db.commit()
    return {"status": "deleted"}


@router.put("/files/{doc_id}")
async def rename_file(doc_id: int, new_name: str, db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    new_name = _safe_filename(new_name)
    new_path = UPLOAD_DIR / new_name
    if new_path.exists():
        raise HTTPException(status_code=400, detail="Filename already exists")

    os.rename(doc.filepath, new_path)
    if doc.thumbnail:
        thumb_ext = Path(doc.thumbnail).suffix
        new_thumb = UPLOAD_DIR / f"{new_name}{thumb_ext}"
        if os.path.exists(doc.thumbnail):
            os.rename(doc.thumbnail, new_thumb)
        doc.thumbnail = str(new_thumb)

    # Update DB + metadata
    doc.filename = new_name
    doc.filepath = str(new_path)
    meta = dict(doc.file_metadata or {})
    meta["filename"] = new_name
    meta["source"] = str(new_path)
    doc.file_metadata = meta

    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "filename": doc.filename, "thumbnail": doc.thumbnail, "topic_id": doc.topic_id}


@router.put("/files/{doc_id}/topic")
async def set_file_topic(doc_id: int, topic_id: Optional[int], db: Session = Depends(get_db)):
    doc = db.get(Document, doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if topic_id is not None:
        topic = db.get(Topic, topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

    doc.topic_id = topic_id
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "topic_id": doc.topic_id}


# --------------------------------------------------------------------------------------
# Chat API (pass-through to Ollama)
# --------------------------------------------------------------------------------------
@router.post("/chat")
async def chat(
    payload: dict,
    db: Session = Depends(get_db),
):
    print('payload****************')
    print(payload)
    """Simple RAG chat endpoint using Ollama as LLM."""
    question = payload.get("question") if isinstance(payload, dict) else None
    if not question:
        raise HTTPException(status_code=400, detail="Question required")

    try:
        client = QdrantClient(url=QDRANT_URL)
        vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)

        retriever = index.as_retriever(similarity_top_k=5)
        nodes = retriever.retrieve(question)

        context = "\n".join([n.get_content() for n in nodes])
        prompt = f"Contexto:\n{context}\n\nPregunta: {question}\nRespuesta:"

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3", "prompt": prompt, "stream": False},
            timeout=60,
        )
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"Ollama error: {response.text}")

        data = response.json()
        answer = data.get("response") or data.get("answer") or ""

        meta = [
            {
                "document_id": n.metadata.get("document_id"),
                "filename": n.metadata.get("filename"),
                "topic": n.metadata.get("topic"),
                "module": n.metadata.get("module"),
            }
            for n in nodes
        ]

        return {"answer": answer, "chunks": meta}

    except HTTPException:
        raise
    except Exception as e:
        print("❌ Error en /chat:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
# @router.post("/chat")
# async def chat(body: ChatRequest):
#     payload: Dict[str, Any] = {
#         "model": body.model,
#         "messages": [m.dict() for m in body.messages],
#         "stream": body.stream,
#     }
#     if body.options:
#         payload["options"] = body.options

#     if body.stream:
#         async def streamer():
#             async with httpx.AsyncClient(timeout=None) as client:
#                 async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json=payload) as resp:
#                     if resp.status_code == 404:
#                         raise HTTPException(502, detail="Ollama devolvió 404 en /api/chat. Revisa URL/puerto o versión.")
#                     if resp.status_code >= 400:
#                         text = await resp.aread()
#                         raise HTTPException(resp.status_code, detail=f"Error Ollama: {text.decode('utf-8','ignore')}")
#                     async for line in resp.aiter_lines():
#                         if line:
#                             yield line + "\n"
#         return StreamingResponse(streamer(), media_type="application/x-ndjson")
#     else:
#         async with httpx.AsyncClient(timeout=None) as client:
#             r = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
#             if r.status_code == 404:
#                 raise HTTPException(502, detail="Ollama devolvió 404 en /api/chat. Revisa URL/puerto o versión.")
#             if r.status_code >= 400:
#                 raise HTTPException(r.status_code, detail=f"Error Ollama: {r.text}")
#             return JSONResponse(content=r.json())


# --------------------------------------------------------------------------------------
# Simple RAG chat (retrieval optional if collection exists)
# --------------------------------------------------------------------------------------
# @router.post("/chat_rag")
# async def chat_rag(payload: Dict[str, Any], db: Session = Depends(get_db)):
#     question = payload.get("question") if isinstance(payload, dict) else None
#     if not question:
#         raise HTTPException(status_code=400, detail="Question required")

#     model_name = "llama3.1:8b"

#     try:
#         client = QdrantClient(url=QDRANT_URL)
#         collection_exists = True
#         try:
#             client.get_collection(QDRANT_COLLECTION)
#         except UnexpectedResponse as ex:
#             if getattr(ex, "status_code", None) == 404:
#                 collection_exists = False
#             else:
#                 raise
#         except Exception:
#             collection_exists = False

#         nodes = []
#         if collection_exists:
#             vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
#             storage_context = StorageContext.from_defaults(vector_store=vector_store)
#             index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)
#             retriever = index.as_retriever(similarity_top_k=5)
#             nodes = retriever.retrieve(question)

#         context = "\n".join([n.get_content() for n in nodes]) if nodes else ""
#         if context.strip():
#             prompt = f"Contexto:\n{context}\n\nPregunta: {question}\nRespuesta:"
#         else:
#             prompt = f"Pregunta: {question}\nRespuesta:"

   
#         resp = requests.post(
#             f"{OLLAMA_URL}/api/generate",
#             json={"model": model_name, "prompt": prompt, "stream": True, "options": {
#                 "num_gpu": 1,
#             }},
#             timeout=(10, 600),
#         )
#         if resp.status_code != 200:
#             raise HTTPException(status_code=500, detail=f"Ollama error: {resp.text}")

#         data = resp.json()
#         answer = data.get("response") or data.get("answer") or ""
#         meta = [
#             {
#                 "document_id": (getattr(n, "metadata", {}) or {}).get("document_id"),
#                 "filename": (getattr(n, "metadata", {}) or {}).get("filename"),
#                 "topic": (getattr(n, "metadata", {}) or {}).get("topic"),
#                 "module": (getattr(n, "metadata", {}) or {}).get("module"),
#             }
#             for n in nodes
#         ] if nodes else []

#         return {"answer": answer, "chunks": meta, "used_rag": bool(nodes)}

#     except HTTPException:
#         raise
#     except Exception as e:
#         traceback.print_exc()
#         raise HTTPException(status_code=400, detail=str(e))


from fastapi.responses import StreamingResponse
import httpx
import json

@router.post("/chat_rag")
async def chat_rag(
    payload: Dict[str, Any],
    request: Request,
    db: Session = Depends(get_db),
):
    question = payload.get("question")
    if not question:
        raise HTTPException(status_code=400, detail="Question required")

    # --- retrieval ---
    client = QdrantClient(url=QDRANT_URL)
    nodes = []
    try:
        vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)
        retriever = index.as_retriever(similarity_top_k=5)
        retrieved = retriever.retrieve(question)
        nodes = [n for n in retrieved if getattr(n, "score", 0) >= RAG_SIMILARITY_THRESHOLD]
    except Exception:
        nodes = []

    BASE_INSTRUCCIONES = """
    Eres un asistente para estudiantes de historia del arte.
    Responde SIEMPRE en **Markdown** (títulos, listas, énfasis cuando ayude; nada de HTML).
    No inventes datos ni referencias.
    Responde de forma breve primero (resumen en 1–3 frases) y luego desarrolla si procede.
    """

    if nodes:
        INSTRUCCIONES = BASE_INSTRUCCIONES + """
    Política de uso de contexto:
    - Si el contexto es RELEVANTE para la pregunta, úsalo para fundamentar.
    - Si el contexto NO es relevante o está vacío, responde con conocimiento general, sin disculparte ni mencionar que falta contexto.
    Citas:
    - Si usaste el contexto, al final añade una sección de nivel 3 llamada "### Fuentes" con una lista de viñetas de las fuentes (usa exactamente los nombres de archivo que te doy).
    - Si NO usaste contexto, NO añadas la sección de fuentes.
    """

        def _truncate(txt: str, max_chars=1200):
            return txt[:max_chars]
        context_text = "\n\n".join(_truncate(n.get_content()) for n in nodes)

        raw_meta = [{
            "document_id": (getattr(n, "metadata", {}) or {}).get("document_id"),
            "filename":    (getattr(n, "metadata", {}) or {}).get("filename"),
            "topic":       (getattr(n, "metadata", {}) or {}).get("topic"),
            "module":      (getattr(n, "metadata", {}) or {}).get("module"),
        } for n in nodes]
        seen = set()
        meta = []
        for m in raw_meta:
            key = (m["document_id"], m["filename"])
            if key not in seen:
                seen.add(key)
                meta.append(m)

        fuentes_md = "\n".join(f"- {m['filename']}" for m in meta)

        prompt = f"""{INSTRUCCIONES}

    ### Contexto (opcional)
    {context_text}

    ### Fuentes disponibles (para citar si usas el contexto)
    {fuentes_md}

    ### Pregunta
    {question}

    ### Respuesta (en Markdown)
    """
    else:
        meta = []
        prompt = f"""{BASE_INSTRUCCIONES}

    ### Pregunta
    {question}

    ### Respuesta (en Markdown)
    """

    async def ndjson_generator():
        yield json.dumps({"event": "meta", "data": {"chunks": meta, "used_rag": bool(nodes)}}) + "\n"
        async with httpx.AsyncClient(timeout=None) as client_http:
            async with client_http.stream(
                "POST",
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": True,
                    "keep_alive": "30m",  # mantiene el modelo cargado
                    "options": {"num_predict": 256, "num_gpu": 1},
                },
            ) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    yield json.dumps({"event": "error", "data": text.decode("utf-8", "ignore")}) + "\n"
                    return
                async for line in resp.aiter_lines():
                    if await request.is_disconnected():
                        break
                    if not line:
                        continue
                    yield line + "\n"

    return StreamingResponse(ndjson_generator(), media_type="application/x-ndjson")
