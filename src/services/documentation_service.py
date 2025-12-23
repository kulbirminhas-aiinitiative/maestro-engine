#!/usr/bin/env python3
"""
DocumentationService - AI-Powered Documentation Generation

MD-2113: [Task T5] DocumentationService class
Parent: MD-2105 (Sub-Story 2: Documentation Service)

Features:
- Generate documentation from RAG templates
- Push documentation to Confluence via adapter
- Template-based document generation with context substitution
- Integration with team execution phases
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import httpx
import yaml

logger = logging.getLogger(__name__)

# Configuration
CONFLUENCE_ADAPTER_URL = os.getenv("CONFLUENCE_ADAPTER_URL", "http://localhost:14100/api")
RAG_TEMPLATES_PATH = Path(os.getenv(
    "RAG_TEMPLATES_PATH",
    "/home/ec2-user/projects/maestro-templates/storage/templates"
))


@dataclass
class DocumentationContext:
    """Context for documentation generation."""
    workflow_id: str
    phase: str
    project_name: str
    variables: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedDocument:
    """Represents a generated document."""
    id: str
    title: str
    content: str
    template_name: str
    format: str  # markdown, confluence-wiki, html
    generated_at: datetime
    context: DocumentationContext
    word_count: int
    sections: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "template_name": self.template_name,
            "format": self.format,
            "generated_at": self.generated_at.isoformat(),
            "context": {
                "workflow_id": self.context.workflow_id,
                "phase": self.context.phase,
                "project_name": self.context.project_name,
                "variables": self.context.variables,
                "metadata": self.context.metadata
            },
            "word_count": self.word_count,
            "sections": self.sections
        }


@dataclass
class ConfluencePageResult:
    """Result of pushing to Confluence."""
    success: bool
    page_id: Optional[str]
    page_url: Optional[str]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "page_id": self.page_id,
            "page_url": self.page_url,
            "error": self.error
        }


class TemplateProcessor:
    """Processes RAG templates with variable substitution."""

    def __init__(self):
        self.delimiter_start = "{{"
        self.delimiter_end = "}}"

    def process(self, template_content: str, context: DocumentationContext) -> str:
        """
        Process template with context substitution.

        Supports:
        - {{variable}} - Simple substitution
        - {{phase}} - Current phase name
        - {{project}} - Project name
        - {{date}} - Current date
        - {{workflow_id}} - Workflow ID
        """
        result = template_content

        # Built-in variables
        built_in = {
            "phase": context.phase,
            "project": context.project_name,
            "workflow_id": context.workflow_id,
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "datetime": datetime.utcnow().isoformat(),
            "timestamp": str(int(datetime.utcnow().timestamp()))
        }

        # Merge with context variables
        all_vars = {**built_in, **context.variables, **context.metadata}

        # Perform substitution
        for key, value in all_vars.items():
            placeholder = f"{self.delimiter_start}{key}{self.delimiter_end}"
            if placeholder in result:
                result = result.replace(placeholder, str(value))

        return result

    def extract_sections(self, content: str) -> List[str]:
        """Extract section headers from markdown content."""
        sections = []
        for line in content.split("\n"):
            if line.startswith("# "):
                sections.append(line[2:].strip())
            elif line.startswith("## "):
                sections.append(line[3:].strip())
        return sections


class DocumentationService:
    """
    Service for AI-powered documentation generation.

    Integrates with:
    - RAG template system for template management
    - Confluence API for publishing
    - Team execution phases for documentation triggers

    Usage:
        service = DocumentationService()

        # Generate from template
        doc = service.generateFromTemplate(
            template_name="phase_summary",
            context=DocumentationContext(
                workflow_id="wf-123",
                phase="design",
                project_name="My Project",
                variables={"description": "..."}
            )
        )

        # Push to Confluence
        result = service.pushToConfluence(
            content=doc.content,
            page_title=doc.title,
            space_key="DEV"
        )
    """

    def __init__(
        self,
        templates_path: Optional[Path] = None,
        confluence_url: Optional[str] = None,
        auth_token: Optional[str] = None
    ):
        self.templates_path = templates_path or RAG_TEMPLATES_PATH
        self.confluence_url = confluence_url or CONFLUENCE_ADAPTER_URL
        self.auth_token = auth_token
        self.processor = TemplateProcessor()

        # Template cache
        self._template_cache: Dict[str, Dict] = {}

        logger.info(f"DocumentationService initialized (templates: {self.templates_path})")

    def generateFromTemplate(
        self,
        template_name: str,
        context: DocumentationContext,
        output_format: str = "markdown"
    ) -> GeneratedDocument:
        """
        Generate documentation from a RAG template.

        Args:
            template_name: Name of the template to use
            context: Context with variables for substitution
            output_format: Output format (markdown, confluence-wiki, html)

        Returns:
            GeneratedDocument with processed content

        Raises:
            ValueError: If template not found
            RuntimeError: If template processing fails
        """
        logger.info(f"Generating document from template: {template_name}")

        # Load template
        template = self.getTemplate(template_name)
        if not template:
            raise ValueError(f"Template not found: {template_name}")

        # Get template content
        template_content = template.get("content", "")
        if not template_content:
            raise ValueError(f"Template has no content: {template_name}")

        # Process template with context
        try:
            processed_content = self.processor.process(template_content, context)
        except Exception as e:
            logger.error(f"Template processing failed: {e}")
            raise RuntimeError(f"Failed to process template: {e}")

        # Convert format if needed
        if output_format == "confluence-wiki":
            processed_content = self._convert_to_confluence_wiki(processed_content)
        elif output_format == "html":
            processed_content = self._convert_to_html(processed_content)

        # Extract metadata
        sections = self.processor.extract_sections(processed_content)
        word_count = len(processed_content.split())

        # Build title
        title = template.get("title", template_name)
        if "{{" in title:
            title = self.processor.process(title, context)

        # Create document
        document = GeneratedDocument(
            id=f"doc-{uuid4().hex[:12]}",
            title=title,
            content=processed_content,
            template_name=template_name,
            format=output_format,
            generated_at=datetime.utcnow(),
            context=context,
            word_count=word_count,
            sections=sections
        )

        logger.info(f"Generated document: {document.id} ({word_count} words, {len(sections)} sections)")
        return document

    def pushToConfluence(
        self,
        content: str,
        page_title: str,
        space_key: str,
        parent_page_id: Optional[str] = None,
        page_id: Optional[str] = None,
        auth_token: Optional[str] = None
    ) -> ConfluencePageResult:
        """
        Push documentation to Confluence via the adapter API.

        Args:
            content: Document content (markdown or wiki format)
            page_title: Title for the Confluence page
            space_key: Confluence space key (e.g., "DEV", "DOCS")
            parent_page_id: Optional parent page ID
            page_id: Optional existing page ID for updates
            auth_token: Optional auth token (overrides instance token)

        Returns:
            ConfluencePageResult with success status and page info
        """
        logger.info(f"Pushing to Confluence: {page_title} (space: {space_key})")

        token = auth_token or self.auth_token
        if not token:
            return ConfluencePageResult(
                success=False,
                page_id=None,
                page_url=None,
                error="No authentication token provided"
            )

        # Build request payload
        payload = {
            "title": page_title,
            "content": content,
            "spaceKey": space_key
        }

        if parent_page_id:
            payload["parentPageId"] = parent_page_id

        # Determine endpoint and method
        if page_id:
            # Update existing page
            endpoint = f"{self.confluence_url}/integrations/confluence/pages/{page_id}"
            method = "PUT"
        else:
            # Create new page
            endpoint = f"{self.confluence_url}/integrations/confluence/pages"
            method = "POST"

        try:
            with httpx.Client(timeout=30.0) as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                }

                if method == "POST":
                    response = client.post(endpoint, json=payload, headers=headers)
                else:
                    response = client.put(endpoint, json=payload, headers=headers)

                if response.status_code in [200, 201]:
                    data = response.json()
                    output = data.get("output", data)

                    return ConfluencePageResult(
                        success=True,
                        page_id=output.get("id") or output.get("pageId"),
                        page_url=output.get("url") or output.get("webUrl")
                    )
                else:
                    error_msg = response.text[:200]
                    logger.error(f"Confluence API error: {response.status_code} - {error_msg}")
                    return ConfluencePageResult(
                        success=False,
                        page_id=None,
                        page_url=None,
                        error=f"API error {response.status_code}: {error_msg}"
                    )

        except httpx.RequestError as e:
            logger.error(f"Confluence request failed: {e}")
            return ConfluencePageResult(
                success=False,
                page_id=None,
                page_url=None,
                error=f"Request failed: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error pushing to Confluence: {e}")
            return ConfluencePageResult(
                success=False,
                page_id=None,
                page_url=None,
                error=f"Unexpected error: {str(e)}"
            )

    def getTemplate(self, template_name: str) -> Optional[Dict[str, Any]]:
        """
        Get a RAG template by name.

        Args:
            template_name: Name of the template

        Returns:
            Template dictionary with content and metadata, or None if not found
        """
        # Check cache first
        if template_name in self._template_cache:
            return self._template_cache[template_name]

        # Try to load from filesystem
        template = self._load_template_from_file(template_name)
        if template:
            self._template_cache[template_name] = template
            return template

        # Try built-in templates
        template = self._get_builtin_template(template_name)
        if template:
            self._template_cache[template_name] = template
            return template

        logger.warning(f"Template not found: {template_name}")
        return None

    def _load_template_from_file(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Load template from filesystem."""
        # Try various file extensions
        extensions = [".md", ".yaml", ".yml", ".json", ".txt", ""]

        for ext in extensions:
            template_file = self.templates_path / f"{template_name}{ext}"
            if template_file.exists():
                try:
                    content = template_file.read_text(encoding="utf-8")

                    # Parse based on extension
                    if ext in [".yaml", ".yml"]:
                        data = yaml.safe_load(content)
                        return {
                            "name": template_name,
                            "title": data.get("title", template_name),
                            "content": data.get("content", ""),
                            "metadata": data.get("metadata", {}),
                            "source": str(template_file)
                        }
                    elif ext == ".json":
                        data = json.loads(content)
                        return {
                            "name": template_name,
                            "title": data.get("title", template_name),
                            "content": data.get("content", ""),
                            "metadata": data.get("metadata", {}),
                            "source": str(template_file)
                        }
                    else:
                        # Plain markdown or text
                        return {
                            "name": template_name,
                            "title": template_name.replace("_", " ").title(),
                            "content": content,
                            "metadata": {},
                            "source": str(template_file)
                        }

                except Exception as e:
                    logger.error(f"Failed to load template {template_file}: {e}")

        return None

    def _get_builtin_template(self, template_name: str) -> Optional[Dict[str, Any]]:
        """Get a built-in template."""
        templates = {
            "phase_summary": {
                "name": "phase_summary",
                "title": "{{phase}} Phase Summary - {{project}}",
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
*Generated automatically by Maestro DocumentationService*
""",
                "metadata": {"category": "sdlc", "phase": "any"}
            },
            "requirements_doc": {
                "name": "requirements_doc",
                "title": "Requirements Document - {{project}}",
                "content": """# Requirements Document

## Project: {{project}}
**Version**: 1.0
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
""",
                "metadata": {"category": "sdlc", "phase": "requirements"}
            },
            "design_doc": {
                "name": "design_doc",
                "title": "Technical Design - {{project}}",
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
""",
                "metadata": {"category": "sdlc", "phase": "design"}
            },
            "test_plan": {
                "name": "test_plan",
                "title": "Test Plan - {{project}}",
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
""",
                "metadata": {"category": "sdlc", "phase": "testing"}
            },
            "deployment_runbook": {
                "name": "deployment_runbook",
                "title": "Deployment Runbook - {{project}}",
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
""",
                "metadata": {"category": "sdlc", "phase": "deployment"}
            }
        }

        return templates.get(template_name)

    def _convert_to_confluence_wiki(self, markdown: str) -> str:
        """Convert markdown to Confluence wiki format."""
        wiki = markdown

        # Headers - replace longest patterns first to avoid partial matches
        wiki = wiki.replace("#### ", "h4. ")
        wiki = wiki.replace("### ", "h3. ")
        wiki = wiki.replace("## ", "h2. ")
        wiki = wiki.replace("# ", "h1. ")

        # Bold
        import re
        wiki = re.sub(r'\*\*(.+?)\*\*', r'*\1*', wiki)

        # Italic
        wiki = re.sub(r'_(.+?)_', r'_\1_', wiki)

        # Code blocks
        wiki = re.sub(r'```(\w+)?\n(.*?)```', r'{code:\1}\n\2{code}', wiki, flags=re.DOTALL)

        # Inline code
        wiki = re.sub(r'`(.+?)`', r'{{\1}}', wiki)

        # Links
        wiki = re.sub(r'\[(.+?)\]\((.+?)\)', r'[\1|\2]', wiki)

        # Horizontal rules
        wiki = wiki.replace("---", "----")

        return wiki

    def _convert_to_html(self, markdown: str) -> str:
        """Convert markdown to HTML."""
        html = markdown

        # This is a basic conversion - in production, use a proper markdown library
        import re

        # Headers
        html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html, flags=re.MULTILINE)

        # Bold
        html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)

        # Italic
        html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)

        # Code blocks
        html = re.sub(r'```(\w+)?\n(.*?)```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)

        # Inline code
        html = re.sub(r'`(.+?)`', r'<code>\1</code>', html)

        # Links
        html = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', html)

        # Paragraphs
        html = re.sub(r'\n\n', r'</p><p>', html)
        html = f"<p>{html}</p>"

        return html

    def listTemplates(self) -> List[Dict[str, Any]]:
        """
        List all available templates.

        Returns:
            List of template metadata dictionaries
        """
        templates = []

        # Add built-in templates
        for name in ["phase_summary", "requirements_doc", "design_doc", "test_plan", "deployment_runbook"]:
            template = self._get_builtin_template(name)
            if template:
                templates.append({
                    "name": template["name"],
                    "title": template["title"],
                    "category": template.get("metadata", {}).get("category", "general"),
                    "phase": template.get("metadata", {}).get("phase", "any"),
                    "source": "builtin"
                })

        # Add filesystem templates
        if self.templates_path.exists():
            for template_file in self.templates_path.glob("*"):
                if template_file.is_file() and template_file.suffix in [".md", ".yaml", ".yml", ".json", ".txt"]:
                    name = template_file.stem
                    if not any(t["name"] == name for t in templates):
                        templates.append({
                            "name": name,
                            "title": name.replace("_", " ").title(),
                            "category": "custom",
                            "phase": "any",
                            "source": str(template_file)
                        })

        return templates

    def clearCache(self) -> None:
        """Clear the template cache."""
        self._template_cache.clear()
        logger.info("Template cache cleared")


# Integration hook for team_execution_v2.py
class DocumentationPhaseHook:
    """
    Hook for integrating documentation generation into phase execution.

    Usage in team_execution_v2.py:
        hook = DocumentationPhaseHook(doc_service)

        # After phase completion
        hook.on_phase_complete(
            workflow_id="wf-123",
            phase="design",
            project_name="My Project",
            artifacts=phase_artifacts
        )
    """

    def __init__(self, doc_service: Optional[DocumentationService] = None):
        self.doc_service = doc_service or DocumentationService()

    def on_phase_complete(
        self,
        workflow_id: str,
        phase: str,
        project_name: str,
        artifacts: Dict[str, Any],
        auto_push_confluence: bool = False,
        confluence_space: Optional[str] = None
    ) -> Optional[GeneratedDocument]:
        """
        Called when a phase completes to generate documentation.

        Args:
            workflow_id: The workflow execution ID
            phase: The completed phase name
            project_name: Name of the project
            artifacts: Phase artifacts/outputs
            auto_push_confluence: Whether to auto-push to Confluence
            confluence_space: Confluence space key for auto-push

        Returns:
            Generated document, or None if generation fails
        """
        logger.info(f"Phase hook triggered: {phase} complete for {workflow_id}")

        # Build context from artifacts
        context = DocumentationContext(
            workflow_id=workflow_id,
            phase=phase,
            project_name=project_name,
            variables={
                "deliverables": artifacts.get("deliverables", "No deliverables recorded"),
                "decisions": artifacts.get("decisions", "No decisions recorded"),
                "next_steps": artifacts.get("next_steps", "To be determined")
            },
            metadata=artifacts.get("metadata", {})
        )

        try:
            # Generate phase summary
            doc = self.doc_service.generateFromTemplate(
                template_name="phase_summary",
                context=context
            )

            # Auto-push to Confluence if enabled
            if auto_push_confluence and confluence_space:
                result = self.doc_service.pushToConfluence(
                    content=doc.content,
                    page_title=doc.title,
                    space_key=confluence_space
                )

                if result.success:
                    logger.info(f"Auto-pushed to Confluence: {result.page_url}")
                else:
                    logger.warning(f"Confluence push failed: {result.error}")

            return doc

        except Exception as e:
            logger.error(f"Phase documentation failed: {e}")
            return None


# Global service instance
_documentation_service: Optional[DocumentationService] = None


def get_documentation_service() -> DocumentationService:
    """Get singleton DocumentationService instance."""
    global _documentation_service
    if _documentation_service is None:
        _documentation_service = DocumentationService()
    return _documentation_service
