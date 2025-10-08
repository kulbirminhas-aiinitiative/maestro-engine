#!/usr/bin/env python3
"""
Persona Domain Mappings for RAG Integration
Maps each persona to their domain expertise, technologies, and template preferences
"""

from typing import Any, Dict, List

# Persona → Domain Tag Mappings
# Aligns with maestro-templates categories, languages, frameworks, and tags
PERSONA_DOMAINS: Dict[str, Dict[str, Any]] = {
    "requirement_analyst": {
        "tags": [
            "requirements",
            "user-stories",
            "acceptance-criteria",
            "specifications",
            "business-analysis",
            "documentation",
        ],
        "template_categories": ["documentation", "utility"],
        "template_types": [
            "requirement-template",
            "user-story-template",
            "acceptance-criteria",
            "specification-doc",
        ],
        "languages": ["markdown", "text"],
        "frameworks": [],
        "file_patterns": [r"requirement", r"user_stor", r"acceptance", r"spec", r"BRD", r"PRD"],
        "git_search_keywords": [
            "requirements template",
            "user story template",
            "BRD template",
            "PRD template",
        ],
    },
    "solution_architect": {
        "tags": [
            "architecture",
            "system-design",
            "tech-stack",
            "c4-diagram",
            "design-patterns",
            "scalability",
        ],
        "template_categories": ["architecture", "documentation"],
        "template_types": [
            "architecture-diagram",
            "tech-stack-template",
            "system-design",
            "c4-model",
            "design-doc",
        ],
        "languages": ["markdown", "plantuml", "mermaid"],
        "frameworks": [],
        "file_patterns": [r"architecture", r"design", r"system", r"tech_stack", r"c4", r"diagram"],
        "git_search_keywords": [
            "architecture template",
            "system design template",
            "C4 diagram",
            "tech stack template",
        ],
    },
    "ui_ux_designer": {
        "tags": [
            "ui",
            "ux",
            "design-system",
            "wireframes",
            "mockups",
            "figma",
            "user-journey",
            "prototyping",
        ],
        "template_categories": ["frontend", "design"],
        "template_types": [
            "design-system",
            "ui-component-library",
            "wireframe-kit",
            "user-journey-map",
            "style-guide",
        ],
        "languages": ["figma", "sketch", "css", "scss"],
        "frameworks": ["tailwindcss", "material-ui", "ant-design"],
        "file_patterns": [r"wireframe", r"mockup", r"design", r"ui", r"ux", r"style", r"theme"],
        "git_search_keywords": [
            "design system",
            "UI kit",
            "component library",
            "tailwind template",
            "material-ui theme",
        ],
    },
    "frontend_developer": {
        "tags": [
            "react",
            "vue",
            "angular",
            "typescript",
            "javascript",
            "nextjs",
            "tailwindcss",
            "component",
            "hooks",
            "state-management",
        ],
        "template_categories": ["frontend", "web_app"],
        "template_types": [
            "react-component",
            "vue-component",
            "page-template",
            "hook",
            "utility",
            "layout",
            "form",
            "dashboard",
        ],
        "languages": ["javascript", "typescript"],
        "frameworks": [
            "react",
            "vue",
            "angular",
            "nextjs",
            "svelte",
            "tailwindcss",
            "bootstrap",
            "material-ui",
        ],
        "file_patterns": [
            r"component",
            r"page",
            r"ui",
            r"\.jsx",
            r"\.tsx",
            r"\.vue",
            r"hooks",
            r"context",
        ],
        "git_search_keywords": [
            "react component",
            "vue component",
            "nextjs template",
            "react hooks",
            "tailwind component",
            "dashboard template",
        ],
    },
    "backend_developer": {
        "tags": [
            "fastapi",
            "flask",
            "django",
            "express",
            "nodejs",
            "api",
            "rest",
            "graphql",
            "microservice",
            "service",
            "authentication",
            "authorization",
            "crud",
            "orm",
        ],
        "template_categories": ["api", "backend", "microservice"],
        "template_types": [
            "api-endpoint",
            "service",
            "controller",
            "model",
            "middleware",
            "authentication",
            "crud-api",
            "graphql-schema",
        ],
        "languages": ["python", "javascript", "typescript", "java", "go"],
        "frameworks": ["fastapi", "flask", "django", "express", "nestjs", "spring", "gin", "fiber"],
        "file_patterns": [
            r"api",
            r"service",
            r"controller",
            r"model",
            r"\.py",
            r"\.java",
            r"\.go",
            r"endpoint",
            r"route",
        ],
        "git_search_keywords": [
            "fastapi template",
            "express api",
            "microservice template",
            "rest api template",
            "graphql server",
            "crud api",
        ],
    },
    "database_administrator": {
        "tags": [
            "postgresql",
            "mysql",
            "mongodb",
            "redis",
            "sql",
            "nosql",
            "migration",
            "schema",
            "indexing",
            "optimization",
        ],
        "template_categories": ["database", "infrastructure"],
        "template_types": [
            "schema",
            "migration",
            "seed-data",
            "query",
            "index-strategy",
            "backup-script",
        ],
        "languages": ["sql", "plpgsql", "nosql"],
        "frameworks": ["postgresql", "mysql", "mongodb", "redis", "alembic", "flyway", "liquibase"],
        "file_patterns": [r"schema", r"migration", r"\.sql", r"database", r"seed", r"fixture"],
        "git_search_keywords": [
            "database schema",
            "migration template",
            "sql template",
            "postgres schema",
            "mongodb schema",
        ],
    },
    "qa_engineer": {
        "tags": [
            "testing",
            "pytest",
            "jest",
            "cypress",
            "selenium",
            "unit-test",
            "integration-test",
            "e2e-test",
            "test-automation",
        ],
        "template_categories": ["testing", "utility"],
        "template_types": [
            "unit-test",
            "integration-test",
            "e2e-test",
            "test-fixture",
            "test-suite",
            "test-data",
        ],
        "languages": ["python", "javascript", "typescript"],
        "frameworks": [
            "pytest",
            "jest",
            "vitest",
            "cypress",
            "playwright",
            "selenium",
            "testing-library",
        ],
        "file_patterns": [r"test", r"spec", r"\.test\.", r"\.spec\.", r"fixture", r"mock"],
        "git_search_keywords": [
            "test template",
            "pytest template",
            "jest template",
            "cypress test",
            "e2e test template",
        ],
    },
    "security_specialist": {
        "tags": [
            "security",
            "authentication",
            "authorization",
            "oauth",
            "jwt",
            "encryption",
            "vulnerability",
            "audit",
            "compliance",
        ],
        "template_categories": ["security", "utility"],
        "template_types": [
            "authentication",
            "authorization",
            "oauth-flow",
            "jwt-implementation",
            "security-middleware",
            "audit-log",
        ],
        "languages": ["python", "javascript", "go"],
        "frameworks": ["oauth2", "jwt", "passport", "auth0"],
        "file_patterns": [
            r"security",
            r"audit",
            r"vulnerability",
            r"auth",
            r"oauth",
            r"jwt",
            r"encrypt",
        ],
        "git_search_keywords": [
            "authentication template",
            "oauth implementation",
            "jwt template",
            "security middleware",
            "audit log",
        ],
    },
    "devops_engineer": {
        "tags": [
            "kubernetes",
            "docker",
            "terraform",
            "ansible",
            "cicd",
            "github-actions",
            "jenkins",
            "deployment",
            "infrastructure",
            "monitoring",
            "prometheus",
            "grafana",
        ],
        "template_categories": ["infrastructure", "devops", "cicd"],
        "template_types": [
            "dockerfile",
            "docker-compose",
            "k8s-manifest",
            "terraform-module",
            "ansible-playbook",
            "cicd-pipeline",
            "monitoring-config",
        ],
        "languages": ["yaml", "hcl", "bash", "dockerfile"],
        "frameworks": [
            "kubernetes",
            "docker",
            "terraform",
            "ansible",
            "github-actions",
            "gitlab-ci",
            "jenkins",
        ],
        "file_patterns": [
            r"docker",
            r"kubernetes",
            r"k8s",
            r"terraform",
            r"ansible",
            r"pipeline",
            r"deploy",
            r"ci",
            r"\.yaml",
        ],
        "git_search_keywords": [
            "dockerfile template",
            "kubernetes manifest",
            "terraform module",
            "github actions workflow",
            "docker-compose template",
            "ci/cd pipeline",
        ],
    },
    "technical_writer": {
        "tags": [
            "documentation",
            "readme",
            "api-docs",
            "tutorial",
            "guide",
            "markdown",
            "openapi",
            "swagger",
        ],
        "template_categories": ["documentation"],
        "template_types": [
            "readme-template",
            "api-documentation",
            "user-guide",
            "tutorial",
            "changelog",
            "contributing-guide",
        ],
        "languages": ["markdown", "asciidoc", "restructuredtext"],
        "frameworks": ["mkdocs", "docusaurus", "sphinx"],
        "file_patterns": [r"README", r"documentation", r"guide", r"tutorial", r"\.md", r"docs"],
        "git_search_keywords": [
            "readme template",
            "documentation template",
            "api docs template",
            "user guide template",
        ],
    },
    "deployment_specialist": {
        "tags": [
            "deployment",
            "aws",
            "azure",
            "gcp",
            "cloudformation",
            "cdk",
            "serverless",
            "lambda",
            "container",
            "ecs",
            "fargate",
        ],
        "template_categories": ["infrastructure", "deployment"],
        "template_types": [
            "deployment-config",
            "cloudformation-template",
            "cdk-stack",
            "serverless-config",
            "lambda-function",
            "ecs-task",
        ],
        "languages": ["yaml", "json", "typescript", "python"],
        "frameworks": ["aws-cdk", "cloudformation", "serverless", "pulumi", "aws-sam"],
        "file_patterns": [
            r"deploy",
            r"cloudformation",
            r"cdk",
            r"serverless",
            r"lambda",
            r"ecs",
            r"fargate",
        ],
        "git_search_keywords": [
            "cloudformation template",
            "cdk template",
            "serverless template",
            "lambda template",
            "ecs deployment",
        ],
    },
}


