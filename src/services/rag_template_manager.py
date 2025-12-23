#!/usr/bin/env python3
"""
RAG Template Manager - Template Loading and Validation

MD-2114: [Task T6] RAG Template Manager
Parent: MD-2105 (Sub-Story 2: Documentation Service)

Features:
- Load templates from filesystem and database
- Validate template structure and variables
- List available templates with metadata
- Template versioning and caching
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import yaml

logger = logging.getLogger(__name__)

# Configuration
RAG_TEMPLATES_PATH = Path(os.getenv(
    "RAG_TEMPLATES_PATH",
    "/home/ec2-user/projects/maestro-templates/storage/templates"
))


@dataclass
class TemplateVariable:
    """Represents a variable in a template."""
    name: str
    required: bool = True
    default_value: Optional[str] = None
    description: Optional[str] = None
    validation_pattern: Optional[str] = None


@dataclass
class TemplateMetadata:
    """Metadata for a template."""
    name: str
    title: str
    version: str
    category: str
    phase: str
    author: Optional[str] = None
    description: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "version": self.version,
            "category": self.category,
            "phase": self.phase,
            "author": self.author,
            "description": self.description,
            "tags": self.tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class Template:
    """Represents a complete template."""
    metadata: TemplateMetadata
    content: str
    variables: List[TemplateVariable]
    source_path: Optional[str] = None
    content_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "content": self.content,
            "variables": [
                {
                    "name": v.name,
                    "required": v.required,
                    "default_value": v.default_value,
                    "description": v.description
                }
                for v in self.variables
            ],
            "source_path": self.source_path,
            "content_hash": self.content_hash
        }


@dataclass
class ValidationResult:
    """Result of template validation."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    variables_found: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "variables_found": self.variables_found
        }


