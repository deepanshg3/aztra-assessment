"""Document indexing pipeline that embeds text documents into ChromaDB.

This module reads every ``.txt`` file from ``data/raw/docs/``, generates an
embedding for each document using Google's embedding model, and stores the
results in a persistent ChromaDB database at ``data/vector_db/``.

The indexing process is idempotent — running it multiple times does not
create duplicate vectors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import chromadb
from chromadb import PersistentClient
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection

from src.core.logger import get_logger
from src.rag.embedding_client import embed

logger = get_logger(__name__)

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_DOCS_DIR: Final[Path] = _PROJECT_ROOT / "data" / "raw" / "docs"
_VECTOR_DB_DIR: Final[Path] = _PROJECT_ROOT / "data" / "vector_db"
_COLLECTION_NAME: Final[str] = "documents"


def _ensure_vector_db_dir() -> Path:
    """Create the vector database directory if it does not exist."""
    _VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)
    return _VECTOR_DB_DIR


def _open_chroma_client() -> PersistentClient:
    """Open or create a persistent ChromaDB client.

    Returns:
        A :class:`chromadb.PersistentClient` instance.

    Raises:
        RuntimeError: If the database cannot be initialised.
    """
    db_dir = _ensure_vector_db_dir()
    try:
        client = chromadb.PersistentClient(path=str(db_dir))
        logger.debug("ChromaDB client opened", extra={"path": str(db_dir)})
        return client
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialise ChromaDB at {db_dir}: {exc}"
        ) from exc


def _get_or_create_collection(client: ClientAPI) -> Collection:
    """Get the existing document collection or create it.

    Args:
        client: An active ChromaDB client.

    Returns:
        The document :class:`Collection`.
    """
    try:
        collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.debug(
            "Collection ready",
            extra={"name": _COLLECTION_NAME, "count": collection.count()},
        )
        return collection
    except Exception as exc:
        raise RuntimeError(
            f"Failed to get or create collection '{_COLLECTION_NAME}': {exc}"
        ) from exc


def _discover_documents() -> list[Path]:
    """Return a sorted list of all ``.txt`` file paths in the docs directory.

    Returns:
        Sorted list of paths.

    Raises:
        FileNotFoundError: If the docs directory does not exist or
            contains no ``.txt`` files.
    """
    if not _DOCS_DIR.is_dir():
        raise FileNotFoundError(
            f"Documents directory not found: {_DOCS_DIR}"
        )
    files = sorted(_DOCS_DIR.glob("*.txt"))
    if not files:
        raise FileNotFoundError(
            f"No .txt files found in {_DOCS_DIR}"
        )
    return files


def _load_document(path: Path) -> str:
    """Read and return the full text content of a document.

    Args:
        path: The document file path.

    Returns:
        The document text.

    Raises:
        IOError: If the file cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise IOError(
            f"Failed to read document {path}: {exc}"
        ) from exc


def _already_indexed(
    collection: Collection,
    doc_id: str,
) -> bool:
    """Check whether a document already exists in the collection."""
    try:
        result = collection.get(ids=[doc_id])
        existing = result.get("ids") if result else []
        return len(existing) > 0

    except Exception as exc:
        logger.error(
            "Failed to check existing document",
            extra={
                "doc_id": doc_id,
                "error": str(exc),
            },
        )
        raise


def _index_single(
    collection: Collection,
    path: Path,
    doc_id: str,
) -> None:
    """Embed a single document and store it in ChromaDB.

    Args:
        collection: The ChromaDB collection.
        path: The document file path (used for error reporting).
        doc_id: The document identifier.
    """
    text = _load_document(path)
    logger.info("Indexing document", extra={"doc_id": doc_id})
    vector = embed(text)
    collection.add(
        ids=[doc_id],
        embeddings=[vector],
        documents=[text],
        metadatas=[
            {
                "filename": path.name,
            }
        ],
    )
    logger.info("Indexed document", extra={"doc_id": doc_id})


def run() -> int:
    """Execute the full document indexing pipeline.

    Discovers ``.txt`` files in the docs directory, generates embeddings
    for new documents, and persists them to ChromaDB. Already-indexed
    documents are skipped.

    Returns:
        The number of newly indexed documents.

    Raises:
        FileNotFoundError: If the docs directory is missing or empty.
        RuntimeError: If ChromaDB cannot be initialised.
    """
    logger.info("Document indexing started")

    documents = _discover_documents()
    logger.info(
        "Documents discovered",
        extra={"count": len(documents)},
    )

    client = _open_chroma_client()
    collection = _get_or_create_collection(client)

    indexed_count = 0

    for doc_path in documents:
        doc_id = doc_path.name

        if _already_indexed(collection, doc_id):
            logger.debug("Skipping already-indexed document", extra={"doc_id": doc_id})
            continue

        try:
            _index_single(collection, doc_path, doc_id)
            indexed_count += 1
        except Exception as exc:
            logger.exception(
                "Failed to index document",
                extra={
                    "doc_id": doc_id,
                },
            )

    logger.info(
        "Document indexing completed",
        extra={
            "indexed": indexed_count,
            "skipped": len(documents) - indexed_count,
            "total_in_db": collection.count(),
        },
    )

    return indexed_count
    
def main() -> None:
    """Run the document indexing pipeline."""
    run()


if __name__ == "__main__":
    main()
