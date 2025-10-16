#!/usr/bin/env python3
"""
Sync Persona JSON Definitions to PostgreSQL Database
Loads all persona JSON files and syncs them to the ai_agents table
Run this after updating persona JSON files
"""

import sys
import os
from pathlib import Path

# Add BFF path for persona_loader import
sys.path.insert(0, str(Path(__file__).parent.parent / 'src' / 'bff'))

from persona_loader import load_all_personas
import psycopg2
from psycopg2.extras import Json
import json

# Database connection from environment or defaults
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5435'),
    'database': os.getenv('DB_NAME', 'maestro_production'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres')
}

def map_persona_to_db(persona_id: str, persona: dict) -> dict:
    """Map persona JSON structure to database schema"""

    # Get raw definition
    raw_def = persona.get('raw_definition', {})

    # Extract metadata
    metadata = raw_def.get('metadata', {})
    role_info = raw_def.get('role', {})
    capabilities_info = raw_def.get('capabilities', {})
    prompts = raw_def.get('prompts', {})
    interaction = raw_def.get('interaction_patterns', {})
    quality = raw_def.get('quality_standards', {})

    # Map to database record
    db_record = {
        'id': persona_id,
        'persona_id': persona_id,
        'name': persona['name'],
        'display_name': persona['name'],
        'type': 'ai',
        'schema_version': raw_def.get('schema_version', '3.0'),
        'version': raw_def.get('version', '1.0.0'),

        # Role
        'role': persona['role'],
        'primary_role': role_info.get('primary_role', persona_id),
        'experience_level': role_info.get('experience_level', 5),
        'autonomy_level': role_info.get('autonomy_level', 5),
        'specializations': role_info.get('specializations', []),

        # Metadata
        'description': persona.get('description', metadata.get('description', '')),
        'category': metadata.get('category', 'general'),
        'status': metadata.get('status', 'active'),
        'tags': metadata.get('tags', []),

        # Visual
        'icon': persona['avatar'],
        'avatar': persona['avatar'],
        'color': persona['color'],

        # Capabilities
        'capabilities': persona.get('specialization', []),
        'technical_skills': capabilities_info.get('technical_skills', []),
        'soft_skills': capabilities_info.get('soft_skills', []),

        # AI Configuration
        'backend_model': 'claude-3-5-sonnet-20241022',
        'response_time': persona.get('response_time', 2.0),

        # Prompts
        'system_prompt': persona.get('system_prompt', prompts.get('system_prompt', '')),
        'greeting': prompts.get('greeting', ''),
        'behavior_guidelines': prompts.get('behavior_guidelines', []),

        # Interaction
        'response_style': persona.get('personality', interaction.get('response_style', '')),
        'communication_tone': interaction.get('communication_tone', ''),
        'collaboration_approach': interaction.get('collaboration_approach', ''),

        # Quality Standards
        'code_quality_standard': quality.get('code_quality', ''),
        'documentation_standard': quality.get('documentation', ''),
        'testing_standard': quality.get('testing', ''),

        # Deliverables
        'deliverable_types': [],
        'artifact_formats': [],

        # Full definition
        'persona_definition': Json(raw_def)
    }

    return db_record

