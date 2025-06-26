import json
from pathlib import Path

CHUNKS_DB_PATH = Path(__file__).with_name("chunks_db.json")

def load_chunks() -> dict:
    if CHUNKS_DB_PATH.exists():
        with open(CHUNKS_DB_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def save_chunks(data: dict) -> None:
    with open(CHUNKS_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_chunks(filename: str, chunks: list[str]) -> None:
    data = load_chunks()
    data[filename] = chunks
    save_chunks(data)
