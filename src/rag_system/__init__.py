#!/usr/bin/env python3
"""
RAG System for MAESTRO Engine

Provides retrieval-augmented generation capabilities for personas:
- Vector storage and retrieval via ChromaDB
- Pattern recommendations from historical projects
- Template and collateral extraction
"""

from .collateral_extractor import CollateralExtractor
from .pattern_recommender import PatternRecommender
from .vector_rag_manager import VectorRAGManager, get_rag_manager

__all__ = ["VectorRAGManager", "get_rag_manager", "PatternRecommender", "CollateralExtractor"]
