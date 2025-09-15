# app/metrics_router.py
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, Response, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Iterator, List, Literal
from pathlib import Path
import json, csv, io

# Ruta del archivo (ajústala si lo mueves)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

METRICS_PATH = Path("D:/UDIT/PLATINO/platino-backend/metrics_platino.jsonl")


router = APIRouter()

class Metric(BaseModel):
    type: Literal["retrieval","generation","other","eval","system"] = "other"
    question: str
    collection: Optional[str] = None
    used_rag: Optional[bool] = None
    similarity_top_k: Optional[int] = None
    similarity_threshold: Optional[float] = None
    retrieval_latency_s: Optional[float] = None
    gen_latency_s: Optional[float] = None
    # Campo libre para claves adicionales sin romper el modelo
    # (permite extender el JSON sin tocar el backend)
    # mypy: ignore-next-line
    # noqa: E701
    def __init__(self, **data):
        super().__init__(**{k: v for k, v in data.items() if k in self.model_fields})
        for k, v in data.items():
            if k not in self.model_fields:
                setattr(self, k, v)

def _iter_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {path}")
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def _filter_item(
    it: dict,
    q: Optional[str],
    type_: Optional[str],
    collection: Optional[str],
    used_rag: Optional[bool],
) -> bool:
    if q and q.lower() not in (it.get("question","")).lower():
        return False
    if type_ and it.get("type") != type_:
        return False
    if collection and it.get("collection") != collection:
        return False
    if used_rag is not None and it.get("used_rag") is not used_rag:
        return False
    return True

@router.get("", response_model=dict)
def list_metrics(
    q: Optional[str] = Query(None, description="Buscar en 'question'"),
    type: Optional[str] = Query(None, pattern="^(retrieval|generation|other|eval|system)$"),
    collection: Optional[str] = None,
    used_rag: Optional[bool] = None,
    sort_by: Optional[str] = Query(None, description="Campo numérico para ordenar, p.ej. gen_latency_s"),
    sort_dir: Literal["asc","desc"] = "desc",
    offset: int = 0,
    limit: int = 50,
):
    print(METRICS_PATH)
    """
    Devuelve una página de métricas con filtros opcionales.
    """
    items: List[dict] = [it for it in _iter_jsonl(METRICS_PATH) if _filter_item(it, q, type, collection, used_rag)]
    total = len(items)

    if sort_by:
        def keyfunc(x):
            v = x.get(sort_by)
            try:
                return float(v) if v is not None else float("-inf")
            except (TypeError, ValueError):
                return float("-inf")
        items.sort(key=keyfunc, reverse=(sort_dir == "desc"))

    page = items[offset: offset + limit]
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": page,
    }

@router.get("/stream", response_class=PlainTextResponse)
def stream_metrics_ndjson(
    q: Optional[str] = None,
    type: Optional[str] = Query(None, pattern="^(retrieval|generation|other|eval|system)$"),
    collection: Optional[str] = None,
    used_rag: Optional[bool] = None,
):
    """
    Devuelve NDJSON (una línea JSON por item) para consumo eficiente por el front.
    """
    def gen():
        for it in _iter_jsonl(METRICS_PATH):
            if _filter_item(it, q, type, collection, used_rag):
                yield json.dumps(it, ensure_ascii=False) + "\n"
    return StreamingResponse(gen(), media_type="application/x-ndjson")

@router.get("/export.csv")
def export_csv(
    q: Optional[str] = None,
    type: Optional[str] = Query(None, pattern="^(retrieval|generation|other|eval|system)$"),
    collection: Optional[str] = None,
    used_rag: Optional[bool] = None,
):
    """
    Exporta las métricas filtradas a CSV (cabeceras dinámicas).
    """
    rows = [it for it in _iter_jsonl(METRICS_PATH) if _filter_item(it, q, type, collection, used_rag)]
    if not rows:
        return Response(content="", media_type="text/csv")
    # Unificar cabeceras
    headers = sorted({k for r in rows for k in r.keys()})
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="metrics_platino.csv"'},
    )
