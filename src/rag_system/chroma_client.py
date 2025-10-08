#!/usr/bin/env python3
"""
ChromaDB Client Configuration for RAG System
"""

import logging
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None
    Settings = None

logger = logging.getLogger(__name__)

# Global client instance
_chroma_client: Optional["chromadb.Client"] = None


def get_chroma_client(persist_directory: Optional[str] = None) -> Optional["chromadb.Client"]:
    """
    Get or create ChromaDB client

    Args:
        persist_directory: Optional persistent storage directory

    Returns:
        ChromaDB client or None if not available
    """
    global _chroma_client

    if not CHROMADB_AVAILABLE:
        logger.warning("ChromaDB is not installed. Install with: pip install chromadb")
        return None

    if _chroma_client is not None:
        return _chroma_client

    # Determine persist directory
    if persist_directory is None:
        persist_directory = "/tmp/maestro_rag_db"

    persist_path = Path(persist_directory)
    persist_path.mkdir(parents=True, exist_ok=True)

    try:
        # Create ChromaDB client with persistent storage
        _chroma_client = chromadb.Client(
            Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(persist_path),
                anonymized_telemetry=False,
            )
        )

        logger.info(f"✅ ChromaDB client initialized: {persist_path}")
        return _chroma_client

    except Exception as e:
        logger.error(f"❌ Failed to initialize ChromaDB: {e}")
        return None


def create_collections(client: "chromadb.Client"):
    """
    Create RAG collections if they don't exist

    Collections:
    - executions: Historical workflow executions
    - collaterals: Code files, docs, configs
    - patterns: Successful patterns and templates
    """
    if client is None:
        return

    try:
        # Execution collection
        try:
            client.get_collection("executions")
            logger.info("Collection 'executions' already exists")
        except:
            client.create_collection(
                name="executions", metadata={"description": "Historical workflow executions"}
            )
            logger.info("✅ Created collection: executions")

        # Collaterals collection
        try:
            client.get_collection("collaterals")
            logger.info("Collection 'collaterals' already exists")
        except:
            client.create_collection(
                name="collaterals", metadata={"description": "Code files, docs, configs"}
            )
            logger.info("✅ Created collection: collaterals")

        # Patterns collection
        try:
            client.get_collection("patterns")
            logger.info("Collection 'patterns' already exists")
        except:
            client.create_collection(
                name="patterns", metadata={"description": "Successful patterns and templates"}
            )
            logger.info("✅ Created collection: patterns")

    except Exception as e:
        logger.error(f"❌ Failed to create collections: {e}")


def initialize_rag_system(persist_directory: Optional[str] = None) -> bool:
    """
    Initialize RAG system with ChromaDB

    Args:
        persist_directory: Optional persistent storage directory

    Returns:
        True if successful, False otherwise
    """
    if not CHROMADB_AVAILABLE:
        logger.warning("ChromaDB not available - RAG features will be disabled")
        return False

    try:
        client = get_chroma_client(persist_directory)
        if client is None:
            return False

        create_collections(client)
        logger.info("✅ RAG system initialized successfully")
        return True

    except Exception as e:
        logger.error(f"❌ RAG system initialization failed: {e}")
        return False
