"""ChromaDB Persistent Vector Store wrapper for JARVIS episodic and semantic memory."""
import datetime
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from config.settings import get_settings

logger = logging.getLogger(__name__)

COLLECTION_EPISODIC = "jarvis_episodic_memory"
COLLECTION_SEMANTIC = "jarvis_semantic_memory"


class ChromaMemoryManager:
    """Manages persistent vector memory collections for conversation turns,

    facts, user preferences, and technical project context.
    """

    def __init__(self, persist_dir: Optional[Path] = None):
        self.settings = get_settings()
        self.persist_dir = Path(persist_dir or self.settings.chroma_persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self._client: Optional[chromadb.ClientAPI] = None
        self._episodic_col = None
        self._semantic_col = None
        self._init_client()

    def _init_client(self) -> None:
        """Initialize ChromaDB PersistentClient and default collections."""
        try:
            self._client = chromadb.PersistentClient(
                path=str(self.persist_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._episodic_col = self._client.get_or_create_collection(
                name=COLLECTION_EPISODIC,
                metadata={"description": "Stores user interactions and conversation turns"},
            )
            self._semantic_col = self._client.get_or_create_collection(
                name=COLLECTION_SEMANTIC,
                metadata={"description": "Stores technical knowledge, facts, and code patterns"},
            )
            logger.info(f"ChromaDB initialized with persistence at: {self.persist_dir}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB PersistentClient: {e}")
            raise

    @property
    def client(self) -> chromadb.ClientAPI:
        """Access underlying ChromaDB client."""
        if self._client is None:
            self._init_client()
        return self._client

    def get_collection(self, name: str):
        """Get or create collection by name."""
        return self.client.get_or_create_collection(name=name)

    def _generate_id(self, text: str, prefix: str = "doc") -> str:
        """Generate deterministic or time-stamped hash ID."""
        ts = time.time_ns()
        content_hash = hashlib.sha256(f"{text}_{ts}".encode("utf-8")).hexdigest()[:12]
        return f"{prefix}_{content_hash}_{int(time.time())}"

    def upsert_document(
        self,
        collection_name: str,
        document: str,
        metadata: Optional[Dict[str, Any]] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """Upsert a single text document with metadata into the specified collection.

        Args:
            collection_name: Target collection name.
            document: Raw text content to embed.
            metadata: Key-value attributes for filtering.
            doc_id: Unique identifier. Auto-generated if not provided.

        Returns:
            The document ID.
        """
        col = self.get_collection(collection_name)
        final_id = doc_id or self._generate_id(document, prefix="mem")
        final_meta = metadata or {}
        final_meta["timestamp"] = final_meta.get("timestamp") or datetime.datetime.now().isoformat()

        # Chroma requires metadata values to be str, int, float, or bool
        sanitized_meta = {
            k: (v if isinstance(v, (str, int, float, bool)) else str(v))
            for k, v in final_meta.items()
        }

        col.upsert(
            ids=[final_id],
            documents=[document],
            metadatas=[sanitized_meta],
        )
        return final_id

    def query_similar(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 4,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Query vector collection for documents semantically similar to query_text."""
        col = self.get_collection(collection_name)
        total_count = col.count()
        if total_count == 0:
            return []

        limit = min(n_results, total_count)
        try:
            results = col.query(
                query_texts=[query_text],
                n_results=limit,
                where=where,
            )
            parsed: List[Dict[str, Any]] = []
            if results and results.get("documents") and results["documents"][0]:
                docs = results["documents"][0]
                metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                ids = results["ids"][0] if results.get("ids") else [""] * len(docs)
                distances = results["distances"][0] if results.get("distances") else [0.0] * len(docs)

                for doc, meta, d_id, dist in zip(docs, metas, ids, distances):
                    parsed.append({
                        "id": d_id,
                        "document": doc,
                        "metadata": meta,
                        "distance": dist,
                    })
            return parsed
        except Exception as e:
            logger.error(f"Error querying collection {collection_name}: {e}")
            return []

    def store_interaction(
        self,
        user_input: str,
        assistant_response: str,
        tools_used: Optional[List[str]] = None,
    ) -> str:
        """Store an episodic turn of user input and assistant response."""
        record_text = f"USER: {user_input}\nJARVIS: {assistant_response}"
        metadata = {
            "type": "conversation_turn",
            "tools_used": ",".join(tools_used or []),
            "timestamp": datetime.datetime.now().isoformat(),
        }
        return self.upsert_document(
            collection_name=COLLECTION_EPISODIC,
            document=record_text,
            metadata=metadata,
            doc_id=self._generate_id(user_input, prefix="chat"),
        )

    def store_fact(
        self,
        fact: str,
        category: str = "general",
        source: str = "user_instruction",
    ) -> str:
        """Store a semantic fact or preference permanently."""
        metadata = {
            "type": "fact",
            "category": category,
            "source": source,
            "timestamp": datetime.datetime.now().isoformat(),
        }
        return self.upsert_document(
            collection_name=COLLECTION_SEMANTIC,
            document=fact,
            metadata=metadata,
            doc_id=self._generate_id(fact, prefix="fact"),
        )

    def semantic_recall(self, query_text: str, n_results: int = 4) -> str:
        """Recall top relevant memories from both episodic and semantic collections

        formatted cleanly for prompt injection.
        """
        memories = []
        # Recall relevant facts
        facts = self.query_similar(COLLECTION_SEMANTIC, query_text, n_results=n_results)
        for f in facts:
            memories.append(f"• [FACT]: {f['document']}")

        # Recall relevant past interactions
        turns = self.query_similar(COLLECTION_EPISODIC, query_text, n_results=n_results)
        for t in turns:
            memories.append(f"• [PAST INTERACTION]:\n  {t['document']}")

        if not memories:
            return ""
        return "RECALLED MEMORIES & CONTEXT:\n" + "\n".join(memories)

    def get_recent_interactions(self, limit: int = 6) -> List[Dict[str, Any]]:
        """Retrieve most recent interaction turns for immediate conversational context."""
        col = self.get_collection(COLLECTION_EPISODIC)
        count = col.count()
        if count == 0:
            return []
        try:
            # Fetch all and sort by timestamp in metadata
            data = col.get(limit=min(count, 50), include=["documents", "metadatas"])
            items = []
            if data and data.get("documents"):
                for doc, meta in zip(data["documents"], data["metadatas"]):
                    items.append({
                        "document": doc,
                        "timestamp": meta.get("timestamp", ""),
                    })
            items.sort(key=lambda x: x["timestamp"], reverse=True)
            return items[:limit]
        except Exception as e:
            logger.error(f"Error fetching recent interactions: {e}")
            return []


_memory_manager_instance: Optional[ChromaMemoryManager] = None


def get_memory_manager() -> ChromaMemoryManager:
    """Get or create singleton ChromaMemoryManager instance."""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = ChromaMemoryManager()
    return _memory_manager_instance
