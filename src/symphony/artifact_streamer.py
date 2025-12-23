"""
Symphony Artifact Streamer

EPIC: MD-3902 - Maestro Symphony Demo
Story: MD-3908 - Wire Artifact Streaming via WebSocket

Service for generating and streaming artifacts during Symphony demo.
Parses conversation context and generates appropriate artifacts.
"""

import asyncio
import json
import re
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable, Awaitable
import logging

from symphony.models import (
    ArtifactType,
    StoryArtifact,
    ArchitectureArtifact,
    CodeArtifact,
    TestArtifact,
    ArtifactEvent,
    WorkflowPhase,
    WorkflowProgress,
    SymphonySession,
)

logger = logging.getLogger(__name__)


class ArtifactStreamer:
    """
    Streams artifacts in real-time during Symphony demo.

    Listens to conversation messages and generates appropriate artifacts
    based on the speaker's role and message content.
    """

    def __init__(self):
        # session_id -> SymphonySession
        self.sessions: Dict[str, SymphonySession] = {}

        # session_id -> list of callback functions for artifact events
        self.listeners: Dict[str, List[Callable[[ArtifactEvent], Awaitable[None]]]] = {}

        # Standard SDLC phases
        self.workflow_phases = [
            WorkflowPhase(id="requirements", name="Requirements", status="pending", progress=0),
            WorkflowPhase(id="design", name="Design", status="pending", progress=0),
            WorkflowPhase(id="implementation", name="Implementation", status="pending", progress=0),
            WorkflowPhase(id="testing", name="Testing", status="pending", progress=0),
        ]

        logger.info("ArtifactStreamer initialized")

    def create_session(self, session_id: str, channel_id: str) -> SymphonySession:
        """Create a new Symphony session"""
        session = SymphonySession(
            sessionId=session_id,
            channelId=channel_id,
            workflowProgress=WorkflowProgress(
                phases=[p.model_copy() for p in self.workflow_phases],
                currentPhase="",
                overallProgress=0
            )
        )
        self.sessions[session_id] = session
        self.listeners[session_id] = []
        logger.info(f"Created Symphony session: {session_id}")
        return session

    def get_session(self, session_id: str) -> Optional[SymphonySession]:
        """Get session by ID"""
        return self.sessions.get(session_id)

    def add_listener(
        self,
        session_id: str,
        callback: Callable[[ArtifactEvent], Awaitable[None]]
    ):
        """Add artifact event listener for a session"""
        if session_id not in self.listeners:
            self.listeners[session_id] = []
        self.listeners[session_id].append(callback)

    def remove_listener(
        self,
        session_id: str,
        callback: Callable[[ArtifactEvent], Awaitable[None]]
    ):
        """Remove artifact event listener"""
        if session_id in self.listeners:
            try:
                self.listeners[session_id].remove(callback)
            except ValueError:
                pass

    async def _emit_artifact(self, session_id: str, event: ArtifactEvent):
        """Emit artifact event to all listeners"""
        if session_id in self.listeners:
            for callback in self.listeners[session_id]:
                try:
                    await callback(event)
                except Exception as e:
                    logger.error(f"Error in artifact listener: {e}")

    async def process_message(
        self,
        session_id: str,
        persona_id: str,
        persona_role: str,
        message_content: str
    ):
        """
        Process a conversation message and generate artifacts if appropriate.

        Different personas generate different artifacts:
        - Product Manager (sarah_pm): User stories
        - Architect (marcus_arch): Architecture diagrams
        - Developer (alex_dev): Code snippets
        - QA Lead (priya_qa): Test cases
        """
        session = self.sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            return

        role_lower = persona_role.lower()

        # Product Manager generates stories
        if "product" in role_lower or "pm" in persona_id.lower():
            await self._extract_stories(session_id, message_content)

        # Architect generates architecture diagrams
        elif "architect" in role_lower or "arch" in persona_id.lower():
            await self._extract_architecture(session_id, message_content)

        # Developer generates code
        elif "developer" in role_lower or "dev" in persona_id.lower():
            await self._extract_code(session_id, message_content)

        # QA generates test cases
        elif "qa" in role_lower or "test" in role_lower:
            await self._extract_tests(session_id, message_content)

    async def _extract_stories(self, session_id: str, content: str):
        """Extract user stories from PM's message"""
        session = self.sessions.get(session_id)
        if not session:
            return

        # Look for story-like patterns
        story_patterns = [
            r"As a[n]? (.+?), I (?:want|need|can) (.+?)(?:so that|because|,|\.)",
            r"(?:user story|US-\d+)[:\s]+(.+?)(?:\.|$)",
            r"(?:story|requirement)[:\s]+(.+?)(?:\.|$)",
        ]

        stories_found = []
        for pattern in story_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                story_text = match.group(0).strip()
                stories_found.append(story_text)

        # If no patterns found but message discusses requirements, create a general story
        if not stories_found and any(kw in content.lower() for kw in ["requirement", "need", "feature", "user"]):
            # Create story from key sentences
            sentences = content.split('.')
            for sentence in sentences[:2]:  # First 2 sentences
                if len(sentence.strip()) > 20:
                    stories_found.append(sentence.strip())

        # Generate story artifacts
        for i, story_text in enumerate(stories_found[:3]):  # Max 3 stories per message
            story_count = len(session.artifacts.get("stories", [])) + 1
            story = StoryArtifact(
                title=story_text[:50] + "..." if len(story_text) > 50 else story_text,
                storyId=f"US-{story_count:03d}",
                description=story_text,
                acceptanceCriteria=self._extract_acceptance_criteria(content),
                priority="high" if "critical" in content.lower() or "important" in content.lower() else "medium",
                status="pending"
            )

            # Add to session
            session.artifacts["stories"].append(story.model_dump(by_alias=True))

            # Emit event
            event = ArtifactEvent(
                eventType="artifact_created",
                artifactType=ArtifactType.STORY,
                artifact=story.model_dump(by_alias=True),
                sessionId=session_id
            )
            await self._emit_artifact(session_id, event)

            # Small delay between artifacts for visual effect
            await asyncio.sleep(0.5)

    def _extract_acceptance_criteria(self, content: str) -> List[str]:
        """Extract acceptance criteria from message"""
        criteria = []

        # Look for bullet points or numbered items
        bullet_pattern = r"[-*•]\s*(.+?)(?:\n|$)"
        matches = re.finditer(bullet_pattern, content)
        for match in matches:
            item = match.group(1).strip()
            if len(item) > 10:
                criteria.append(item)

        # Look for "should" statements
        should_pattern = r"(?:should|must|needs to)\s+(.+?)(?:\.|$)"
        matches = re.finditer(should_pattern, content, re.IGNORECASE)
        for match in matches:
            item = match.group(1).strip()
            if len(item) > 10 and item not in criteria:
                criteria.append(f"System {match.group(0).strip()}")

        return criteria[:5]  # Max 5 criteria

    async def _extract_architecture(self, session_id: str, content: str):
        """Extract architecture diagrams from Architect's message"""
        session = self.sessions.get(session_id)
        if not session:
            return

        # Check for architecture-related keywords
        arch_keywords = ["microservice", "api", "service", "layer", "component",
                        "database", "frontend", "backend", "gateway", "auth"]

        has_arch_content = any(kw in content.lower() for kw in arch_keywords)
        if not has_arch_content:
            return

        # Generate a Mermaid diagram based on content
        mermaid_code = self._generate_mermaid_from_content(content)

        arch = ArchitectureArtifact(
            title="System Architecture",
            diagramType="flowchart",
            mermaidCode=mermaid_code,
            description=content[:200] + "..." if len(content) > 200 else content
        )

        # Add to session
        session.artifacts["architecture"].append(arch.model_dump(by_alias=True))

        # Emit event
        event = ArtifactEvent(
            eventType="artifact_created",
            artifactType=ArtifactType.ARCHITECTURE,
            artifact=arch.model_dump(by_alias=True),
            sessionId=session_id
        )
        await self._emit_artifact(session_id, event)

    def _generate_mermaid_from_content(self, content: str) -> str:
        """Generate Mermaid diagram code from architecture discussion"""
        content_lower = content.lower()

        # Detect components mentioned
        components = []
        component_map = {
            "frontend": "Frontend[React Frontend]",
            "backend": "Backend[Backend API]",
            "api": "API[API Gateway]",
            "gateway": "Gateway[API Gateway]",
            "database": "DB[(Database)]",
            "auth": "Auth[Auth Service]",
            "cache": "Cache[(Redis Cache)]",
            "queue": "Queue[Message Queue]",
            "microservice": "Service[Microservice]",
        }

        for keyword, component in component_map.items():
            if keyword in content_lower and component not in components:
                components.append(component)

        # Build diagram
        if len(components) < 2:
            # Default architecture
            components = [
                "Client[Client App]",
                "Gateway[API Gateway]",
                "Service[Service Layer]",
                "DB[(Database)]"
            ]

        lines = ["graph TD"]
        for i in range(len(components) - 1):
            lines.append(f"    {components[i].split('[')[0]} --> {components[i+1].split('[')[0]}")

        # Add component definitions
        for comp in components:
            name = comp.split('[')[0]
            lines.append(f"    {comp}")

        return "\n".join(lines)

    async def _extract_code(self, session_id: str, content: str):
        """Extract code snippets from Developer's message"""
        session = self.sessions.get(session_id)
        if not session:
            return

        # Look for code blocks in markdown
        code_pattern = r"```(\w+)?\n(.*?)```"
        matches = re.finditer(code_pattern, content, re.DOTALL)

        for match in matches:
            language = match.group(1) or "python"
            code = match.group(2).strip()

            # Determine filename from code
            filename = self._determine_filename(code, language)

            code_artifact = CodeArtifact(
                title=f"{filename}",
                filename=filename,
                code=code,
                language=language,
                lines=len(code.split('\n'))
            )

            session.artifacts["code"].append(code_artifact.model_dump(by_alias=True))

            event = ArtifactEvent(
                eventType="artifact_created",
                artifactType=ArtifactType.CODE,
                artifact=code_artifact.model_dump(by_alias=True),
                sessionId=session_id
            )
            await self._emit_artifact(session_id, event)
            await asyncio.sleep(0.3)

        # If no code blocks but mentions code concepts, generate stub
        if not list(matches):
            code_keywords = ["class", "function", "method", "component", "service", "api"]
            if any(kw in content.lower() for kw in code_keywords):
                await self._generate_code_stub(session_id, content)

    async def _generate_code_stub(self, session_id: str, content: str):
        """Generate a code stub based on discussion"""
        session = self.sessions.get(session_id)
        if not session:
            return

        # Extract class/service names
        class_pattern = r"(?:class|service|component)\s+['\"]?(\w+)['\"]?"
        match = re.search(class_pattern, content, re.IGNORECASE)
        class_name = match.group(1) if match else "Service"

        # Generate Python stub
        code = f'''"""
{class_name} - Auto-generated from conversation
"""

class {class_name}:
    """Generated service class"""

    def __init__(self):
        self.initialized = True

    async def process(self, data: dict) -> dict:
        """Process incoming data"""
        # TODO: Implement based on requirements
        return {{"status": "success", "data": data}}
'''

        code_artifact = CodeArtifact(
            title=f"{class_name} Service",
            filename=f"{class_name.lower()}_service.py",
            code=code,
            language="python",
            lines=len(code.split('\n'))
        )

        session.artifacts["code"].append(code_artifact.model_dump(by_alias=True))

        event = ArtifactEvent(
            eventType="artifact_created",
            artifactType=ArtifactType.CODE,
            artifact=code_artifact.model_dump(by_alias=True),
            sessionId=session_id
        )
        await self._emit_artifact(session_id, event)

    def _determine_filename(self, code: str, language: str) -> str:
        """Determine filename from code content"""
        extensions = {
            "python": ".py",
            "javascript": ".js",
            "typescript": ".ts",
            "react": ".tsx",
            "go": ".go",
            "rust": ".rs",
            "java": ".java",
        }
        ext = extensions.get(language, ".txt")

        # Try to find class/function name
        patterns = [
            r"class\s+(\w+)",
            r"function\s+(\w+)",
            r"def\s+(\w+)",
            r"const\s+(\w+)\s*=",
            r"export\s+(?:default\s+)?(?:class|function)\s+(\w+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                name = match.group(1)
                # Convert CamelCase to snake_case
                snake_name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
                return f"{snake_name}{ext}"

        return f"generated{ext}"

    async def _extract_tests(self, session_id: str, content: str):
        """Extract test cases from QA's message"""
        session = self.sessions.get(session_id)
        if not session:
            return

        # Look for test-related keywords
        test_keywords = ["test", "verify", "validate", "check", "ensure", "assert"]

        if not any(kw in content.lower() for kw in test_keywords):
            return

        # Extract test scenarios
        test_patterns = [
            r"test[:\s]+(.+?)(?:\n|$)",
            r"verify[:\s]+(.+?)(?:\n|$)",
            r"(?:should|must)\s+(.+?)(?:\.|$)",
        ]

        tests_found = []
        for pattern in test_patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE)
            for match in matches:
                test_desc = match.group(1).strip()
                if len(test_desc) > 10:
                    tests_found.append(test_desc)

        # Generate test artifacts
        test_types = ["unit", "integration", "e2e", "contract"]
        for i, test_desc in enumerate(tests_found[:4]):
            test_type = test_types[i % len(test_types)]

            test = TestArtifact(
                title=test_desc[:40] + "..." if len(test_desc) > 40 else test_desc,
                name=test_desc,
                suite="Symphony Tests",
                type=test_type,
                status="pending"
            )

            session.artifacts["tests"].append(test.model_dump(by_alias=True))

            event = ArtifactEvent(
                eventType="artifact_created",
                artifactType=ArtifactType.TEST,
                artifact=test.model_dump(by_alias=True),
                sessionId=session_id
            )
            await self._emit_artifact(session_id, event)
            await asyncio.sleep(0.3)

    async def update_workflow_progress(
        self,
        session_id: str,
        phase_id: str,
        status: str,
        progress: int,
        activity: Optional[str] = None
    ):
        """Update workflow phase progress"""
        session = self.sessions.get(session_id)
        if not session or not session.workflow_progress:
            return

        for phase in session.workflow_progress.phases:
            if phase.id == phase_id:
                phase.status = status
                phase.progress = progress
                phase.current_activity = activity
                break

        # Update current phase
        session.workflow_progress.current_phase = phase_id

        # Calculate overall progress
        total_progress = sum(p.progress for p in session.workflow_progress.phases)
        session.workflow_progress.overall_progress = total_progress // len(session.workflow_progress.phases)

    def cleanup_session(self, session_id: str):
        """Clean up session resources"""
        if session_id in self.sessions:
            del self.sessions[session_id]
        if session_id in self.listeners:
            del self.listeners[session_id]
        logger.info(f"Cleaned up Symphony session: {session_id}")


# Singleton instance
_artifact_streamer: Optional[ArtifactStreamer] = None


def get_artifact_streamer() -> ArtifactStreamer:
    """Get or create singleton ArtifactStreamer instance"""
    global _artifact_streamer
    if _artifact_streamer is None:
        _artifact_streamer = ArtifactStreamer()
    return _artifact_streamer