class RAGTemplateManager:
    """
    Manages RAG documentation templates.

    Provides:
    - Template loading from filesystem
    - Template validation
    - Variable extraction
    - Template listing and search

    Usage:
        manager = RAGTemplateManager()

        # Load a template
        template = manager.loadTemplate("phase_summary")

        # Validate template
        result = manager.validateTemplate(template)

        # List all templates
        templates = manager.listTemplates()
    """

    # Variable pattern: {{variable_name}}
    VARIABLE_PATTERN = re.compile(r'\{\{(\w+)\}\}')

    # Built-in variables that don't need to be provided
    BUILTIN_VARIABLES = {
        "date", "datetime", "timestamp", "phase", "project",
        "workflow_id", "version", "author"
    }

    # Valid template categories
    VALID_CATEGORIES = {
        "sdlc", "documentation", "api", "architecture",
        "testing", "deployment", "governance", "general"
    }

    # Valid phases
    VALID_PHASES = {
        "requirements", "design", "implementation", "testing",
        "deployment", "maintenance", "any"
    }

    def __init__(self, templates_path: Optional[Path] = None):
        self.templates_path = templates_path or RAG_TEMPLATES_PATH
        self._cache: Dict[str, Template] = {}
        self._cache_timestamps: Dict[str, float] = {}

        logger.info(f"RAGTemplateManager initialized (path: {self.templates_path})")

    def loadTemplate(self, template_name: str, force_reload: bool = False) -> Optional[Template]:
        """
        Load a template by name.

        Args:
            template_name: Name of the template to load
            force_reload: If True, bypass cache and reload from source

        Returns:
            Template object, or None if not found
        """
        # Check cache
        if not force_reload and template_name in self._cache:
            # Check if source file has been modified
            if not self._is_cache_stale(template_name):
                return self._cache[template_name]

        # Try loading from filesystem
        template = self._load_from_filesystem(template_name)
        if template:
            self._cache[template_name] = template
            return template

        # Try built-in templates
        template = self._load_builtin_template(template_name)
        if template:
            self._cache[template_name] = template
            return template

        logger.warning(f"Template not found: {template_name}")
        return None

    def validateTemplate(self, template: Union[Template, str, Dict]) -> ValidationResult:
        """
        Validate a template structure and content.

        Args:
            template: Template object, template name, or template dict

        Returns:
            ValidationResult with errors and warnings
        """
        errors = []
        warnings = []
        variables_found = []

        # Get template object
        if isinstance(template, str):
            template = self.loadTemplate(template)
            if not template:
                return ValidationResult(
                    is_valid=False,
                    errors=[f"Template not found: {template}"],
                    warnings=[],
                    variables_found=[]
                )
        elif isinstance(template, dict):
            template = self._dict_to_template(template)

        # Validate metadata
        if not template.metadata.name:
            errors.append("Template name is required")
        if not template.metadata.title:
            warnings.append("Template title is missing")
        if template.metadata.category not in self.VALID_CATEGORIES:
            warnings.append(f"Unknown category: {template.metadata.category}")
        if template.metadata.phase not in self.VALID_PHASES:
            warnings.append(f"Unknown phase: {template.metadata.phase}")

        # Validate content
        if not template.content:
            errors.append("Template content is empty")
        elif len(template.content) < 10:
            warnings.append("Template content is very short")

        # Extract and validate variables
        variables_found = self._extract_variables(template.content)

        # Check for unclosed variable brackets
        open_brackets = template.content.count("{{")
        close_brackets = template.content.count("}}")
        if open_brackets != close_brackets:
            errors.append(f"Mismatched variable brackets: {open_brackets} open, {close_brackets} close")

        # Check for invalid variable names
        for var in variables_found:
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', var):
                errors.append(f"Invalid variable name: {var}")

        # Check declared variables match found variables
        declared_vars = {v.name for v in template.variables}
        found_vars = set(variables_found) - self.BUILTIN_VARIABLES

        undeclared = found_vars - declared_vars
        if undeclared:
            warnings.append(f"Undeclared variables used: {', '.join(undeclared)}")

        unused = declared_vars - found_vars
        if unused:
            warnings.append(f"Declared but unused variables: {', '.join(unused)}")

        is_valid = len(errors) == 0

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            variables_found=variables_found
        )

    def listTemplates(
        self,
        category: Optional[str] = None,
        phase: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[TemplateMetadata]:
        """
        List available templates with optional filtering.

        Args:
            category: Filter by category
            phase: Filter by SDLC phase
            tags: Filter by tags (templates must have all specified tags)

        Returns:
            List of TemplateMetadata objects
        """
        templates = []

        # Load built-in templates
        for name in self._get_builtin_template_names():
            template = self._load_builtin_template(name)
            if template:
                templates.append(template.metadata)

        # Load filesystem templates
        if self.templates_path.exists():
            for file_path in self.templates_path.glob("*"):
                if self._is_template_file(file_path):
                    template = self._load_from_filesystem(file_path.stem)
                    if template and template.metadata.name not in [t.name for t in templates]:
                        templates.append(template.metadata)

        # Apply filters
        if category:
            templates = [t for t in templates if t.category == category]
        if phase:
            templates = [t for t in templates if t.phase == phase or t.phase == "any"]
        if tags:
            templates = [t for t in templates if all(tag in t.tags for tag in tags)]

        return templates

    def getTemplateVariables(self, template_name: str) -> List[TemplateVariable]:
        """
        Get variables required by a template.

        Args:
            template_name: Name of the template

        Returns:
            List of TemplateVariable objects
        """
        template = self.loadTemplate(template_name)
        if not template:
            return []

        # Extract all variables from content
        content_vars = self._extract_variables(template.content)

        # Build list with declared + discovered variables
        variables = []
        declared_names = {v.name for v in template.variables}

        # Add declared variables
        variables.extend(template.variables)

        # Add discovered variables not in declared list
        for var_name in content_vars:
            if var_name not in declared_names and var_name not in self.BUILTIN_VARIABLES:
                variables.append(TemplateVariable(
                    name=var_name,
                    required=True,
                    description=f"Auto-discovered variable: {var_name}"
                ))

        return variables

    def searchTemplates(
        self,
        query: str,
        include_content: bool = False
    ) -> List[Tuple[TemplateMetadata, float]]:
        """
        Search templates by name, title, or description.

        Args:
            query: Search query
            include_content: If True, also search in template content

        Returns:
            List of (TemplateMetadata, relevance_score) tuples, sorted by relevance
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for metadata in self.listTemplates():
            score = 0.0

            # Name match (highest weight)
            if query_lower in metadata.name.lower():
                score += 10.0
            if metadata.name.lower().startswith(query_lower):
                score += 5.0

            # Title match
            if query_lower in metadata.title.lower():
                score += 8.0

            # Description match
            if metadata.description and query_lower in metadata.description.lower():
                score += 3.0

            # Tag match
            for tag in metadata.tags:
                if query_lower in tag.lower():
                    score += 2.0

            # Word match in name/title
            name_words = set(metadata.name.lower().replace("_", " ").split())
            title_words = set(metadata.title.lower().split())
            common_words = query_words & (name_words | title_words)
            score += len(common_words) * 1.5

            # Content match (if enabled)
            if include_content and score == 0:
                template = self.loadTemplate(metadata.name)
                if template and query_lower in template.content.lower():
                    score += 1.0

            if score > 0:
                results.append((metadata, score))

        # Sort by relevance score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def createTemplate(
        self,
        name: str,
        content: str,
        title: Optional[str] = None,
        category: str = "general",
        phase: str = "any",
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        variables: Optional[List[Dict]] = None
    ) -> Template:
        """
        Create a new template.

        Args:
            name: Template name (must be unique)
            content: Template content with {{variables}}
            title: Human-readable title
            category: Template category
            phase: SDLC phase
            description: Template description
            tags: List of tags
            variables: List of variable definitions

        Returns:
            Created Template object
        """
        # Build metadata
        metadata = TemplateMetadata(
            name=name,
            title=title or name.replace("_", " ").title(),
            version="1.0",
            category=category,
            phase=phase,
            description=description,
            tags=tags or [],
            created_at=datetime.utcnow()
        )

        # Build variables list
        template_vars = []
        if variables:
            for var_def in variables:
                template_vars.append(TemplateVariable(
                    name=var_def.get("name", ""),
                    required=var_def.get("required", True),
                    default_value=var_def.get("default_value"),
                    description=var_def.get("description"),
                    validation_pattern=var_def.get("validation_pattern")
                ))

        # Auto-discover variables from content
        content_vars = self._extract_variables(content)
        existing_names = {v.name for v in template_vars}

        for var_name in content_vars:
            if var_name not in existing_names and var_name not in self.BUILTIN_VARIABLES:
                template_vars.append(TemplateVariable(
                    name=var_name,
                    required=True
                ))

        # Create content hash
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        template = Template(
            metadata=metadata,
            content=content,
            variables=template_vars,
            source_path="dynamic",  # Mark as dynamically created (not from file)
            content_hash=content_hash
        )

        # Cache the template
        self._cache[name] = template

        logger.info(f"Created template: {name} ({len(template_vars)} variables)")
        return template

    def saveTemplate(self, template: Template, format: str = "yaml") -> str:
        """
        Save a template to filesystem.

        Args:
            template: Template to save
            format: Output format (yaml, json, or md)

        Returns:
            Path to saved file
        """
        # Ensure templates directory exists
        self.templates_path.mkdir(parents=True, exist_ok=True)

        # Determine filename
        extension = ".yaml" if format == "yaml" else (".json" if format == "json" else ".md")
        file_path = self.templates_path / f"{template.metadata.name}{extension}"

        if format == "yaml":
            data = {
                "name": template.metadata.name,
                "title": template.metadata.title,
                "version": template.metadata.version,
                "category": template.metadata.category,
                "phase": template.metadata.phase,
                "description": template.metadata.description,
                "tags": template.metadata.tags,
                "variables": [
                    {
                        "name": v.name,
                        "required": v.required,
                        "default_value": v.default_value,
                        "description": v.description
                    }
                    for v in template.variables
                ],
                "content": template.content
            }
            file_path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))

        elif format == "json":
            file_path.write_text(json.dumps(template.to_dict(), indent=2))

        else:  # markdown
            file_path.write_text(template.content)

        # Update template source path
        template.source_path = str(file_path)

        logger.info(f"Saved template to: {file_path}")
        return str(file_path)

    def clearCache(self) -> None:
        """Clear the template cache."""
        self._cache.clear()
        self._cache_timestamps.clear()
        logger.info("Template cache cleared")

    # Private methods

    def _extract_variables(self, content: str) -> List[str]:
        """Extract variable names from template content."""
        matches = self.VARIABLE_PATTERN.findall(content)
        # Preserve order, remove duplicates
        seen = set()
        unique = []
        for var in matches:
            if var not in seen:
                seen.add(var)
                unique.append(var)
        return unique

    def _load_from_filesystem(self, template_name: str) -> Optional[Template]:
        """Load template from filesystem."""
        extensions = [".yaml", ".yml", ".json", ".md", ".txt"]

        for ext in extensions:
            file_path = self.templates_path / f"{template_name}{ext}"
            if file_path.exists():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    stat = file_path.stat()

                    # Parse based on format
                    if ext in [".yaml", ".yml"]:
                        return self._parse_yaml_template(content, template_name, file_path)
                    elif ext == ".json":
                        return self._parse_json_template(content, template_name, file_path)
                    else:
                        return self._parse_markdown_template(content, template_name, file_path)

                except Exception as e:
                    logger.error(f"Failed to load template {file_path}: {e}")

        return None

    def _parse_yaml_template(self, content: str, name: str, path: Path) -> Template:
        """Parse YAML template file."""
        data = yaml.safe_load(content)
        stat = path.stat()

        metadata = TemplateMetadata(
            name=data.get("name", name),
            title=data.get("title", name.replace("_", " ").title()),
            version=data.get("version", "1.0"),
            category=data.get("category", "general"),
            phase=data.get("phase", "any"),
            author=data.get("author"),
            description=data.get("description"),
            tags=data.get("tags", []),
            created_at=datetime.fromtimestamp(stat.st_ctime),
            updated_at=datetime.fromtimestamp(stat.st_mtime)
        )

        variables = []
        for var_def in data.get("variables", []):
            variables.append(TemplateVariable(
                name=var_def.get("name", ""),
                required=var_def.get("required", True),
                default_value=var_def.get("default_value"),
                description=var_def.get("description"),
                validation_pattern=var_def.get("validation_pattern")
            ))

        template_content = data.get("content", "")
        content_hash = hashlib.sha256(template_content.encode()).hexdigest()[:16]

        return Template(
            metadata=metadata,
            content=template_content,
            variables=variables,
            source_path=str(path),
            content_hash=content_hash
        )

    def _parse_json_template(self, content: str, name: str, path: Path) -> Template:
        """Parse JSON template file."""
        data = json.loads(content)
        return self._parse_yaml_template(yaml.dump(data), name, path)

    def _parse_markdown_template(self, content: str, name: str, path: Path) -> Template:
        """Parse markdown template file."""
        stat = path.stat()

        # Extract title from first H1 heading
        title = name.replace("_", " ").title()
        for line in content.split("\n"):
            if line.startswith("# "):
                title = line[2:].strip()
                break

        metadata = TemplateMetadata(
            name=name,
            title=title,
            version="1.0",
            category="general",
            phase="any",
            created_at=datetime.fromtimestamp(stat.st_ctime),
            updated_at=datetime.fromtimestamp(stat.st_mtime)
        )

        # Auto-discover variables
        variables = []
        for var_name in self._extract_variables(content):
            if var_name not in self.BUILTIN_VARIABLES:
                variables.append(TemplateVariable(name=var_name, required=True))

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        return Template(
            metadata=metadata,
            content=content,
            variables=variables,
            source_path=str(path),
            content_hash=content_hash
        )

    def _load_builtin_template(self, template_name: str) -> Optional[Template]:
        """Load a built-in template."""
        templates = self._get_builtin_templates()
        if template_name not in templates:
            return None

        data = templates[template_name]
        metadata = TemplateMetadata(
            name=data["name"],
            title=data["title"],
            version="1.0",
            category=data.get("category", "sdlc"),
            phase=data.get("phase", "any"),
            description=data.get("description"),
            tags=data.get("tags", [])
        )

        variables = []
        for var_name in self._extract_variables(data["content"]):
            if var_name not in self.BUILTIN_VARIABLES:
                variables.append(TemplateVariable(name=var_name, required=True))

        content_hash = hashlib.sha256(data["content"].encode()).hexdigest()[:16]

        return Template(
            metadata=metadata,
            content=data["content"],
            variables=variables,
            source_path="builtin",
            content_hash=content_hash
        )

    def _get_builtin_template_names(self) -> List[str]:
        """Get list of built-in template names."""
        return list(self._get_builtin_templates().keys())

    def _get_builtin_templates(self) -> Dict[str, Dict]:
        """Get all built-in templates."""
        return {
            "phase_summary": {
                "name": "phase_summary",
                "title": "Phase Summary",
                "category": "sdlc",
                "phase": "any",
                "description": "Summary document for completed SDLC phases",
                "tags": ["summary", "phase", "documentation"],
                "content": """# {{phase}} Phase Summary

## Project: {{project}}
**Workflow ID**: {{workflow_id}}
**Date**: {{date}}

## Overview
This document summarizes the {{phase}} phase execution for the {{project}} project.

## Key Deliverables
{{deliverables}}

## Decisions Made
{{decisions}}

## Next Steps
{{next_steps}}

---
*Generated by Maestro DocumentationService*
"""
            },
            "requirements_doc": {
                "name": "requirements_doc",
                "title": "Requirements Document",
                "category": "sdlc",
                "phase": "requirements",
                "description": "Template for requirements documentation",
                "tags": ["requirements", "functional", "non-functional"],
                "content": """# Requirements Document

## Project: {{project}}
**Version**: {{version}}
**Date**: {{date}}

## 1. Introduction
### 1.1 Purpose
{{purpose}}

### 1.2 Scope
{{scope}}

## 2. Functional Requirements
{{functional_requirements}}

## 3. Non-Functional Requirements
{{non_functional_requirements}}

## 4. Constraints
{{constraints}}

## 5. Dependencies
{{dependencies}}

---
*Generated by Maestro DocumentationService*
"""
            },
            "design_doc": {
                "name": "design_doc",
                "title": "Technical Design Document",
                "category": "sdlc",
                "phase": "design",
                "description": "Template for technical design documentation",
                "tags": ["design", "architecture", "technical"],
                "content": """# Technical Design Document

## Project: {{project}}
**Workflow ID**: {{workflow_id}}
**Date**: {{date}}

## 1. Architecture Overview
{{architecture_overview}}

## 2. Component Design
{{component_design}}

## 3. Data Model
{{data_model}}

## 4. API Specifications
{{api_specs}}

## 5. Security Considerations
{{security}}

## 6. Performance Requirements
{{performance}}

---
*Generated by Maestro DocumentationService*
"""
            },
            "test_plan": {
                "name": "test_plan",
                "title": "Test Plan",
                "category": "sdlc",
                "phase": "testing",
                "description": "Template for test planning documentation",
                "tags": ["testing", "qa", "test-plan"],
                "content": """# Test Plan

## Project: {{project}}
**Date**: {{date}}

## 1. Test Scope
{{test_scope}}

## 2. Test Approach
{{test_approach}}

## 3. Test Cases
{{test_cases}}

## 4. Test Environment
{{test_environment}}

## 5. Success Criteria
{{success_criteria}}

---
*Generated by Maestro DocumentationService*
"""
            },
            "deployment_runbook": {
                "name": "deployment_runbook",
                "title": "Deployment Runbook",
                "category": "sdlc",
                "phase": "deployment",
                "description": "Template for deployment runbooks",
                "tags": ["deployment", "runbook", "operations"],
                "content": """# Deployment Runbook

## Project: {{project}}
**Date**: {{date}}

## 1. Pre-Deployment Checklist
{{pre_deployment_checklist}}

## 2. Deployment Steps
{{deployment_steps}}

## 3. Verification Steps
{{verification_steps}}

## 4. Rollback Procedure
{{rollback_procedure}}

## 5. Post-Deployment Tasks
{{post_deployment_tasks}}

---
*Generated by Maestro DocumentationService*
"""
            },
            "api_spec": {
                "name": "api_spec",
                "title": "API Specification",
                "category": "api",
                "phase": "design",
                "description": "Template for API specifications",
                "tags": ["api", "rest", "specification"],
                "content": """# API Specification

## Service: {{service_name}}
**Version**: {{version}}
**Date**: {{date}}

## Base URL
{{base_url}}

## Authentication
{{authentication}}

## Endpoints

### {{endpoint_name}}
**Method**: {{method}}
**Path**: {{path}}

#### Request
{{request_schema}}

#### Response
{{response_schema}}

#### Error Codes
{{error_codes}}

---
*Generated by Maestro DocumentationService*
"""
            }
        }

    def _dict_to_template(self, data: Dict) -> Template:
        """Convert dictionary to Template object."""
        metadata = TemplateMetadata(
            name=data.get("name", "unnamed"),
            title=data.get("title", "Untitled"),
            version=data.get("version", "1.0"),
            category=data.get("category", "general"),
            phase=data.get("phase", "any"),
            description=data.get("description"),
            tags=data.get("tags", [])
        )

        variables = []
        for var_def in data.get("variables", []):
            variables.append(TemplateVariable(
                name=var_def.get("name", ""),
                required=var_def.get("required", True),
                default_value=var_def.get("default_value"),
                description=var_def.get("description")
            ))

        content = data.get("content", "")
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        return Template(
            metadata=metadata,
            content=content,
            variables=variables,
            content_hash=content_hash
        )

    def _is_template_file(self, path: Path) -> bool:
        """Check if path is a valid template file."""
        return (
            path.is_file() and
            path.suffix in [".yaml", ".yml", ".json", ".md", ".txt"] and
            not path.name.startswith(".")
        )

    def _is_cache_stale(self, template_name: str) -> bool:
        """Check if cached template is stale."""
        if template_name not in self._cache:
            return True

        template = self._cache[template_name]
        if template.source_path in ("builtin", "dynamic"):
            return False  # Built-in and dynamically created templates never go stale

        if not template.source_path:
            return True

        source_path = Path(template.source_path)
        if not source_path.exists():
            return True

        cache_time = self._cache_timestamps.get(template_name, 0)
        file_mtime = source_path.stat().st_mtime

        return file_mtime > cache_time


# Global manager instance
_template_manager: Optional[RAGTemplateManager] = None


def get_template_manager() -> RAGTemplateManager:
    """Get singleton RAGTemplateManager instance."""
    global _template_manager
    if _template_manager is None:
        _template_manager = RAGTemplateManager()
    return _template_manager
