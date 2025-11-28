"""
Persona Loader
Loads real personas from JSON definitions and maps them for collaboration
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, List

# Path to persona definitions
PERSONAS_DIR = Path(__file__).parent.parent / "personas" / "definitions"

def load_persona_from_file(filepath: Path) -> Dict[str, Any]:
    """Load a single persona from JSON file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract key info
    persona_id = data.get('persona_id')
    display_name = data.get('display_name', persona_id.replace('_', ' ').title())

    # Extract human_alias from metadata (NEW: use human name if available)
    metadata = data.get('metadata', {})
    human_alias = metadata.get('human_alias')

    # Use human_alias if available, otherwise fall back to display_name
    name_to_use = human_alias if human_alias else display_name

    role = data.get('role', {})
    primary_role = role.get('primary_role', persona_id)
    description = metadata.get('description', '')
    specializations = role.get('specializations', [])

    # Get system prompt from prompts section
    prompts = data.get('prompts', {})
    system_prompt = prompts.get('system_prompt', '')

    # Create collaboration-friendly persona
    return {
        'id': persona_id,
        'name': name_to_use,  # NOW USES HUMAN NAME (e.g., "Marcus")
        'role': display_name,  # Keep role name separate (e.g., "Backend Developer")
        'avatar': get_avatar_for_role(persona_id),
        'color': get_color_for_role(persona_id),
        'status': 'active' if metadata.get('status') == 'active' else 'active',
        'specialization': specializations,
        'personality': f"professional, expert in {primary_role}",
        'response_time': 2.0,
        'system_prompt': system_prompt or f"You are a {display_name} expert. Provide professional, accurate assistance.",
        'description': description,
        'raw_definition': data  # Keep full definition for reference
    }

def get_avatar_for_role(persona_id: str) -> str:
    """Map persona to appropriate emoji avatar"""
    avatar_map = {
        'requirement_analyst': '📋',
        'solution_architect': '🏗️',
        'backend_developer': '⚙️',
        'frontend_developer': '💻',
        'ui_ux_designer': '🎨',
        'qa_engineer': '🧪',
        'test_engineer': '✅',
        'devops_engineer': '🚀',
        'database_administrator': '🗄️',
        'security_specialist': '🔒',
        'technical_writer': '📝',
        'deployment_specialist': '📦',
        'phase_reviewer': '👀',
        'deliverable_validator': '✔️',
        'project_reviewer': '🔍',
        'maestro': '🤖',
        'amigo': '🤝'
    }
    return avatar_map.get(persona_id, '🤖')

def get_color_for_role(persona_id: str) -> str:
    """Map persona to appropriate color"""
    color_map = {
        'requirement_analyst': '#3b82f6',  # blue
        'solution_architect': '#8b5cf6',   # purple
        'backend_developer': '#f97316',    # orange
        'frontend_developer': '#10b981',   # green
        'ui_ux_designer': '#ec4899',       # pink
        'qa_engineer': '#14b8a6',          # teal
        'test_engineer': '#06b6d4',        # cyan
        'devops_engineer': '#8b5cf6',      # purple
        'database_administrator': '#6366f1', # indigo
        'security_specialist': '#ef4444',  # red
        'technical_writer': '#84cc16',     # lime
        'deployment_specialist': '#a855f7', # purple
        'phase_reviewer': '#f59e0b',       # amber
        'deliverable_validator': '#22c55e', # green
        'project_reviewer': '#0ea5e9',     # sky
        'maestro': '#6366f1',              # indigo
        'amigo': '#10b981'                 # green
    }
    return color_map.get(persona_id, '#6b7280')

def load_all_personas() -> Dict[str, Dict[str, Any]]:
    """Load all personas from definitions directory"""
    personas = {}

    if not PERSONAS_DIR.exists():
        print(f"Warning: Personas directory not found: {PERSONAS_DIR}")
        return {}

    for json_file in PERSONAS_DIR.glob("*.json"):
        try:
            persona = load_persona_from_file(json_file)
            personas[persona['id']] = persona
        except Exception as e:
            print(f"Error loading persona from {json_file}: {e}")

    return personas

# Load personas on module import
AI_AGENT_PERSONAS = load_all_personas()

print(f"✅ Loaded {len(AI_AGENT_PERSONAS)} personas from {PERSONAS_DIR}")
for pid, persona in AI_AGENT_PERSONAS.items():
    print(f"   - {persona['avatar']} {persona['name']} ({pid})")
