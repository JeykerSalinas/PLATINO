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

#Embedding wrapper
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.embeddings import BaseEmbedding

class E5Embedding(HuggingFaceEmbedding):
    def get_text_embedding(self, text: str):
        # documentos / pasajes
        return super().get_text_embedding(f"passage: {text}")

    def get_query_embedding(self, query: str):
        # consultas
        return super().get_query_embedding(f"query: {query}")

# --------------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------------
router = APIRouter()
# --------------------------------------------------------------------------------------
# --- MÉTRICAS / LOGGING ---
# --------------------------------------------------------------------------------------
import time, json
from datetime import datetime
from pathlib import Path

METRICS_LOG = Path(os.getenv("METRICS_LOG", "metrics_platino.jsonl"))
def _log_event(event: dict):
    METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)
    event["ts"] = datetime.utcnow().isoformat() + "Z"
    with open(METRICS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

import numpy as np
import re

# Groundedness

def _split_sentences(text: str):
    sents = re.split(r'(?<=[\.\?\!])\s+|\n+', text.strip())
    return [s.strip() for s in sents if s.strip()]

def _cosine(u, v):
    u = np.array(u, dtype=float); v = np.array(v, dtype=float)
    du = np.linalg.norm(u) + 1e-12
    dv = np.linalg.norm(v) + 1e-12
    return float(np.dot(u, v) / (du * dv))

def compute_groundedness_sem(answer: str, nodes) -> dict:
    """
    Para cada oración de la respuesta, calcula la máxima similitud coseno
    (E5) contra los chunks recuperados. Devuelve mean/median/min.
    """
    try:
        if not answer or not nodes:
            return {"mean": None, "median": None, "min": None, "n_sents": 0, "n_ctx": 0}

        embedder = Settings.embed_model  # tu E5Embedding ya configurado
        # Embeddings del contexto (capados por estabilidad)
        ctx_texts = []
        for n in nodes:
            try:
                ctx_texts.append(n.get_content()[:1000])
            except Exception:
                pass
        if not ctx_texts:
            return {"mean": None, "median": None, "min": None, "n_sents": 0, "n_ctx": 0}
        ctx_embs = [embedder.get_text_embedding(t) for t in ctx_texts]

        # Oraciones de la respuesta
        sents = _split_sentences(answer)
        if not sents:
            return {"mean": None, "median": None, "min": None, "n_sents": 0, "n_ctx": len(ctx_embs)}
        ans_embs = [embedder.get_text_embedding(s) for s in sents]

        # Máxima similitud por oración
        per_sent_max = []
        for a in ans_embs:
            sims = [_cosine(a, c) for c in ctx_embs]
            per_sent_max.append(max(sims) if sims else 0.0)

        arr = np.array(per_sent_max, dtype=float)
        return {
            "mean": float(np.mean(arr)),
            "median": float(np.median(arr)),
            "min": float(np.min(arr)),
            "n_sents": len(sents),
            "n_ctx": len(ctx_embs),
        }
    except Exception:
        return {"mean": None, "median": None, "min": None, "n_sents": 0, "n_ctx": 0}





# --------------------------------------------------------------------------------------
# Global config
# --------------------------------------------------------------------------------------
# EMBED_MODEL_NAME = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_MODEL="intfloat/multilingual-e5-small"
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))

# Make LlamaIndex use our embedding model (set once at import)
# Settings.embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)
Settings.embed_model = E5Embedding(model_name=EMBED_MODEL)

# File storage
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Qdrant
QDRANT_URL = app_settings.qdrant_url  # e.g. http://qdrant:6333
# QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents_384")
QDRANT_COLLECTION="documents_e5_384"
QDRANT_DISTANCE = Distance.COSINE
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.6"))

# Ollama
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")  # single source of truth

#Variables de inferencia
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "4096"))  # o 2048 / -1 (sin límite)
NUM_CTX        = int(os.getenv("NUM_CTX", "8192"))         # según el modelo (p.ej., 8192 o 32768)
READ_TIMEOUT_S = int(os.getenv("READ_TIMEOUT_S", "600"))

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

