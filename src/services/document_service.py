#!/usr/bin/env python3
"""
Document Service for MAESTRO Engine
Classifies and reads SDLC documents for frontend rendering
"""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import yaml


class DocumentClassifier:
    """Classifies documents based on content analysis"""

    # Patterns for detecting document types
    MERMAID_PATTERNS = [
        r"^\s*(graph\s+(TD|TB|BT|RL|LR))",
        r"^\s*sequenceDiagram",
        r"^\s*classDiagram",
        r"^\s*stateDiagram",
        r"^\s*erDiagram",
        r"^\s*journey",
        r"^\s*gantt",
        r"^\s*pie",
        r"^\s*flowchart",
    ]

    OPENAPI_PATTERNS = [r"^\s*openapi:\s*['\"]?3\.", r"^\s*swagger:\s*['\"]?2\."]

    USER_JOURNEY_PATTERNS = [
        r"^\s*journey\s*\n",
        r"title:\s*.+journey",
        r"section:\s*.+\n.+:\s*\d+:\s*.+",
    ]

    C4_PATTERNS = [r"C4Context", r"C4Container", r"C4Component", r"C4Dynamic", r"C4Deployment"]

    PLANTUML_PATTERNS = [r"@startuml", r"@enduml"]

    REQUIREMENTS_PATTERNS = [
        r"(REQ|FR|NFR)-\d+",
        r"## (Functional|Non-Functional) Requirements",
        r"Requirement ID:",
    ]

    @staticmethod
    def detect_render_type(content: str, file_extension: str = "") -> str:
        """
        Detect the render type from file content

        Args:
            content: File content
            file_extension: File extension (e.g., '.md', '.yaml')

        Returns:
            Render type string
        """
        # Check for Mermaid diagrams
        for pattern in DocumentClassifier.MERMAID_PATTERNS:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                # Check if it's a C4 diagram
                for c4_pattern in DocumentClassifier.C4_PATTERNS:
                    if c4_pattern in content:
                        return "c4-diagram"

                # Check if it's a user journey
                for journey_pattern in DocumentClassifier.USER_JOURNEY_PATTERNS:
                    if re.search(journey_pattern, content, re.MULTILINE | re.IGNORECASE):
                        return "user-journey"

                return "mermaid"

        # Check for OpenAPI spec
        for pattern in DocumentClassifier.OPENAPI_PATTERNS:
            if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                return "openapi"

        # Check for PlantUML
        for pattern in DocumentClassifier.PLANTUML_PATTERNS:
            if re.search(pattern, content, re.MULTILINE):
                return "plantuml"

        # Check for requirements documents
        for pattern in DocumentClassifier.REQUIREMENTS_PATTERNS:
            if re.search(pattern, content, re.MULTILINE):
                return "requirements"

        # Check file extension hints
        if file_extension in [".md", ".markdown"]:
            # If markdown has substantial markdown syntax, classify as markdown
            if re.search(r"^#+\s+", content, re.MULTILINE):
                return "markdown"

        if file_extension in [".yaml", ".yml"]:
            # Check if it's OpenAPI by structure
            try:
                parsed = yaml.safe_load(content)
                if isinstance(parsed, dict) and ("openapi" in parsed or "swagger" in parsed):
                    return "openapi"
            except:
                pass

        # Default: markdown if has markdown syntax, otherwise raw
        if (
            re.search(r"^#+\s+", content, re.MULTILINE)
            or re.search(r"\[.+\]\(.+\)", content)
            or re.search(r"```", content)
        ):
            return "markdown"

        return "raw"

    @staticmethod
    def infer_phase_from_content(content: str, filename: str) -> Optional[str]:
        """Infer SDLC phase from document content and filename"""
        content_lower = content.lower()
        filename_lower = filename.lower()

        # Requirements phase
        if any(
            keyword in content_lower or keyword in filename_lower
            for keyword in ["requirement", "user story", "use case", "acceptance criteria"]
        ):
            return "requirements"

        # Design phase
        if any(
            keyword in content_lower or keyword in filename_lower
            for keyword in ["architecture", "design", "diagram", "api spec", "openapi"]
        ):
            return "design"

        # Implementation phase
        if any(
            keyword in content_lower or keyword in filename_lower
            for keyword in ["implementation", "code", ".py", ".js", ".ts", ".java"]
        ):
            return "implementation"

        # Testing phase
        if any(
            keyword in content_lower or keyword in filename_lower
            for keyword in ["test", "qa", "quality", "coverage"]
        ):
            return "testing"

        # Deployment phase
        if any(
            keyword in content_lower or keyword in filename_lower
            for keyword in ["deploy", "cicd", "pipeline", "kubernetes", "docker"]
        ):
            return "deployment"

        return None


