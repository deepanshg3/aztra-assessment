"""Semantic document retriever using ChromaDB vector search.

Generates an embedding for a user question and retrieves the top-3 most
semantically similar documents from the persistent ChromaDB database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import chromadb

from src.core.logger import get_logger
from src.rag.embedding_client import embed

logger = get_logger(__name__)

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_VECTOR_DB_DIR: Final[Path] = _PROJECT_ROOT / "data" / "vector_db"
_COLLECTION_NAME: Final[str] = "documents"
_TOP_K: Final[int] = 3


def _open_chroma_client() -> chromadb.PersistentClient:
    """Open the persistent ChromaDB database.

    Returns:
        A :class:`chromadb.PersistentClient` instance.

    Raises:
        RuntimeError: If the vector database directory does not exist.
    """
    if not _VECTOR_DB_DIR.is_dir():
        raise RuntimeError(
            f"Vector database directory not found: {_VECTOR_DB_DIR}. "
            "Run the indexing pipeline first."
        )
    try:
        client = chromadb.PersistentClient(path=str(_VECTOR_DB_DIR))
        logger.debug("ChromaDB client opened", extra={"path": str(_VECTOR_DB_DIR)})
        return client
    except Exception as exc:
        raise RuntimeError(
            f"Failed to open ChromaDB at {_VECTOR_DB_DIR}: {exc}"
        ) from exc


def _get_collection(client: chromadb.ClientAPI) -> chromadb.Collection:
    """Get the existing document collection.

    Args:
        client: An active ChromaDB client.

    Returns:
        The document :class:`Collection`.

    Raises:
        RuntimeError: If the collection does not exist.
    """
    try:
        collection = client.get_collection(name=_COLLECTION_NAME)
        logger.debug(
            "Collection loaded",
            extra={"name": _COLLECTION_NAME, "count": collection.count()},
        )
        return collection
    except ValueError as exc:
        raise RuntimeError(
            f"Collection '{_COLLECTION_NAME}' not found in the vector database. "
            "Run the indexing pipeline first."
        ) from exc


def _format_results(
    ids: list[str],
    distances: list[float],
    metadatas: list[dict[str, Any]],
    documents: list[str],
) -> list[dict[str, object]]:
    """Format ChromaDB query results into the standard output structure.

    Args:
        ids: Document IDs from ChromaDB.
        distances: Cosine distances from ChromaDB.
        metadatas: Metadata dicts (must contain ``filename``).
        documents: Full document text.

    Returns:
        A list of dicts with keys ``filename``, ``content``, ``distance``.
    """
    results: list[dict[str, object]] = []
    for doc_id, dist, meta, text in zip(ids, distances, metadatas, documents):
        filename = meta.get("filename", doc_id)
        results.append(
            {
                "filename": filename,
                "content": text,
                "distance": dist,
            }
        )
    return results


def retrieve(question: str) -> list[dict[str, object]]:
    """Retrieve the top-3 most semantically similar documents for a question.

    Args:
        question: The user's natural-language search query.

    Returns:
        A list of up to 3 dicts, each containing ``filename``, ``content``,
        and ``distance``. Returns an empty list if no documents are found.

    Raises:
        RuntimeError: If the vector database or collection does not exist.
    """
    logger.info("Semantic retrieval started", extra={"question": question})

    embedded_query = embed(question)
    client = _open_chroma_client()
    collection = _get_collection(client)

    results = collection.query(
        query_embeddings=[embedded_query],
        n_results=_TOP_K,
        include=["documents", "metadatas", "distances"],
    )

    raw_ids: list[str] = results.get("ids", [[]])[0]
    raw_distances: list[float] = results.get("distances", [[]])[0]
    raw_metadatas: list[dict[str, Any]] = results.get("metadatas", [[]])[0]
    raw_documents: list[str] = results.get("documents", [[]])[0]

    if not raw_ids:
        logger.info("No matching documents found")
        return []

    formatted = _format_results(raw_ids, raw_distances, raw_metadatas, raw_documents)

    logger.info(
        "Semantic retrieval completed",
        extra={"results_count": len(formatted)},
    )
    return formatted


def main() -> None:
    """Manual test: retrieve top-3 documents for the sample question."""
    question = "Why are GlucoJoy sales decreasing in Delhi?"
    results = retrieve(question)

    if not results:
        print("No results found.")
        return

    for i, doc in enumerate(results, start=1):
        print(f"{'='*60}")
        print(f"Result {i}")
        print(f"{'='*60}")
        print(f"Filename:   {doc['filename']}")
        print(f"Distance:   {doc['distance']:.6f}")
        print(f"Content:\n{doc['content']}\n")


if __name__ == "__main__":
    main()