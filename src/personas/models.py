"""
MAESTRO Persona Definition Models (Schema v3.0)

Clean, production-ready persona models using Pydantic v2.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class PersonaCategory(str, Enum):
    """Persona categories for organization."""

    ANALYSIS_DESIGN = "analysis_design"
    DEVELOPMENT = "development"
    OPERATIONS = "operations"
    QUALITY_SECURITY = "quality_security"
    DOCUMENTATION = "documentation"


class PersonaStatus(str, Enum):
    """Persona status."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    EXPERIMENTAL = "experimental"


class PersonaMetadata(BaseModel):
    """Persona metadata."""

    description: str = Field(..., min_length=10, max_length=500)
    author: str = "MAESTRO Team"
    created_at: str  # ISO date
    updated_at: str  # ISO date
    category: PersonaCategory
    status: PersonaStatus = PersonaStatus.ACTIVE
    human_alias: Optional[str] = Field(None, min_length=2, max_length=50, description="Human name for the agent (e.g., 'Marcus', 'Emma')")


class PersonaRole(BaseModel):
    """Persona role definition."""

    primary_role: str = Field(..., min_length=3, max_length=100)
    experience_level: int = Field(..., ge=1, le=10, description="1=Novice, 10=Expert")
    autonomy_level: int = Field(..., ge=1, le=10, description="1=Supervised, 10=Autonomous")
    specializations: List[str] = Field(default_factory=list, min_length=1)


class PersonaCapabilities(BaseModel):
    """Persona capabilities."""

    core: List[str] = Field(..., min_length=1, description="Core capabilities")
    tools: List[str] = Field(default_factory=list, description="Available tools")


class ContractValidation(BaseModel):
    """Input/output validation rules."""

    requirement_text_min_length: Optional[int] = None
    requirement_text_max_length: Optional[int] = None


class InputContract(BaseModel):
    """Input contract specification."""

    required: List[str] = Field(..., min_length=1)
    optional: List[str] = Field(default_factory=list)
    validation: Optional[ContractValidation] = None


class OutputContract(BaseModel):
    """Output contract specification."""

    required: List[str] = Field(..., min_length=1)
    optional: List[str] = Field(default_factory=list)
    format: Optional[Dict[str, str]] = None


class PersonaContracts(BaseModel):
    """Persona input/output contracts."""

    input: InputContract
    output: OutputContract


class DomainInfo(BaseModel):
    """Domain-specific information."""

    keywords: List[str] = Field(default_factory=list)
    platforms: List[str] = Field(default_factory=list)
    complexity_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    typical_features: List[str] = Field(default_factory=list)


class ComplexityScoring(BaseModel):
    """Complexity scoring ranges."""

    min: int = Field(..., ge=0, le=100)
    max: int = Field(..., ge=0, le=100)
    description: str


class ComplexityFactors(BaseModel):
    """Complexity calculation factors."""

    base_factors: Dict[str, float] = Field(default_factory=dict)
    scoring: Dict[str, ComplexityScoring] = Field(default_factory=dict)


class PersonaIntelligence(BaseModel):
    """Persona intelligence configuration."""

    domains: Dict[str, DomainInfo] = Field(default_factory=dict)
    complexity_factors: Optional[ComplexityFactors] = None
    platform_indicators: Dict[str, List[str]] = Field(default_factory=dict)


class PersonaDependencies(BaseModel):
    """Persona dependencies and relationships."""

    depends_on: List[str] = Field(
        default_factory=list, description="Personas that must execute before this one"
    )
    required_by: List[str] = Field(
        default_factory=list, description="Personas that require this persona's output"
    )
    collaboration_with: List[str] = Field(
        default_factory=list, description="Personas that work together with this one"
    )


class PersonaExecution(BaseModel):
    """Persona execution configuration."""

    timeout_seconds: int = Field(default=300, ge=30, le=900)
    max_retries: int = Field(default=3, ge=0, le=5)
    priority: int = Field(default=5, ge=1, le=10, description="1=highest, 10=lowest")
    parallel_capable: bool = Field(
        default=False, description="Can this persona run in parallel with others?"
    )
    estimated_duration_seconds: Optional[int] = None


class PersonaPrompts(BaseModel):
    """Persona prompt templates."""

    system_prompt: str = Field(..., min_length=50)
    task_prompt_template: str = Field(..., min_length=50)