# Reverse mapping: Category → Personas
CATEGORY_TO_PERSONAS: Dict[str, List[str]] = {
    "api": ["backend_developer", "solution_architect"],
    "backend": ["backend_developer", "database_administrator"],
    "frontend": ["frontend_developer", "ui_ux_designer"],
    "web_app": ["frontend_developer", "ui_ux_designer"],
    "microservice": ["backend_developer", "solution_architect"],
    "database": ["database_administrator", "backend_developer"],
    "infrastructure": ["devops_engineer", "deployment_specialist", "database_administrator"],
    "devops": ["devops_engineer", "deployment_specialist"],
    "cicd": ["devops_engineer"],
    "testing": ["qa_engineer"],
    "security": ["security_specialist", "backend_developer"],
    "documentation": ["technical_writer", "requirement_analyst", "solution_architect"],
    "design": ["ui_ux_designer"],
    "architecture": ["solution_architect"],
    "utility": ["backend_developer", "frontend_developer", "qa_engineer"],
}


# Language → Personas
LANGUAGE_TO_PERSONAS: Dict[str, List[str]] = {
    "python": ["backend_developer", "qa_engineer", "deployment_specialist"],
    "javascript": ["frontend_developer", "backend_developer", "qa_engineer"],
    "typescript": ["frontend_developer", "backend_developer", "deployment_specialist"],
    "java": ["backend_developer"],
    "go": ["backend_developer", "security_specialist"],
    "sql": ["database_administrator", "backend_developer"],
    "yaml": ["devops_engineer", "deployment_specialist"],
    "dockerfile": ["devops_engineer"],
    "hcl": ["devops_engineer", "deployment_specialist"],
    "markdown": ["technical_writer", "requirement_analyst", "solution_architect"],
}


