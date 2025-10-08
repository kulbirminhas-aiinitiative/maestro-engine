#!/usr/bin/env python3
"""
Collateral Extractor for MAESTRO Engine
Extracts and classifies project collaterals for indexing
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Collateral:
    """Represents a project collateral (file/document)"""

    filename: str
    filepath: str
    content: str
    file_type: str  # code, documentation, configuration, test
    persona: str  # Persona that likely created it
    tags: List[str]  # Domain tags (react, python, kubernetes, etc.)
    quality_score: Optional[float] = None


class CollateralExtractor:
    """
    Extracts and classifies project collaterals

    Responsibilities:
    - Classify requirement types
    - Extract files from project directories
    - Tag files with domain/technology markers
    - Associate files with personas
    """

    # File extension to type mapping
    FILE_TYPE_MAP = {
        # Code files
        ".py": ("code", "python"),
        ".js": ("code", "javascript"),
        ".ts": ("code", "typescript"),
        ".jsx": ("code", "react"),
        ".tsx": ("code", "react"),
        ".java": ("code", "java"),
        ".go": ("code", "golang"),
        ".rs": ("code", "rust"),
        ".cpp": ("code", "cpp"),
        ".c": ("code", "c"),
        # Documentation
        ".md": ("documentation", "markdown"),
        ".rst": ("documentation", "restructuredtext"),
        ".txt": ("documentation", "text"),
        # Configuration
        ".yaml": ("configuration", "yaml"),
        ".yml": ("configuration", "yaml"),
        ".json": ("configuration", "json"),
        ".toml": ("configuration", "toml"),
        ".ini": ("configuration", "ini"),
        ".env": ("configuration", "env"),
        # Infrastructure
        "Dockerfile": ("infrastructure", "docker"),
        "docker-compose.yml": ("infrastructure", "docker"),
        "kubernetes.yaml": ("infrastructure", "kubernetes"),
        # Build/Package
        "package.json": ("configuration", "npm"),
        "requirements.txt": ("configuration", "python"),
        "Pipfile": ("configuration", "python"),
        "pom.xml": ("configuration", "maven"),
        "build.gradle": ("configuration", "gradle"),
    }

    # Requirement type keywords
    REQUIREMENT_PATTERNS = {
        "web_app": [
            "website",
            "web application",
            "frontend",
            "dashboard",
            "web portal",
            "user interface",
            "react",
            "vue",
            "angular",
        ],
        "api": ["REST API", "API", "backend", "microservice", "GraphQL", "endpoint", "service"],
        "mobile_app": [
            "mobile app",
            "iOS",
            "Android",
            "React Native",
            "Flutter",
            "mobile application",
        ],
        "data_pipeline": [
            "data pipeline",
            "ETL",
            "data processing",
            "data warehouse",
            "analytics",
            "big data",
        ],
        "ml_model": [
            "machine learning",
            "ML model",
            "AI",
            "neural network",
            "deep learning",
            "training model",
        ],
        "devops": [
            "CI/CD",
            "deployment",
            "kubernetes",
            "docker",
            "infrastructure",
            "pipeline",
            "automation",
        ],
        "database": ["database", "SQL", "PostgreSQL", "MongoDB", "data model", "schema"],
    }

    # Persona to file pattern mapping
    PERSONA_FILE_PATTERNS = {
        "requirement_analyst": [r"requirement", r"user_stor", r"acceptance", r"spec"],
        "solution_architect": [r"architecture", r"design", r"system", r"tech_stack"],
        "ui_ux_designer": [r"wireframe", r"mockup", r"design", r"ui", r"ux"],
        "frontend_developer": [r"component", r"page", r"ui", r"\.jsx", r"\.tsx", r"\.vue"],
        "backend_developer": [r"api", r"service", r"controller", r"model", r"\.py", r"\.java"],
        "database_administrator": [r"schema", r"migration", r"\.sql", r"database"],
        "qa_engineer": [r"test", r"spec", r"\.test\.", r"\.spec\."],
        "security_specialist": [r"security", r"audit", r"vulnerability", r"auth"],
        "devops_engineer": [r"docker", r"kubernetes", r"pipeline", r"deploy", r"ci"],
        "technical_writer": [r"README", r"documentation", r"guide", r"tutorial"],
    }

    def _classify_requirement(self, requirement: str) -> str:
        """
        Classify requirement type based on keywords

        Args:
            requirement: Requirement text

        Returns:
            Requirement type
        """
        requirement_lower = requirement.lower()

        # Count matches for each type
        scores = {}
        for req_type, keywords in self.REQUIREMENT_PATTERNS.items():
            score = sum(1 for keyword in keywords if keyword.lower() in requirement_lower)
            scores[req_type] = score

        # Get type with highest score
        if scores:
            best_type = max(scores, key=scores.get)
            if scores[best_type] > 0:
                return best_type

        return "general"

    def classify_file(self, filename: str, content: Optional[str] = None) -> Dict[str, Any]:
        """
        Classify a file based on name and content

        Args:
            filename: File name
            content: File content (optional)

        Returns:
            Classification info
        """
        file_path = Path(filename)
        extension = file_path.suffix.lower()
        basename = file_path.name

        # Get file type and primary tag
        file_type = "unknown"
        tags = []

        # Check exact filename matches first
        if basename in self.FILE_TYPE_MAP:
            file_type, primary_tag = self.FILE_TYPE_MAP[basename]
            tags.append(primary_tag)
        elif extension in self.FILE_TYPE_MAP:
            file_type, primary_tag = self.FILE_TYPE_MAP[extension]
            tags.append(primary_tag)

        # Add technology tags from filename
        if "react" in basename.lower():
            tags.append("react")
        if "vue" in basename.lower():
            tags.append("vue")
        if "angular" in basename.lower():
            tags.append("angular")
        if "docker" in basename.lower():
            tags.append("docker")
        if "kubernetes" in basename.lower() or "k8s" in basename.lower():
            tags.append("kubernetes")
        if "test" in basename.lower():
            file_type = "test"
            tags.append("testing")

        # Infer persona
        persona = self.infer_persona_from_filename(filename)

        return {
            "file_type": file_type,
            "tags": list(set(tags)),  # Remove duplicates
            "persona": persona,
        }

    def infer_persona_from_filename(self, filename: str) -> str:
        """
        Infer which persona likely created this file

        Args:
            filename: File name/path

        Returns:
            Persona ID
        """
        filename_lower = filename.lower()

        # Score each persona
        scores = {}
        for persona, patterns in self.PERSONA_FILE_PATTERNS.items():
            score = sum(
                1 for pattern in patterns if re.search(pattern, filename_lower, re.IGNORECASE)
            )
            scores[persona] = score

        # Get persona with highest score
        if scores:
            best_persona = max(scores, key=scores.get)
            if scores[best_persona] > 0:
                return best_persona

        # Default based on file extension
        if filename_lower.endswith((".jsx", ".tsx", ".vue", ".css", ".scss")):
            return "frontend_developer"
        elif filename_lower.endswith((".py", ".java", ".go", ".rs")):
            return "backend_developer"
        elif filename_lower.endswith(".sql"):
            return "database_administrator"
        elif filename_lower.endswith((".md", ".rst", ".txt")):
            return "technical_writer"
        elif "docker" in filename_lower or "k8s" in filename_lower:
            return "devops_engineer"

        return "backend_developer"  # Default

    def extract_from_directory(self, project_dir: Path) -> List[Collateral]:
        """
        Extract all collaterals from a project directory

        Args:
            project_dir: Project directory path

        Returns:
            List of Collateral objects
        """
        collaterals = []

        if not project_dir.exists():
            logger.warning(f"Project directory does not exist: {project_dir}")
            return collaterals

        # Recursively scan directory
        for file_path in project_dir.rglob("*"):
            # Skip directories
            if file_path.is_dir():
                continue

            # Skip hidden files and system files
            if file_path.name.startswith("."):
                continue

            # Skip common exclude patterns
            if any(
                excluded in file_path.parts
                for excluded in ["node_modules", "__pycache__", ".git", "venv"]
            ):
                continue

            # Read file content
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except:
                # Skip binary files or unreadable files
                continue

            # Classify file
            classification = self.classify_file(file_path.name, content)

            # Create collateral
            collateral = Collateral(
                filename=file_path.name,
                filepath=str(file_path.relative_to(project_dir)),
                content=content,
                file_type=classification["file_type"],
                persona=classification["persona"],
                tags=classification["tags"],
            )

            collaterals.append(collateral)

        logger.info(f"📦 Extracted {len(collaterals)} collaterals from {project_dir}")
        return collaterals

    def extract_requirement_metadata(self, requirement: str) -> Dict[str, Any]:
        """
        Extract metadata from requirement text

        Args:
            requirement: Requirement text

        Returns:
            Metadata dict
        """
        metadata = {
            "requirement_type": self._classify_requirement(requirement),
            "word_count": len(requirement.split()),
            "has_technical_terms": self._has_technical_terms(requirement),
            "complexity": self._estimate_complexity(requirement),
        }

        return metadata

    def _has_technical_terms(self, text: str) -> bool:
        """Check if text contains technical terms"""
        technical_terms = [
            "API",
            "backend",
            "frontend",
            "database",
            "authentication",
            "authorization",
            "microservice",
            "REST",
            "GraphQL",
            "SQL",
            "NoSQL",
            "Docker",
            "Kubernetes",
            "CI/CD",
            "pipeline",
        ]

        text_lower = text.lower()
        return any(term.lower() in text_lower for term in technical_terms)

    def _estimate_complexity(self, requirement: str) -> str:
        """Estimate requirement complexity"""
        word_count = len(requirement.split())

        # Simple heuristic based on length and detail
        if word_count < 20:
            return "simple"
        elif word_count < 50:
            return "medium"
        else:
            return "complex"