def sync_personas():
    """Sync JSON personas to database"""
    print("=" * 70)
    print("SYNCING PERSONAS FROM JSON TO POSTGRESQL DATABASE")
    print("=" * 70)

    # Load personas from JSON
    print("\n📂 Loading personas from JSON files...")
    personas = load_all_personas()
    print(f"✅ Loaded {len(personas)} personas from JSON files\n")

    # Connect to database
    print(f"🔌 Connecting to PostgreSQL database...")
    print(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print(f"   Database: {DB_CONFIG['database']}")

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        print("✅ Connected to database\n")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        return

    # Sync each persona
    print("📝 Syncing personas to database...")
    print("-" * 70)

    synced_count = 0
    error_count = 0

    for persona_id, persona in personas.items():
        try:
            # Map persona to database format
            db_record = map_persona_to_db(persona_id, persona)

            # Upsert query
            cur.execute("""
                INSERT INTO ai_agents (
                    id, persona_id, name, display_name, type, schema_version, version,
                    role, primary_role, experience_level, autonomy_level, specializations,
                    description, category, status, tags,
                    icon, avatar, color,
                    capabilities, technical_skills, soft_skills,
                    backend_model, response_time,
                    system_prompt, greeting, behavior_guidelines,
                    response_style, communication_tone, collaboration_approach,
                    code_quality_standard, documentation_standard, testing_standard,
                    deliverable_types, artifact_formats,
                    persona_definition,
                    created_at, updated_at
                ) VALUES (
                    %(id)s, %(persona_id)s, %(name)s, %(display_name)s, %(type)s,
                    %(schema_version)s, %(version)s,
                    %(role)s, %(primary_role)s, %(experience_level)s, %(autonomy_level)s,
                    %(specializations)s,
                    %(description)s, %(category)s, %(status)s, %(tags)s,
                    %(icon)s, %(avatar)s, %(color)s,
                    %(capabilities)s, %(technical_skills)s, %(soft_skills)s,
                    %(backend_model)s, %(response_time)s,
                    %(system_prompt)s, %(greeting)s, %(behavior_guidelines)s,
                    %(response_style)s, %(communication_tone)s, %(collaboration_approach)s,
                    %(code_quality_standard)s, %(documentation_standard)s, %(testing_standard)s,
                    %(deliverable_types)s, %(artifact_formats)s,
                    %(persona_definition)s,
                    NOW(), NOW()
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    display_name = EXCLUDED.display_name,
                    role = EXCLUDED.role,
                    primary_role = EXCLUDED.primary_role,
                    experience_level = EXCLUDED.experience_level,
                    autonomy_level = EXCLUDED.autonomy_level,
                    specializations = EXCLUDED.specializations,
                    description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    status = EXCLUDED.status,
                    tags = EXCLUDED.tags,
                    icon = EXCLUDED.icon,
                    avatar = EXCLUDED.avatar,
                    color = EXCLUDED.color,
                    capabilities = EXCLUDED.capabilities,
                    technical_skills = EXCLUDED.technical_skills,
                    soft_skills = EXCLUDED.soft_skills,
                    backend_model = EXCLUDED.backend_model,
                    response_time = EXCLUDED.response_time,
                    system_prompt = EXCLUDED.system_prompt,
                    greeting = EXCLUDED.greeting,
                    behavior_guidelines = EXCLUDED.behavior_guidelines,
                    response_style = EXCLUDED.response_style,
                    communication_tone = EXCLUDED.communication_tone,
                    collaboration_approach = EXCLUDED.collaboration_approach,
                    code_quality_standard = EXCLUDED.code_quality_standard,
                    documentation_standard = EXCLUDED.documentation_standard,
                    testing_standard = EXCLUDED.testing_standard,
                    deliverable_types = EXCLUDED.deliverable_types,
                    artifact_formats = EXCLUDED.artifact_formats,
                    persona_definition = EXCLUDED.persona_definition,
                    updated_at = NOW()
            """, db_record)

            print(f"  ✅ {persona['avatar']} {persona['name']:30} ({persona_id})")
            synced_count += 1

        except Exception as e:
            print(f"  ❌ {persona['name']:30} ({persona_id}) - Error: {e}")
            error_count += 1

    # Commit changes
    conn.commit()
    cur.close()
    conn.close()

    print("-" * 70)
    print(f"\n✅ Sync Complete!")
    print(f"   Synced: {synced_count} personas")
    print(f"   Errors: {error_count} personas")
    print("=" * 70)

if __name__ == '__main__':
    try:
        sync_personas()
    except KeyboardInterrupt:
        print("\n\n⚠️  Sync interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
