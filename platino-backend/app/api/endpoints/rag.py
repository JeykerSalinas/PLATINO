from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List

from ...db.session import get_db
from ...db.models import Document

router = APIRouter()

# In memory storage of uploaded files (name only)
FILES: List[str] = []

@router.post("/files")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a file to be used for retrieval."""
    try:
        content = await file.read()
        # placeholder: store content in real vector store
        FILES.append(file.filename)
        doc = Document(filename=file.filename)
        db.add(doc)
        db.commit()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"filename": file.filename}

@router.get("/files")
async def list_files(db: Session = Depends(get_db)):
    """List uploaded files."""
    docs = db.query(Document).all()
    filenames = [doc.filename for doc in docs]
    return {"files": filenames}
