#!/usr/bin/env python3
"""
Learning Snapshot Service for MAESTRO Engine
Implements EPIC QF-400: Learning Snapshots with RAG Ingestion & Provenance

This service provides:
- Learning snapshot generation at execution completion (AC-1)
- Ingestion to Elasticsearch/vector store (AC-2)
- Vector embeddings for RAG retrieval (AC-3)
- Provenance links and citations (AC-4)
- RAG queries for relevant snapshots (AC-5)

Acceptance Criteria:
- AC-1: Snapshot generated at execution end
- AC-2: Ingested to ES with proper mapping
- AC-3: Vector embeddings created for retrieval
- AC-4: Provenance links valid and resolvable
- AC-5: RAG queries return relevant snapshots
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try to import ChromaDB for vector storage
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge

    SNAPSHOTS_CREATED = Counter(
        "maestro_learning_snapshots_total",
        "Total learning snapshots created",
        ["status"]
    )
    SNAPSHOT_LATENCY = Histogram(
        "maestro_snapshot_generation_latency_seconds",
        "Snapshot generation latency",
        buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    RAG_QUERIES = Counter(
        "maestro_rag_queries_total",
        "Total RAG queries",
        ["collection"]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self

    SNAPSHOTS_CREATED = StubMetric()
    SNAPSHOT_LATENCY = StubMetric()
    RAG_QUERIES = StubMetric()

logger = logging.getLogger("learning_snapshot_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class SnapshotStatus(str, Enum):
    """Status of a learning snapshot."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class ProvenanceType(str, Enum):
    """Types of provenance links."""
    SOURCE_REPO = "source_repo"
    COMMIT = "commit"
    GOLDEN_PROJECT = "golden_project"
    TEMPLATE = "template"
    ARTIFACT = "artifact"
    VALIDATION_REPORT = "validation_report"


# Default collection name for learning snapshots
LEARNING_COLLECTION_NAME = "qf_learnings"

# Environment config
CHROMA_PERSIST_DIR = os.environ.get(
    "CHROMA_PERSIST_DIR",
    str(Path(__file__).parent.parent.parent / "data" / "chroma")
)


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class PhaseResult:
    """Result from a phase execution."""
    id: str
    name: str
    score: float
    gates: Dict[str, str]  # e.g., {"DDE": "passed", "BRV": "passed"}
    artifacts: List[str]
    duration_ms: float = 0
    test_results: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "score": round(self.score, 3),
            "gates": self.gates,
            "artifacts": self.artifacts,
            "duration_ms": round(self.duration_ms, 2),
            "test_results": self.test_results,
        }


@dataclass
class Defect:
    """Defect found during execution."""
    id: str
    severity: str  # critical, high, medium, low
    phase: str
    description: str
    resolution: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity,
            "phase": self.phase,
            "description": self.description,
            "resolution": self.resolution,
        }


@dataclass
class Citation:
    """Citation/provenance link."""
    source: str  # e.g., "golden-projects/api-auth"
    ref: str     # e.g., "commit:abc123"
    type: ProvenanceType = ProvenanceType.SOURCE_REPO
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "ref": self.ref,
            "type": self.type.value,
            "description": self.description,
        }


@dataclass
class Provenance:
    """Full provenance information for a snapshot."""
    source_repo: Optional[str] = None
    commit: Optional[str] = None
    tool_chain: str = "maestro+quality-fabric"
    validation_report_id: Optional[str] = None
    created_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_repo": self.source_repo,
            "commit": self.commit,
            "tool_chain": self.tool_chain,
            "validation_report_id": self.validation_report_id,
            "created_by": self.created_by,
        }


