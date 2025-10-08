"""
MAESTRO Quality Analysis Integration for Template Repository
Version: 1.0
Purpose: Extract high-quality code patterns and convert them to reusable templates
"""

import ast
import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from templates.enterprise_template_repository.template_manager import (
    ComplexityLevel,
    EnterpriseTemplateRepository,
    TemplateMetadata,
    TemplateStatus,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class QualityAnalysisResult:
    """Quality analysis result from existing pipeline"""

    file_path: str
    language: str
    quality_score: float
    security_score: int
    performance_score: int
    maintainability_score: int
    test_coverage: float
    issues: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    code_content: str


class TemplateExtractor:
    """
    Extracts reusable patterns from high-quality code analyzed by the quality pipeline

    Features:
    - Pattern recognition for common structures
    - Quality threshold filtering (>80 score)
    - Automatic categorization and tagging
    - Integration with existing MAESTRO quality tools
    """

    def __init__(self, repository: EnterpriseTemplateRepository, quality_threshold: float = 80.0):
        self.repository = repository
        self.quality_threshold = quality_threshold
        self.pattern_extractors = {
            "python": self._extract_python_patterns,
            "typescript": self._extract_typescript_patterns,
            "javascript": self._extract_javascript_patterns,
            "java": self._extract_java_patterns,
        }

    async def process_quality_analysis_result(
        self, analysis_result: QualityAnalysisResult
    ) -> List[str]:
        """
        Process quality analysis result and extract templates if quality is high enough

        Args:
            analysis_result: Result from quality analysis pipeline

        Returns:
            List of created template IDs
        """
        created_templates = []

        try:
            # Check if quality meets threshold
            if analysis_result.quality_score < self.quality_threshold:
                logger.info(
                    f"⏭️ Skipping {analysis_result.file_path}: Quality score {analysis_result.quality_score} below threshold {self.quality_threshold}"
                )
                return created_templates

            # Extract patterns from code
            patterns = await self._extract_patterns(analysis_result)

            # Create templates from patterns
            for pattern in patterns:
                if await self._is_template_worthy(pattern, analysis_result):
                    template_id = await self._create_template_from_pattern(pattern, analysis_result)
                    if template_id:
                        created_templates.append(template_id)

            logger.info(
                f"✅ Extracted {len(created_templates)} templates from {analysis_result.file_path}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to process quality analysis result: {e}")

        return created_templates

    async def _extract_patterns(
        self, analysis_result: QualityAnalysisResult
    ) -> List[Dict[str, Any]]:
        """Extract reusable patterns from code based on language"""
        language = analysis_result.language.lower()
        extractor = self.pattern_extractors.get(language)

        if not extractor:
            logger.warning(f"⚠️ No pattern extractor for language: {language}")
            return []

        try:
            return await extractor(analysis_result.code_content, analysis_result.file_path)
        except Exception as e:
            logger.error(f"❌ Pattern extraction failed for {language}: {e}")
            return []

    async def _extract_python_patterns(self, code: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract Python patterns (classes, functions, decorators)"""
        patterns = []

        try:
            tree = ast.parse(code)

            for node in ast.walk(tree):
                # Extract class patterns
                if isinstance(node, ast.ClassDef):
                    pattern = await self._extract_python_class_pattern(node, code)
                    if pattern:
                        patterns.append(pattern)

                # Extract function patterns
                elif isinstance(node, ast.FunctionDef):
                    pattern = await self._extract_python_function_pattern(node, code)
                    if pattern:
                        patterns.append(pattern)

                # Extract decorator patterns
                elif isinstance(node, ast.FunctionDef) and node.decorator_list:
                    pattern = await self._extract_python_decorator_pattern(node, code)
                    if pattern:
                        patterns.append(pattern)

        except SyntaxError as e:
            logger.warning(f"⚠️ Syntax error in Python code: {e}")

        return patterns

    async def _extract_python_class_pattern(
        self, node: ast.ClassDef, code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract Python class as template pattern"""
        # Get class source code
        try:
            lines = code.split("\n")
            start_line = node.lineno - 1
            end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line + 10

            class_source = "\n".join(lines[start_line:end_line])

            # Analyze class characteristics
            has_init = any(
                isinstance(n, ast.FunctionDef) and n.name == "__init__" for n in node.body
            )
            method_count = len([n for n in node.body if isinstance(n, ast.FunctionDef)])
            has_inheritance = len(node.bases) > 0
            has_decorators = len(node.decorator_list) > 0

            # Determine pattern category and complexity
            category = "classes"
            complexity = ComplexityLevel.SIMPLE

            if method_count > 5 or has_inheritance:
                complexity = ComplexityLevel.INTERMEDIATE
            if method_count > 10 or has_decorators:
                complexity = ComplexityLevel.ADVANCED

            # Generate tags
            tags = ["python", "class"]
            if has_init:
                tags.append("initialization")
            if has_inheritance:
                tags.append("inheritance")
            if has_decorators:
                tags.extend(["decorators", "metadata"])

            # Detect domain
            domain = self._detect_domain_from_code(class_source)

            return {
                "name": f"{node.name} Class Pattern",
                "category": category,
                "pattern_type": "class",
                "complexity": complexity,
                "domain": domain,
                "tags": tags,
                "source_code": class_source,
                "description": f"Reusable {node.name} class pattern with {method_count} methods",
                "ast_node_type": "ClassDef",
                "characteristics": {
                    "has_init": has_init,
                    "method_count": method_count,
                    "has_inheritance": has_inheritance,
                    "has_decorators": has_decorators,
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract class pattern: {e}")
            return None

    async def _extract_python_function_pattern(
        self, node: ast.FunctionDef, code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract Python function as template pattern"""
        try:
            lines = code.split("\n")
            start_line = node.lineno - 1
            end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line + 10

            func_source = "\n".join(lines[start_line:end_line])

            # Skip simple/trivial functions
            if len(func_source.split("\n")) < 3:
                return None

            # Analyze function characteristics
            param_count = len(node.args.args)
            is_async = isinstance(node, ast.AsyncFunctionDef)
            has_decorators = len(node.decorator_list) > 0
            has_type_hints = any(arg.annotation for arg in node.args.args)

            # Determine complexity
            complexity = ComplexityLevel.SIMPLE
            if param_count > 3 or has_decorators or is_async:
                complexity = ComplexityLevel.INTERMEDIATE
            if param_count > 6 or has_type_hints:
                complexity = ComplexityLevel.ADVANCED

            # Generate tags
            tags = ["python", "function"]
            if is_async:
                tags.append("async")
            if has_decorators:
                tags.append("decorators")
            if has_type_hints:
                tags.append("type-hints")

            # Detect domain
            domain = self._detect_domain_from_code(func_source)
            if not domain and "api" in node.name.lower():
                domain = "api"
            elif not domain and any(
                keyword in node.name.lower() for keyword in ["auth", "login", "user"]
            ):
                domain = "auth"

            return {
                "name": f"{node.name} Function Pattern",
                "category": "functions",
                "pattern_type": "function",
                "complexity": complexity,
                "domain": domain,
                "tags": tags,
                "source_code": func_source,
                "description": f"Reusable {node.name} function pattern with {param_count} parameters",
                "ast_node_type": "FunctionDef",
                "characteristics": {
                    "parameter_count": param_count,
                    "is_async": is_async,
                    "has_decorators": has_decorators,
                    "has_type_hints": has_type_hints,
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract function pattern: {e}")
            return None

    async def _extract_python_decorator_pattern(
        self, node: ast.FunctionDef, code: str
    ) -> Optional[Dict[str, Any]]:
        """Extract Python decorator pattern"""
        if not node.decorator_list:
            return None

        try:
            lines = code.split("\n")
            # Include decorators in the pattern
            decorator_start = node.decorator_list[0].lineno - 1
            func_end = node.end_lineno if hasattr(node, "end_lineno") else node.lineno + 10

            pattern_source = "\n".join(lines[decorator_start:func_end])

            # Extract decorator names
            decorator_names = []
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name):
                    decorator_names.append(decorator.id)
                elif isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                    decorator_names.append(decorator.func.id)

            tags = ["python", "decorators", "pattern"] + decorator_names

            # Detect common decorator patterns
            domain = None
            if any(dec in ["route", "app", "api"] for dec in decorator_names):
                domain = "api"
            elif any(dec in ["login_required", "auth", "permission"] for dec in decorator_names):
                domain = "auth"
            elif any(dec in ["cache", "memoize"] for dec in decorator_names):
                domain = "performance"

            return {
                "name": f"{' + '.join(decorator_names)} Decorator Pattern",
                "category": "decorators",
                "pattern_type": "decorator",
                "complexity": ComplexityLevel.INTERMEDIATE,
                "domain": domain,
                "tags": tags,
                "source_code": pattern_source,
                "description": f"Decorator pattern using {', '.join(decorator_names)}",
                "ast_node_type": "DecoratorPattern",
                "characteristics": {
                    "decorator_count": len(decorator_names),
                    "decorator_names": decorator_names,
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract decorator pattern: {e}")
            return None

    async def _extract_typescript_patterns(self, code: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract TypeScript patterns (interfaces, components, hooks)"""
        patterns = []

        try:
            # Extract React components
            component_matches = re.finditer(
                r"(?:export\s+)?(?:const|function)\s+(\w+)(?:\s*:\s*React\.FC(?:<[^>]*>)?|\s*\([^)]*\))\s*[=]?\s*(?:\([^)]*\))?\s*=>\s*\{",
                code,
                re.MULTILINE,
            )

            for match in component_matches:
                component_name = match.group(1)
                pattern = await self._extract_react_component_pattern(
                    component_name, code, match.start()
                )
                if pattern:
                    patterns.append(pattern)

            # Extract TypeScript interfaces
            interface_matches = re.finditer(
                r"(?:export\s+)?interface\s+(\w+)(?:\s*extends\s+[\w,\s]+)?\s*\{",
                code,
                re.MULTILINE,
            )

            for match in interface_matches:
                interface_name = match.group(1)
                pattern = await self._extract_typescript_interface_pattern(
                    interface_name, code, match.start()
                )
                if pattern:
                    patterns.append(pattern)

            # Extract custom hooks
            hook_matches = re.finditer(
                r"(?:export\s+)?(?:const|function)\s+(use\w+)", code, re.MULTILINE
            )

            for match in hook_matches:
                hook_name = match.group(1)
                pattern = await self._extract_react_hook_pattern(hook_name, code, match.start())
                if pattern:
                    patterns.append(pattern)

        except Exception as e:
            logger.error(f"❌ TypeScript pattern extraction failed: {e}")

        return patterns

    async def _extract_react_component_pattern(
        self, component_name: str, code: str, start_pos: int
    ) -> Optional[Dict[str, Any]]:
        """Extract React component as template pattern"""
        try:
            # Find component source
            lines = code.split("\n")
            start_line = code[:start_pos].count("\n")

            # Find component end (simplified heuristic)
            brace_count = 0
            end_line = start_line
            found_start = False

            for i, line in enumerate(lines[start_line:], start_line):
                for char in line:
                    if char == "{":
                        brace_count += 1
                        found_start = True
                    elif char == "}":
                        brace_count -= 1

                if found_start and brace_count == 0:
                    end_line = i
                    break

            component_source = "\n".join(lines[start_line : end_line + 1])

            # Analyze component characteristics
            has_props = "props" in component_source or ":" in component_source[:100]
            has_hooks = bool(re.search(r"use\w+\(", component_source))
            has_jsx = "<" in component_source and ">" in component_source
            line_count = len(component_source.split("\n"))

            # Determine complexity
            complexity = ComplexityLevel.SIMPLE
            if has_hooks or line_count > 20:
                complexity = ComplexityLevel.INTERMEDIATE
            if has_hooks and has_props and line_count > 50:
                complexity = ComplexityLevel.ADVANCED

            # Generate tags
            tags = ["typescript", "react", "component"]
            if has_props:
                tags.append("props")
            if has_hooks:
                tags.append("hooks")
            if has_jsx:
                tags.append("jsx")

            # Detect domain
            domain = self._detect_domain_from_code(component_source)
            if not domain:
                if any(
                    keyword in component_name.lower() for keyword in ["form", "input", "button"]
                ):
                    domain = "forms"
                elif any(
                    keyword in component_name.lower() for keyword in ["nav", "menu", "header"]
                ):
                    domain = "navigation"
                elif any(
                    keyword in component_name.lower() for keyword in ["auth", "login", "user"]
                ):
                    domain = "auth"

            return {
                "name": f"{component_name} React Component",
                "category": "components",
                "pattern_type": "react_component",
                "complexity": complexity,
                "domain": domain,
                "tags": tags,
                "source_code": component_source,
                "description": f"Reusable React component: {component_name}",
                "framework": "react",
                "characteristics": {
                    "has_props": has_props,
                    "has_hooks": has_hooks,
                    "has_jsx": has_jsx,
                    "line_count": line_count,
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract React component pattern: {e}")
            return None

    async def _extract_typescript_interface_pattern(
        self, interface_name: str, code: str, start_pos: int
    ) -> Optional[Dict[str, Any]]:
        """Extract TypeScript interface as template pattern"""
        try:
            # Find interface source
            lines = code.split("\n")
            start_line = code[:start_pos].count("\n")

            # Find interface end
            brace_count = 0
            end_line = start_line
            found_start = False

            for i, line in enumerate(lines[start_line:], start_line):
                for char in line:
                    if char == "{":
                        brace_count += 1
                        found_start = True
                    elif char == "}":
                        brace_count -= 1

                if found_start and brace_count == 0:
                    end_line = i
                    break

            interface_source = "\n".join(lines[start_line : end_line + 1])

            # Count properties
            property_count = len(re.findall(r"^\s*\w+[?]?:\s*", interface_source, re.MULTILINE))

            # Determine complexity
            complexity = ComplexityLevel.SIMPLE
            if property_count > 5:
                complexity = ComplexityLevel.INTERMEDIATE
            if property_count > 10 or "extends" in interface_source:
                complexity = ComplexityLevel.ADVANCED

            # Generate tags
            tags = ["typescript", "interface", "types"]

            # Detect domain
            domain = self._detect_domain_from_code(interface_source)

            return {
                "name": f"{interface_name} Interface",
                "category": "interfaces",
                "pattern_type": "typescript_interface",
                "complexity": complexity,
                "domain": domain,
                "tags": tags,
                "source_code": interface_source,
                "description": f"TypeScript interface: {interface_name} with {property_count} properties",
                "characteristics": {
                    "property_count": property_count,
                    "has_extends": "extends" in interface_source,
                    "has_optional": "?" in interface_source,
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract interface pattern: {e}")
            return None

    async def _extract_react_hook_pattern(
        self, hook_name: str, code: str, start_pos: int
    ) -> Optional[Dict[str, Any]]:
        """Extract React hook as template pattern"""
        try:
            # Find hook source (simplified)
            lines = code.split("\n")
            start_line = code[:start_pos].count("\n")

            # Find function end (simplified heuristic)
            brace_count = 0
            end_line = start_line + 20  # Default fallback
            found_start = False

            for i, line in enumerate(lines[start_line : start_line + 50], start_line):
                for char in line:
                    if char == "{":
                        brace_count += 1
                        found_start = True
                    elif char == "}":
                        brace_count -= 1

                if found_start and brace_count == 0:
                    end_line = i
                    break

            hook_source = "\n".join(lines[start_line : end_line + 1])

            # Analyze hook characteristics
            uses_state = "useState" in hook_source
            uses_effect = "useEffect" in hook_source
            uses_other_hooks = bool(re.search(r"use[A-Z]\w+", hook_source))

            # Determine complexity
            complexity = ComplexityLevel.INTERMEDIATE  # Hooks are generally intermediate
            if uses_effect and uses_state and uses_other_hooks:
                complexity = ComplexityLevel.ADVANCED

            # Generate tags
            tags = ["typescript", "react", "hooks", "custom-hook"]
            if uses_state:
                tags.append("state")
            if uses_effect:
                tags.append("effects")

            # Detect domain
            domain = self._detect_domain_from_code(hook_source)

            return {
                "name": f"{hook_name} Custom Hook",
                "category": "hooks",
                "pattern_type": "react_hook",
                "complexity": complexity,
                "domain": domain,
                "tags": tags,
                "source_code": hook_source,
                "description": f"Custom React hook: {hook_name}",
                "framework": "react",
                "characteristics": {
                    "uses_state": uses_state,
                    "uses_effect": uses_effect,
                    "uses_other_hooks": uses_other_hooks,
                },
            }

        except Exception as e:
            logger.error(f"❌ Failed to extract hook pattern: {e}")
            return None

    async def _extract_javascript_patterns(self, code: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract JavaScript patterns"""
        # Similar to TypeScript but without type annotations
        # Implementation would be similar to TypeScript extractor
        return []

    async def _extract_java_patterns(self, code: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract Java patterns (classes, methods, annotations)"""
        # Java pattern extraction would go here
        return []

    def _detect_domain_from_code(self, code: str) -> Optional[str]:
        """Detect business domain from code content"""
        code_lower = code.lower()

        # Authentication domain
        if any(
            keyword in code_lower
            for keyword in ["auth", "login", "password", "token", "jwt", "oauth"]
        ):
            return "auth"

        # API domain
        if any(
            keyword in code_lower for keyword in ["api", "endpoint", "request", "response", "http"]
        ):
            return "api"

        # E-commerce domain
        if any(
            keyword in code_lower for keyword in ["cart", "product", "order", "payment", "checkout"]
        ):
            return "e-commerce"

        # Dashboard domain
        if any(
            keyword in code_lower
            for keyword in ["dashboard", "analytics", "chart", "metric", "report"]
        ):
            return "dashboard"

        # Machine Learning domain
        if any(
            keyword in code_lower for keyword in ["model", "predict", "train", "tensor", "ml", "ai"]
        ):
            return "ml"

        # DevOps domain
        if any(
            keyword in code_lower for keyword in ["docker", "kubernetes", "deployment", "ci", "cd"]
        ):
            return "devops"

        return None

    async def _is_template_worthy(
        self, pattern: Dict[str, Any], analysis_result: QualityAnalysisResult
    ) -> bool:
        """Determine if pattern is worthy of being a template"""
        # Check minimum code length
        if len(pattern["source_code"].split("\n")) < 5:
            return False

        # Check if it's too generic/simple
        if (
            pattern.get("complexity") == ComplexityLevel.SIMPLE
            and len(pattern["source_code"]) < 200
        ):
            return False

        # Ensure it has good structure
        if not pattern.get("description") or len(pattern["description"]) < 10:
            return False

        # Check for domain classification
        if not pattern.get("domain") and not pattern.get("category"):
            return False

        return True

    async def _create_template_from_pattern(
        self, pattern: Dict[str, Any], analysis_result: QualityAnalysisResult
    ) -> Optional[str]:
        """Create template from extracted pattern"""
        try:
            metadata = TemplateMetadata(
                name=pattern["name"],
                category=pattern["category"],
                language=analysis_result.language,
                framework=pattern.get("framework"),
                domain=pattern.get("domain"),
                pattern=pattern.get("pattern_type"),
                description=pattern["description"],
                tags=pattern.get("tags", []),
                complexity=pattern.get("complexity", ComplexityLevel.INTERMEDIATE),
                status=TemplateStatus.DRAFT,
                created_by="MAESTRO_Quality_Pipeline",
                organization="MAESTRO",
                quality_score=analysis_result.quality_score,
                security_score=analysis_result.security_score,
                performance_score=analysis_result.performance_score,
                maintainability_score=analysis_result.maintainability_score,
                test_coverage=analysis_result.test_coverage,
            )

            # Generate basic test content
            test_content = await self._generate_test_template(pattern, analysis_result.language)

            # Generate usage examples
            examples = await self._generate_usage_examples(pattern)

            # Create template
            template_id = await self.repository.create_template(
                pattern["source_code"], metadata, test_content, examples
            )

            logger.info(f"✅ Created template {template_id} from pattern {pattern['name']}")
            return template_id

        except Exception as e:
            logger.error(f"❌ Failed to create template from pattern: {e}")
            return None

    async def _generate_test_template(self, pattern: Dict[str, Any], language: str) -> str:
        """Generate basic test template for the pattern"""
        if language.lower() == "python":
            return f"""import unittest
from unittest.mock import Mock, patch

class Test{pattern['name'].replace(' ', '')}(unittest.TestCase):
    \"\"\"Test cases for {pattern['name']}\"\"\"

    def setUp(self):
        \"\"\"Set up test fixtures\"\"\"
        pass

    def test_basic_functionality(self):
        \"\"\"Test basic functionality\"\"\"
        # TODO: Implement test
        pass

    def test_edge_cases(self):
        \"\"\"Test edge cases\"\"\"
        # TODO: Implement edge case tests
        pass

if __name__ == '__main__':
    unittest.main()
"""

        elif language.lower() in ["typescript", "javascript"]:
            return f"""import {{ describe, it, expect, beforeEach }} from '@jest/globals';

describe('{pattern['name']}', () => {{
    beforeEach(() => {{
        // Set up test fixtures
    }});

    it('should work with basic functionality', () => {{
        // TODO: Implement test
        expect(true).toBe(true);
    }});

    it('should handle edge cases', () => {{
        // TODO: Implement edge case tests
        expect(true).toBe(true);
    }});
}});
"""

        return "# Tests for this template would go here"

    async def _generate_usage_examples(self, pattern: Dict[str, Any]) -> Dict[str, str]:
        """Generate usage examples for the pattern"""
        examples = {}

        # Basic example
        examples[
            "basic"
        ] = f"""// Basic usage of {pattern['name']}
// This example shows the simplest way to use this pattern

{pattern['source_code'][:200]}...

// Usage:
// TODO: Add basic usage example
"""

        # Advanced example
        examples[
            "advanced"
        ] = f"""// Advanced usage of {pattern['name']}
// This example shows advanced customization options

// TODO: Add advanced usage example with configuration
"""

        # Integration example
        examples[
            "integration"
        ] = f"""// Integration example for {pattern['name']}
// This example shows how to integrate with other components

// TODO: Add integration example
"""

        return examples


# Integration function for existing quality pipeline
async def integrate_with_quality_pipeline(
    quality_results_dir: str = "/data/maestro-v1/quality_analysis_results",
    repository_path: str = "/data/maestro-v1/enterprise_template_repository",
):
    """
    Integration point for existing quality analysis pipeline

    This function should be called by the existing quality analysis system
    whenever a file with high quality score (>80) is analyzed.
    """

    # Initialize repository and extractor
    repository = EnterpriseTemplateRepository(repository_path)
    await repository.initialize()

    extractor = TemplateExtractor(repository)

    # Process quality analysis results
    results_path = Path(quality_results_dir)
    if results_path.exists():
        for result_file in results_path.glob("*.json"):
            try:
                with open(result_file, "r") as f:
                    result_data = json.load(f)

                # Convert to QualityAnalysisResult
                analysis_result = QualityAnalysisResult(
                    file_path=result_data["file_path"],
                    language=result_data["language"],
                    quality_score=result_data["quality_score"],
                    security_score=result_data.get("security_score", 85),
                    performance_score=result_data.get("performance_score", 85),
                    maintainability_score=result_data.get("maintainability_score", 85),
                    test_coverage=result_data.get("test_coverage", 0.0),
                    issues=result_data.get("issues", []),
                    metrics=result_data.get("metrics", {}),
                    code_content=result_data["code_content"],
                )

                # Extract templates
                created_templates = await extractor.process_quality_analysis_result(analysis_result)
                logger.info(
                    f"📄 Processed {result_file.name}: {len(created_templates)} templates created"
                )

            except Exception as e:
                logger.error(f"❌ Failed to process {result_file}: {e}")

    await repository.close()
    logger.info("✅ Quality pipeline integration completed")


# Example usage
async def main():
    """Example usage and testing"""

    # Sample quality analysis result
    sample_result = QualityAnalysisResult(
        file_path="/app/components/UserAuth.tsx",
        language="typescript",
        quality_score=92.5,
        security_score=95,
        performance_score=88,
        maintainability_score=90,
        test_coverage=85.0,
        issues=[],
        metrics={},
        code_content="""
import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

interface LoginFormProps {
    onSuccess?: () => void;
    className?: string;
}

export const LoginForm: React.FC<LoginFormProps> = ({ onSuccess, className }) => {
    const [credentials, setCredentials] = useState({ username: '', password: '' });
    const { login, isLoading } = useAuth();

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            await login(credentials);
            onSuccess?.();
        } catch (error) {
            console.error('Login failed:', error);
        }
    };

    return (
        <form onSubmit={handleSubmit} className={className}>
            <input
                type="text"
                value={credentials.username}
                onChange={(e) => setCredentials(prev => ({ ...prev, username: e.target.value }))}
                placeholder="Username"
                required
            />
            <input
                type="password"
                value={credentials.password}
                onChange={(e) => setCredentials(prev => ({ ...prev, password: e.target.value }))}
                placeholder="Password"
                required
            />
            <button type="submit" disabled={isLoading}>
                {isLoading ? 'Logging in...' : 'Login'}
            </button>
        </form>
    );
};
""",
    )

    # Initialize repository and extractor
    repository = EnterpriseTemplateRepository()
    await repository.initialize()

    extractor = TemplateExtractor(repository)

    # Process sample result
    created_templates = await extractor.process_quality_analysis_result(sample_result)
    print(f"✅ Created {len(created_templates)} templates")

    await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
