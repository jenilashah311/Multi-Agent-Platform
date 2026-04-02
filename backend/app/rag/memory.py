import logging
import os
import uuid

import chromadb
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

from app.config import settings

logger = logging.getLogger(__name__)


def _embeddings():
    if settings.demo_mode:
        return None
    if settings.llm_provider == "gemini":
        if not settings.google_api_key:
            return None
        os.environ.setdefault("GOOGLE_API_KEY", settings.google_api_key)
        return GoogleGenerativeAIEmbeddings(model=settings.gemini_embedding_model)
    if not settings.openai_api_key:
        return None
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key or "")
    return OpenAIEmbeddings(model="text-embedding-3-small")


def get_vectorstore(session_id: str):
    emb = _embeddings()
    if emb is None:
        return None
    client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)
    return Chroma(
        client=client,
        collection_name=f"s_{session_id.replace('-', '')[:48]}",
        embedding_function=emb,
    )


def ingest_text(session_id: str, text: str, source: str = "user") -> int:
    vs = get_vectorstore(session_id)
    if vs is None:
        return 0
    doc = Document(page_content=text, metadata={"source": source, "id": str(uuid.uuid4())})
    try:
        vs.add_documents([doc])
    except Exception as e:
        logger.warning("RAG ingest skipped (embeddings error): %s", e)
        return 0
    return 1


def retrieve_context(session_id: str, query: str, k: int = 4) -> str:
    vs = get_vectorstore(session_id)
    if vs is None:
        return ""
    try:
        docs = vs.similarity_search(query, k=k)
    except Exception as e:
        logger.warning("RAG retrieve skipped (embeddings error): %s", e)
        return ""
    return "\n\n".join(d.page_content for d in docs)
