"""
Symphony Artifact Extractor

EPIC: MD-4123 - Symphony Real LLM Integration via claude_code_api_layer
Story: MD-4133 - Implement ArtifactExtractor for LLM response parsing

Parses structured outputs from LLM responses to extract:
- User Stories (from Product Owner)
- Architecture Documents (from Architect)
- Code Blocks (from Developer)
- Test Cases (from QA Engineer)
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ArtifactType(Enum):
    """Types of artifacts that can be extracted"""
    USER_STORY = "user_story"
    ARCHITECTURE = "architecture"
    CODE = "code"
    TEST_CASE = "test_case"
    ADR = "adr"
    API_CONTRACT = "api_contract"


@dataclass
class UserStory:
    """Extracted user story"""
    id: str
    title: str
    as_a: str
    i_want: str
    so_that: str
    acceptance_criteria: List[str]
    priority: str
    story_points: Optional[int] = None
    dependencies: List[str] = field(default_factory=list)


@dataclass
class ArchitectureComponent:
    """Extracted architecture component"""
    name: str
    responsibility: str
    technology: str
    interfaces: List[str]
    dependencies: List[str]


@dataclass
class CodeBlock:
    """Extracted code block"""
    filename: str
    language: str
    content: str
    description: str


@dataclass
class TestCase:
    """Extracted test case"""
    id: str
    name: str
    test_type: str  # unit, integration, e2e
    priority: str
    related_story: Optional[str]
    preconditions: List[str]
    steps: List[str]
    expected_result: str
    test_code: Optional[str] = None


@dataclass
class APIContract:
    """Extracted API contract"""
    name: str
    method: str
    path: str
    request_schema: Dict[str, Any]
    response_schema: Dict[str, Any]
    error_codes: List[str]


class ArtifactExtractor:
    """
    Extracts structured artifacts from LLM responses.

    Handles:
    - Markdown-formatted outputs
    - Code blocks with language tags
    - Structured sections (headers, lists)
    - Edge cases and malformed outputs
    """

    def __init__(self):
        """Initialize the artifact extractor"""
        self._story_counter = 0
        self._test_counter = 0

    def extract_stories(self, llm_response: str) -> List[UserStory]:
        """
        Extract user stories from Product Owner response.

        Args:
            llm_response: Raw LLM response text

        Returns:
            List of UserStory objects
        """
        stories = []

        # Pattern for story blocks
        story_pattern = r'###\s*Story:\s*(.+?)(?=###\s*Story:|$)'
        story_matches = re.findall(story_pattern, llm_response, re.DOTALL | re.IGNORECASE)

        for match in story_matches:
            try:
                story = self._parse_story_block(match)
                if story:
                    stories.append(story)
            except Exception as e:
                logger.warning(f"Failed to parse story block: {e}")

        # Fallback: try simpler pattern
        if not stories:
            stories = self._extract_stories_simple(llm_response)

        return stories

    def _parse_story_block(self, block: str) -> Optional[UserStory]:
        """Parse a single story block"""
        # Extract title from first line
        lines = block.strip().split('\n')
        title = lines[0].strip() if lines else "Untitled Story"

        # Extract As a/I want/So that
        as_a_match = re.search(r'\*\*As a\*\*\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
        i_want_match = re.search(r'\*\*I want\*\*\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
        so_that_match = re.search(r'\*\*So that\*\*\s*(.+?)(?:\n|$)', block, re.IGNORECASE)

        as_a = as_a_match.group(1).strip() if as_a_match else "user"
        i_want = i_want_match.group(1).strip() if i_want_match else title
        so_that = so_that_match.group(1).strip() if so_that_match else "achieve my goal"

        # Extract acceptance criteria
        ac_pattern = r'\*\*Acceptance Criteria:\*\*\s*(.*?)(?:\*\*Priority|$)'
        ac_match = re.search(ac_pattern, block, re.DOTALL | re.IGNORECASE)
        acceptance_criteria = []
        if ac_match:
            ac_text = ac_match.group(1)
            criteria = re.findall(r'[-•]\s*(.+?)(?=\n[-•]|\n\n|$)', ac_text)
            acceptance_criteria = [c.strip() for c in criteria if c.strip()]

        # Extract priority
        priority_match = re.search(r'\*\*Priority:\*\*\s*(\w+)', block, re.IGNORECASE)
        priority = priority_match.group(1) if priority_match else "Medium"

        # Extract story points
        points_match = re.search(r'\*\*Story Points:\*\*\s*(\d+)', block, re.IGNORECASE)
        story_points = int(points_match.group(1)) if points_match else None

        self._story_counter += 1
        return UserStory(
            id=f"US-{self._story_counter:03d}",
            title=title,
            as_a=as_a,
            i_want=i_want,
            so_that=so_that,
            acceptance_criteria=acceptance_criteria,
            priority=priority,
            story_points=story_points,
        )

    def _extract_stories_simple(self, text: str) -> List[UserStory]:
        """Fallback: extract stories from simpler format"""
        stories = []

        # Look for "As a ... I want ... so that" pattern
        pattern = r'As a\s+(.+?),?\s+I (?:want|need) (?:to\s+)?(.+?)(?:,\s*)?so that\s+(.+?)(?:\.|$)'
        matches = re.findall(pattern, text, re.IGNORECASE | re.DOTALL)

        for as_a, i_want, so_that in matches:
            self._story_counter += 1
            stories.append(UserStory(
                id=f"US-{self._story_counter:03d}",
                title=i_want[:50].strip(),
                as_a=as_a.strip(),
                i_want=i_want.strip(),
                so_that=so_that.strip(),
                acceptance_criteria=[],
                priority="Medium",
            ))

        return stories

    def extract_architecture(self, llm_response: str) -> Dict[str, Any]:
        """
        Extract architecture components from Architect response.

        Args:
            llm_response: Raw LLM response text

        Returns:
            Dict with components, data_flow, technologies, api_contracts
        """
        result = {
            "components": [],
            "data_flow": "",
            "technologies": [],
            "api_contracts": [],
            "decisions": [],
        }

        # Extract components
        component_pattern = r'###\s*(?:\[)?([^\]\n]+)(?:\])?\s*\n(.*?)(?=###|## |$)'
        component_matches = re.findall(component_pattern, llm_response, re.DOTALL)

        for name, content in component_matches:
            if any(skip in name.lower() for skip in ['decision', 'api:', 'data flow']):
                continue
            component = self._parse_component(name, content)
            if component:
                result["components"].append(component.__dict__)

        # Extract data flow section
        data_flow_match = re.search(r'(?:##|###)\s*Data Flow\s*\n(.*?)(?=##|$)', llm_response, re.DOTALL | re.IGNORECASE)
        if data_flow_match:
            result["data_flow"] = data_flow_match.group(1).strip()

        # Extract technologies
        tech_pattern = r'\*\*Technology:\*\*\s*(.+?)(?:\n|$)'
        tech_matches = re.findall(tech_pattern, llm_response)
        result["technologies"] = list(set(t.strip() for t in tech_matches))

        # Extract API contracts
        api_pattern = r'###\s*API:\s*(.+?)\n(.*?)(?=###|$)'
        api_matches = re.findall(api_pattern, llm_response, re.DOTALL)
        for name, content in api_matches:
            contract = self._parse_api_contract(name, content)
            if contract:
                result["api_contracts"].append(contract.__dict__)

        # Extract decisions (ADRs)
        decision_pattern = r'###\s*Decision:\s*(.+?)\n(.*?)(?=###\s*Decision|## |$)'
        decision_matches = re.findall(decision_pattern, llm_response, re.DOTALL)
        for title, content in decision_matches:
            result["decisions"].append({
                "title": title.strip(),
                "content": content.strip(),
            })

        return result

    def _parse_component(self, name: str, content: str) -> Optional[ArchitectureComponent]:
        """Parse a single component block"""
        resp_match = re.search(r'\*\*Responsibility:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
        tech_match = re.search(r'\*\*Technology:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)

        interface_match = re.search(r'\*\*Interfaces?:\*\*\s*(.+?)(?:\n\*\*|$)', content, re.DOTALL | re.IGNORECASE)
        interfaces = []
        if interface_match:
            interfaces = [i.strip() for i in interface_match.group(1).split(',')]

        dep_match = re.search(r'\*\*Dependencies:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
        dependencies = []
        if dep_match:
            dependencies = [d.strip() for d in dep_match.group(1).split(',')]

        return ArchitectureComponent(
            name=name.strip(),
            responsibility=resp_match.group(1).strip() if resp_match else "Not specified",
            technology=tech_match.group(1).strip() if tech_match else "Not specified",
            interfaces=interfaces,
            dependencies=dependencies,
        )

    def _parse_api_contract(self, name: str, content: str) -> Optional[APIContract]:
        """Parse an API contract block"""
        method_match = re.search(r'\*\*Method:\*\*\s*(\w+)', content, re.IGNORECASE)
        path_match = re.search(r'\*\*Path:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)

        return APIContract(
            name=name.strip(),
            method=method_match.group(1).upper() if method_match else "GET",
            path=path_match.group(1).strip() if path_match else "/api/unknown",
            request_schema={},
            response_schema={},
            error_codes=[],
        )

    def extract_code(self, llm_response: str) -> List[CodeBlock]:
        """
        Extract code blocks from Developer response.

        Args:
            llm_response: Raw LLM response text

        Returns:
            List of CodeBlock objects
        """
        code_blocks = []

        # Pattern for code blocks with language and optional filename
        # Matches ```python\n# file: path/to/file.py\n...```
        pattern = r'```(\w+)?\n(?:#\s*file:\s*(.+?)\n)?(.*?)```'
        matches = re.findall(pattern, llm_response, re.DOTALL)

        for lang, filename, content in matches:
            language = lang or "python"
            file = filename.strip() if filename else self._infer_filename(language, content)
            description = self._extract_code_description(content)

            code_blocks.append(CodeBlock(
                filename=file,
                language=language,
                content=content.strip(),
                description=description,
            ))

        return code_blocks

    def _infer_filename(self, language: str, content: str) -> str:
        """Infer filename from language and content"""
        extensions = {
            "python": ".py",
            "typescript": ".ts",
            "javascript": ".js",
            "go": ".go",
            "rust": ".rs",
            "java": ".java",
        }

        # Try to find class or function name
        class_match = re.search(r'class\s+(\w+)', content)
        func_match = re.search(r'def\s+(\w+)', content)

        name = "module"
        if class_match:
            name = self._to_snake_case(class_match.group(1))
        elif func_match:
            name = func_match.group(1)

        ext = extensions.get(language, ".txt")
        return f"{name}{ext}"

    def _to_snake_case(self, name: str) -> str:
        """Convert CamelCase to snake_case"""
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    def _extract_code_description(self, content: str) -> str:
        """Extract description from docstring or comments"""
        # Python docstring
        docstring_match = re.search(r'"""(.+?)"""', content, re.DOTALL)
        if docstring_match:
            return docstring_match.group(1).strip().split('\n')[0]

        # Comment block
        comment_match = re.search(r'^#\s*(.+?)$', content, re.MULTILINE)
        if comment_match:
            return comment_match.group(1).strip()

        return "Code implementation"

    def extract_tests(self, llm_response: str) -> List[TestCase]:
        """
        Extract test cases from QA Engineer response.

        Args:
            llm_response: Raw LLM response text

        Returns:
            List of TestCase objects
        """
        test_cases = []

        # Pattern for test case blocks
        tc_pattern = r'###\s*TC-(\d+):\s*(.+?)\n(.*?)(?=###\s*TC-|## |$)'
        tc_matches = re.findall(tc_pattern, llm_response, re.DOTALL)

        for tc_id, name, content in tc_matches:
            test_case = self._parse_test_case(tc_id, name, content)
            if test_case:
                test_cases.append(test_case)

        # Extract test code blocks
        code_blocks = self.extract_code(llm_response)
        for block in code_blocks:
            if 'test' in block.filename.lower():
                # Associate code with matching test case or create new
                for tc in test_cases:
                    if tc.test_code is None:
                        tc.test_code = block.content
                        break

        return test_cases

    def _parse_test_case(self, tc_id: str, name: str, content: str) -> Optional[TestCase]:
        """Parse a single test case block"""
        type_match = re.search(r'\*\*Type:\*\*\s*(\w+)', content, re.IGNORECASE)
        priority_match = re.search(r'\*\*Priority:\*\*\s*(\w+)', content, re.IGNORECASE)
        story_match = re.search(r'\*\*Related Story:\*\*\s*(.+?)(?:\n|$)', content, re.IGNORECASE)

        # Extract preconditions
        precond_match = re.search(r'\*\*Preconditions:\*\*\s*(.*?)(?:\*\*Test Steps|$)', content, re.DOTALL | re.IGNORECASE)
        preconditions = []
        if precond_match:
            preconditions = [p.strip() for p in re.findall(r'[-•]\s*(.+)', precond_match.group(1))]

        # Extract test steps
        steps_match = re.search(r'\*\*Test Steps:\*\*\s*(.*?)(?:\*\*Expected|$)', content, re.DOTALL | re.IGNORECASE)
        steps = []
        if steps_match:
            steps = [s.strip() for s in re.findall(r'\d+\.\s*(.+)', steps_match.group(1))]

        # Extract expected result
        expected_match = re.search(r'\*\*Expected Result:\*\*\s*(.*?)(?:\*\*|$)', content, re.DOTALL | re.IGNORECASE)
        expected = expected_match.group(1).strip() if expected_match else "Test passes"

        return TestCase(
            id=f"TC-{tc_id}",
            name=name.strip(),
            test_type=type_match.group(1).lower() if type_match else "unit",
            priority=priority_match.group(1) if priority_match else "Medium",
            related_story=story_match.group(1).strip() if story_match else None,
            preconditions=preconditions,
            steps=steps,
            expected_result=expected,
        )

    def extract_all(self, llm_response: str, persona: str) -> Dict[str, Any]:
        """
        Extract all artifacts based on persona type.

        Args:
            llm_response: Raw LLM response text
            persona: Persona identifier (sarah, marcus, alex, priya)

        Returns:
            Dict with extracted artifacts
        """
        if persona == "sarah":
            stories = self.extract_stories(llm_response)
            return {
                "type": "user_stories",
                "stories": [s.__dict__ for s in stories],
                "count": len(stories),
            }
        elif persona == "marcus":
            arch = self.extract_architecture(llm_response)
            return {
                "type": "architecture",
                **arch,
            }
        elif persona == "alex":
            code = self.extract_code(llm_response)
            return {
                "type": "code",
                "files": [c.__dict__ for c in code],
                "count": len(code),
            }
        elif persona == "priya":
            tests = self.extract_tests(llm_response)
            return {
                "type": "test_cases",
                "tests": [t.__dict__ for t in tests],
                "count": len(tests),
            }
        else:
            # Raw output for unknown personas
            return {
                "type": "raw",
                "content": llm_response,
            }

    def reset_counters(self):
        """Reset ID counters"""
        self._story_counter = 0
        self._test_counter = 0


# Singleton instance
_extractor: Optional[ArtifactExtractor] = None


def get_artifact_extractor() -> ArtifactExtractor:
    """Get or create singleton artifact extractor"""
    global _extractor
    if _extractor is None:
        _extractor = ArtifactExtractor()
    return _extractor
