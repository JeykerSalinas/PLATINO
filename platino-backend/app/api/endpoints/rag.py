from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List
from io import BytesIO
from pathlib import Path
import fitz  # PyMuPDF
from llama_index.readers.file import PyMuPDFReader, PDFReader
from llama_index.core.node_parser import SimpleNodeParser
import tempfile

from ...db.session import get_db
from ...db.models import Document

router = APIRouter()

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a file, store it and generate chunks."""
    try:
        content = await file.read()

        path = UPLOAD_DIR / file.filename
        with open(path, "wb") as f:
            f.write(content)

        thumb_path = None
        chunks: List[str] = []
        if file.filename.lower().endswith(".pdf"):
            # generate thumbnail
            doc_pdf = fitz.open(path)
            page = doc_pdf.load_page(0)
            pix = page.get_pixmap()
            thumb_path = str(UPLOAD_DIR / f"{file.filename}.png")
            pix.save(thumb_path)
            doc_pdf.close()

            pdf_reader = PDFReader()
            documents = pdf_reader.load_data(BytesIO(content))
            parser = SimpleNodeParser.from_defaults()
            nodes = parser.get_nodes_from_documents(documents)
            chunks = [node.text for node in nodes]

        doc_db = Document(
            filename=file.filename,
            filepath=str(path),
            thumbnail=thumb_path,
        )
        db.add(doc_db)
        db.commit()
        db.refresh(doc_db)

        return {
            "id": doc_db.id,
            "filename": doc_db.filename,
            "thumbnail": doc_db.thumbnail,
            "chunks": chunks,
        }
    except Exception as e:
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
        }
        for doc in docs
    ]
    return {"files": files}


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