@dataclass
class LearningSnapshot:
    """
    Learning snapshot generated at execution completion.

    Contains all relevant information about a workflow execution
    for RAG retrieval and learning purposes.
    """
    # Identifiers
    snapshot_id: str
    session_id: str
    execution_id: str
    workflow_id: Optional[str] = None

    # Execution summary
    requirement: str = ""
    requirement_summary: str = ""

    # Phase results
    phases: List[PhaseResult] = field(default_factory=list)

    # Overall scores
    overall_score: float = 0.0
    quality_score: float = 0.0
    coverage_score: float = 0.0

    # Templates and patterns
    templates_used: List[str] = field(default_factory=list)
    patterns_applied: List[str] = field(default_factory=list)

    # Defects and issues
    defects: List[Defect] = field(default_factory=list)

    # Citations and provenance
    citations: List[Citation] = field(default_factory=list)
    provenance: Optional[Provenance] = None

    # Metadata
    personas: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    environment: str = "development"

    # Timing
    execution_time_ms: float = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    indexed_at: Optional[str] = None

    # Status
    status: SnapshotStatus = SnapshotStatus.PENDING
    success: bool = True

    # Vector embedding (populated after indexing)
    embedding_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "execution_id": self.execution_id,
            "workflow_id": self.workflow_id,
            "requirement": self.requirement,
            "requirement_summary": self.requirement_summary,
            "phases": [p.to_dict() for p in self.phases],
            "overall_score": round(self.overall_score, 3),
            "quality_score": round(self.quality_score, 3),
            "coverage_score": round(self.coverage_score, 3),
            "templates_used": self.templates_used,
            "patterns_applied": self.patterns_applied,
            "defects": [d.to_dict() for d in self.defects],
            "citations": [c.to_dict() for c in self.citations],
            "provenance": self.provenance.to_dict() if self.provenance else None,
            "personas": self.personas,
            "tags": self.tags,
            "environment": self.environment,
            "execution_time_ms": round(self.execution_time_ms, 2),
            "created_at": self.created_at,
            "indexed_at": self.indexed_at,
            "status": self.status.value,
            "success": self.success,
            "embedding_id": self.embedding_id,
        }

    def generate_search_text(self) -> str:
        """Generate text for vector embedding and search."""
        parts = [
            self.requirement,
            self.requirement_summary,
            " ".join(self.templates_used),
            " ".join(self.patterns_applied),
            " ".join(self.tags),
            " ".join(self.personas),
        ]

        # Add phase summaries
        for phase in self.phases:
            parts.append(f"Phase {phase.name}: score={phase.score}")

        # Add defect summaries
        for defect in self.defects:
            parts.append(f"Defect: {defect.description}")

        return " ".join(filter(None, parts))


@dataclass
class RAGQueryResult:
    """Result from a RAG query."""
    snapshot_id: str
    similarity: float
    snapshot: LearningSnapshot
    highlights: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "similarity": round(self.similarity, 4),
            "snapshot": self.snapshot.to_dict(),
            "highlights": self.highlights,
        }


# ============================================================================
# LEARNING SNAPSHOT SERVICE
# ============================================================================

