"""
Workflow Template Extractor

Analyzes completed workflows and extracts reusable templates for the MAESTRO template library.
"""

import os
import json
import yaml
import httpx
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import Counter

logger = logging.getLogger(__name__)


class WorkflowTemplateExtractor:
    """
    Extracts templates from successful workflow executions.

    Features:
    - Analyzes project structure and tech stack
    - Generates template metadata
    - Creates Jinja2 templates with variables
    - Publishes to Template Registry
    - Updates RAG cache for immediate discovery
    """

    # Quality threshold for template extraction
    MIN_QUALITY_THRESHOLD = 0.80

    # Template Registry configuration
    TEMPLATE_REGISTRY_URL = "http://localhost:9600"
    TEMPLATE_REGISTRY_API_KEY = "maestro-dev-api-key-12345"

    def __init__(
        self,
        registry_url: str = None,
        api_key: str = None,
        templates_storage_dir: str = None
    ):
        """
        Initialize template extractor.

        Args:
            registry_url: Template Registry API URL
            api_key: API key for registry authentication
            templates_storage_dir: Directory to store generated templates
        """
        self.registry_url = registry_url or os.getenv(
            "TEMPLATE_REGISTRY_URL",
            self.TEMPLATE_REGISTRY_URL
        )
        self.api_key = api_key or os.getenv(
            "MAESTRO_TEMPLATES_API_KEY",
            self.TEMPLATE_REGISTRY_API_KEY
        )
        self.templates_storage_dir = Path(templates_storage_dir or
            "/home/ec2-user/projects/maestro-platform/maestro-templates/storage/templates"
        )

        # Ensure storage directory exists
        self.templates_storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📦 Template Extractor initialized")
        logger.info(f"   Registry: {self.registry_url}")
        logger.info(f"   Storage: {self.templates_storage_dir}")

    async def review_and_extract(
        self,
        workflow_id: str,
        project_name: str,
        requirement: str,
        work_dir: Path,
        phase_quality_scores: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """
        Review completed workflow and extract template if quality meets threshold.

        Args:
            workflow_id: Workflow identifier
            project_name: Project name
            requirement: Original requirement
            work_dir: Workflow working directory
            phase_quality_scores: Quality scores per phase

        Returns:
            Template metadata if extracted, None otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info(f"🔍 POST-EXECUTION REVIEW: {workflow_id}")
        logger.info(f"{'='*80}")

        # Calculate average quality score
        avg_quality = sum(phase_quality_scores.values()) / len(phase_quality_scores)
        logger.info(f"   Average quality: {avg_quality*100:.1f}%")

        # Check if quality meets threshold
        if avg_quality < self.MIN_QUALITY_THRESHOLD:
            logger.info(f"⚠️  Quality below threshold ({self.MIN_QUALITY_THRESHOLD*100}%), skipping template extraction")
            return None

        logger.info(f"✅ Quality meets threshold! Extracting template...")

        try:
            # Analyze project structure
            analysis = self._analyze_project_structure(work_dir)
            logger.info(f"📊 Project analysis complete:")
            logger.info(f"   Tech stack: {analysis['tech_stack']}")
            logger.info(f"   Category: {analysis['category']}")
            logger.info(f"   Files analyzed: {analysis['file_count']}")

            # Generate template metadata
            template_metadata = self._generate_template_metadata(
                project_name=project_name,
                requirement=requirement,
                workflow_id=workflow_id,
                analysis=analysis,
                quality_score=avg_quality
            )

            # Create template package
            template_path = await self._create_template_package(
                template_metadata=template_metadata,
                work_dir=work_dir,
                analysis=analysis
            )

            # Publish to registry
            published = await self._publish_to_registry(
                template_metadata=template_metadata,
                template_path=template_path
            )

            if published:
                logger.info(f"✅ Template published successfully!")
                logger.info(f"   Name: {template_metadata['name']}")
                logger.info(f"   Location: {template_path}")
                logger.info(f"   Registry: {self.registry_url}")

                # Trigger RAG cache update
                await self._update_rag_cache(template_metadata)

                return template_metadata
            else:
                logger.warning(f"⚠️  Template creation succeeded but publishing failed")
                return None

        except Exception as e:
            logger.error(f"❌ Template extraction failed: {e}", exc_info=True)
            return None

    def _analyze_project_structure(self, work_dir: Path) -> Dict[str, Any]:
        """
        Analyze project structure to determine tech stack and category.

        Args:
            work_dir: Project working directory

        Returns:
            Analysis results
        """
        analysis = {
            "tech_stack": [],
            "languages": [],
            "frameworks": [],
            "category": "utility",
            "file_count": 0,
            "file_types": Counter(),
            "has_tests": False,
            "has_docs": False,
            "has_docker": False,
            "has_k8s": False,
        }

        # Scan all files
        for phase_dir in work_dir.iterdir():
            if not phase_dir.is_dir() or phase_dir.name.startswith('.'):
                continue

            for file_path in phase_dir.rglob("*"):
                if file_path.is_file():
                    analysis["file_count"] += 1

                    # Count file types
                    ext = file_path.suffix.lower()
                    if ext:
                        analysis["file_types"][ext] += 1

                    # Detect specific patterns
                    file_name = file_path.name.lower()

                    # Language detection
                    if ext == ".py":
                        analysis["languages"].append("python")
                    elif ext in [".js", ".jsx"]:
                        analysis["languages"].append("javascript")
                    elif ext in [".ts", ".tsx"]:
                        analysis["languages"].append("typescript")
                    elif ext == ".go":
                        analysis["languages"].append("go")
                    elif ext == ".java":
                        analysis["languages"].append("java")
                    elif ext == ".rs":
                        analysis["languages"].append("rust")

                    # Framework detection
                    if "package.json" in file_name:
                        content = file_path.read_text()
                        if "react" in content.lower():
                            analysis["frameworks"].append("react")
                        if "express" in content.lower():
                            analysis["frameworks"].append("express")
                        if "next" in content.lower():
                            analysis["frameworks"].append("nextjs")

                    if "requirements.txt" in file_name or "pyproject.toml" in file_name:
                        content = file_path.read_text()
                        if "fastapi" in content.lower():
                            analysis["frameworks"].append("fastapi")
                        if "django" in content.lower():
                            analysis["frameworks"].append("django")
                        if "flask" in content.lower():
                            analysis["frameworks"].append("flask")

                    # Feature detection
                    if "test" in file_name or file_path.parent.name == "tests":
                        analysis["has_tests"] = True
                    if "readme" in file_name or file_path.parent.name == "docs":
                        analysis["has_docs"] = True
                    if "dockerfile" in file_name:
                        analysis["has_docker"] = True
                    if file_name.endswith((".yaml", ".yml")) and "kubernetes" in file_path.parent.name.lower():
                        analysis["has_k8s"] = True

        # Deduplicate and build tech stack
        analysis["languages"] = list(set(analysis["languages"]))
        analysis["frameworks"] = list(set(analysis["frameworks"]))
        analysis["tech_stack"] = analysis["languages"] + analysis["frameworks"]

        # Determine category
        if any(fw in analysis["frameworks"] for fw in ["react", "nextjs", "vue"]):
            analysis["category"] = "frontend"
        elif any(fw in analysis["frameworks"] for fw in ["fastapi", "express", "django", "flask"]):
            analysis["category"] = "backend"
        elif analysis["has_k8s"]:
            analysis["category"] = "microservice"
        else:
            analysis["category"] = "fullstack"

        return analysis

    def _generate_template_metadata(
        self,
        project_name: str,
        requirement: str,
        workflow_id: str,
        analysis: Dict[str, Any],
        quality_score: float
    ) -> Dict[str, Any]:
        """
        Generate template metadata from workflow analysis.

        Args:
            project_name: Project name
            requirement: Original requirement
            workflow_id: Workflow ID
            analysis: Project analysis results
            quality_score: Average quality score

        Returns:
            Template metadata
        """
        # Generate template name
        template_name = f"workflow-{project_name}".lower().replace("_", "-")

        # Extract tags from requirement and analysis
        tags = []
        tags.extend(analysis["languages"])
        tags.extend(analysis["frameworks"])
        tags.append(analysis["category"])

        # Add feature tags
        if analysis["has_tests"]:
            tags.append("testing")
        if analysis["has_docker"]:
            tags.append("docker")
        if analysis["has_k8s"]:
            tags.append("kubernetes")

        # Extract key concepts from requirement
        requirement_lower = requirement.lower()
        if "auth" in requirement_lower:
            tags.append("authentication")
        if "api" in requirement_lower:
            tags.append("api")
        if "database" in requirement_lower or "db" in requirement_lower:
            tags.append("database")
        if "ui" in requirement_lower or "interface" in requirement_lower:
            tags.append("ui")

        tags = list(set(tags))  # Deduplicate

        # Determine complexity
        complexity = "intermediate"
        if analysis["file_count"] < 10:
            complexity = "simple"
        elif analysis["file_count"] > 50:
            complexity = "advanced"
        if analysis["has_k8s"] or len(analysis["frameworks"]) > 2:
            complexity = "advanced"

        # Generate description
        primary_lang = analysis["languages"][0] if analysis["languages"] else "unknown"
        primary_framework = analysis["frameworks"][0] if analysis["frameworks"] else None

        description = f"Generated from successful workflow execution. "
        if primary_framework:
            description += f"{primary_framework.title()} {analysis['category']} application"
        else:
            description += f"{primary_lang.title()} {analysis['category']} application"

        metadata = {
            "name": template_name,
            "description": description,
            "version": "1.0.0",
            "author": "MAESTRO Workflow System",
            "organization": "MAESTRO Platform",
            "language": primary_lang,
            "framework": primary_framework,
            "category": analysis["category"],
            "tags": tags,
            "complexity": complexity,
            "quality_score": int(quality_score * 100),
            "source_workflow_id": workflow_id,
            "tech_stack": analysis["tech_stack"],
            "features": {
                "testing": analysis["has_tests"],
                "documentation": analysis["has_docs"],
                "docker": analysis["has_docker"],
                "kubernetes": analysis["has_k8s"]
            },
            "created_at": datetime.utcnow().isoformat() + "Z",
            "usage_stats": {
                "downloads": 0,
                "successful_uses": 0,
                "rating": 0.0
            }
        }

        return metadata

    async def _create_template_package(
        self,
        template_metadata: Dict[str, Any],
        work_dir: Path,
        analysis: Dict[str, Any]
    ) -> Path:
        """
        Create template package with manifest and files.

        Args:
            template_metadata: Template metadata
            work_dir: Workflow working directory
            analysis: Project analysis

        Returns:
            Path to created template
        """
        template_name = template_metadata["name"]
        template_dir = self.templates_storage_dir / template_name
        template_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"📦 Creating template package: {template_dir}")

        # Create manifest.yaml
        manifest = {
            **template_metadata,
            "templating_engine": "jinja2",
            "variables": [
                {
                    "name": "project_name",
                    "description": "Name of the project",
                    "type": "string",
                    "required": True,
                    "default": "my-project"
                },
                {
                    "name": "author",
                    "description": "Author name",
                    "type": "string",
                    "required": False,
                    "default": "MAESTRO User"
                },
                {
                    "name": "description",
                    "description": "Project description",
                    "type": "string",
                    "required": False,
                    "default": template_metadata["description"]
                }
            ]
        }

        manifest_path = template_dir / "manifest.yaml"
        with open(manifest_path, 'w') as f:
            yaml.dump(manifest, f, default_flow_style=False, sort_keys=False)

        logger.info(f"✓ Created manifest.yaml")

        # Create README.md
        readme_content = f"""# {template_name}

{template_metadata['description']}

## Features

- Tech Stack: {', '.join(template_metadata['tech_stack'])}
- Category: {template_metadata['category']}
- Quality Score: {template_metadata['quality_score']}/100
- Complexity: {template_metadata['complexity']}

## Generated From

This template was automatically generated from a successful MAESTRO workflow execution.

- Workflow ID: {template_metadata['source_workflow_id']}
- Generated: {template_metadata['created_at']}

## Usage

Use this template with MAESTRO to quickly bootstrap similar projects.

```bash
# Via MAESTRO Platform
curl -X POST http://localhost:5001/api/workflow/execute \\
  -H "Content-Type: application/json" \\
  -d '{{
    "project_name": "my-{template_metadata['category']}-app",
    "requirement": "Create a similar project using template {template_name}",
    "mode": "mixed"
  }}'
```

## Tags

{', '.join([f'`{tag}`' for tag in template_metadata['tags']])}

## License

MIT License
"""

        (template_dir / "README.md").write_text(readme_content)
        logger.info(f"✓ Created README.md")

        # Copy representative files from workflow (deployment phase)
        deployment_dir = work_dir / "deployment"
        if deployment_dir.exists():
            examples_dir = template_dir / "examples"
            examples_dir.mkdir(exist_ok=True)

            # Copy up to 10 most relevant files
            files_copied = 0
            for file_path in deployment_dir.rglob("*"):
                if file_path.is_file() and files_copied < 10:
                    rel_path = file_path.relative_to(deployment_dir)
                    dest_path = examples_dir / rel_path
                    dest_path.parent.mkdir(parents=True, exist_ok=True)

                    # Copy file
                    import shutil
                    shutil.copy2(file_path, dest_path)
                    files_copied += 1

            logger.info(f"✓ Copied {files_copied} example files")

        logger.info(f"✅ Template package created: {template_dir}")
        return template_dir

    async def _publish_to_registry(
        self,
        template_metadata: Dict[str, Any],
        template_path: Path
    ) -> bool:
        """
        Publish template to central registry.

        Args:
            template_metadata: Template metadata
            template_path: Path to template package

        Returns:
            True if published successfully
        """
        logger.info(f"📤 Publishing to registry: {self.registry_url}")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Check if template already exists
                response = await client.get(
                    f"{self.registry_url}/api/v1/templates/{template_metadata['name']}",
                    headers={"X-API-Key": self.api_key}
                )

                if response.status_code == 200:
                    logger.info(f"⚠️  Template already exists, updating...")
                    # Update existing template
                    response = await client.put(
                        f"{self.registry_url}/api/v1/templates/{template_metadata['name']}",
                        headers={"X-API-Key": self.api_key},
                        json=template_metadata
                    )
                else:
                    # Create new template
                    response = await client.post(
                        f"{self.registry_url}/api/v1/templates",
                        headers={"X-API-Key": self.api_key},
                        json=template_metadata
                    )

                if response.status_code in [200, 201]:
                    logger.info(f"✅ Published to registry successfully")
                    return True
                else:
                    logger.error(f"❌ Registry returned status {response.status_code}: {response.text}")
                    return False

        except httpx.ConnectError:
            logger.warning(f"⚠️  Could not connect to registry at {self.registry_url}")
            logger.info(f"   Template saved locally at: {template_path}")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to publish to registry: {e}")
            return False

    async def _update_rag_cache(self, template_metadata: Dict[str, Any]):
        """
        Trigger RAG cache update for immediate template discovery.

        Args:
            template_metadata: Template metadata
        """
        logger.info(f"🔄 Triggering RAG cache update...")

        try:
            # RAG cache should automatically pick up new templates
            # from the templates storage directory
            logger.info(f"✅ Template will be available in RAG on next cache refresh")
            logger.info(f"   Cache dir: /tmp/maestro_rag_cache")

            # TODO: Implement immediate cache invalidation/update
            # This could call a RAG service endpoint to force refresh

        except Exception as e:
            logger.warning(f"⚠️  RAG cache update failed: {e}")