# Framework → Personas
FRAMEWORK_TO_PERSONAS: Dict[str, List[str]] = {
    "react": ["frontend_developer"],
    "vue": ["frontend_developer"],
    "angular": ["frontend_developer"],
    "nextjs": ["frontend_developer"],
    "fastapi": ["backend_developer"],
    "flask": ["backend_developer"],
    "django": ["backend_developer"],
    "express": ["backend_developer"],
    "nestjs": ["backend_developer"],
    "kubernetes": ["devops_engineer"],
    "docker": ["devops_engineer"],
    "terraform": ["devops_engineer", "deployment_specialist"],
    "postgresql": ["database_administrator"],
    "mongodb": ["database_administrator"],
    "pytest": ["qa_engineer"],
    "jest": ["qa_engineer", "frontend_developer"],
    "cypress": ["qa_engineer"],
    "oauth2": ["security_specialist"],
    "jwt": ["security_specialist", "backend_developer"],
}


def get_persona_domain(persona_id: str) -> Dict[str, Any]:
    """
    Get domain information for a persona

    Args:
        persona_id: Persona identifier

    Returns:
        Domain mapping dict
    """
    return PERSONA_DOMAINS.get(
        persona_id,
        {
            "tags": [],
            "template_categories": [],
            "template_types": [],
            "languages": [],
            "frameworks": [],
            "file_patterns": [],
            "git_search_keywords": [],
        },
    )