class LearningSnapshotService:
    """
    Service for generating and managing learning snapshots.

    Provides:
    - Snapshot generation from execution results
    - Vector embedding and indexing
    - RAG queries for similar executions
    - Provenance tracking and validation
    """

    def __init__(
        self,
        persist_dir: str = None,
        collection_name: str = LEARNING_COLLECTION_NAME,
        enable_persistence: bool = True,
    ):
        """
        Initialize Learning Snapshot Service.

        Args:
            persist_dir: Directory for ChromaDB persistence
            collection_name: Name of the vector collection
            enable_persistence: Whether to persist to disk
        """
        self.persist_dir = persist_dir or CHROMA_PERSIST_DIR
        self.collection_name = collection_name
        self.enable_persistence = enable_persistence

        # Initialize ChromaDB client
        self._client = None
        self._collection = None
        self._enabled = False

        self._init_vector_store()

        # In-memory snapshot cache
        self._snapshots: Dict[str, LearningSnapshot] = {}

        logger.info(
            f"Learning Snapshot Service initialized: "
            f"collection={collection_name}, enabled={self._enabled}"
        )

    def _init_vector_store(self):
        """Initialize ChromaDB vector store."""
        if not HAS_CHROMADB:
            logger.warning("ChromaDB not available - RAG features disabled")
            return

        try:
            if self.enable_persistence:
                # Ensure persist directory exists
                Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

                self._client = chromadb.PersistentClient(
                    path=self.persist_dir,
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                self._client = chromadb.Client()

            # Get or create collection
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={
                    "description": "MAESTRO learning snapshots for RAG retrieval",
                    "hnsw:space": "cosine",
                }
            )

            self._enabled = True
            logger.info(f"ChromaDB collection '{self.collection_name}' initialized")

        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if the service is enabled."""
        return self._enabled

    # =========================================================================
    # AC-1: Snapshot Generation
    # =========================================================================

    def generate_snapshot(
        self,
        session_id: str,
        execution_id: str,
        requirement: str,
        phases: List[Dict[str, Any]],
        quality_score: float = 0.0,
        templates_used: List[str] = None,
        defects: List[Dict[str, Any]] = None,
        citations: List[Dict[str, Any]] = None,
        provenance: Dict[str, Any] = None,
        personas: List[str] = None,
        tags: List[str] = None,
        environment: str = "development",
        execution_time_ms: float = 0,
        success: bool = True,
        workflow_id: str = None,
    ) -> LearningSnapshot:
        """
        Generate a learning snapshot from execution results.

        Args:
            session_id: Workflow session ID
            execution_id: Unique execution ID
            requirement: Original requirement text
            phases: List of phase results
            quality_score: Overall quality score (0-1)
            templates_used: List of template IDs used
            defects: List of defects found
            citations: List of citation references
            provenance: Provenance information
            personas: List of personas involved
            tags: Tags for categorization
            environment: Execution environment
            execution_time_ms: Total execution time
            success: Whether execution was successful
            workflow_id: Optional workflow ID

        Returns:
            Generated LearningSnapshot
        """
        start_time = time.time()

        # Generate snapshot ID
        snapshot_id = f"snap_{hashlib.md5(f'{session_id}_{execution_id}_{time.time()}'.encode()).hexdigest()[:16]}"

        # Convert phase dicts to PhaseResult objects
        phase_results = []
        for p in phases:
            phase_results.append(PhaseResult(
                id=p.get("id", ""),
                name=p.get("name", p.get("id", "")),
                score=p.get("score", 0.0),
                gates=p.get("gates", {}),
                artifacts=p.get("artifacts", []),
                duration_ms=p.get("duration_ms", 0),
                test_results=p.get("test_results"),
            ))

        # Convert defect dicts
        defect_objects = []
        for d in (defects or []):
            defect_objects.append(Defect(
                id=d.get("id", ""),
                severity=d.get("severity", "medium"),
                phase=d.get("phase", ""),
                description=d.get("description", ""),
                resolution=d.get("resolution"),
            ))

        # Convert citation dicts
        citation_objects = []
        for c in (citations or []):
            citation_objects.append(Citation(
                source=c.get("source", ""),
                ref=c.get("ref", ""),
                type=ProvenanceType(c.get("type", "source_repo")),
                description=c.get("description"),
            ))

        # Create provenance object
        prov_obj = None
        if provenance:
            prov_obj = Provenance(
                source_repo=provenance.get("source_repo"),
                commit=provenance.get("commit"),
                tool_chain=provenance.get("tool_chain", "maestro+quality-fabric"),
                validation_report_id=provenance.get("validation_report_id"),
                created_by=provenance.get("created_by"),
            )

        # Calculate overall score from phases
        if phase_results:
            overall_score = sum(p.score for p in phase_results) / len(phase_results)
        else:
            overall_score = quality_score

        # Generate requirement summary (first 200 chars)
        requirement_summary = requirement[:200] + "..." if len(requirement) > 200 else requirement

        # Create snapshot
        snapshot = LearningSnapshot(
            snapshot_id=snapshot_id,
            session_id=session_id,
            execution_id=execution_id,
            workflow_id=workflow_id,
            requirement=requirement,
            requirement_summary=requirement_summary,
            phases=phase_results,
            overall_score=overall_score,
            quality_score=quality_score,
            templates_used=templates_used or [],
            defects=defect_objects,
            citations=citation_objects,
            provenance=prov_obj,
            personas=personas or [],
            tags=tags or [],
            environment=environment,
            execution_time_ms=execution_time_ms,
            success=success,
            status=SnapshotStatus.PENDING,
        )

        # Cache snapshot
        self._snapshots[snapshot_id] = snapshot

        generation_time = (time.time() - start_time) * 1000

        if HAS_PROMETHEUS:
            SNAPSHOT_LATENCY.observe(generation_time / 1000)
            SNAPSHOTS_CREATED.labels(status="generated").inc()

        logger.info(f"Generated snapshot {snapshot_id} in {generation_time:.2f}ms")

        return snapshot

    # =========================================================================
    # AC-2: Ingestion to Vector Store
    # =========================================================================

    def index_snapshot(self, snapshot: LearningSnapshot) -> bool:
        """
        Index a snapshot to the vector store.

        Args:
            snapshot: LearningSnapshot to index

        Returns:
            True if indexed successfully
        """
        if not self._enabled:
            logger.warning("Vector store not enabled - skipping indexing")
            return False

        try:
            snapshot.status = SnapshotStatus.PROCESSING

            # Generate search text for embedding
            search_text = snapshot.generate_search_text()

            # Prepare metadata (ChromaDB requires flat dict)
            metadata = {
                "session_id": snapshot.session_id,
                "execution_id": snapshot.execution_id,
                "workflow_id": snapshot.workflow_id or "",
                "requirement_summary": snapshot.requirement_summary,
                "overall_score": snapshot.overall_score,
                "quality_score": snapshot.quality_score,
                "success": snapshot.success,
                "environment": snapshot.environment,
                "templates_used": ",".join(snapshot.templates_used),
                "personas": ",".join(snapshot.personas),
                "tags": ",".join(snapshot.tags),
                "defect_count": len(snapshot.defects),
                "phase_count": len(snapshot.phases),
                "created_at": snapshot.created_at,
            }

            # Add to collection
            self._collection.add(
                documents=[search_text],
                metadatas=[metadata],
                ids=[snapshot.snapshot_id],
            )

            # Update snapshot status
            snapshot.status = SnapshotStatus.INDEXED
            snapshot.indexed_at = datetime.now().isoformat()
            snapshot.embedding_id = snapshot.snapshot_id

            if HAS_PROMETHEUS:
                SNAPSHOTS_CREATED.labels(status="indexed").inc()

            logger.info(f"Indexed snapshot {snapshot.snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index snapshot: {e}")
            snapshot.status = SnapshotStatus.FAILED
            return False

    def generate_and_index(
        self,
        session_id: str,
        execution_id: str,
        requirement: str,
        phases: List[Dict[str, Any]],
        **kwargs
    ) -> Tuple[LearningSnapshot, bool]:
        """
        Generate and index a snapshot in one operation.

        Returns:
            Tuple of (snapshot, indexed_successfully)
        """
        snapshot = self.generate_snapshot(
            session_id=session_id,
            execution_id=execution_id,
            requirement=requirement,
            phases=phases,
            **kwargs
        )

        indexed = self.index_snapshot(snapshot)

        return snapshot, indexed

    # =========================================================================
    # AC-3: Vector Embeddings for RAG
    # =========================================================================

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection."""
        if not self._enabled:
            return {"enabled": False, "count": 0}

        try:
            count = self._collection.count()
            return {
                "enabled": True,
                "collection_name": self.collection_name,
                "count": count,
                "persist_dir": self.persist_dir,
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {"enabled": True, "count": 0, "error": str(e)}

    # =========================================================================
    # AC-4: Provenance Validation
    # =========================================================================

    def validate_provenance(self, snapshot: LearningSnapshot) -> Tuple[bool, List[str]]:
        """
        Validate provenance links in a snapshot.

        Args:
            snapshot: Snapshot to validate

        Returns:
            Tuple of (is_valid, list of issues)
        """
        issues = []

        # Check provenance object
        if not snapshot.provenance:
            issues.append("No provenance information provided")
        else:
            if not snapshot.provenance.source_repo and not snapshot.provenance.commit:
                issues.append("Provenance missing source_repo or commit")

        # Check citations
        for citation in snapshot.citations:
            if not citation.source:
                issues.append(f"Citation missing source")
            if not citation.ref:
                issues.append(f"Citation '{citation.source}' missing ref")

        return len(issues) == 0, issues

    def resolve_citation(self, citation: Citation) -> Dict[str, Any]:
        """
        Resolve a citation to its target.

        Args:
            citation: Citation to resolve

        Returns:
            Resolution result with URI and status
        """
        # Build resolution URI based on type
        uri = None
        if citation.type == ProvenanceType.SOURCE_REPO:
            uri = f"https://github.com/{citation.source}"
        elif citation.type == ProvenanceType.COMMIT:
            uri = f"https://github.com/{citation.source}/commit/{citation.ref}"
        elif citation.type == ProvenanceType.GOLDEN_PROJECT:
            uri = f"/api/templates/{citation.source}"
        elif citation.type == ProvenanceType.TEMPLATE:
            uri = f"/api/templates/{citation.source}/versions/{citation.ref}"
        elif citation.type == ProvenanceType.VALIDATION_REPORT:
            uri = f"/api/quality/validations/{citation.ref}"
        elif citation.type == ProvenanceType.ARTIFACT:
            uri = citation.ref  # Use ref as URI directly

        return {
            "citation": citation.to_dict(),
            "resolved_uri": uri,
            "resolvable": uri is not None,
        }

    # =========================================================================
    # AC-5: RAG Queries
    # =========================================================================

    def query_similar(
        self,
        query_text: str,
        top_k: int = 5,
        min_score: float = 0.0,
        filters: Dict[str, Any] = None,
    ) -> List[RAGQueryResult]:
        """
        Query for similar learning snapshots.

        Args:
            query_text: Query text to search for
            top_k: Number of results to return
            min_score: Minimum similarity score (0-1)
            filters: Optional metadata filters

        Returns:
            List of RAGQueryResult sorted by similarity
        """
        if not self._enabled:
            logger.warning("Vector store not enabled")
            return []

        try:
            if HAS_PROMETHEUS:
                RAG_QUERIES.labels(collection=self.collection_name).inc()

            # Build where clause for filters
            where = None
            if filters:
                where_clauses = []
                for key, value in filters.items():
                    if isinstance(value, bool):
                        where_clauses.append({key: {"$eq": value}})
                    elif isinstance(value, (int, float)):
                        where_clauses.append({key: {"$gte": value}})
                    else:
                        where_clauses.append({key: {"$eq": str(value)}})

                if len(where_clauses) == 1:
                    where = where_clauses[0]
                elif len(where_clauses) > 1:
                    where = {"$and": where_clauses}

            # Query ChromaDB
            results = self._collection.query(
                query_texts=[query_text],
                n_results=top_k * 2,  # Get more for filtering
                where=where,
                include=["metadatas", "distances", "documents"],
            )

            # Process results
            query_results = []

            if results and "ids" in results and results["ids"]:
                for i, snapshot_id in enumerate(results["ids"][0]):
                    distance = results["distances"][0][i]
                    metadata = results["metadatas"][0][i]
                    document = results["documents"][0][i] if results.get("documents") else ""

                    # Convert distance to similarity (cosine)
                    similarity = 1.0 - distance if distance <= 1.0 else 1.0 / (1.0 + distance)

                    # Filter by min_score
                    if similarity < min_score:
                        continue

                    # Get full snapshot from cache or reconstruct
                    snapshot = self._snapshots.get(snapshot_id)
                    if not snapshot:
                        # Reconstruct minimal snapshot from metadata
                        snapshot = LearningSnapshot(
                            snapshot_id=snapshot_id,
                            session_id=metadata.get("session_id", ""),
                            execution_id=metadata.get("execution_id", ""),
                            workflow_id=metadata.get("workflow_id"),
                            requirement_summary=metadata.get("requirement_summary", ""),
                            overall_score=metadata.get("overall_score", 0.0),
                            quality_score=metadata.get("quality_score", 0.0),
                            success=metadata.get("success", True),
                            environment=metadata.get("environment", ""),
                            templates_used=metadata.get("templates_used", "").split(",") if metadata.get("templates_used") else [],
                            personas=metadata.get("personas", "").split(",") if metadata.get("personas") else [],
                            tags=metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                            created_at=metadata.get("created_at", ""),
                            status=SnapshotStatus.INDEXED,
                        )

                    query_results.append(RAGQueryResult(
                        snapshot_id=snapshot_id,
                        similarity=similarity,
                        snapshot=snapshot,
                        highlights=[document[:200]] if document else [],
                    ))

                    if len(query_results) >= top_k:
                        break

            logger.info(f"RAG query returned {len(query_results)} results")
            return query_results

        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return []

    def query_by_requirement(
        self,
        requirement: str,
        top_k: int = 5,
        min_quality: float = 0.0,
    ) -> List[RAGQueryResult]:
        """
        Query for similar executions by requirement text.

        Args:
            requirement: Requirement text to search for
            top_k: Number of results
            min_quality: Minimum quality score filter

        Returns:
            List of similar execution snapshots
        """
        filters = {}
        if min_quality > 0:
            filters["quality_score"] = min_quality

        return self.query_similar(
            query_text=requirement,
            top_k=top_k,
            filters=filters if filters else None,
        )

    def query_by_template(
        self,
        template_id: str,
        top_k: int = 10,
    ) -> List[RAGQueryResult]:
        """
        Query for executions that used a specific template.

        Args:
            template_id: Template ID to search for
            top_k: Number of results

        Returns:
            List of executions using this template
        """
        return self.query_similar(
            query_text=f"template {template_id}",
            top_k=top_k,
        )

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def get_snapshot(self, snapshot_id: str) -> Optional[LearningSnapshot]:
        """Get a snapshot by ID."""
        return self._snapshots.get(snapshot_id)

    def list_snapshots(
        self,
        limit: int = 100,
        status: SnapshotStatus = None,
    ) -> List[LearningSnapshot]:
        """List cached snapshots with optional filtering."""
        snapshots = list(self._snapshots.values())

        if status:
            snapshots = [s for s in snapshots if s.status == status]

        return snapshots[:limit]

    def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a snapshot from cache and vector store."""
        try:
            if snapshot_id in self._snapshots:
                del self._snapshots[snapshot_id]

            if self._enabled:
                self._collection.delete(ids=[snapshot_id])

            logger.info(f"Deleted snapshot {snapshot_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete snapshot: {e}")
            return False

    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the service."""
        stats = self.get_collection_stats()
        return {
            "service": "learning_snapshot_service",
            "enabled": self._enabled,
            "collection": self.collection_name,
            "vector_store": stats,
            "cached_snapshots": len(self._snapshots),
            "chromadb_available": HAS_CHROMADB,
            "prometheus_available": HAS_PROMETHEUS,
        }


# ============================================================================
# SINGLETON & MODULE FUNCTIONS
# ============================================================================

_snapshot_service: Optional[LearningSnapshotService] = None


def get_snapshot_service(
    persist_dir: str = None,
    collection_name: str = LEARNING_COLLECTION_NAME,
) -> LearningSnapshotService:
    """Get or create singleton snapshot service."""
    global _snapshot_service
    if _snapshot_service is None:
        _snapshot_service = LearningSnapshotService(
            persist_dir=persist_dir,
            collection_name=collection_name,
        )
    return _snapshot_service


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 70)
    print("LEARNING SNAPSHOT SERVICE - Test")
    print("=" * 70)

    service = get_snapshot_service()

    # Test AC-1: Generate snapshot
    print("\n[AC-1] Generating snapshot...")
    snapshot = service.generate_snapshot(
        session_id="sess_test_001",
        execution_id="exec_abc123",
        requirement="Build a REST API for user authentication with JWT tokens",
        phases=[
            {
                "id": "design",
                "name": "Design Phase",
                "score": 0.85,
                "gates": {"DDE": "passed"},
                "artifacts": ["s3://artifacts/architecture.md"],
            },
            {
                "id": "implementation",
                "name": "Implementation Phase",
                "score": 0.78,
                "gates": {"BRV": "passed", "ACC": "passed"},
                "artifacts": ["s3://artifacts/api.py", "s3://artifacts/auth.py"],
            },
        ],
        quality_score=0.82,
        templates_used=["api_auth_v3", "jwt_handler_v2"],
        defects=[
            {"id": "DEF-1", "severity": "medium", "phase": "implementation", "description": "Missing input validation"}
        ],
        citations=[
            {"source": "golden-projects/api-auth", "ref": "commit:abc123", "type": "source_repo"}
        ],
        provenance={
            "source_repo": "github://org/my-project",
            "commit": "def456",
            "validation_report_id": "qf-val-789",
        },
        personas=["backend_developer", "security_specialist"],
        tags=["auth", "jwt", "api"],
        success=True,
    )
    print(f"   Snapshot ID: {snapshot.snapshot_id}")
    print(f"   Status: {snapshot.status.value}")
    print(f"   Overall Score: {snapshot.overall_score:.2f}")

    # Test AC-2: Index snapshot
    print("\n[AC-2] Indexing to vector store...")
    indexed = service.index_snapshot(snapshot)
    print(f"   Indexed: {indexed}")
    print(f"   Status: {snapshot.status.value}")

    # Test AC-3: Check stats
    print("\n[AC-3] Vector store stats...")
    stats = service.get_collection_stats()
    print(f"   Collection: {stats.get('collection_name')}")
    print(f"   Count: {stats.get('count')}")

    # Test AC-4: Validate provenance
    print("\n[AC-4] Validating provenance...")
    valid, issues = service.validate_provenance(snapshot)
    print(f"   Valid: {valid}")
    if issues:
        print(f"   Issues: {issues}")

    # Resolve citation
    for citation in snapshot.citations:
        resolved = service.resolve_citation(citation)
        print(f"   Citation: {citation.source} -> {resolved['resolved_uri']}")

    # Test AC-5: RAG query
    print("\n[AC-5] RAG query for similar executions...")
    results = service.query_by_requirement(
        "Create an API with authentication",
        top_k=3,
    )
    print(f"   Found {len(results)} similar executions")
    for r in results:
        print(f"   - {r.snapshot_id}: similarity={r.similarity:.3f}")

    # Service info
    print("\n[Service Info]")
    info = service.get_service_info()
    for key, value in info.items():
        print(f"   {key}: {value}")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETED!")
    print("=" * 70)