INTENT_SYS = """Eres un clasificador de intención.
Devuelve solo una palabra: RAG o CHITCHAT.
- RAG: la entrada pide info del corpus.
- CHITCHAT: saludos/charla ('hola', 'gracias', etc.)."""

def classify_intent(question: str) -> str:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": "llama3.1:8b",
                "prompt": f"{INTENT_SYS}\n\nEntrada: {question}\nSalida:",
                "options": {"num_predict": 1},
                "stream": False
            },
            timeout=10,
        )
        label = (r.json().get("response") or "").strip().upper()
        return "RAG" if "RAG" in label else "CHITCHAT"
    except Exception:
        tokens = question.lower().strip().split()
        greetings = {"hola","buenas","hey","hello","hi","gracias"}
        return "CHITCHAT" if (len(tokens)<=3 or any(t in greetings for t in tokens)) else "RAG"

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
# @router.post("/chat")
# async def chat(
#     payload: dict,
#     db: Session = Depends(get_db),
# ):
#     print('payload****************')
#     print(payload)
#     """Simple RAG chat endpoint using Ollama as LLM."""
#     question = payload.get("question") if isinstance(payload, dict) else None
#     if not question:
#         raise HTTPException(status_code=400, detail="Question required")

#     try:
#         client = QdrantClient(url=QDRANT_URL)
#         vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
#         storage_context = StorageContext.from_defaults(vector_store=vector_store)
#         index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)

#         retriever = index.as_retriever(similarity_top_k=5)
#         nodes = retriever.retrieve(question)

#         context = "\n".join([n.get_content() for n in nodes])
#         prompt = f"Contexto:\n{context}\n\nPregunta: {question}\nRespuesta:"

#         response = requests.post(
#             "http://localhost:11434/api/generate",
#             json={"model": "llama3", "prompt": prompt, "stream": False},
#             timeout=60,
#         )
#         if response.status_code != 200:
#             raise HTTPException(status_code=500, detail=f"Ollama error: {response.text}")

#         data = response.json()
#         answer = data.get("response") or data.get("answer") or ""

#         meta = [
#             {
#                 "document_id": n.metadata.get("document_id"),
#                 "filename": n.metadata.get("filename"),
#                 "topic": n.metadata.get("topic"),
#                 "module": n.metadata.get("module"),
#             }
#             for n in nodes
#         ]

#         return {"answer": answer, "chunks": meta}