def get_personas_for_category(category: str) -> List[str]:
    """
    Get personas associated with a template category

    Args:
        category: Template category

    Returns:
        List of persona IDs
    """
    return CATEGORY_TO_PERSONAS.get(category, [])


def get_personas_for_language(language: str) -> List[str]:
    """
    Get personas associated with a programming language

    Args:
        language: Programming language

    Returns:
        List of persona IDs
    """
    return LANGUAGE_TO_PERSONAS.get(language.lower(), [])


def get_personas_for_framework(framework: str) -> List[str]:
    """
    Get personas associated with a framework

    Args:
        framework: Framework name

    Returns:
        List of persona IDs
    """
    return FRAMEWORK_TO_PERSONAS.get(framework.lower(), [])


def match_template_to_persona(template_metadata: Dict[str, Any]) -> List[str]:
    """
    Match a maestro-template to relevant personas

    Args:
        template_metadata: Template metadata dict from maestro-templates

    Returns:
        List of matching persona IDs, sorted by relevance
    """
    from collections import Counter

    persona_scores = Counter()

    # Match by category
    category = template_metadata.get("category", "")
    if category:
        for persona in get_personas_for_category(category):
            persona_scores[persona] += 3  # High weight for category match

    # Match by language
    language = template_metadata.get("language", "")
    if language:
        for persona in get_personas_for_language(language):
            persona_scores[persona] += 2  # Medium weight for language match

    # Match by framework
    framework = template_metadata.get("framework", "")
    if framework:
        for persona in get_personas_for_framework(framework):
            persona_scores[persona] += 2  # Medium weight for framework match

    # Match by tags
    tags = template_metadata.get("tags", [])
    for tag in tags:
        for persona_id, domain in PERSONA_DOMAINS.items():
            if tag in domain["tags"]:
                persona_scores[persona_id] += 1  # Low weight for tag match

    # Return personas sorted by score
    return [persona for persona, _ in persona_scores.most_common()]


def get_relevant_templates_for_persona(
    persona_id: str, all_templates: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Filter templates relevant to a persona

    Args:
        persona_id: Persona identifier
        all_templates: List of template metadata dicts

    Returns:
        Filtered and sorted list of templates
    """
    domain = get_persona_domain(persona_id)
    relevant_templates = []

    for template in all_templates:
        score = 0

        # Category match
        if template.get("category") in domain["template_categories"]:
            score += 5

        # Language match
        if template.get("language") in domain["languages"]:
            score += 3

        # Framework match
        if template.get("framework") in domain["frameworks"]:
            score += 3

        # Tag matches
        template_tags = set(template.get("tags", []))
        domain_tags = set(domain["tags"])
        tag_overlap = len(template_tags & domain_tags)
        score += tag_overlap

        if score > 0:
            template_with_score = template.copy()
            template_with_score["_relevance_score"] = score
            relevant_templates.append(template_with_score)

    # Sort by relevance score descending
    return sorted(relevant_templates, key=lambda t: t["_relevance_score"], reverse=True)


# Default SDLC team (fallback when no recommendations available)
DEFAULT_SDLC_TEAM = [
    "requirement_analyst",
    "solution_architect",
    "frontend_developer",
    "backend_developer",
    "database_administrator",
    "qa_engineer",
    "devops_engineer",
    "technical_writer",
]
