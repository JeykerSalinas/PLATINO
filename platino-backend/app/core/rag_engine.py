from pathlib import Path
from llama_index.core import (
    VectorStoreIndex,
    StorageContext,
    ServiceContext,
    load_index_from_storage,
)
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

# Directory to persist the Chroma database
PERSIST_DIR = Path("chroma_db")
COLLECTION_NAME = "documents"

# Initialize embed model and LLM for the service context
_embed_model = OllamaEmbedding(model_name="nomic-embed-text")
_llm = Ollama(model="llama3")
_service_context = ServiceContext.from_defaults(llm=_llm, embed_model=_embed_model)

_vector_store = ChromaVectorStore(
    persist_dir=str(PERSIST_DIR), collection_name=COLLECTION_NAME
)
_storage_context = StorageContext.from_defaults(vector_store=_vector_store)

# Load an existing index if present, otherwise create a new one
if PERSIST_DIR.exists():
    _index = load_index_from_storage(_storage_context, service_context=_service_context)
else:
    _index = VectorStoreIndex(
        [], service_context=_service_context, storage_context=_storage_context
    )
    _index.storage_context.persist()


def insert_nodes(nodes):
    """Insert nodes into the index and persist the vector store."""
    _index.insert_nodes(nodes)
    _index.storage_context.persist()


def query(text: str):
    """Query the index and return the LLM response."""
    query_engine = _index.as_query_engine()
    return query_engine.query(text)