#     except HTTPException:
#         raise
#     except Exception as e:
#         print("❌ Error en /chat:", e)
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
    stream_flag: bool = bool(payload.get("stream", True))

    intent = classify_intent(question)
    if not question:
        raise HTTPException(status_code=400, detail="Question required")

    
    
    # --- retrieval ---
    t0 = time.time()
    client = QdrantClient(url=QDRANT_URL)
    nodes = []
    retrieve_ok = True
    try:
        vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)


        retriever = index.as_retriever(similarity_top_k=5 , similarity_cutoff=RAG_SIMILARITY_THRESHOLD )
        retrieved = retriever.retrieve(question)
        # guardamos todos los scores crudos

        raw_hits = [{
            "score": getattr(n, "score", None),
            "filename": (getattr(n, "metadata", {}) or {}).get("filename"),
            "document_id": (getattr(n, "metadata", {}) or {}).get("document_id"),
        } for n in retrieved]
        # filtramos por umbral configurado
        nodes = [n for n in retrieved if getattr(n, "score", 0) >= RAG_SIMILARITY_THRESHOLD]
        
    except Exception as e:
        retrieve_ok = False
        raw_hits = []
        nodes = []
    t1 = time.time()
    retrieval_latency = t1 - t0
    used_rag = (intent == "RAG") and (len(nodes) >= 2)

    # --- construcción del prompt + metadatos para UI y citas ---
    BASE_INSTRUCCIONES = """
    Eres un asistente para estudiantes de historia del arte.
    Responde SIEMPRE en **Markdown** (títulos, listas, énfasis cuando ayude; nada de HTML).
    No inventes datos ni referencias.
    Responde de forma breve primero (resumen en 1–3 frases) y luego desarrolla si procede.
    """

    if used_rag:
        INSTRUCCIONES = BASE_INSTRUCCIONES + """
    Política de uso de contexto:
    - Si el contexto es RELEVANTE para la pregunta, úsalo para fundamentar.
    - Si el contexto NO es relevante o está vacío, responde con conocimiento general.
    Citas:
    - Si usaste el contexto, al final añade "### Fuentes" con la lista de archivos utilizados (exactamente los nombres).
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

    # --- generación (latencia) ---
    async def ndjson_generator():
        # primer frame: metadatos y datos de recuperación
        _log_event({
            "type": "retrieval",
            "question": question,
            "collection": QDRANT_COLLECTION,
            "similarity_top_k": 5,
            "similarity_threshold": RAG_SIMILARITY_THRESHOLD,
            "retrieval_latency_s": retrieval_latency,
            "retrieval_ok": retrieve_ok,
            "raw_hits": raw_hits,
            "used_rag": used_rag,
        })
        yield json.dumps({"event": "meta", "data": {"chunks": meta, "used_rag": used_rag}}) + "\n"

        t2 = time.time()
        async with httpx.AsyncClient(timeout=None) as client_http:
            async with client_http.stream(
                "POST",
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": True,
                    "keep_alive": "30m",
                    "options": {
                        "num_predict": MAX_NEW_TOKENS,
                        "num_ctx": NUM_CTX,
                        "repeat_penalty": 1.1,
                        "num_gpu": 1
                    }
                },
            ) as resp:
                if resp.status_code != 200:
                    text = await resp.aread()
                    _log_event({
                        "type": "generation_error",
                        "question": question,
                        "status": resp.status_code,
                        "error": text.decode("utf-8","ignore"),
                    })
                    yield json.dumps({"event": "error", "data": text.decode("utf-8", "ignore")}) + "\n"
                    return
                answer_parts = []
                async for line in resp.aiter_lines():
                    if await request.is_disconnected():
                        break
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        if "response" in obj:
                            answer_parts.append(obj["response"])
                    except Exception:
                        pass
                    yield line + "\n"
        t3 = time.time()
        gen_latency = t3 - t2
        final_answer = "".join(answer_parts)
        
        # Groundedness semántica (proxy de faithfulness) ---
        grounded = compute_groundedness_sem(final_answer, nodes)

        _log_event({
            "type": "generation",
            "question": question,
            "used_rag": used_rag,
            "gen_latency_s": gen_latency,
            "answer_len_chars": len(final_answer),
            "tokens_approx": len(final_answer.split()),
            "answer": final_answer,
            "files_used": [m["filename"] for m in meta] if used_rag else [],
            "groundedness_sem": grounded  # {mean, median, min, n_sents, n_ctx}
        })

    if not stream_flag:
        _log_event({
            "type": "retrieval",
            "question": question,
            "collection": QDRANT_COLLECTION,
            "similarity_top_k": 5,
            "similarity_threshold": RAG_SIMILARITY_THRESHOLD,
            "retrieval_latency_s": retrieval_latency,
            "retrieval_ok": retrieve_ok,
            "raw_hits": raw_hits,
            "used_rag": used_rag,
        })

        t2 = time.time()
        async with httpx.AsyncClient(timeout=None) as client_http:
            resp = await client_http.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.1:8b",
                    "prompt": prompt,
                    "stream": False,           # ← clave: NO streaming
                    "keep_alive": "30m",
                    "options": {
                        "num_predict": MAX_NEW_TOKENS,
                        "num_ctx": NUM_CTX,
                        "repeat_penalty": 1.1,
                        "num_gpu": 1
                    }
                },
            )
        if resp.status_code != 200:
            _log_event({"type": "generation_error", "question": question,
                        "status": resp.status_code, "error": resp.text})
            raise HTTPException(status_code=500, detail=f"Ollama error: {resp.text}")

        gen_latency = time.time() - t2
        data = resp.json()
        final_answer = data.get("response") or data.get("answer") or ""
        grounded = compute_groundedness_sem(final_answer, nodes)

        _log_event({
            "type": "generation", "question": question, "used_rag": used_rag,
            "gen_latency_s": gen_latency, "answer_len_chars": len(final_answer),
            "tokens_approx": len(final_answer.split()),
            "files_used": [m["filename"] for m in meta] if used_rag else [],
            "groundedness_sem": grounded,
            "answer": final_answer,
        })

        return {
            "answer": final_answer,
            "chunks": meta,
            "used_rag": used_rag,
            "retrieval": {
                "latency_s": retrieval_latency,
                "ok": retrieve_ok,
                "raw_hits": raw_hits
            },
            "generation": {"latency_s": gen_latency},
            "groundedness_sem": grounded
        }

    return StreamingResponse(ndjson_generator(), media_type="application/x-ndjson")


# --------------------------------------------------------------------------------------
# --- Endpoint para evaluación de recuperación (precision/recall/F1@k) ---
# Body
# POST /eval/retrieval
# {
#   "items": [
#     {
#       "question": "¿Qué es el arte románico?",
#       "gold_filenames": ["apuntes_tema1.pdf", "historia_románico.pdf"],
#       "k": 5
#     }
#   ]
# }
# --------------------------------------------------------------------------------------

from sklearn.metrics import precision_score, recall_score, f1_score

class RetrievalEvalItem(BaseModel):
    question: str
    gold_filenames: List[str]  # define tu oro por nombres de archivo (o cambia a IDs)
    k: int = 5
    threshold: float = RAG_SIMILARITY_THRESHOLD

class RetrievalEvalRequest(BaseModel):
    items: List[RetrievalEvalItem]

@router.post("/eval/retrieval")
async def eval_retrieval(payload: RetrievalEvalRequest):
    client = QdrantClient(url=QDRANT_URL)
    vector_store = QdrantVectorStore(client=client, collection_name=QDRANT_COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)
    retriever = index.as_retriever(similarity_top_k=max((it.k for it in payload.items), default=5))

    results = []
    bin_gold_all, bin_pred_all = [], []

    for it in payload.items:
        retrieved = retriever.retrieve(it.question)
        # top-k y umbral
        filtered = [n for n in retrieved if getattr(n, "score", 0) >= it.threshold][:it.k]
        got_filenames = [(getattr(n, "metadata", {}) or {}).get("filename") for n in filtered]

        # vector binario por universo = union(gold ∪ got) para estabilidad
        universe = sorted(set(it.gold_filenames) | set(got_filenames))
        gold_bin = [1 if f in it.gold_filenames else 0 for f in universe]
        pred_bin = [1 if f in got_filenames else 0 for f in universe]

        p = precision_score(gold_bin, pred_bin, zero_division=0)
        r = recall_score(gold_bin, pred_bin, zero_division=0)
        f1 = f1_score(gold_bin, pred_bin, zero_division=0)

        results.append({
            "question": it.question,
            "k": it.k,
            "threshold": it.threshold,
            "precision": p, "recall": r, "f1": f1,
            "retrieved": got_filenames,
            "gold": it.gold_filenames,
        })
        bin_gold_all.extend(gold_bin)
        bin_pred_all.extend(pred_bin)

    macro_p = precision_score(bin_gold_all, bin_pred_all, zero_division=0)
    macro_r = recall_score(bin_gold_all, bin_pred_all, zero_division=0)
    macro_f1 = f1_score(bin_gold_all, bin_pred_all, zero_division=0)

    summary = {"precision": macro_p, "recall": macro_r, "f1": macro_f1, "n": len(payload.items)}
    _log_event({"type": "eval_retrieval", "summary": summary, "results": results})
    return {"summary": summary, "results": results}
