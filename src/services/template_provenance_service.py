#!/usr/bin/env python3
"""
Template Provenance & Citations Service for MAESTRO Engine
Implements Epic MD-1824: [MT-200] Template Provenance & Citations System

This service provides:
- Comprehensive provenance tracking for templates (source_repo, commit, tool_chain)
- Citation management for golden projects and successful runs
- Provenance validation on create/promote operations
- Full lineage chain retrieval

Acceptance Criteria:
- AC-1: Provenance fields added to template metadata schema
- AC-2: Create/promote APIs require provenance payload
- AC-3: GET /templates/{id} returns full provenance
- AC-4: Search results include provenance summary
- AC-5: Citations link to source artifacts with valid URIs
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Try to import Prometheus metrics
try:
    from prometheus_client import Counter, Histogram

    PROVENANCE_OPERATIONS = Counter(
        "maestro_template_provenance_ops_total",
        "Total provenance operations",
        ["operation", "status"]
    )
    CITATION_OPERATIONS = Counter(
        "maestro_template_citation_ops_total",
        "Total citation operations",
        ["operation"]
    )
    PROVENANCE_VALIDATION_LATENCY = Histogram(
        "maestro_provenance_validation_latency_seconds",
        "Provenance validation latency",
        buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
    )
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False

    class StubMetric:
        def inc(self): pass
        def observe(self, value): pass
        def labels(self, **kwargs): return self

    PROVENANCE_OPERATIONS = StubMetric()
    CITATION_OPERATIONS = StubMetric()
    PROVENANCE_VALIDATION_LATENCY = StubMetric()

logger = logging.getLogger("template_provenance_service")


# ============================================================================
# ENUMS AND CONSTANTS
# ============================================================================

class ProvenanceType(str, Enum):
    """Type of provenance source."""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    LOCAL = "local"
    GOLDEN_PROJECT = "golden_project"
    GENERATED = "generated"
    IMPORTED = "imported"


class CitationType(str, Enum):
    """Type of citation relationship."""
    DERIVED_FROM = "derived_from"          # Direct derivation
    INSPIRED_BY = "inspired_by"            # Inspiration/reference
    TRANSFORMED_FROM = "transformed_from"  # Modified version
    VALIDATED_BY = "validated_by"          # Validation reference
    GOLDEN_PROJECT = "golden_project"      # Reference golden project
    SUCCESSFUL_RUN = "successful_run"      # Reference successful execution


class ProvenanceValidationStatus(str, Enum):
    """Status of provenance validation."""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    UNVERIFIED = "unverified"


# URI pattern validation
SUPPORTED_URI_SCHEMES = {
    "github": r"^github://[\w-]+/[\w.-]+(/[\w.-]+)?$",
    "gitlab": r"^gitlab://[\w-]+/[\w.-]+(/[\w.-]+)?$",
    "bitbucket": r"^bitbucket://[\w-]+/[\w.-]+(/[\w.-]+)?$",
    "s3": r"^s3://[\w.-]+/.*$",
    "http": r"^https?://.*$",
    "file": r"^file://.*$",
    "maestro": r"^maestro://templates/[\w-]+(/v[\d.]+)?$",
}


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ProvenanceSource:
    """Source repository information for provenance."""
    source_repo: str                          # e.g., "github://org/repo"
    commit: Optional[str] = None              # Commit hash
    branch: Optional[str] = None              # Branch name
    tag: Optional[str] = None                 # Tag if applicable
    path: Optional[str] = None                # Path within repo

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_repo": self.source_repo,
            "commit": self.commit,
            "branch": self.branch,
            "tag": self.tag,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProvenanceSource":
        return cls(
            source_repo=data.get("source_repo", ""),
            commit=data.get("commit"),
            branch=data.get("branch"),
            tag=data.get("tag"),
            path=data.get("path"),
        )


@dataclass
class ToolChain:
    """Tool chain information used to create/validate template."""
    name: str                                 # e.g., "maestro+quality-fabric"
    version: str = "1.0.0"                    # Tool chain version
    components: List[str] = field(default_factory=list)  # Individual tools

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "components": self.components,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ToolChain":
        return cls(
            name=data.get("name", "unknown"),
            version=data.get("version", "1.0.0"),
            components=data.get("components", []),
        )


@dataclass
class Citation:
    """Citation to a source artifact."""
    citation_id: str
    citation_type: CitationType
    source_uri: str                           # URI to source artifact
    title: Optional[str] = None               # Human-readable title
    description: Optional[str] = None         # Why this was cited
    verified: bool = False                    # Whether URI was verified
    verified_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citation_id": self.citation_id,
            "citation_type": self.citation_type.value,
            "source_uri": self.source_uri,
            "title": self.title,
            "description": self.description,
            "verified": self.verified,
            "verified_at": self.verified_at,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Citation":
        return cls(
            citation_id=data.get("citation_id", ""),
            citation_type=CitationType(data.get("citation_type", "derived_from")),
            source_uri=data.get("source_uri", ""),
            title=data.get("title"),
            description=data.get("description"),
            verified=data.get("verified", False),
            verified_at=data.get("verified_at"),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().isoformat()),
        )


@dataclass
class TemplateProvenance:
    """
    Complete provenance record for a template.

    AC-1: Provenance fields for template metadata schema
    """
    provenance_id: str
    template_id: str

    # Source information
    source: ProvenanceSource
    tool_chain: ToolChain

    # Validation linkage
    validation_report_id: Optional[str] = None

    # Parent template (for derived templates)
    parent_template_id: Optional[str] = None
    parent_version: Optional[str] = None

    # Citations to related artifacts
    citations: List[Citation] = field(default_factory=list)

    # Metadata
    provenance_type: ProvenanceType = ProvenanceType.GENERATED
    validation_status: ProvenanceValidationStatus = ProvenanceValidationStatus.PENDING
    created_by: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Additional context
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provenance_id": self.provenance_id,
            "template_id": self.template_id,
            "source": self.source.to_dict(),
            "tool_chain": self.tool_chain.to_dict(),
            "validation_report_id": self.validation_report_id,
            "parent_template_id": self.parent_template_id,
            "parent_version": self.parent_version,
            "citations": [c.to_dict() for c in self.citations],
            "provenance_type": self.provenance_type.value,
            "validation_status": self.validation_status.value,
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TemplateProvenance":
        citations = [Citation.from_dict(c) for c in data.get("citations", [])]
        return cls(
            provenance_id=data.get("provenance_id", ""),
            template_id=data.get("template_id", ""),
            source=ProvenanceSource.from_dict(data.get("source", {})),
            tool_chain=ToolChain.from_dict(data.get("tool_chain", {})),
            validation_report_id=data.get("validation_report_id"),
            parent_template_id=data.get("parent_template_id"),
            parent_version=data.get("parent_version"),
            citations=citations,
            provenance_type=ProvenanceType(data.get("provenance_type", "generated")),
            validation_status=ProvenanceValidationStatus(
                data.get("validation_status", "pending")
            ),
            created_by=data.get("created_by"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            context=data.get("context", {}),
        )

    def get_summary(self) -> Dict[str, Any]:
        """
        Get provenance summary for search results.

        AC-4: Search results include provenance summary
        """
        return {
            "source_repo": self.source.source_repo,
            "commit": self.source.commit,
            "tool_chain": self.tool_chain.name,
            "validation_report_id": self.validation_report_id,
            "citation_count": len(self.citations),
            "provenance_type": self.provenance_type.value,
        }


@dataclass
class ProvenanceValidationResult:
    """Result of provenance validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    validated_uris: List[str] = field(default_factory=list)
    validation_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "validated_uris": self.validated_uris,
            "validation_time_ms": self.validation_time_ms,
        }


