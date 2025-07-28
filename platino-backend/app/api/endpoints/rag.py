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
from qdrant_client.models import VectorParams, Distance
import tempfile
import traceback
from ...db.session import get_db
from ...db.models import Document, Topic
from ...core.config import settings
from llama_index.core.settings import Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

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

        if topic_id is not None:
            topic = db.query(Topic).get(topic_id)
            if not topic:
                raise HTTPException(status_code=404, detail="Topic not found")

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