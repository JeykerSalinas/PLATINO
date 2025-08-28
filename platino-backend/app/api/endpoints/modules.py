from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...db.models import Module, Topic
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
from ...core.config import settings as app_settings
from llama_index.vector_stores.qdrant import QdrantVectorStore
import os
router = APIRouter()
QDRANT_URL = app_settings.qdrant_url
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents_384")
@router.post("/modules")
def create_module(title: str, db: Session = Depends(get_db)):
    module = Module(title=title)
    db.add(module)
    db.commit()
    db.refresh(module)
    return {"id": module.id, "title": module.title}

@router.get("/modules")
def list_modules(db: Session = Depends(get_db)):
    modules = db.query(Module).all()
    return {"modules": [{"id": m.id, "title": m.title} for m in modules]}

@router.put("/modules/{module_id}")
def update_module(module_id: int, title: str, db: Session = Depends(get_db)):
    module = db.query(Module).get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    module.title = title
    db.commit()
    db.refresh(module)
    return {"id": module.id, "title": module.title}

@router.delete("/modules/{module_id}")
def delete_module(module_id: int, db: Session = Depends(get_db)):
    module = db.query(Module).get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    # 1) Borrado en Qdrant por metadato module_id
    try:
        client = QdrantClient(url=QDRANT_URL)
        # si no existe la colección, esto fallará suave
        q_filter = Filter(must=[
            FieldCondition(key="module_id", match=MatchValue(value=module_id))
        ])
        try:
            client.delete(collection_name=QDRANT_COLLECTION, filter=q_filter)  # clientes recientes
        except TypeError:
            client.delete(collection_name=QDRANT_COLLECTION, points_selector=q_filter)  # compat
    except Exception as e:
        # No impide continuar con SQL; registra el error si quieres
        print(f"[WARN] Fallo borrando en Qdrant módulo {module_id}: {e}")

    # 2) Borrado en SQL
    db.delete(module)
    db.commit()
    return {"status": "deleted"}

@router.post("/modules/{module_id}/topics")
def create_topic(module_id: int, title: str, db: Session = Depends(get_db)):
    module = db.query(Module).get(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")
    topic = Topic(title=title, module_id=module_id)
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "title": topic.title, "module_id": module_id}

@router.get("/modules/{module_id}/topics")
def list_topics(module_id: int, db: Session = Depends(get_db)):
    topics = db.query(Topic).filter_by(module_id=module_id).all()
    return {
        "topics": [
            {"id": t.id, "title": t.title, "module_id": t.module_id} for t in topics
        ]
    }

@router.put("/topics/{topic_id}")
def update_topic(topic_id: int, title: str, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    topic.title = title
    db.commit()
    db.refresh(topic)
    return {"id": topic.id, "title": topic.title, "module_id": topic.module_id}


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: int, db: Session = Depends(get_db)):
    topic = db.query(Topic).get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Topic not found")
    # 1) Borrado en Qdrant por metadato topic_id
    try:
        client = QdrantClient(url=QDRANT_URL)
        # si no existe la colección, esto fallará suave
        q_filter = Filter(must=[
            FieldCondition(key="topic_id", match=MatchValue(value=topic_id))
        ])
        try:
            client.delete(collection_name=QDRANT_COLLECTION, filter=q_filter)  # clientes recientes
        except TypeError:
            client.delete(collection_name=QDRANT_COLLECTION, points_selector=q_filter)  # compat
    except Exception as e:
        # No impide continuar con SQL; registra el error si quieres
        print(f"[WARN] Fallo borrando en Qdrant módulo {topic_id}: {e}")

    db.delete(topic)
    db.commit()
    return {"status": "deleted"}