@dataclass
class LineageNode:
    """Node in template lineage chain."""
    template_id: str
    version: str
    provenance_id: str
    source_repo: str
    created_at: str
    depth: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "version": self.version,
            "provenance_id": self.provenance_id,
            "source_repo": self.source_repo,
            "created_at": self.created_at,
            "depth": self.depth,
        }


# ============================================================================
# TEMPLATE PROVENANCE SERVICE
# ============================================================================

class TemplateProvenanceService:
    """
    Service for managing template provenance and citations.

    Implements MT-200 acceptance criteria:
    - Tracks provenance metadata (source, commit, tool_chain)
    - Validates provenance on create/promote
    - Manages citations to source artifacts
    - Provides lineage chain retrieval
    """

    def __init__(self):
        self._provenance_cache: Dict[str, TemplateProvenance] = {}
        self._citation_index: Dict[str, List[str]] = {}  # template_id -> citation_ids
        self._lineage_cache: Dict[str, List[LineageNode]] = {}

        logger.info("TemplateProvenanceService initialized")

    def _generate_provenance_id(self, template_id: str) -> str:
        """Generate unique provenance ID."""
        content = f"{template_id}_{time.time()}"
        return f"prov_{hashlib.md5(content.encode()).hexdigest()[:16]}"

    def _generate_citation_id(self, template_id: str, source_uri: str) -> str:
        """Generate unique citation ID."""
        content = f"{template_id}_{source_uri}_{time.time()}"
        return f"cite_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def validate_uri(self, uri: str) -> Tuple[bool, Optional[str]]:
        """
        Validate URI format and scheme.

        AC-5: Citations link to source artifacts with valid URIs

        Returns:
            (is_valid, error_message or None)
        """
        if not uri:
            return False, "URI cannot be empty"

        # Check for supported schemes
        for scheme, pattern in SUPPORTED_URI_SCHEMES.items():
            if uri.startswith(scheme) or uri.startswith("http"):
                if re.match(pattern, uri):
                    return True, None

        # Try standard URL parsing
        try:
            parsed = urlparse(uri)
            if parsed.scheme and parsed.netloc:
                return True, None
        except Exception:
            pass

        return False, f"Invalid URI format: {uri}"

    def validate_provenance(
        self,
        provenance: TemplateProvenance,
        require_commit: bool = False,
    ) -> ProvenanceValidationResult:
        """
        Validate provenance data.

        AC-2: Create/promote APIs require provenance payload
        """
        start_time = time.time()
        errors = []
        warnings = []
        validated_uris = []

        # Validate source repository
        if not provenance.source.source_repo:
            errors.append("source_repo is required")
        else:
            is_valid, error = self.validate_uri(provenance.source.source_repo)
            if is_valid:
                validated_uris.append(provenance.source.source_repo)
            else:
                errors.append(f"Invalid source_repo: {error}")

        # Validate commit if required
        if require_commit and not provenance.source.commit:
            errors.append("commit hash is required for this operation")
        elif provenance.source.commit:
            if not re.match(r"^[a-f0-9]{7,40}$", provenance.source.commit):
                warnings.append("commit hash format may be invalid")

        # Validate tool chain
        if not provenance.tool_chain.name:
            warnings.append("tool_chain.name is recommended")

        # Validate citations
        for citation in provenance.citations:
            is_valid, error = self.validate_uri(citation.source_uri)
            if is_valid:
                validated_uris.append(citation.source_uri)
            else:
                errors.append(f"Invalid citation URI '{citation.source_uri}': {error}")

        validation_time = (time.time() - start_time) * 1000

        if HAS_PROMETHEUS:
            PROVENANCE_VALIDATION_LATENCY.observe(validation_time / 1000)

        result = ProvenanceValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            validated_uris=validated_uris,
            validation_time_ms=validation_time,
        )

        return result

    def create_provenance(
        self,
        template_id: str,
        source_repo: str,
        commit: Optional[str] = None,
        tool_chain: Optional[str] = None,
        validation_report_id: Optional[str] = None,
        parent_template_id: Optional[str] = None,
        citations: Optional[List[Dict[str, Any]]] = None,
        created_by: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> TemplateProvenance:
        """
        Create a new provenance record.

        AC-1: Provenance fields added to template metadata schema
        """
        provenance_id = self._generate_provenance_id(template_id)

        # Determine provenance type from source
        prov_type = self._infer_provenance_type(source_repo)

        # Parse tool chain
        tool_chain_obj = ToolChain(
            name=tool_chain or "maestro+quality-fabric",
            version="1.0.0",
            components=["maestro-engine", "quality-fabric"],
        )

        # Parse citations
        citation_objects = []
        if citations:
            for cite_data in citations:
                citation_id = self._generate_citation_id(
                    template_id, cite_data.get("source_uri", "")
                )
                citation = Citation(
                    citation_id=citation_id,
                    citation_type=CitationType(cite_data.get("type", "derived_from")),
                    source_uri=cite_data.get("source_uri", ""),
                    title=cite_data.get("title"),
                    description=cite_data.get("description"),
                    metadata=cite_data.get("metadata", {}),
                )
                citation_objects.append(citation)

        provenance = TemplateProvenance(
            provenance_id=provenance_id,
            template_id=template_id,
            source=ProvenanceSource(
                source_repo=source_repo,
                commit=commit,
            ),
            tool_chain=tool_chain_obj,
            validation_report_id=validation_report_id,
            parent_template_id=parent_template_id,
            citations=citation_objects,
            provenance_type=prov_type,
            validation_status=ProvenanceValidationStatus.PENDING,
            created_by=created_by,
            context=context or {},
        )

        # Validate
        validation_result = self.validate_provenance(provenance)
        if validation_result.is_valid:
            provenance.validation_status = ProvenanceValidationStatus.VALID
        else:
            provenance.validation_status = ProvenanceValidationStatus.INVALID

        # Cache
        self._provenance_cache[provenance_id] = provenance
        self._provenance_cache[f"template:{template_id}"] = provenance

        # Update citation index
        for citation in citation_objects:
            if template_id not in self._citation_index:
                self._citation_index[template_id] = []
            self._citation_index[template_id].append(citation.citation_id)

        if HAS_PROMETHEUS:
            PROVENANCE_OPERATIONS.labels(
                operation="create",
                status=provenance.validation_status.value
            ).inc()

        logger.info(
            f"Created provenance {provenance_id} for template {template_id}: "
            f"source={source_repo}, status={provenance.validation_status.value}"
        )

        return provenance

    def _infer_provenance_type(self, source_repo: str) -> ProvenanceType:
        """Infer provenance type from source repository URI."""
        if source_repo.startswith("github://"):
            return ProvenanceType.GITHUB
        elif source_repo.startswith("gitlab://"):
            return ProvenanceType.GITLAB
        elif source_repo.startswith("bitbucket://"):
            return ProvenanceType.BITBUCKET
        elif source_repo.startswith("maestro://golden"):
            return ProvenanceType.GOLDEN_PROJECT
        elif source_repo.startswith("file://"):
            return ProvenanceType.LOCAL
        else:
            return ProvenanceType.GENERATED

    def get_provenance(self, template_id: str) -> Optional[TemplateProvenance]:
        """
        Get provenance for a template.

        AC-3: GET /templates/{id} returns full provenance
        """
        return self._provenance_cache.get(f"template:{template_id}")

    def get_provenance_by_id(self, provenance_id: str) -> Optional[TemplateProvenance]:
        """Get provenance by provenance ID."""
        return self._provenance_cache.get(provenance_id)

    def add_citation(
        self,
        template_id: str,
        citation_type: str,
        source_uri: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Citation]:
        """
        Add a citation to a template's provenance.

        AC-5: Citations link to source artifacts with valid URIs
        """
        provenance = self.get_provenance(template_id)
        if not provenance:
            logger.warning(f"No provenance found for template {template_id}")
            return None

        # Validate URI
        is_valid, error = self.validate_uri(source_uri)
        if not is_valid:
            logger.error(f"Invalid citation URI: {error}")
            return None

        citation_id = self._generate_citation_id(template_id, source_uri)
        citation = Citation(
            citation_id=citation_id,
            citation_type=CitationType(citation_type),
            source_uri=source_uri,
            title=title,
            description=description,
            metadata=metadata or {},
        )

        provenance.citations.append(citation)
        provenance.updated_at = datetime.now().isoformat()

        # Update index
        if template_id not in self._citation_index:
            self._citation_index[template_id] = []
        self._citation_index[template_id].append(citation_id)

        if HAS_PROMETHEUS:
            CITATION_OPERATIONS.labels(operation="add").inc()

        logger.info(f"Added citation {citation_id} to template {template_id}")

        return citation

    def get_citations(self, template_id: str) -> List[Citation]:
        """Get all citations for a template."""
        provenance = self.get_provenance(template_id)
        if not provenance:
            return []
        return provenance.citations

    def verify_citation(
        self,
        template_id: str,
        citation_id: str,
    ) -> bool:
        """Verify a citation URI is accessible."""
        provenance = self.get_provenance(template_id)
        if not provenance:
            return False

        for citation in provenance.citations:
            if citation.citation_id == citation_id:
                # In production, would check URI accessibility
                # For now, just validate format
                is_valid, _ = self.validate_uri(citation.source_uri)
                if is_valid:
                    citation.verified = True
                    citation.verified_at = datetime.now().isoformat()
                    return True
        return False

    def get_lineage(
        self,
        template_id: str,
        max_depth: int = 10,
    ) -> List[LineageNode]:
        """
        Get lineage chain for a template.

        Traces parent_template_id relationships.
        """
        if template_id in self._lineage_cache:
            return self._lineage_cache[template_id]

        lineage = []
        current_id = template_id
        depth = 0

        while current_id and depth < max_depth:
            provenance = self.get_provenance(current_id)
            if not provenance:
                break

            node = LineageNode(
                template_id=current_id,
                version="1.0.0",  # Would come from template metadata
                provenance_id=provenance.provenance_id,
                source_repo=provenance.source.source_repo,
                created_at=provenance.created_at,
                depth=depth,
            )
            lineage.append(node)

            # Move to parent
            current_id = provenance.parent_template_id
            depth += 1

        self._lineage_cache[template_id] = lineage
        return lineage

    def get_derived_templates(self, template_id: str) -> List[str]:
        """Get templates derived from this template."""
        derived = set()  # Use set to avoid duplicates
        for key, prov in self._provenance_cache.items():
            if isinstance(prov, TemplateProvenance):
                if prov.parent_template_id == template_id:
                    derived.add(prov.template_id)
        return list(derived)

    def update_validation_report(
        self,
        template_id: str,
        validation_report_id: str,
    ) -> bool:
        """Update provenance with validation report ID."""
        provenance = self.get_provenance(template_id)
        if not provenance:
            return False

        provenance.validation_report_id = validation_report_id
        provenance.updated_at = datetime.now().isoformat()

        logger.info(
            f"Updated provenance for {template_id} with "
            f"validation_report_id={validation_report_id}"
        )
        return True

    def search_by_source(
        self,
        source_pattern: str,
        limit: int = 50,
    ) -> List[TemplateProvenance]:
        """Search templates by source repository pattern."""
        seen_ids = set()  # Track seen provenance IDs to avoid duplicates
        results = []
        for key, prov in self._provenance_cache.items():
            if not isinstance(prov, TemplateProvenance):
                continue
            if prov.provenance_id in seen_ids:
                continue  # Skip duplicate
            if source_pattern in prov.source.source_repo:
                results.append(prov)
                seen_ids.add(prov.provenance_id)
                if len(results) >= limit:
                    break
        return results

    def get_config(self) -> Dict[str, Any]:
        """Get service configuration."""
        return {
            "supported_uri_schemes": list(SUPPORTED_URI_SCHEMES.keys()),
            "provenance_types": [t.value for t in ProvenanceType],
            "citation_types": [t.value for t in CitationType],
            "cache_size": len(self._provenance_cache),
            "citation_count": sum(len(c) for c in self._citation_index.values()),
        }


# ============================================================================
# SINGLETON & MODULE FUNCTIONS
# ============================================================================

_template_provenance_service: Optional[TemplateProvenanceService] = None


def get_template_provenance_service() -> TemplateProvenanceService:
    """Get singleton instance of TemplateProvenanceService."""
    global _template_provenance_service
    if _template_provenance_service is None:
        _template_provenance_service = TemplateProvenanceService()
    return _template_provenance_service


def create_template_provenance(
    template_id: str,
    source_repo: str,
    commit: Optional[str] = None,
    tool_chain: Optional[str] = None,
    validation_report_id: Optional[str] = None,
    **kwargs,
) -> TemplateProvenance:
    """Convenience function to create template provenance."""
    service = get_template_provenance_service()
    return service.create_provenance(
        template_id=template_id,
        source_repo=source_repo,
        commit=commit,
        tool_chain=tool_chain,
        validation_report_id=validation_report_id,
        **kwargs,
    )


def get_template_provenance(template_id: str) -> Optional[TemplateProvenance]:
    """Convenience function to get template provenance."""
    service = get_template_provenance_service()
    return service.get_provenance(template_id)
