#!/usr/bin/env python3
"""
Unit Tests for Documentation Service

Tests for:
- MD-2113: DocumentationService class
- MD-2114: RAG Template Manager
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from services.documentation_service import (
    DocumentationContext,
    DocumentationPhaseHook,
    DocumentationService,
    GeneratedDocument,
    TemplateProcessor,
    get_documentation_service,
)
from services.rag_template_manager import (
    RAGTemplateManager,
    Template,
    TemplateMetadata,
    TemplateVariable,
    ValidationResult,
    get_template_manager,
)


# ============================================================================
# DocumentationService Tests (MD-2113)
# ============================================================================


class TestDocumentationContext:
    """Test DocumentationContext dataclass."""

    def test_context_creation(self):
        """Test creating a documentation context."""
        context = DocumentationContext(
            workflow_id="wf-123",
            phase="design",
            project_name="Test Project",
            variables={"key": "value"},
            metadata={"author": "test"}
        )

        assert context.workflow_id == "wf-123"
        assert context.phase == "design"
        assert context.project_name == "Test Project"
        assert context.variables["key"] == "value"
        assert context.metadata["author"] == "test"

    def test_context_default_values(self):
        """Test context with default values."""
        context = DocumentationContext(
            workflow_id="wf-456",
            phase="testing",
            project_name="Default Test"
        )

        assert context.variables == {}
        assert context.metadata == {}


class TestTemplateProcessor:
    """Test TemplateProcessor class."""

    def test_simple_substitution(self):
        """Test simple variable substitution."""
        processor = TemplateProcessor()
        context = DocumentationContext(
            workflow_id="wf-123",
            phase="design",
            project_name="My Project",
            variables={"description": "Test description"}
        )

        template = "Project: {{project}}, Phase: {{phase}}, Desc: {{description}}"
        result = processor.process(template, context)

        assert "My Project" in result
        assert "design" in result
        assert "Test description" in result

    def test_builtin_variables(self):
        """Test built-in variable substitution."""
        processor = TemplateProcessor()
        context = DocumentationContext(
            workflow_id="wf-abc",
            phase="testing",
            project_name="Test"
        )

        template = "Workflow: {{workflow_id}}, Date: {{date}}"
        result = processor.process(template, context)

        assert "wf-abc" in result
        # Date should be in YYYY-MM-DD format
        today = datetime.utcnow().strftime("%Y-%m-%d")
        assert today in result

    def test_extract_sections(self):
        """Test section extraction from markdown."""
        processor = TemplateProcessor()

        content = """# Main Title
Some content

## Section 1
Content for section 1

## Section 2
Content for section 2

### Subsection
More content
"""
        sections = processor.extract_sections(content)

        assert "Main Title" in sections
        assert "Section 1" in sections
        assert "Section 2" in sections
        assert len(sections) == 3  # H1 and H2 only


class TestDocumentationService:
    """Test DocumentationService class."""

    def test_service_initialization(self):
        """Test service initialization."""
        service = DocumentationService()
        assert service.templates_path is not None
        assert service.processor is not None

    def test_get_builtin_template(self):
        """Test getting a built-in template."""
        service = DocumentationService()
        template = service.getTemplate("phase_summary")

        assert template is not None
        assert template["name"] == "phase_summary"
        assert "content" in template
        assert "{{phase}}" in template["content"]

    def test_get_nonexistent_template(self):
        """Test getting a non-existent template."""
        service = DocumentationService()
        template = service.getTemplate("nonexistent_template_xyz")

        assert template is None

    def test_generate_from_template(self):
        """Test document generation from template."""
        service = DocumentationService()
        context = DocumentationContext(
            workflow_id="wf-test-123",
            phase="design",
            project_name="Test Project",
            variables={
                "deliverables": "Test deliverables list",
                "decisions": "Important decisions made",
                "next_steps": "Next steps to take"
            }
        )

        doc = service.generateFromTemplate("phase_summary", context)

        assert doc is not None
        assert isinstance(doc, GeneratedDocument)
        assert doc.template_name == "phase_summary"
        assert "Test Project" in doc.content
        assert "design" in doc.content
        assert doc.word_count > 0
        assert len(doc.sections) > 0

    def test_generate_with_invalid_template(self):
        """Test generation with invalid template."""
        service = DocumentationService()
        context = DocumentationContext(
            workflow_id="wf-123",
            phase="design",
            project_name="Test"
        )

        with pytest.raises(ValueError) as exc_info:
            service.generateFromTemplate("invalid_template_xyz", context)

        assert "not found" in str(exc_info.value)

    def test_list_templates(self):
        """Test listing available templates."""
        service = DocumentationService()
        templates = service.listTemplates()

        assert len(templates) >= 5  # At least 5 built-in templates
        names = [t["name"] for t in templates]
        assert "phase_summary" in names
        assert "requirements_doc" in names
        assert "design_doc" in names

    def test_convert_to_confluence_wiki(self):
        """Test markdown to Confluence wiki conversion."""
        service = DocumentationService()

        markdown = """# Heading 1