class DocumentScanner:
    """Scans project directories and generates SDLCDocument objects"""

    # File extensions to scan
    SCANNABLE_EXTENSIONS = {
        ".md",
        ".markdown",
        ".txt",
        ".yaml",
        ".yml",
        ".mermaid",
        ".mmd",
        ".puml",
        ".plantuml",
    }

    # Files to exclude
    EXCLUDED_FILES = {
        "package.json",
        "package-lock.json",
        "yarn.lock",
        "requirements.txt",
        "Pipfile",
        "Pipfile.lock",
        ".gitignore",
        "node_modules",
        "__pycache__",
    }

    def __init__(self, classifier: Optional[DocumentClassifier] = None):
        self.classifier = classifier or DocumentClassifier()

    def scan_project_directory(
        self, project_dir: Path, session_id: Optional[str] = None
    ) -> List[Dict]:
        """
        Scan project directory for SDLC documents

        Args:
            project_dir: Path to project directory
            session_id: Optional session ID for document IDs

        Returns:
            List of SDLCDocument dictionaries
        """
        documents = []

        if not project_dir.exists():
            return documents

        # Recursively scan all files
        for file_path in project_dir.rglob("*"):
            # Skip directories
            if file_path.is_dir():
                continue

            # Skip files in excluded directories
            if any(
                excluded in file_path.parts for excluded in ["node_modules", "__pycache__", ".git"]
            ):
                continue

            # Skip excluded files
            if file_path.name in self.EXCLUDED_FILES:
                continue

            # Only process scannable file types
            if file_path.suffix.lower() not in self.SCANNABLE_EXTENSIONS:
                continue

            # Try to read and classify the file
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Skip empty files
                if not content.strip():
                    continue

                # Generate document
                doc = self._create_document_from_file(file_path, content, project_dir, session_id)

                if doc:
                    documents.append(doc)

            except Exception as e:
                # Skip files that can't be read
                print(f"Warning: Could not read file {file_path}: {e}")
                continue

        return documents

    def _create_document_from_file(
        self, file_path: Path, content: str, project_dir: Path, session_id: Optional[str] = None
    ) -> Optional[Dict]:
        """Create SDLCDocument dictionary from file"""

        # Get relative path
        rel_path = file_path.relative_to(project_dir)

        # Generate document ID
        doc_id = self._generate_document_id(file_path, session_id)

        # Detect render type
        render_type = self.classifier.detect_render_type(content, file_path.suffix)

        # Infer phase
        phase = self.classifier.infer_phase_from_content(content, file_path.name)

        # Extract title from content or filename
        title = self._extract_title(content, file_path.name, render_type)

        # Get file stats
        stat = file_path.stat()

        # Build document
        document = {
            "id": doc_id,
            "title": title,
            "renderType": render_type,
            "rawContent": content,
            "generatedAt": datetime.fromtimestamp(stat.st_mtime).isoformat() + "Z",
            "phase": phase,
            "version": "1.0",
            "generatedBy": "ai-agent",  # TODO: Extract from file metadata
            "artifactType": render_type,
            "description": f"Generated document: {rel_path}",
            "size": stat.st_size,
            "filePath": str(rel_path),
        }

        return document

    @staticmethod
    def _generate_document_id(file_path: Path, session_id: Optional[str] = None) -> str:
        """Generate unique document ID"""
        # Use file path hash for consistency
        path_str = str(file_path)
        hash_suffix = hashlib.md5(path_str.encode()).hexdigest()[:8]

        if session_id:
            return f"doc-{session_id}-{hash_suffix}"
        else:
            return f"doc-{hash_suffix}"

    @staticmethod
    def _extract_title(content: str, filename: str, render_type: str) -> str:
        """Extract document title from content"""

        # Try to extract title from content
        if render_type in ["markdown", "requirements"]:
            # Look for first H1 heading
            match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            if match:
                return match.group(1).strip()

        if render_type == "mermaid":
            # Look for title in diagram
            match = re.search(r"title\s+(.+)$", content, re.MULTILINE)
            if match:
                return match.group(1).strip()

        if render_type == "openapi":
            # Try to parse YAML and extract title
            try:
                parsed = yaml.safe_load(content)
                if isinstance(parsed, dict) and "info" in parsed and "title" in parsed["info"]:
                    return parsed["info"]["title"]
            except:
                pass

        # Fallback: Use filename without extension
        return Path(filename).stem.replace("_", " ").replace("-", " ").title()


class DocumentService:
    """Service for managing SDLC documents"""

    def __init__(self):
        self.classifier = DocumentClassifier()
        self.scanner = DocumentScanner(self.classifier)

    def get_documents_by_session(self, project_dir: Path, session_id: str) -> List[Dict]:
        """Get all documents for a session"""
        return self.scanner.scan_project_directory(project_dir, session_id)

    def get_document_by_id(self, project_dir: Path, doc_id: str) -> Optional[Dict]:
        """Get a specific document by ID"""
        documents = self.scanner.scan_project_directory(project_dir, None)

        for doc in documents:
            if doc["id"] == doc_id:
                return doc

        return None

    def get_documents_by_phase(
        self, project_dir: Path, phase: str, session_id: Optional[str] = None
    ) -> List[Dict]:
        """Get documents filtered by SDLC phase"""
        all_docs = self.scanner.scan_project_directory(project_dir, session_id)

        return [doc for doc in all_docs if doc.get("phase") == phase]


# Global service instance
_document_service: Optional[DocumentService] = None


def get_document_service() -> DocumentService:
    """Get singleton document service instance"""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
