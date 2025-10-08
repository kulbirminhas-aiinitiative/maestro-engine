#!/usr/bin/env python3
"""
Model Context Protocol (MCP) Cache Configuration
Centralized cache management for information sharing across personas
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """Standard cache entry structure"""
    key: str
    value: Any
    created_at: str
    expires_at: str
    persona_source: str
    session_id: str
    metadata: Dict[str, Any]

class MCPCacheManager:
    """
    Centralized Model Context Protocol cache for persona information sharing
    Replaces scattered cache implementations with unified MCP-compliant system
    """
    
    def __init__(self, cache_dir: str = "/tmp/mcp_cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_hours = ttl_hours
        self.session_cache = {}  # In-memory session cache
        self.logger = logger
        
        # Initialize MCP cache structure
        self.cache_file = self.cache_dir / "mcp_cache.json"
        self.session_file = self.cache_dir / "session_state.json"
        
        # Load existing cache
        self._load_cache()
    
    def _load_cache(self):
        """Load existing cache from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    cache_data = json.load(f)
                    # Convert to CacheEntry objects
                    for key, entry_data in cache_data.items():
                        if self._is_entry_valid(entry_data):
                            self.session_cache[key] = entry_data
                            
            self.logger.info(f"✅ Loaded {len(self.session_cache)} cache entries from MCP cache")
        except Exception as e:
            self.logger.warning(f"Failed to load MCP cache: {e}")
    
    def _save_cache(self):
        """Save cache to disk"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.session_cache, f, indent=2, default=str)
            
            # Save current session state
            session_state = {
                "last_updated": datetime.now().isoformat(),
                "cache_size": len(self.session_cache),
                "active_sessions": list(set(entry.get('session_id', 'unknown') 
                                           for entry in self.session_cache.values()))
            }
            
            with open(self.session_file, 'w') as f:
                json.dump(session_state, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to save MCP cache: {e}")
    
    def _is_entry_valid(self, entry_data: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid"""
        try:
            expires_at = datetime.fromisoformat(entry_data.get('expires_at', ''))
            return datetime.now() < expires_at
        except:
            return False
    
    def _generate_cache_key(self, category: str, identifier: str, persona: str = "") -> str:
        """Generate standardized cache key"""
        if persona:
            return f"{category}:{persona}:{identifier}"
        return f"{category}:{identifier}"
    
    def store_persona_analysis(self, persona_name: str, requirement: str, 
                             analysis: Dict[str, Any], session_id: str) -> str:
        """Store persona analysis results in MCP cache"""
        
        cache_key = self._generate_cache_key("analysis", requirement[:50], persona_name)
        
        cache_entry = {
            "key": cache_key,
            "value": analysis,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=self.ttl_hours)).isoformat(),
            "persona_source": persona_name,
            "session_id": session_id,
            "metadata": {
                "requirement_hash": hash(requirement),
                "analysis_type": "progressive_analysis",
                "file_count": len(analysis.get('generated_files', [])),
                "context_shared": True
            }
        }
        
        self.session_cache[cache_key] = cache_entry
        self._save_cache()
        
        self.logger.info(f"📚 Stored {persona_name} analysis in MCP cache: {cache_key}")
        return cache_key
    
    def store_generated_artifacts(self, persona_name: str, artifacts: Dict[str, Any], 
                                session_id: str) -> str:
        """Store generated artifacts (files, configs, docs) in MCP cache"""
        
        cache_key = self._generate_cache_key("artifacts", f"{session_id}_{int(time.time())}", persona_name)
        
        cache_entry = {
            "key": cache_key,
            "value": artifacts,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=self.ttl_hours * 2)).isoformat(),  # Artifacts last longer
            "persona_source": persona_name,
            "session_id": session_id,
            "metadata": {
                "artifact_types": list(artifacts.keys()),
                "total_files": sum(len(v) if isinstance(v, list) else 1 for v in artifacts.values()),
                "generation_method": "unified_claude_tools"
            }
        }
        
        self.session_cache[cache_key] = cache_entry
        self._save_cache()
        
        self.logger.info(f"🗃️ Stored {persona_name} artifacts in MCP cache: {cache_key}")
        return cache_key
    
    def store_context_decisions(self, decisions: List[Dict[str, Any]], session_id: str) -> str:
        """Store decision trail for context sharing"""
        
        cache_key = self._generate_cache_key("decisions", session_id, "context_trail")
        
        cache_entry = {
            "key": cache_key,
            "value": {"decision_trail": decisions, "insights_count": len(decisions)},
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=self.ttl_hours)).isoformat(),
            "persona_source": "context_manager",
            "session_id": session_id,
            "metadata": {
                "decision_count": len(decisions),
                "context_type": "decision_trail",
                "shareable": True
            }
        }
        
        self.session_cache[cache_key] = cache_entry
        self._save_cache()
        
        return cache_key
    
    def get_session_context(self, session_id: str) -> Dict[str, Any]:
        """Get all cached context for a session"""
        
        session_entries = {
            key: entry for key, entry in self.session_cache.items()
            if entry.get('session_id') == session_id and self._is_entry_valid(entry)
        }
        
        context = {
            "session_id": session_id,
            "cached_analyses": {},
            "cached_artifacts": {},
            "decision_trails": [],
            "available_insights": []
        }
        
        for key, entry in session_entries.items():
            if "analysis:" in key:
                persona = entry.get('persona_source', 'unknown')
                context["cached_analyses"][persona] = entry['value']
            elif "artifacts:" in key:
                persona = entry.get('persona_source', 'unknown')
                context["cached_artifacts"][persona] = entry['value']
            elif "decisions:" in key:
                context["decision_trails"].append(entry['value'])
        
        return context
    
    def get_previous_persona_work(self, session_id: str, exclude_persona: str = "") -> Dict[str, Any]:
        """Get work from previous personas in the session for context sharing"""
        
        previous_work = {}
        
        for key, entry in self.session_cache.items():
            if (entry.get('session_id') == session_id and 
                entry.get('persona_source') != exclude_persona and
                self._is_entry_valid(entry)):
                
                persona = entry.get('persona_source', 'unknown')
                if persona not in previous_work:
                    previous_work[persona] = {
                        "analysis": None,
                        "artifacts": None,
                        "metadata": entry.get('metadata', {})
                    }
                
                if "analysis:" in key:
                    previous_work[persona]["analysis"] = entry['value']
                elif "artifacts:" in key:
                    previous_work[persona]["artifacts"] = entry['value']
        
        self.logger.info(f"🔗 Retrieved context from {len(previous_work)} previous personas")
        return previous_work
    
    def cleanup_expired(self):
        """Remove expired cache entries"""
        
        expired_keys = []
        for key, entry in self.session_cache.items():
            if not self._is_entry_valid(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.session_cache[key]
        
        if expired_keys:
            self._save_cache()
            self.logger.info(f"🧹 Cleaned up {len(expired_keys)} expired cache entries")
        
        return len(expired_keys)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get MCP cache statistics"""

        stats = {
            "total_entries": len(self.session_cache),
            "cache_size_mb": len(json.dumps(self.session_cache)) / (1024 * 1024),
            "active_sessions": len(set(entry.get('session_id', 'unknown')
                                     for entry in self.session_cache.values())),
            "personas_active": len(set(entry.get('persona_source', 'unknown')
                                     for entry in self.session_cache.values())),
            "cache_hit_data": {
                "analyses": len([k for k in self.session_cache.keys() if "analysis:" in k]),
                "artifacts": len([k for k in self.session_cache.keys() if "artifacts:" in k]),
                "decisions": len([k for k in self.session_cache.keys() if "decisions:" in k])
            }
        }

        return stats

    def store_workflow_event(self, event: Dict[str, Any], session_id: str) -> str:
        """
        Store workflow event for audit observation
        Used by maestro_orchestrator_v1.py to emit events for separate audit process
        """

        event_id = f"{session_id}_{event.get('type', 'unknown')}_{int(time.time() * 1000)}"
        cache_key = self._generate_cache_key("event", event_id)

        cache_entry = {
            "key": cache_key,
            "value": event,
            "created_at": datetime.now().isoformat(),
            "expires_at": (datetime.now() + timedelta(hours=48)).isoformat(),
            "persona_source": "orchestrator",
            "session_id": session_id,
            "event_type": event.get("type", "unknown"),
            "metadata": {
                "observable": True,
                "audit_required": True,
                "event_category": self._categorize_event(event.get("type", "unknown"))
            }
        }

        self.session_cache[cache_key] = cache_entry
        self._save_cache()

        return cache_key

    def get_all_workflow_events(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get all workflow events for a session (for audit reconstruction)
        Used by mcp_audit_observer.py to reconstruct audit trail
        """

        events = []
        for key, entry in self.session_cache.items():
            if (entry.get('session_id') == session_id and
                'event:' in key and
                self._is_entry_valid(entry)):
                events.append(entry['value'])

        events.sort(key=lambda e: e.get('timestamp', ''))

        return events

    def _categorize_event(self, event_type: str) -> str:
        """Categorize event type for audit filtering"""

        categories = {
            "orchestrator_init": "initialization",
            "workflow_start": "workflow",
            "workflow_complete": "workflow",
            "team_assignment": "team",
            "prompt_generated": "chat",
            "unified_tools_start": "tool",
            "unified_tools_complete": "tool",
            "deliverables_generated": "output",
            "file_created": "file",
            "execution_error": "error",
            "workflow_exception": "error",
            "unified_tools_error": "error",
            "results_saved": "output"
        }

        return categories.get(event_type, "general")


# Global MCP cache instance
_mcp_cache = None

def get_mcp_cache() -> MCPCacheManager:
    """Get global MCP cache instance"""
    global _mcp_cache
    if _mcp_cache is None:
        _mcp_cache = MCPCacheManager()
    return _mcp_cache

def configure_mcp_tools(persona_name: str, session_id: str) -> List[str]:
    """Configure MCP-aware tools for persona"""
    
    # Return list of MCP-enabled tools that personas should use
    mcp_tools = [
        "create_code_file",
        "create_documentation", 
        "create_config_file",
        "save_persona_analysis",
        "create_project_structure",
        "get_session_context",
        "list_artifacts",
        "store_context_decision",  # New MCP tool
        "get_previous_context",    # New MCP tool
        "share_insights"           # New MCP tool
    ]
    
    return mcp_tools


if __name__ == "__main__":
    # Test MCP cache
    cache = MCPCacheManager()
    
    # Test storing analysis
    test_analysis = {
        "content": "Test analysis content",
        "generated_files": ["file1.py", "file2.js"]
    }
    
    key = cache.store_persona_analysis(
        "test_persona", 
        "test requirement", 
        test_analysis, 
        "test_session_123"
    )
    
    # Test retrieving context
    context = cache.get_session_context("test_session_123")
    print(f"MCP Cache test successful! Context: {context}")
    
    # Test cache stats
    stats = cache.get_cache_stats()
    print(f"Cache stats: {stats}")