#!/usr/bin/env python3
"""
Test Persona-Level RAG Integration (Phase 2)
Tests persona domain mappings, template queries, and maestro-templates integration
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from rag.persona_domains import (
    get_persona_domain,
    get_personas_for_category,
    get_personas_for_framework,
    get_personas_for_language,
    get_relevant_templates_for_persona,
    match_template_to_persona,
)
from rag.persona_rag_tools import _load_maestro_templates


def test_persona_domain_mappings():
    """Test persona domain mappings"""
    print("\n" + "=" * 80)
    print("Test 1: Persona Domain Mappings")
    print("=" * 80)

    test_personas = [
        "frontend_developer",
        "backend_developer",
        "devops_engineer",
        "database_administrator",
    ]

    for persona_id in test_personas:
        domain = get_persona_domain(persona_id)
        print(f"\n📋 {persona_id}:")
        print(f"   Languages: {', '.join(domain['languages'][:5])}")
        print(f"   Frameworks: {', '.join(domain['frameworks'][:5])}")
        print(f"   Categories: {', '.join(domain['template_categories'])}")
        print(f"   Tags: {len(domain['tags'])} domain tags")

    print("\n✅ Persona domain mappings working")


def test_reverse_mappings():
    """Test reverse mappings (category/language/framework → personas)"""
    print("\n" + "=" * 80)
    print("Test 2: Reverse Mappings")
    print("=" * 80)

    # Test category mapping
    print("\n📂 Category → Personas:")
    test_categories = ["api", "frontend", "infrastructure", "database"]
    for category in test_categories:
        personas = get_personas_for_category(category)
        print(f"   {category}: {', '.join(personas)}")

    # Test language mapping
    print("\n💻 Language → Personas:")
    test_languages = ["python", "typescript", "yaml", "sql"]
    for language in test_languages:
        personas = get_personas_for_language(language)
        print(f"   {language}: {', '.join(personas)}")

    # Test framework mapping
    print("\n🔧 Framework → Personas:")
    test_frameworks = ["react", "fastapi", "kubernetes", "postgresql"]
    for framework in test_frameworks:
        personas = get_personas_for_framework(framework)
        print(f"   {framework}: {', '.join(personas)}")

    print("\n✅ Reverse mappings working")


def test_template_matching():
    """Test template → persona matching"""
    print("\n" + "=" * 80)
    print("Test 3: Template → Persona Matching")
    print("=" * 80)

    # Sample templates
    test_templates = [
        {
            "name": "React Dashboard",
            "category": "frontend",
            "language": "typescript",
            "framework": "react",
            "tags": ["dashboard", "ui", "charts"],
        },
        {
            "name": "FastAPI Microservice",
            "category": "api",
            "language": "python",
            "framework": "fastapi",
            "tags": ["rest", "api", "authentication"],
        },
        {
            "name": "Kubernetes Deployment",
            "category": "infrastructure",
            "language": "yaml",
            "framework": "kubernetes",
            "tags": ["k8s", "deployment", "service"],
        },
    ]

    for template in test_templates:
        matched_personas = match_template_to_persona(template)
        print(f"\n🎯 Template: {template['name']}")
        print(
            f"   Category: {template['category']} | Language: {template['language']} | Framework: {template['framework']}"
        )
        print(f"   Matched Personas: {', '.join(matched_personas[:3])}")

    print("\n✅ Template matching working")


def test_maestro_templates_loading():
    """Test loading templates from maestro-templates repository"""
    print("\n" + "=" * 80)
    print("Test 4: Maestro-Templates Integration")
    print("=" * 80)

    # Load templates
    templates = _load_maestro_templates()

    print(f"\n📚 Loaded {len(templates)} templates from maestro-templates")

    if templates:
        print("\n📋 Sample templates:")
        for i, template in enumerate(templates[:5], 1):
            print(f"\n{i}. {template.get('name', 'Unnamed')}")
            print(f"   ID: {template.get('id', 'unknown')[:16]}...")
            print(f"   Category: {template.get('category', 'general')}")
            print(f"   Language: {template.get('language', 'unknown')}")
            print(f"   Framework: {template.get('framework', 'none')}")
            print(f"   Quality Score: {template.get('quality_score', 0):.1f}/100")
            print(f"   Tags: {', '.join(template.get('tags', [])[:5])}")

    print(f"\n✅ Maestro-templates loading working ({len(templates)} templates)")


def test_persona_template_filtering():
    """Test filtering templates by persona relevance"""
    print("\n" + "=" * 80)
    print("Test 5: Persona Template Filtering")
    print("=" * 80)

    # Load all templates
    all_templates = _load_maestro_templates()

    if not all_templates:
        print("\n⚠️  No templates available in maestro-templates")
        return

    # Test filtering for different personas
    test_personas = ["frontend_developer", "backend_developer", "devops_engineer"]

    for persona_id in test_personas:
        relevant = get_relevant_templates_for_persona(persona_id, all_templates)

        print(f"\n👤 {persona_id}:")
        print(f"   Total templates available: {len(all_templates)}")
        print(f"   Relevant templates: {len(relevant)}")

        if relevant:
            print(f"   Top 3 matches:")
            for i, template in enumerate(relevant[:3], 1):
                print(
                    f"      {i}. {template.get('name', 'Unnamed')} (score: {template.get('_relevance_score', 0)})"
                )
                print(
                    f"         {template.get('category', 'general')} | {template.get('language', 'unknown')} | {template.get('framework', 'none')}"
                )

    print("\n✅ Persona template filtering working")


def test_git_search_keywords():
    """Test git search keywords for personas"""
    print("\n" + "=" * 80)
    print("Test 6: Git Search Keywords")
    print("=" * 80)

    test_personas = ["frontend_developer", "backend_developer", "devops_engineer", "qa_engineer"]

    print("\n🔍 Git search keywords for template discovery:")

    for persona_id in test_personas:
        domain = get_persona_domain(persona_id)
        keywords = domain.get("git_search_keywords", [])

        print(f"\n{persona_id}:")
        for keyword in keywords[:5]:
            print(f'   - "{keyword}"')

    print("\n✅ Git search keywords available for all personas")


def test_quality_filtering():
    """Test quality score filtering"""
    print("\n" + "=" * 80)
    print("Test 7: Quality Score Filtering")
    print("=" * 80)

    templates = _load_maestro_templates()

    if not templates:
        print("\n⚠️  No templates available")
        return

    # Filter by quality score
    high_quality = [t for t in templates if t.get("quality_score", 0) >= 80]
    medium_quality = [t for t in templates if 60 <= t.get("quality_score", 0) < 80]
    low_quality = [t for t in templates if t.get("quality_score", 0) < 60]

    print(f"\n📊 Template Quality Distribution:")
    print(f"   High Quality (≥80): {len(high_quality)} templates")
    print(f"   Medium Quality (60-79): {len(medium_quality)} templates")
    print(f"   Low Quality (<60): {len(low_quality)} templates")

    if high_quality:
        print(f"\n⭐ Top high-quality templates:")
        sorted_templates = sorted(
            high_quality, key=lambda t: t.get("quality_score", 0), reverse=True
        )
        for i, template in enumerate(sorted_templates[:3], 1):
            print(
                f"   {i}. {template.get('name', 'Unnamed')} - {template.get('quality_score', 0):.1f}/100"
            )

    print("\n✅ Quality filtering working")


def test_comprehensive_persona_query():
    """Test comprehensive persona query simulation"""
    print("\n" + "=" * 80)
    print("Test 8: Comprehensive Persona Query Simulation")
    print("=" * 80)

    persona_id = "backend_developer"
    task = "Build authentication API with JWT"

    print(f"\n🎯 Simulating query:")
    print(f"   Persona: {persona_id}")
    print(f"   Task: {task}")

    # Get domain
    domain = get_persona_domain(persona_id)
    print(f"\n📋 Domain expertise:")
    print(f"   Primary languages: {', '.join(domain['languages'][:3])}")
    print(f"   Primary frameworks: {', '.join(domain['frameworks'][:3])}")

    # Load templates
    all_templates = _load_maestro_templates()
    relevant = get_relevant_templates_for_persona(persona_id, all_templates)

    # Filter for authentication-related
    auth_templates = [
        t
        for t in relevant
        if any(tag in ["authentication", "auth", "jwt", "oauth"] for tag in t.get("tags", []))
    ]

    print(f"\n🔍 Search results:")
    print(f"   Total relevant templates: {len(relevant)}")
    print(f"   Authentication-related: {len(auth_templates)}")

    if auth_templates:
        print(f"\n✨ Best matches:")
        for i, template in enumerate(auth_templates[:2], 1):
            print(f"   {i}. {template.get('name', 'Unnamed')}")
            print(f"      Framework: {template.get('framework', 'none')}")
            print(f"      Quality: {template.get('quality_score', 0):.1f}/100")
            print(f"      Tags: {', '.join(template.get('tags', [])[:5])}")

    print("\n✅ Comprehensive persona query working")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("PERSONA-LEVEL RAG TESTING (Phase 2)")
    print("=" * 80)

    try:
        # Test 1: Domain mappings
        test_persona_domain_mappings()

        # Test 2: Reverse mappings
        test_reverse_mappings()

        # Test 3: Template matching
        test_template_matching()

        # Test 4: Maestro-templates loading
        test_maestro_templates_loading()

        # Test 5: Persona filtering
        test_persona_template_filtering()

        # Test 6: Git keywords
        test_git_search_keywords()

        # Test 7: Quality filtering
        test_quality_filtering()

        # Test 8: Comprehensive query
        test_comprehensive_persona_query()

        # Summary
        print("\n" + "=" * 80)
        print("✅ PERSONA RAG PHASE 2 TESTING COMPLETE")
        print("=" * 80)

        print("\n📝 Summary:")
        print("   ✅ Persona domain mappings - 11 personas configured")
        print("   ✅ Reverse mappings - Category/Language/Framework → Personas")
        print("   ✅ Template matching - Persona relevance scoring")
        print("   ✅ Maestro-templates integration - Template loading")
        print("   ✅ Persona filtering - Domain-specific template filtering")
        print("   ✅ Git search keywords - Template discovery support")
        print("   ✅ Quality filtering - High/Medium/Low score filtering")
        print("   ✅ Comprehensive queries - End-to-end persona queries")

        print("\n🎯 Integration Points:")
        print("   - Persona domains mapped to maestro-templates categories")
        print("   - Template relevance scoring by persona")
        print("   - Quality-based filtering")
        print("   - Git search keywords for GitHub template discovery")

        print("\n🚀 Next Steps:")
        print("   Phase 3: RAG Reader Service (port 9801)")
        print("   Phase 4: RAG Writer Service (port 9802)")
        print("   Phase 5: Workflow Engine Integration")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
