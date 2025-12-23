#!/usr/bin/env python3
"""
ArtifactStamper - Artifact Metadata and Provenance

Stamps all artifacts with metadata and persists to storage.

MD-2093: [DDE-3] Wire artifact_stamper to persistent storage

Features:
- SHA-256 content hashing
- Metadata stamping with provenance chain
- Storage integration
- Content verification
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True

    ARTIFACTS_STAMPED = Counter(
        "dde_artifacts_stamped_total",
        "Total artifacts stamped",
        ["content_type"]
    )
    ARTIFACT_SIZE = Histogram(
        "dde_artifact_size_bytes",
        "Artifact sizes",
        buckets=[1024, 10240, 102400, 1048576, 10485760]
    )
    VERIFICATION_RESULTS = Counter(
        "dde_artifact_verifications_total",
        "Artifact verification results",
        ["result"]
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    ARTIFACTS_STAMPED = None
    ARTIFACT_SIZE = None
    VERIFICATION_RESULTS = None


class VerificationStatus(Enum):
    """Status of artifact verification."""
    VALID = "valid"
    INVALID = "invalid"
    MISSING = "missing"
    CORRUPTED = "corrupted"


@dataclass
class VerificationResult:
    """Result of artifact verification."""
    artifact_id: str
    status: VerificationStatus
    expected_hash: str
    actual_hash: Optional[str]
    message: str
    verified_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "status": self.status.value,
            "expected_hash": self.expected_hash,
            "actual_hash": self.actual_hash,
            "message": self.message,
            "verified_at": self.verified_at.isoformat(),
        }


@dataclass
class ArtifactStamp:
    """
    Metadata stamp for an artifact.

    Contains SHA-256 hash, provenance chain, and storage location.
    """
    artifact_id: str
    workflow_id: str
    node_id: str
    execution_id: str
    content_hash: str  # SHA-256
    content_type: str  # MIME type
    size_bytes: int
    storage_path: str
    created_at: datetime
    created_by: str  # persona/agent ID
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: List[str] = field(default_factory=list)  # parent artifact IDs
    version: int = 1
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "workflow_id": self.workflow_id,
            "node_id": self.node_id,
            "execution_id": self.execution_id,
            "content_hash": self.content_hash,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "storage_path": self.storage_path,
            "created_at": self.created_at.isoformat(),
            "created_by": self.created_by,
            "metadata": self.metadata,
            "provenance": self.provenance,
            "version": self.version,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactStamp":
        return cls(
            artifact_id=data["artifact_id"],
            workflow_id=data["workflow_id"],
            node_id=data["node_id"],
            execution_id=data["execution_id"],
            content_hash=data["content_hash"],
            content_type=data["content_type"],
            size_bytes=data["size_bytes"],
            storage_path=data["storage_path"],
            created_at=datetime.fromisoformat(data["created_at"]),
            created_by=data["created_by"],
            metadata=data.get("metadata", {}),
            provenance=data.get("provenance", []),
            version=data.get("version", 1),
            tags=data.get("tags", []),
        )


@dataclass
class ArtifactQuery:
    """Query parameters for artifact search."""
    workflow_id: Optional[str] = None
    node_id: Optional[str] = None
    execution_id: Optional[str] = None
    content_type: Optional[str] = None
    content_hash: Optional[str] = None
    created_by: Optional[str] = None
    tags: Optional[List[str]] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    limit: int = 100
    offset: int = 0


class ArtifactStamper:
    """
    Stamps and persists artifact metadata.

    Provides:
    - SHA-256 content hashing
    - Metadata stamping
    - Provenance chain tracking
    - Storage integration
    - Content verification
    """

    def __init__(
        self,
        storage_base_path: str = "/tmp/artifacts",
        metadata_store_path: str = "/tmp/artifact_metadata",
    ):
        self.storage_base_path = Path(storage_base_path)
        self.metadata_store_path = Path(metadata_store_path)
        self._stamps: Dict[str, ArtifactStamp] = {}
        self._hash_index: Dict[str, List[str]] = {}  # hash -> artifact_ids

        # Ensure directories exist
        self.storage_base_path.mkdir(parents=True, exist_ok=True)
        self.metadata_store_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"ArtifactStamper initialized with storage at {storage_base_path}")

    def _compute_hash(self, content: bytes) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def _infer_content_type(self, filename: Optional[str] = None, content: Optional[bytes] = None) -> str:
        """Infer MIME type from filename or content."""
        if filename:
            ext = Path(filename).suffix.lower()
            type_map = {
                ".py": "text/x-python",
                ".js": "text/javascript",
                ".ts": "text/typescript",
                ".json": "application/json",
                ".yaml": "application/x-yaml",
                ".yml": "application/x-yaml",
                ".md": "text/markdown",
                ".txt": "text/plain",
                ".html": "text/html",
                ".css": "text/css",
                ".xml": "application/xml",
                ".sql": "application/sql",
                ".sh": "application/x-sh",
                ".dockerfile": "text/x-dockerfile",
            }
            return type_map.get(ext, "application/octet-stream")

        return "application/octet-stream"

    def stamp(
        self,
        content: bytes,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        created_by: str,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> ArtifactStamp:
        """
        Stamp artifact with metadata and persist.

        Returns the ArtifactStamp with storage location and hash.
        """
        # Generate artifact ID
        artifact_id = f"art_{uuid4().hex[:12]}"

        # Compute hash
        content_hash = self._compute_hash(content)

        # Determine content type
        if not content_type:
            content_type = self._infer_content_type(filename, content)

        # Determine storage path
        storage_subdir = self.storage_base_path / workflow_id / node_id
        storage_subdir.mkdir(parents=True, exist_ok=True)

        if filename:
            storage_filename = f"{artifact_id}_{filename}"
        else:
            ext = content_type.split("/")[-1].replace("x-", "")
            storage_filename = f"{artifact_id}.{ext}"

        storage_path = storage_subdir / storage_filename

        # Write content
        with open(storage_path, "wb") as f:
            f.write(content)

        # Create stamp
        stamp = ArtifactStamp(
            artifact_id=artifact_id,
            workflow_id=workflow_id,
            node_id=node_id,
            execution_id=execution_id,
            content_hash=content_hash,
            content_type=content_type,
            size_bytes=len(content),
            storage_path=str(storage_path),
            created_at=datetime.utcnow(),
            created_by=created_by,
            metadata=metadata or {},
            provenance=provenance or [],
            tags=tags or [],
        )

        # Store stamp
        self._stamps[artifact_id] = stamp

        # Update hash index
        if content_hash not in self._hash_index:
            self._hash_index[content_hash] = []
        self._hash_index[content_hash].append(artifact_id)

        # Persist stamp metadata
        self._persist_stamp(stamp)

        # Metrics
        if PROMETHEUS_AVAILABLE:
            if ARTIFACTS_STAMPED:
                ARTIFACTS_STAMPED.labels(content_type=content_type).inc()
            if ARTIFACT_SIZE:
                ARTIFACT_SIZE.observe(len(content))

        logger.info(f"Stamped artifact {artifact_id} ({len(content)} bytes, hash: {content_hash[:16]}...)")
        return stamp

    def stamp_file(
        self,
        file_path: str,
        workflow_id: str,
        node_id: str,
        execution_id: str,
        created_by: str,
        metadata: Optional[Dict[str, Any]] = None,
        provenance: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> ArtifactStamp:
        """Stamp an existing file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            content = f.read()

        return self.stamp(
            content=content,
            workflow_id=workflow_id,
            node_id=node_id,
            execution_id=execution_id,
            created_by=created_by,
            filename=path.name,
            metadata=metadata,
            provenance=provenance,
            tags=tags,
        )

    def verify(self, artifact_id: str) -> VerificationResult:
        """Verify artifact integrity."""
        stamp = self._stamps.get(artifact_id)

        if not stamp:
            # Try to load from metadata store
            stamp = self._load_stamp(artifact_id)

        if not stamp:
            result = VerificationResult(
                artifact_id=artifact_id,
                status=VerificationStatus.MISSING,
                expected_hash="",
                actual_hash=None,
                message="Artifact metadata not found",
            )
            if PROMETHEUS_AVAILABLE and VERIFICATION_RESULTS:
                VERIFICATION_RESULTS.labels(result="missing").inc()
            return result

        # Check if file exists
        storage_path = Path(stamp.storage_path)
        if not storage_path.exists():
            result = VerificationResult(
                artifact_id=artifact_id,
                status=VerificationStatus.MISSING,
                expected_hash=stamp.content_hash,
                actual_hash=None,
                message=f"Artifact file not found at {stamp.storage_path}",
            )
            if PROMETHEUS_AVAILABLE and VERIFICATION_RESULTS:
                VERIFICATION_RESULTS.labels(result="missing").inc()
            return result

        # Verify hash
        with open(storage_path, "rb") as f:
            content = f.read()

        actual_hash = self._compute_hash(content)

        if actual_hash == stamp.content_hash:
            result = VerificationResult(
                artifact_id=artifact_id,
                status=VerificationStatus.VALID,
                expected_hash=stamp.content_hash,
                actual_hash=actual_hash,
                message="Artifact integrity verified",
            )
            if PROMETHEUS_AVAILABLE and VERIFICATION_RESULTS:
                VERIFICATION_RESULTS.labels(result="valid").inc()
        else:
            result = VerificationResult(
                artifact_id=artifact_id,
                status=VerificationStatus.CORRUPTED,
                expected_hash=stamp.content_hash,
                actual_hash=actual_hash,
                message="Hash mismatch - artifact may be corrupted",
            )
            if PROMETHEUS_AVAILABLE and VERIFICATION_RESULTS:
                VERIFICATION_RESULTS.labels(result="corrupted").inc()

        logger.debug(f"Verified artifact {artifact_id}: {result.status.value}")
        return result

    def get_provenance_chain(self, artifact_id: str) -> List[ArtifactStamp]:
        """Get the full provenance chain for an artifact."""
        chain = []
        visited = set()
        to_visit = [artifact_id]

        while to_visit:
            current_id = to_visit.pop(0)
            if current_id in visited:
                continue

            visited.add(current_id)
            stamp = self.get_stamp(current_id)

            if stamp:
                chain.append(stamp)
                to_visit.extend(stamp.provenance)

        return chain

    def get_stamp(self, artifact_id: str) -> Optional[ArtifactStamp]:
        """Get stamp by artifact ID."""
        stamp = self._stamps.get(artifact_id)
        if not stamp:
            stamp = self._load_stamp(artifact_id)
        return stamp

    def get_by_hash(self, content_hash: str) -> List[ArtifactStamp]:
        """Get all artifacts with a specific content hash."""
        artifact_ids = self._hash_index.get(content_hash, [])
        return [self.get_stamp(aid) for aid in artifact_ids if self.get_stamp(aid)]

    def search(self, query: ArtifactQuery) -> List[ArtifactStamp]:
        """Search artifacts by query parameters."""
        results = []

        for stamp in self._stamps.values():
            if query.workflow_id and stamp.workflow_id != query.workflow_id:
                continue
            if query.node_id and stamp.node_id != query.node_id:
                continue
            if query.execution_id and stamp.execution_id != query.execution_id:
                continue
            if query.content_type and stamp.content_type != query.content_type:
                continue
            if query.content_hash and stamp.content_hash != query.content_hash:
                continue
            if query.created_by and stamp.created_by != query.created_by:
                continue
            if query.tags and not all(t in stamp.tags for t in query.tags):
                continue
            if query.created_after and stamp.created_at < query.created_after:
                continue
            if query.created_before and stamp.created_at > query.created_before:
                continue

            results.append(stamp)

        # Apply pagination
        results = results[query.offset:query.offset + query.limit]

        return results

    def _persist_stamp(self, stamp: ArtifactStamp) -> None:
        """Persist stamp metadata to storage."""
        metadata_path = self.metadata_store_path / f"{stamp.artifact_id}.json"
        with open(metadata_path, "w") as f:
            json.dump(stamp.to_dict(), f, indent=2)

    def _load_stamp(self, artifact_id: str) -> Optional[ArtifactStamp]:
        """Load stamp from metadata storage."""
        metadata_path = self.metadata_store_path / f"{artifact_id}.json"
        if not metadata_path.exists():
            return None

        with open(metadata_path, "r") as f:
            data = json.load(f)

        stamp = ArtifactStamp.from_dict(data)
        self._stamps[artifact_id] = stamp

        # Update hash index
        if stamp.content_hash not in self._hash_index:
            self._hash_index[stamp.content_hash] = []
        if artifact_id not in self._hash_index[stamp.content_hash]:
            self._hash_index[stamp.content_hash].append(artifact_id)

        return stamp

    def get_stats(self) -> Dict[str, Any]:
        """Get artifact statistics."""
        total_size = sum(s.size_bytes for s in self._stamps.values())
        content_types = {}
        for s in self._stamps.values():
            content_types[s.content_type] = content_types.get(s.content_type, 0) + 1

        return {
            "total_artifacts": len(self._stamps),
            "total_size_bytes": total_size,
            "unique_hashes": len(self._hash_index),
            "content_types": content_types,
        }

    def delete(self, artifact_id: str, delete_content: bool = False) -> bool:
        """Delete artifact metadata and optionally content."""
        stamp = self.get_stamp(artifact_id)
        if not stamp:
            return False

        # Remove from stamps
        if artifact_id in self._stamps:
            del self._stamps[artifact_id]

        # Remove from hash index
        if stamp.content_hash in self._hash_index:
            self._hash_index[stamp.content_hash] = [
                aid for aid in self._hash_index[stamp.content_hash]
                if aid != artifact_id
            ]

        # Delete metadata file
        metadata_path = self.metadata_store_path / f"{artifact_id}.json"
        if metadata_path.exists():
            metadata_path.unlink()

        # Optionally delete content
        if delete_content:
            storage_path = Path(stamp.storage_path)
            if storage_path.exists():
                storage_path.unlink()

        logger.info(f"Deleted artifact {artifact_id}")
        return True
