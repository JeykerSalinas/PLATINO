from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import os
from sqlalchemy.orm import Session
from typing import List
from io import BytesIO
from pathlib import Path
import fitz  # PyMuPDF
from llama_index.readers.file import PyMuPDFReader, PDFReader
from llama_index.core.node_parser import SimpleNodeParser
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, Filter, FieldCondition, MatchValue
import tempfile
import traceback
from ...db.session import get_db
from ...db.models import Document, Topic, Module
from ...core.config import settings
from llama_index.core.settings import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
import requests

router = APIRouter()
Settings.embed_model = HuggingFaceEmbedding(
    model_name="BAAI/bge-large-en-v1.5"
)
EMBEDDING_DIM = 1024  # Para bge-large-en-v1.5
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    topic_id: int | None = None,
):
    try:
        content = await file.read()

        path = UPLOAD_DIR / file.filename
        with open(path, "wb") as f:
            f.write(content)

        thumb_path = None
        chunks: List[str] = []
        metadata = {"filename": file.filename, "source": str(path)}

        if file.filename.lower().endswith(".pdf"):
            doc_pdf = fitz.open(path)
            metadata["pages"] = doc_pdf.page_count
            page = doc_pdf.load_page(0)
            pix = page.get_pixmap()
            thumb_path = f"uploads/{file.filename}.png"
            pix.save(UPLOAD_DIR / f"{file.filename}.png")
            doc_pdf.close()

            pdf_reader = PDFReader()
            documents = pdf_reader.load_data(str(path))
            parser = SimpleNodeParser.from_defaults()
            nodes = parser.get_nodes_from_documents(documents)
            chunks = [node.text for node in nodes]

        if topic_id is not None:
            topic = db.query(Topic).get(topic_id)
            if not topic:
                raise HTTPException(status_code=404, detail="Topic not found")
        else:
            topic = None

        doc_db = Document(
            filename=file.filename,
            filepath=str(path),
            thumbnail=thumb_path,
            file_metadata=metadata,
            chunks=chunks,
            topic_id=topic_id,
        )
        db.add(doc_db)
        db.commit()
        db.refresh(doc_db)

        topic_name = topic.title if topic else None
        module_name = topic.module.title if topic else None

        if file.filename.lower().endswith(".pdf"):
            for node in nodes:
                node.metadata = {
                    "document_id": doc_db.id,
                    "filename": doc_db.filename,
                    "topic": topic_name,
                    "module": module_name,
                }

            client = QdrantClient(url=settings.qdrant_url)
            collection_name = "documents"
            try:
                info = client.get_collection(collection_name)
                if info.config.params.vectors.size != EMBEDDING_DIM:
                    raise ValueError("Dim mismatch, recreating collection")
            except Exception:
                client.recreate_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
                )

            vector_store = QdrantVectorStore(client=client, collection_name=collection_name)
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            VectorStoreIndex(nodes, storage_context=storage_context)

        return {
            "id": doc_db.id,
            "filename": doc_db.filename,
            "thumbnail": doc_db.thumbnail,
            "chunks": chunks,
            "metadata": metadata,
            "topic_id": doc_db.topic_id,
        }

    except Exception as e:
        print("❌ Error en /files:", e)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))    
    
    
@router.get("/files")
async def list_files(db: Session = Depends(get_db)):
    """List uploaded files."""
    docs = db.query(Document).all()
    files = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "thumbnail": doc.thumbnail,
            "topic_id": doc.topic_id,
        }
        for doc in docs
    ]
    return {"files": files}


@router.get("/files/{doc_id}")
async def get_file(doc_id: int, db: Session = Depends(get_db)):
    """Return detailed information for a single document."""
    doc = db.query(Document).get(doc_id)
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
    """Delete a document and its files."""
    doc = db.query(Document).get(doc_id)
    print(doc)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.filepath):
        os.remove(doc.filepath)
    if doc.thumbnail and os.path.exists(doc.thumbnail):
        os.remove(doc.thumbnail)

    try:
        client = QdrantClient(url=settings.qdrant_url)
        qdrant_filter = Filter(
            must=[FieldCondition(key="filename", match=MatchValue(value=doc.filename))]
        )
        client.delete(collection_name="documents", points_selector=qdrant_filter)
        print('*********************')
       
        print('FILE DELETED|')
    except Exception as e:
        print("❌ Error deleting vectors from Qdrant:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Failed to delete from Qdrant")

    db.delete(doc)
    db.commit()
    return {"status": "deleted"}


@router.put("/files/{doc_id}")
async def rename_file(doc_id: int, new_name: str, db: Session = Depends(get_db)):
    """Rename a stored document."""
    doc = db.query(Document).get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    new_path = UPLOAD_DIR / new_name
    if new_path.exists():
        raise HTTPException(status_code=400, detail="Filename already exists")

    os.rename(doc.filepath, new_path)
    doc.filepath = str(new_path)
    if doc.thumbnail:
        thumb_ext = Path(doc.thumbnail).suffix
        new_thumb = UPLOAD_DIR / f"{new_name}{thumb_ext}"
        os.rename(doc.thumbnail, new_thumb)
        doc.thumbnail = str(new_thumb)

    doc.filename = new_name
    meta = doc.file_metadata or {}
    meta["filename"] = new_name
    meta["source"] = str(new_path)
    doc.file_metadata = meta

    db.commit()
    db.refresh(doc)
    return {
        "id": doc.id,
        "filename": doc.filename,
        "thumbnail": doc.thumbnail,
        "topic_id": doc.topic_id,
    }


@router.put("/files/{doc_id}/topic")
async def set_file_topic(doc_id: int, topic_id: int | None, db: Session = Depends(get_db)):
    doc = db.query(Document).get(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if topic_id is not None:
        topic = db.query(Topic).get(topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Topic not found")

    doc.topic_id = topic_id
    db.commit()
    db.refresh(doc)
    return {"id": doc.id, "topic_id": doc.topic_id}


@router.post("/split_pdf")
async def split_pdf(file: UploadFile = File(...)):
    """Return PDF chunks using LlamaIndex."""
    try:
        contents = await file.read()
        pdf_reader = PDFReader()
        documents = pdf_reader.load_data(BytesIO(contents))
        parser = SimpleNodeParser.from_defaults()
        nodes = parser.get_nodes_from_documents(documents)
        chunks = [node.text for node in nodes]
        return {"chunks": chunks}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/files_2")
async def upload_and_split_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se permiten archivos PDF")

    try:
        content = await file.read()

        # Escribir contenido a archivo temporal
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        # Leer el PDF usando la ruta temporal
        reader = PyMuPDFReader()
        documents = reader.load_data(file_path=tmp_path)

        # Dividir en chunks
        parser = SimpleNodeParser()
        nodes = parser.get_nodes_from_documents(documents)
        chunks = [node.text for node in nodes]

        return {"filename": file.filename, "chunks": chunks}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
        raise HTTPException(status_code=400, detail=str(e))


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
        client = QdrantClient(url=settings.qdrant_url)
        vector_store = QdrantVectorStore(client=client, collection_name="documents")
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_vector_store(vector_store=vector_store, storage_context=storage_context)

        retriever = index.as_retriever(similarity_top_k=5)
        nodes = retriever.retrieve(question)

        context = "\n".join([n.get_content() for n in nodes])
        prompt = f"Contexto:\n{context}\n\nPregunta: {question}\nRespuesta:"

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": "llama3.1:8b", "prompt": prompt, "stream": False},
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