class QualityMetrics(BaseModel):
    """Quality metrics and thresholds."""

    expected_output_quality: Dict[str, float] = Field(default_factory=dict)
    performance_targets: Dict[str, float] = Field(default_factory=dict)


class PersonaDefinition(BaseModel):
    """
    Complete persona definition (Schema v3.0).

    This is the main model for loading and validating persona JSON files.
    """

    persona_id: str = Field(
        ...,
        pattern=r"^[a-z][a-z0-9_]*[a-z0-9]$",
        min_length=3,
        max_length=50,
        description="Unique persona identifier (snake_case)",
    )
    schema_version: str = Field(
        ..., pattern=r"^\d+\.\d+$", description="Schema version (e.g., '3.0')"
    )
    version: str = Field(
        ..., pattern=r"^\d+\.\d+\.\d+$", description="Persona version (semantic: major.minor.patch)"
    )
    display_name: str = Field(
        ..., min_length=3, max_length=50, description="Human-readable name for UI"
    )

    metadata: PersonaMetadata
    role: PersonaRole
    capabilities: PersonaCapabilities
    contracts: PersonaContracts
    intelligence: Optional[PersonaIntelligence] = None
    dependencies: PersonaDependencies = Field(default_factory=PersonaDependencies)
    execution: PersonaExecution = Field(default_factory=PersonaExecution)
    prompts: PersonaPrompts
    quality_metrics: Optional[QualityMetrics] = None

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        """Ensure schema version is 3.0 or higher."""
        major, minor = map(int, v.split("."))
        if major < 3:
            raise ValueError(f"Schema version must be 3.0 or higher, got {v}")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        """
        Ensure display name is Title Case or contains valid acronyms.

        Allows:
        - "Requirement Analyst" (standard Title Case)
        - "UI/UX Designer" (acronyms)
        - "DevOps Engineer" (acronyms)
        - "QA Engineer" (acronyms)
        """
        # Allow common acronyms
        valid_acronyms = ["UI/UX", "DevOps", "QA", "API", "SRE", "ML", "AI"]

        # Check if first character is uppercase
        if not v[0].isupper():
            raise ValueError(f"display_name must start with uppercase, got: {v}")

        # If it contains known acronyms, allow it
        for acronym in valid_acronyms:
            if acronym in v:
                return v

        # Otherwise, check standard Title Case
        if v != v.title():
            raise ValueError(f"display_name must be Title Case or contain valid acronyms, got: {v}")

        return v

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        validate_assignment = True
        json_schema_extra = {
            "example": {
                "persona_id": "requirement_analyst",
                "schema_version": "3.0",
                "version": "1.0.0",
                "display_name": "Requirement Analyst",
                "metadata": {
                    "description": "Expert requirement analyst",
                    "author": "MAESTRO Team",
                    "created_at": "2025-10-03",
                    "updated_at": "2025-10-03",
                    "category": "analysis_design",
                    "status": "active",
                },
                "role": {
                    "primary_role": "business_analyst",
                    "experience_level": 9,
                    "autonomy_level": 8,
                    "specializations": ["requirement_elicitation"],
                },
                "capabilities": {
                    "core": ["requirement_extraction"],
                    "tools": ["ai_analysis_engine"],
                },
                "contracts": {
                    "input": {"required": ["requirement_text"], "optional": ["context"]},
                    "output": {
                        "required": ["functional_requirements"],
                        "optional": ["complexity_score"],
                    },
                },
                "prompts": {
                    "system_prompt": "You are an expert Requirement Analyst...",
                    "task_prompt_template": "Analyze this requirement: {requirement_text}",
                },
            }
        }


class PersonaExecutionResult(BaseModel):
    """Result of persona execution."""

    persona_id: str
    success: bool
    output: Optional[Dict] = None
    error: Optional[str] = None
    execution_time_seconds: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class WorkflowConfig(BaseModel):
    """Configuration for workflow execution."""

    selected_personas: List[str] = Field(..., min_length=1)
    enable_mcp: bool = True
    enable_rag: bool = True
    execution_mode: str = Field(default="sequential", pattern="^(sequential|parallel)$")
    timeout_seconds: int = Field(default=900, ge=60, le=3600)


class WorkflowResult(BaseModel):
    """Result of complete workflow execution."""

    session_id: str
    requirement: str
    persona_results: List[PersonaExecutionResult]
    total_execution_time_seconds: float
    success: bool
    artifacts: Dict[str, Any] = Field(default_factory=dict)
    quality_score: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