## Heading 2
**bold text**
`inline code`
[link](http://example.com)
"""
        wiki = service._convert_to_confluence_wiki(markdown)

        assert "h1. Heading 1" in wiki
        assert "h2. Heading 2" in wiki
        assert "*bold text*" in wiki
        assert "{{inline code}}" in wiki
        assert "[link|http://example.com]" in wiki

    def test_convert_to_html(self):
        """Test markdown to HTML conversion."""
        service = DocumentationService()

        markdown = """# Title
**bold** and _italic_
`code`
"""
        html = service._convert_to_html(markdown)

        assert "<h1>Title</h1>" in html
        assert "<strong>bold</strong>" in html
        assert "<em>italic</em>" in html
        assert "<code>code</code>" in html

    def test_generate_different_formats(self):
        """Test generating documents in different formats."""
        service = DocumentationService()
        context = DocumentationContext(
            workflow_id="wf-format-test",
            phase="testing",
            project_name="Format Test",
            variables={"test_scope": "All components"}
        )

        # Markdown (default)
        md_doc = service.generateFromTemplate("test_plan", context, output_format="markdown")
        assert md_doc.format == "markdown"
        assert "# " in md_doc.content

        # Confluence wiki
        wiki_doc = service.generateFromTemplate("test_plan", context, output_format="confluence-wiki")
        assert wiki_doc.format == "confluence-wiki"
        assert "h1." in wiki_doc.content

        # HTML
        html_doc = service.generateFromTemplate("test_plan", context, output_format="html")
        assert html_doc.format == "html"
        assert "<h1>" in html_doc.content

    def test_generated_document_to_dict(self):
        """Test GeneratedDocument serialization."""
        service = DocumentationService()
        context = DocumentationContext(
            workflow_id="wf-dict-test",
            phase="design",
            project_name="Dict Test"
        )

        doc = service.generateFromTemplate("phase_summary", context)
        doc_dict = doc.to_dict()

        assert isinstance(doc_dict, dict)
        assert doc_dict["id"].startswith("doc-")
        assert doc_dict["template_name"] == "phase_summary"
        assert "content" in doc_dict
        assert "context" in doc_dict

    def test_cache_clearing(self):
        """Test template cache clearing."""
        service = DocumentationService()

        # Load a template (caches it)
        service.getTemplate("phase_summary")
        assert len(service._template_cache) > 0

        # Clear cache
        service.clearCache()
        assert len(service._template_cache) == 0


class TestDocumentationPhaseHook:
    """Test DocumentationPhaseHook class."""

    def test_hook_initialization(self):
        """Test hook initialization."""
        hook = DocumentationPhaseHook()
        assert hook.doc_service is not None

    def test_on_phase_complete(self):
        """Test phase completion hook."""
        hook = DocumentationPhaseHook()

        doc = hook.on_phase_complete(
            workflow_id="wf-hook-test",
            phase="design",
            project_name="Hook Test",
            artifacts={
                "deliverables": "Component designs complete",
                "decisions": "Chose microservices architecture",
                "next_steps": "Begin implementation"
            }
        )

        assert doc is not None
        assert "design" in doc.content.lower()
        assert "Hook Test" in doc.content


# ============================================================================
# RAGTemplateManager Tests (MD-2114)
# ============================================================================


class TestRAGTemplateManager:
    """Test RAGTemplateManager class."""

    def test_manager_initialization(self):
        """Test manager initialization."""
        manager = RAGTemplateManager()
        assert manager.templates_path is not None

    def test_load_builtin_template(self):
        """Test loading a built-in template."""
        manager = RAGTemplateManager()
        template = manager.loadTemplate("phase_summary")

        assert template is not None
        assert isinstance(template, Template)
        assert template.metadata.name == "phase_summary"
        assert template.content is not None
        assert len(template.content) > 0

    def test_load_nonexistent_template(self):
        """Test loading non-existent template."""
        manager = RAGTemplateManager()
        template = manager.loadTemplate("nonexistent_xyz_123")

        assert template is None

    def test_validate_valid_template(self):
        """Test validation of valid template."""
        manager = RAGTemplateManager()
        template = manager.loadTemplate("phase_summary")

        result = manager.validateTemplate(template)

        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.variables_found) > 0

    def test_validate_template_by_name(self):
        """Test validation by template name."""
        manager = RAGTemplateManager()
        result = manager.validateTemplate("design_doc")

        assert result.is_valid
        assert "architecture_overview" in result.variables_found

    def test_validate_invalid_template(self):
        """Test validation of invalid template."""
        manager = RAGTemplateManager()

        invalid_template = {
            "name": "",  # Empty name
            "title": "",
            "content": "",  # Empty content
            "category": "unknown_category",
            "phase": "unknown_phase"
        }

        result = manager.validateTemplate(invalid_template)

        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("name" in e.lower() for e in result.errors)
        assert any("content" in e.lower() for e in result.errors)

    def test_validate_mismatched_brackets(self):
        """Test validation catches mismatched brackets."""
        manager = RAGTemplateManager()

        template = {
            "name": "test",
            "title": "Test",
            "content": "Hello {{world} missing bracket",
            "category": "general",
            "phase": "any"
        }

        result = manager.validateTemplate(template)

        assert not result.is_valid
        assert any("bracket" in e.lower() for e in result.errors)

    def test_list_templates(self):
        """Test listing templates."""
        manager = RAGTemplateManager()
        templates = manager.listTemplates()

        assert len(templates) >= 5
        names = [t.name for t in templates]
        assert "phase_summary" in names
        assert "requirements_doc" in names

    def test_list_templates_filter_by_category(self):
        """Test filtering templates by category."""
        manager = RAGTemplateManager()
        templates = manager.listTemplates(category="sdlc")

        assert len(templates) >= 1
        for t in templates:
            assert t.category == "sdlc"

    def test_list_templates_filter_by_phase(self):
        """Test filtering templates by phase."""
        manager = RAGTemplateManager()
        templates = manager.listTemplates(phase="design")

        assert len(templates) >= 1
        for t in templates:
            assert t.phase in ["design", "any"]

    def test_get_template_variables(self):
        """Test getting template variables."""
        manager = RAGTemplateManager()
        variables = manager.getTemplateVariables("phase_summary")

        assert len(variables) > 0
        names = [v.name for v in variables]
        assert "deliverables" in names
        assert "decisions" in names
        assert "next_steps" in names

    def test_search_templates(self):
        """Test template search."""
        manager = RAGTemplateManager()

        results = manager.searchTemplates("design")
        assert len(results) > 0

        # First result should be most relevant
        top_result = results[0]
        assert "design" in top_result[0].name.lower() or "design" in top_result[0].title.lower()

    def test_search_templates_by_phase(self):
        """Test searching templates by phase name."""
        manager = RAGTemplateManager()

        results = manager.searchTemplates("deployment")
        assert len(results) > 0

        # Should find deployment_runbook
        names = [r[0].name for r in results]
        assert "deployment_runbook" in names

    def test_create_template(self):
        """Test creating a new template."""
        manager = RAGTemplateManager()

        # Use variables that are NOT in BUILTIN_VARIABLES
        template = manager.createTemplate(
            name="custom_test_template",
            content="# {{title}}\n\nContent for {{project}} with {{description}} and {{notes}}",
            title="Custom Test Template",
            category="testing",
            phase="any",
            description="A test template",
            tags=["test", "custom"]
        )

        assert template is not None
        assert template.metadata.name == "custom_test_template"
        assert template.metadata.category == "testing"
        # title, description, notes are not builtin; project is builtin
        assert len(template.variables) >= 3

        # Should be cached
        loaded = manager.loadTemplate("custom_test_template")
        assert loaded is not None

    def test_template_to_dict(self):
        """Test template serialization."""
        manager = RAGTemplateManager()
        template = manager.loadTemplate("phase_summary")

        template_dict = template.to_dict()

        assert isinstance(template_dict, dict)
        assert "metadata" in template_dict
        assert "content" in template_dict
        assert "variables" in template_dict
        assert template_dict["metadata"]["name"] == "phase_summary"

    def test_validation_result_to_dict(self):
        """Test ValidationResult serialization."""
        result = ValidationResult(
            is_valid=True,
            errors=[],
            warnings=["Minor warning"],
            variables_found=["var1", "var2"]
        )

        result_dict = result.to_dict()

        assert isinstance(result_dict, dict)
        assert result_dict["is_valid"] is True
        assert len(result_dict["warnings"]) == 1
        assert len(result_dict["variables_found"]) == 2

    def test_cache_clearing(self):
        """Test cache clearing."""
        manager = RAGTemplateManager()

        # Load templates to populate cache
        manager.loadTemplate("phase_summary")
        manager.loadTemplate("design_doc")
        assert len(manager._cache) >= 2

        # Clear cache
        manager.clearCache()
        assert len(manager._cache) == 0

    def test_force_reload(self):
        """Test force reload bypasses cache."""
        manager = RAGTemplateManager()

        # Load template
        template1 = manager.loadTemplate("phase_summary")
        assert template1 is not None

        # Load again with force_reload
        template2 = manager.loadTemplate("phase_summary", force_reload=True)
        assert template2 is not None

        # Should be same content
        assert template1.content == template2.content


class TestTemplateMetadata:
    """Test TemplateMetadata dataclass."""

    def test_metadata_to_dict(self):
        """Test metadata serialization."""
        now = datetime.utcnow()
        metadata = TemplateMetadata(
            name="test",
            title="Test Template",
            version="1.0",
            category="testing",
            phase="any",
            author="test_author",
            description="Test description",
            tags=["tag1", "tag2"],
            created_at=now,
            updated_at=now
        )

        meta_dict = metadata.to_dict()

        assert meta_dict["name"] == "test"
        assert meta_dict["title"] == "Test Template"
        assert meta_dict["author"] == "test_author"
        assert len(meta_dict["tags"]) == 2


class TestTemplateVariable:
    """Test TemplateVariable dataclass."""

    def test_variable_creation(self):
        """Test variable creation."""
        var = TemplateVariable(
            name="test_var",
            required=True,
            default_value="default",
            description="A test variable"
        )

        assert var.name == "test_var"
        assert var.required is True
        assert var.default_value == "default"

    def test_variable_defaults(self):
        """Test variable default values."""
        var = TemplateVariable(name="simple_var")

        assert var.required is True
        assert var.default_value is None
        assert var.description is None


# ============================================================================
# Singleton Tests
# ============================================================================


class TestSingletons:
    """Test singleton factory functions."""

    def test_documentation_service_singleton(self):
        """Test DocumentationService singleton."""
        service1 = get_documentation_service()
        service2 = get_documentation_service()

        assert service1 is service2

    def test_template_manager_singleton(self):
        """Test RAGTemplateManager singleton."""
        manager1 = get_template_manager()
        manager2 = get_template_manager()

        assert manager1 is manager2


# ============================================================================
# Integration Tests
# ============================================================================


class TestDocumentationIntegration:
    """Integration tests for documentation services."""

    def test_full_workflow(self):
        """Test complete documentation workflow."""
        # Initialize services
        doc_service = DocumentationService()
        template_manager = RAGTemplateManager()

        # List available templates
        templates = template_manager.listTemplates(phase="design")
        assert len(templates) > 0

        # Get template variables
        design_template = next(t for t in templates if t.name == "design_doc")
        variables = template_manager.getTemplateVariables(design_template.name)

        # Create context with required variables
        context = DocumentationContext(
            workflow_id="wf-integration-test",
            phase="design",
            project_name="Integration Test Project",
            variables={
                "architecture_overview": "Microservices architecture",
                "component_design": "Three main components",
                "data_model": "PostgreSQL with Redis cache",
                "api_specs": "REST API with OpenAPI spec",
                "security": "OAuth 2.0 authentication",
                "performance": "99.9% uptime SLA"
            }
        )

        # Generate document
        doc = doc_service.generateFromTemplate("design_doc", context)

        # Validate output
        assert doc.id.startswith("doc-")
        assert "Integration Test Project" in doc.content
        assert "Microservices architecture" in doc.content
        assert doc.word_count > 50
        assert "design" in [s.lower() for s in doc.sections] or len(doc.sections) > 0

    def test_template_creation_and_usage(self):
        """Test creating and using a custom template."""
        manager = RAGTemplateManager()
        doc_service = DocumentationService()

        # Create custom template
        template = manager.createTemplate(
            name="custom_integration_test",
            content="""# {{title}}

## Overview
{{overview}}

## Details
{{details}}

---
Generated on {{date}}
""",
            title="Custom Integration Test",
            category="testing",
            phase="any"
        )

        # Validate template
        result = manager.validateTemplate(template)
        assert result.is_valid

        # Add to documentation service cache
        doc_service._template_cache["custom_integration_test"] = {
            "name": template.metadata.name,
            "title": template.metadata.title,
            "content": template.content
        }

        # Generate document
        context = DocumentationContext(
            workflow_id="wf-custom-test",
            phase="testing",
            project_name="Custom Test",
            variables={
                "title": "Integration Test Document",
                "overview": "This is an integration test",
                "details": "Testing custom template creation and usage"
            }
        )

        doc = doc_service.generateFromTemplate("custom_integration_test", context)

        assert "Integration Test Document" in doc.content
        assert "Testing custom template creation" in doc.content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
