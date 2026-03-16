"""
Vector store for semantic deduplication using ChromaDB.

Prevents publishing posts with similar meaning even if different words.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from loguru import logger

# ChromaDB imports with fallback handling
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB not available. Semantic deduplication will be disabled.")


@dataclass
class SimilarPost:
    """
    Represents a similar post found in the vector store.

    Attributes:
        post_id: Database ID of the similar post
        content: Post content text
        similarity: Similarity score (0.0 to 1.0, higher = more similar)
        metadata: Additional metadata about the post
    """
    post_id: int
    content: str
    similarity: float
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class VectorStore:
    """
    ChromaDB-based vector store for semantic deduplication.

    Stores post embeddings and finds semantically similar content
    to prevent publishing repetitive posts.

    Example:
        store = VectorStore()
        await store.add_post(1, "AI is transforming business...")

        # Check similarity before posting
        similar = await store.find_similar("AI changes how companies work...")
        if similar and similar[0].similarity > 0.85:
            print("Post too similar to existing content!")
    """

    def __init__(
        self,
        persist_directory: str = "./data/chroma",
        collection_name: str = "tg_posts",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        """
        Initialize vector store.

        Args:
            persist_directory: Directory to store ChromaDB data
            collection_name: Name of the collection to use
            embedding_model: Sentence transformer model for embeddings
        """
        self.persist_directory = Path(persist_directory)
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self._client: Optional[chromadb.Client] = None
        self._collection = None
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Initialize the vector store.

        Returns:
            bool: True if initialization successful
        """
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available, vector store disabled")
            return False

        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._init_sync)
            self._initialized = True
            logger.info(f"Vector store initialized: {self.collection_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            return False

    def _init_sync(self) -> None:
        """Synchronous initialization."""
        # Ensure directory exists
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with persistence
        self._client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True,
            )
        )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )

    async def add_post(
        self,
        post_id: int,
        content: str,
        metadata: Optional[dict] = None,
    ) -> Optional[str]:
        """
        Add a post to the vector store.

        Args:
            post_id: Database ID of the post
            content: Post content text
            metadata: Optional metadata to store

        Returns:
            Optional[str]: ChromaDB document ID, or None if failed
        """
        if not self._initialized or not self._collection:
            logger.warning("Vector store not initialized, skipping add")
            return None

        if not content or not content.strip():
            logger.warning("Empty content, skipping add")
            return None

        try:
            doc_id = f"post_{post_id}"

            # Prepare metadata
            meta = metadata or {}
            meta.update({
                "post_id": post_id,
                "added_at": datetime.now().isoformat(),
                "content_length": len(content),
            })

            # Run in thread pool
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._add_sync,
                doc_id,
                content,
                meta
            )

            logger.debug(f"Added post {post_id} to vector store")
            return doc_id

        except Exception as e:
            logger.error(f"Failed to add post to vector store: {e}")
            return None

    def _add_sync(self, doc_id: str, content: str, metadata: dict) -> None:
        """Synchronous add operation."""
        self._collection.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata],
        )

    async def find_similar(
        self,
        content: str,
        n_results: int = 5,
        where_filter: Optional[dict] = None,
    ) -> list[SimilarPost]:
        """
        Find semantically similar posts.

        Args:
            content: Content to compare against
            n_results: Maximum number of results
            where_filter: Optional metadata filter

        Returns:
            list[SimilarPost]: List of similar posts with similarity scores
        """
        if not self._initialized or not self._collection:
            return []

        if not content or not content.strip():
            return []

        try:
            # Run in thread pool
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                self._query_sync,
                content,
                n_results,
                where_filter
            )

            similar_posts = []

            if results and results.get("ids"):
                ids = results["ids"][0] if results["ids"] else []
                documents = results.get("documents", [[]])[0]
                distances = results.get("distances", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]

                for i, doc_id in enumerate(ids):
                    # Convert cosine distance to similarity (1 - distance)
                    distance = distances[i] if i < len(distances) else 1.0
                    similarity = 1.0 - distance

                    # Extract post_id from document ID
                    post_id = 0
                    if doc_id.startswith("post_"):
                        try:
                            post_id = int(doc_id.split("_")[1])
                        except (ValueError, IndexError):
                            pass

                    similar_posts.append(SimilarPost(
                        post_id=post_id,
                        content=documents[i] if i < len(documents) else "",
                        similarity=round(similarity, 4),
                        metadata=metadatas[i] if i < len(metadatas) else {},
                    ))

            return similar_posts

        except Exception as e:
            logger.error(f"Failed to find similar posts: {e}")
            return []

    def _query_sync(
        self,
        query_text: str,
        n_results: int,
        where_filter: Optional[dict]
    ) -> dict:
        """Synchronous query operation."""
        return self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where_filter,
            include=["documents", "distances", "metadatas"]
        )

    async def check_similarity(
        self,
        content: str,
        threshold: float = 0.85,
        n_results: int = 5,
    ) -> tuple[bool, Optional[SimilarPost]]:
        """
        Check if content is too similar to existing posts.

        Args:
            content: Content to check
            threshold: Similarity threshold (0.0 to 1.0)
            n_results: Number of similar posts to check

        Returns:
            tuple[bool, Optional[SimilarPost]]: (is_duplicate, most_similar_post)
        """
        similar_posts = await self.find_similar(content, n_results)

        if not similar_posts:
            return False, None

        # Find the most similar post above threshold
        for post in similar_posts:
            if post.similarity >= threshold:
                logger.warning(
                    f"Found similar post (similarity: {post.similarity:.2%}): "
                    f"Post ID {post.post_id}"
                )
                return True, post

        return False, similar_posts[0] if similar_posts else None

    async def delete_post(self, post_id: int) -> bool:
        """
        Delete a post from the vector store.

        Args:
            post_id: Database ID of the post to delete

        Returns:
            bool: True if deletion successful
        """
        if not self._initialized or not self._collection:
            return False

        try:
            doc_id = f"post_{post_id}"

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self._delete_sync,
                doc_id
            )

            logger.debug(f"Deleted post {post_id} from vector store")
            return True

        except Exception as e:
            logger.error(f"Failed to delete post from vector store: {e}")
            return False

    def _delete_sync(self, doc_id: str) -> None:
        """Synchronous delete operation."""
        self._collection.delete(ids=[doc_id])

    async def get_collection_size(self) -> int:
        """
        Get the number of documents in the collection.

        Returns:
            int: Number of stored posts
        """
        if not self._initialized or not self._collection:
            return 0

        try:
            return self._collection.count()
        except Exception as e:
            logger.warning("Failed to get collection count: %s", e)
            return 0

    async def clear_all(self) -> bool:
        """
        Clear all documents from the collection.

        Returns:
            bool: True if successful
        """
        if not self._initialized or not self._client:
            return False

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._clear_sync)
            logger.info("Vector store cleared")
            return True

        except Exception as e:
            logger.error(f"Failed to clear vector store: {e}")
            return False

    def _clear_sync(self) -> None:
        """Synchronous clear operation."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"}
        )


# Singleton instance
_vector_store: Optional[VectorStore] = None


async def get_vector_store() -> VectorStore:
    """
    Get the global vector store instance.

    Returns:
        VectorStore: Global vector store instance
    """
    global _vector_store

    if _vector_store is None:
        _vector_store = VectorStore()
        await _vector_store.initialize()

    return _vector_store


async def init_vector_store(
    persist_directory: str = "./data/chroma",
    collection_name: str = "tg_posts",
) -> VectorStore:
    """
    Initialize the global vector store.

    Args:
        persist_directory: Directory to store ChromaDB data
        collection_name: Name of the collection

    Returns:
        VectorStore: Initialized vector store
    """
    global _vector_store

    _vector_store = VectorStore(
        persist_directory=persist_directory,
        collection_name=collection_name,
    )
    await _vector_store.initialize()

    return _vector_store
