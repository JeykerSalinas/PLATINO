from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
import os
from sqlalchemy.orm import Session
from typing import List
from io import BytesIO
from pathlib import Path
import fitz  # PyMuPDF
from llama_index.readers.file import PyMuPDFReader, PDFReader
from llama_index.core.node_parser import SimpleNodeParser
import tempfile
import traceback
from ...db.session import get_db
from ...db.models import Document, Topic

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    topic_id: int | None = None,
):
    """Upload a file, store it and generate chunks."""
    try:
        content = await file.read()

        path = UPLOAD_DIR / file.filename
        with open(path, "wb") as f:
            f.write(content)

        thumb_path = None
        chunks: List[str] = []
        metadata = {"filename": file.filename, "source": str(path)}

        if file.filename.lower().endswith(".pdf"):
            # generate thumbnail
            doc_pdf = fitz.open(path)
            metadata["pages"] = doc_pdf.page_count
            page = doc_pdf.load_page(0)
            pix = page.get_pixmap()
            thumb_path = f"uploads/{file.filename}.png"  # ✅ guarda esto en la base de datos
            pix.save(UPLOAD_DIR / f"{file.filename}.png")  # ✅ guarda en disco con Path    
            doc_pdf.close()

            pdf_reader = PDFReader()
            documents = pdf_reader.load_data(str(path))  # ✅ aquí el cambio
            parser = SimpleNodeParser.from_defaults()
            nodes = parser.get_nodes_from_documents(documents)
            chunks = [node.text for node in nodes]

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
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if os.path.exists(doc.filepath):
        os.remove(doc.filepath)
    if doc.thumbnail and os.path.exists(doc.thumbnail):
        os.remove(doc.thumbnail)

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
