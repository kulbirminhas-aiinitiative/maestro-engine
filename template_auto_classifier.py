#!/usr/bin/env python3
"""
Template Auto-Classifier
Analyzes project files to automatically classify templates by:
- Primary language
- Framework
- Category (backend/frontend/fullstack/library/etc.)
- Architecture pattern
- Tags

Used for classifying existing 417 projects that lack metadata.
"""

import json
import logging
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProjectClassification:
    """Classification result for a project"""

    name: str
    description: str
    category: str
    language: str
    framework: Optional[str]
    version: str
    tags: List[str]
    architecture: str
    confidence: float

    # Additional metadata
    file_count: int
    total_lines: int
    detected_languages: Dict[str, int]  # language → lines of code
    detected_frameworks: List[str]
    features: List[str]


class TemplateAutoClassifier:
    """
    Auto-classifier for template projects
    """

    # Language detection based on file extensions
    LANGUAGE_EXTENSIONS = {
        "python": [".py", ".pyw", ".pyx"],
        "javascript": [".js", ".jsx", ".mjs"],
        "typescript": [".ts", ".tsx"],
        "html": [".html", ".htm"],
        "css": [".css", ".scss", ".sass", ".less"],
        "java": [".java"],
        "go": [".go"],
        "rust": [".rs"],
        "ruby": [".rb"],
        "php": [".php"],
        "c": [".c", ".h"],
        "cpp": [".cpp", ".cc", ".cxx", ".hpp"],
        "csharp": [".cs"],
        "swift": [".swift"],
        "kotlin": [".kt"],
        "scala": [".scala"],
        "shell": [".sh", ".bash"],
        "yaml": [".yaml", ".yml"],
        "json": [".json"],
        "markdown": [".md", ".markdown"],
    }

    # Framework detection patterns
    FRAMEWORK_PATTERNS = {
        # Python frameworks
        "fastapi": ["from fastapi", "import fastapi", "FastAPI()", '"fastapi"'],
        "django": ["from django", "import django", "django.", "INSTALLED_APPS"],
        "flask": ["from flask", "import flask", "Flask(__name__)"],
        "pytest": ["import pytest", "from pytest", "@pytest."],
        # JavaScript/TypeScript frameworks
        "react": ['"react"', "'react'", 'from "react"', "import React"],
        "vue": ['"vue"', "'vue'", 'from "vue"', "import Vue"],
        "angular": ['"@angular', "'@angular", "import { Component }"],
        "express": ['"express"', "'express'", 'require("express")', "Express()"],
        "next": ['"next"', "'next'", 'from "next"'],
        "svelte": ['"svelte"', "'svelte'", ".svelte"],
        # Backend frameworks
        "spring": ["org.springframework", "@SpringBootApplication", "spring-boot"],
        "rails": ["Rails.application", "ActiveRecord", "rails"],
        # Testing frameworks
        "jest": ['"jest"', "'jest'", "describe(", "test(", "it("],
        "mocha": ['"mocha"', "'mocha'", "describe(", "it("],
        # Build tools
        "webpack": ['"webpack"', "'webpack'", "webpack.config"],
        "vite": ['"vite"', "'vite'", "vite.config"],
        "docker": ["FROM ", "RUN ", "COPY ", "CMD "],
    }

    # Category classification keywords
    CATEGORY_KEYWORDS = {
        "api": ["api", "rest", "restful", "endpoint", "routes", "/api/"],
        "backend": ["server", "backend", "database", "db", "sql", "api"],
        "frontend": ["frontend", "ui", "component", "view", "render", "html", "css"],
        "fullstack": ["frontend", "backend", "fullstack", "full-stack", "monorepo"],
        "library": ["library", "package", "module", "pip", "npm", "pypi"],
        "cli": ["cli", "command", "argparse", "click", "typer", "commander"],
        "mobile": ["mobile", "ios", "android", "react-native", "flutter"],
        "devops": ["devops", "deployment", "docker", "kubernetes", "k8s", "ci/cd"],
        "data": ["data", "analytics", "etl", "pipeline", "spark", "pandas"],
        "ml": ["machine learning", "ml", "ai", "tensorflow", "pytorch", "scikit"],
        "utility": ["utility", "helper", "utils", "tools"],
    }

    def __init__(self):
        self.ignored_dirs = {
            ".git",
            "__pycache__",
            "node_modules",
            ".venv",
            "venv",
            ".pytest_cache",
            "dist",
            "build",
        }
        self.ignored_files = {".DS_Store", ".gitignore", ".dockerignore"}

    def classify_project(self, project_path: Path) -> ProjectClassification:
        """
        Classify a project by analyzing its files

        Args:
            project_path: Path to project directory

        Returns:
            ProjectClassification with all detected metadata
        """
        logger.info(f"Classifying project: {project_path.name}")

        # Scan project files
        files = self._scan_files(project_path)

        if not files:
            logger.warning(f"No files found in {project_path}")
            return self._create_default_classification(project_path)

        # Detect languages (weighted by LOC)
        detected_languages = self._detect_languages(files)
        primary_language = (
            max(detected_languages.items(), key=lambda x: x[1])[0]
            if detected_languages
            else "unknown"
        )

        # Detect frameworks
        detected_frameworks = self._detect_frameworks(project_path, files)
        primary_framework = detected_frameworks[0] if detected_frameworks else None

        # Read README for description and features
        description, features = self._extract_from_readme(project_path)

        # Classify category
        category, confidence = self._classify_category(
            files, detected_languages, detected_frameworks, description, features
        )

        # Infer architecture
        architecture = self._infer_architecture(files, detected_languages, detected_frameworks)

        # Extract tags
        tags = self._extract_tags(
            detected_languages, detected_frameworks, category, architecture, features
        )

        # Calculate total lines and file count
        total_lines = sum(self._count_lines(f) for f in files)

        return ProjectClassification(
            name=project_path.name,
            description=description or f"Generated project: {project_path.name}",
            category=category,
            language=primary_language,
            framework=primary_framework,
            version="1.0.0",
            tags=tags,
            architecture=architecture,
            confidence=confidence,
            file_count=len(files),
            total_lines=total_lines,
            detected_languages=detected_languages,
            detected_frameworks=detected_frameworks,
            features=features,
        )

    def _scan_files(self, project_path: Path) -> List[Path]:
        """Scan project directory for code files"""
        files = []

        for item in project_path.rglob("*"):
            if item.is_file():
                # Skip ignored directories
                if any(ignored in item.parts for ignored in self.ignored_dirs):
                    continue

                # Skip ignored files
                if item.name in self.ignored_files:
                    continue

                files.append(item)

        return files

    def _detect_languages(self, files: List[Path]) -> Dict[str, int]:
        """
        Detect languages based on file extensions, weighted by lines of code

        Returns:
            Dict mapping language -> lines of code
        """
        language_lines = Counter()

        for file_path in files:
            ext = file_path.suffix.lower()

            # Find language for this extension
            for language, extensions in self.LANGUAGE_EXTENSIONS.items():
                if ext in extensions:
                    lines = self._count_lines(file_path)
                    language_lines[language] += lines
                    break

        return dict(language_lines)

    def _count_lines(self, file_path: Path) -> int:
        """Count non-empty lines in a file"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for line in f if line.strip())
        except Exception:
            return 0

    def _detect_frameworks(self, project_path: Path, files: List[Path]) -> List[str]:
        """
        Detect frameworks by analyzing dependencies and source code

        Returns:
            List of detected frameworks
        """
        frameworks = set()

        # Check package.json (JavaScript/TypeScript)
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json, "r") as f:
                    data = json.load(f)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

                    for fw_name in self.FRAMEWORK_PATTERNS.keys():
                        if fw_name in deps or any(fw_name in dep for dep in deps):
                            frameworks.add(fw_name)
            except Exception:
                pass

        # Check requirements.txt (Python)
        requirements_txt = project_path / "requirements.txt"
        if requirements_txt.exists():
            try:
                with open(requirements_txt, "r") as f:
                    requirements = f.read().lower()

                    for fw_name in ["fastapi", "django", "flask", "pytest"]:
                        if fw_name in requirements:
                            frameworks.add(fw_name)
            except Exception:
                pass

        # Check pyproject.toml (Python)
        pyproject_toml = project_path / "pyproject.toml"
        if pyproject_toml.exists():
            try:
                with open(pyproject_toml, "r") as f:
                    content = f.read().lower()

                    for fw_name in ["fastapi", "django", "flask", "pytest"]:
                        if fw_name in content:
                            frameworks.add(fw_name)
            except Exception:
                pass

        # Scan source files for framework imports
        for file_path in files[:50]:  # Check first 50 files for performance
            if file_path.suffix in [".py", ".js", ".ts", ".jsx", ".tsx"]:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(5000)  # Read first 5KB

                        for fw_name, patterns in self.FRAMEWORK_PATTERNS.items():
                            if any(pattern in content for pattern in patterns):
                                frameworks.add(fw_name)
                except Exception:
                    pass

        return sorted(frameworks)

    def _extract_from_readme(self, project_path: Path) -> Tuple[str, List[str]]:
        """
        Extract description and features from README

        Returns:
            (description, features)
        """
        readme_files = ["README.md", "readme.md", "README.txt", "README"]

        for readme_name in readme_files:
            readme_path = project_path / readme_name
            if readme_path.exists():
                try:
                    with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                        # Extract first paragraph as description
                        lines = [line.strip() for line in content.split("\n") if line.strip()]
                        description = ""

                        for line in lines:
                            if line.startswith("#"):
                                continue
                            if len(line) > 20:  # Skip very short lines
                                description = line
                                break

                        # Extract features (lines starting with - or ✅)
                        features = []
                        for line in lines:
                            if (
                                line.startswith("- ")
                                or line.startswith("* ")
                                or line.startswith("✅")
                            ):
                                feature = line.lstrip("-*✅ ").strip()
                                if feature:
                                    features.append(feature)

                        return description, features[:10]  # Limit to 10 features

                except Exception:
                    pass

        return "", []

    def _classify_category(
        self,
        files: List[Path],
        detected_languages: Dict[str, int],
        detected_frameworks: List[str],
        description: str,
        features: List[str],
    ) -> Tuple[str, float]:
        """
        Classify project category based on multiple signals

        Returns:
            (category, confidence)
        """
        category_scores = Counter()

        # Check file types
        has_html = any(f.suffix in [".html", ".htm"] for f in files)
        has_css = any(f.suffix in [".css", ".scss", ".sass"] for f in files)
        has_js_frontend = any(f.suffix in [".jsx", ".tsx", ".vue", ".svelte"] for f in files)
        has_python = "python" in detected_languages
        has_api_file = any(
            "api" in f.name.lower() or "routes" in f.name.lower() or "endpoints" in f.name.lower()
            for f in files
        )
        has_test_files = any("test" in f.name.lower() for f in files)
        has_setup_py = any(f.name == "setup.py" for f in files)
        has_dockerfile = any(f.name == "Dockerfile" for f in files)

        # Heuristic classification
        is_frontend = has_html and has_css
        is_backend = (
            has_api_file
            or "fastapi" in detected_frameworks
            or "django" in detected_frameworks
            or "express" in detected_frameworks
            or "flask" in detected_frameworks
        )
        is_library = has_setup_py and has_test_files and not is_frontend and not is_backend

        # Score categories
        if is_frontend and is_backend:
            category_scores["fullstack"] += 10
        elif is_frontend:
            category_scores["frontend"] += 10
        elif is_backend:
            category_scores["backend"] += 10
        elif is_library:
            category_scores["library"] += 10

        # Check frameworks for hints
        if (
            "react" in detected_frameworks
            or "vue" in detected_frameworks
            or "angular" in detected_frameworks
        ):
            category_scores["frontend"] += 5

        if (
            "fastapi" in detected_frameworks
            or "django" in detected_frameworks
            or "express" in detected_frameworks
        ):
            category_scores["backend"] += 5
            category_scores["api"] += 3

        if has_dockerfile:
            category_scores["devops"] += 3

        # Scan description and features for keywords
        text = (description + " " + " ".join(features)).lower()

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    category_scores[category] += 2

        # Determine category
        if category_scores:
            category, score = category_scores.most_common(1)[0]
            total_score = sum(category_scores.values())
            confidence = min(1.0, score / total_score) if total_score > 0 else 0.5
        else:
            # Default to utility
            category = "utility"
            confidence = 0.3

        return category, confidence

    def _infer_architecture(
        self, files: List[Path], detected_languages: Dict[str, int], detected_frameworks: List[str]
    ) -> str:
        """Infer architecture pattern"""

        has_html = any(f.suffix in [".html", ".htm"] for f in files)
        has_api = any("api" in f.name.lower() or "routes" in f.name.lower() for f in files)
        has_db = any(
            "model" in f.name.lower() or "schema" in f.name.lower() or "database" in f.name.lower()
            for f in files
        )
        has_components = any("component" in f.name.lower() for f in files)

        if "react" in detected_frameworks or "vue" in detected_frameworks:
            if has_api:
                return "spa-api"
            return "spa"

        if has_api and has_db:
            return "rest-api-db"
        elif has_api:
            return "rest-api"

        if has_html and not has_components:
            return "static-site"

        if "library" in detected_frameworks or any(f.name == "setup.py" for f in files):
            return "library"

        if any(f.suffix == ".sh" for f in files):
            return "cli"

        return "monolithic"

    def _extract_tags(
        self,
        detected_languages: Dict[str, int],
        detected_frameworks: List[str],
        category: str,
        architecture: str,
        features: List[str],
    ) -> List[str]:
        """Extract tags from various sources"""
        tags = set()

        # Add languages
        tags.update(detected_languages.keys())

        # Add frameworks
        tags.update(detected_frameworks)

        # Add category
        tags.add(category)

        # Add architecture
        if architecture != "monolithic":
            tags.add(architecture.replace("-", " "))

        # Extract from features
        common_tags = {
            "authentication",
            "authorization",
            "auth",
            "login",
            "jwt",
            "rest",
            "api",
            "graphql",
            "websocket",
            "database",
            "sql",
            "nosql",
            "mongodb",
            "postgresql",
            "mysql",
            "docker",
            "kubernetes",
            "ci/cd",
            "testing",
            "responsive",
            "mobile-first",
            "pwa",
            "typescript",
            "eslint",
            "prettier",
            "webpack",
        }

        features_text = " ".join(features).lower()
        for tag in common_tags:
            if tag in features_text:
                tags.add(tag)

        # Limit to 10 most relevant tags
        return sorted(tags)[:10]

    def _create_default_classification(self, project_path: Path) -> ProjectClassification:
        """Create default classification when no files found"""
        return ProjectClassification(
            name=project_path.name,
            description=f"Project: {project_path.name}",
            category="utility",
            language="unknown",
            framework=None,
            version="1.0.0",
            tags=["unknown"],
            architecture="unknown",
            confidence=0.0,
            file_count=0,
            total_lines=0,
            detected_languages={},
            detected_frameworks=[],
            features=[],
        )


def classify_and_print(project_path: str):
    """
    Classify a project and print results (for testing)
    """
    classifier = TemplateAutoClassifier()
    classification = classifier.classify_project(Path(project_path))

    print(f"\n{'='*60}")
    print(f"Project: {classification.name}")
    print(f"{'='*60}")
    print(f"Category: {classification.category} (confidence: {classification.confidence:.2%})")
    print(f"Language: {classification.language}")
    print(f"Framework: {classification.framework or 'None'}")
    print(f"Architecture: {classification.architecture}")
    print(f"Tags: {', '.join(classification.tags)}")
    print(f"\nDescription: {classification.description}")
    print(f"\nFiles: {classification.file_count}")
    print(f"Total Lines: {classification.total_lines}")
    print(f"\nDetected Languages:")
    for lang, lines in classification.detected_languages.items():
        print(f"  - {lang}: {lines} lines")
    print(f"\nDetected Frameworks: {', '.join(classification.detected_frameworks) or 'None'}")
    print(f"\nFeatures:")
    for feature in classification.features[:5]:
        print(f"  - {feature}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        classify_and_print(sys.argv[1])
    else:
        # Test on sample projects
        test_projects = [
            "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/utcp_20251001_095047",
            "/home/ec2-user/projects/maestro-v2/enhanced_lean_output/ultimate_20250929_233042",
        ]

        for project in test_projects:
            if Path(project).exists():
                classify_and_print(project)
