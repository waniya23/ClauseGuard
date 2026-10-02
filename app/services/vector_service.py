# app/services/vector_service.py
"""
Vector Database and Embedding Service for ClauseGuard.

Production Responsibilities:
1. Text Chunking: Break down large legal documents into semantic chunks with overlap.
2. Embedding Generation: Compute local, lightweight vector embeddings via FastEmbed (ONNX).
3. Vector Storage: Persist vector indexes locally in Qdrant with doc_id tenant isolation.
4. Semantic Retrieval: Retrieve the most relevant clauses for a user's question with strict doc_id filtering.
"""

import os
import uuid
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from fastembed import TextEmbedding

from app.config import settings


# Vector dimensions for BAAI/bge-small-en-v1.5
EMBEDDING_DIM = 384
DEFAULT_MODEL_NAME = "BAAI/bge-small-en-v1.5"

# Persistent storage directory for Qdrant local files
QDRANT_STORAGE_PATH = os.path.join(os.getcwd(), "qdrant_data")


class VectorService:
    """Manages Qdrant local vector store and FastEmbed embeddings."""

    def __init__(self, storage_path: str = QDRANT_STORAGE_PATH, collection_name: str = settings.VECTOR_COLLECTION_NAME):
        self.collection_name = collection_name
        self.storage_path = storage_path
        
        # Initialize local persistent Qdrant client
        os.makedirs(self.storage_path, exist_ok=True)
        self.client = QdrantClient(path=self.storage_path)

        # Initialize FastEmbed embedding model (quantized ONNX, runs locally on CPU)
        self.embed_model = TextEmbedding(model_name=DEFAULT_MODEL_NAME)

        # Ensure collection exists
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Creates the Qdrant collection if it does not already exist."""
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
            )

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 80) -> list[str]:
        """
        Splits text into overlapping character windows, snapping to whitespace or paragraph breaks.

        Why Overlap?
        Legal clauses often span across sentence boundaries. Overlap ensures that a clause
        falling on the edge of a chunk is not split and retains its complete meaning.
        """
        if not text:
            return []

        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            if end >= text_len:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Try to break cleanly at paragraph or newline, then space
            break_point = text.rfind("\n\n", start, end)
            if break_point == -1 or break_point <= start:
                break_point = text.rfind("\n", start, end)
            if break_point == -1 or break_point <= start:
                break_point = text.rfind(" ", start, end)
            if break_point == -1 or break_point <= start:
                break_point = end

            chunk = text[start:break_point].strip()
            if chunk:
                chunks.append(chunk)

            # Advance start pointer with overlap
            start = max(start + 1, break_point - chunk_overlap)

        return chunks

    def index_document_pages(self, doc_id: str, pages_data: list[dict]) -> int:
        """
        Chunks and vectorizes document pages, preserving page citations for RAG.

        Args:
            doc_id: Unique document identifier.
            pages_data: List of page dictionaries [{"page_number": int, "text": str}].

        Returns:
            int: Total number of chunks indexed into Qdrant.
        """
        all_chunks: list[dict] = []
        chunk_texts_for_embedding: list[str] = []

        chunk_counter = 0
        for page in pages_data:
            page_num = page.get("page_number", 1)
            raw_text = page.get("text", "")
            if not raw_text.strip():
                continue

            page_chunks = self.chunk_text(raw_text, chunk_size=600, chunk_overlap=80)
            for ch in page_chunks:
                all_chunks.append({
                    "chunk_id": str(uuid.uuid4()),
                    "doc_id": doc_id,
                    "page_number": page_num,
                    "chunk_index": chunk_counter,
                    "text": ch
                })
                chunk_texts_for_embedding.append(ch)
                chunk_counter += 1

        if not chunk_texts_for_embedding:
            return 0

        # Generate embeddings in batch
        embeddings = list(self.embed_model.embed(chunk_texts_for_embedding))

        # Build Qdrant PointStructs
        points: list[PointStruct] = []
        for meta, vector in zip(all_chunks, embeddings):
            points.append(
                PointStruct(
                    id=meta["chunk_id"],
                    vector=vector.tolist(),
                    payload={
                        "doc_id": meta["doc_id"],
                        "page_number": meta["page_number"],
                        "chunk_index": meta["chunk_index"],
                        "text": meta["text"]
                    }
                )
            )

        # Upsert into Qdrant
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )

        return len(points)

    def search_relevant_chunks(self, doc_id: str, query: str, top_k: int = 4) -> list[dict]:
        """
        Retrieves the top_k most semantically relevant text chunks for a query,
        strictly filtered by doc_id (preventing cross-document data leakage).

        Args:
            doc_id: Document ID to restrict search.
            query: User's follow-up question.
            top_k: Number of relevant chunks to retrieve.

        Returns:
            list[dict]: [{"text": str, "page_number": int, "score": float}]
        """
        # Embed the query
        query_vectors = list(self.embed_model.embed([query]))
        if not query_vectors:
            return []
        query_vector = query_vectors[0].tolist()

        # Strict tenant isolation filter: match doc_id
        doc_filter = Filter(
            must=[
                FieldCondition(
                    key="doc_id",
                    match=MatchValue(value=doc_id)
                )
            ]
        )

        # Query points from Qdrant
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=doc_filter,
            limit=top_k
        ).points

        relevant_chunks: list[dict] = []
        for hit in search_results:
            payload = hit.payload or {}
            relevant_chunks.append({
                "text": payload.get("text", ""),
                "page_number": payload.get("page_number", 1),
                "chunk_index": payload.get("chunk_index", 0),
                "score": float(hit.score) if hit.score is not None else 0.0
            })

        return relevant_chunks


# Global singleton instance for use across FastAPI routes and agents
vector_service = VectorService()
