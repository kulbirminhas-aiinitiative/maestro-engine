"""
Tests for Symphony Artifact Extractor

EPIC: MD-4123 - Symphony Real LLM Integration via claude_code_api_layer
Story: MD-4136 - Create comprehensive test suite for LLM integration
"""

import pytest

import sys
sys.path.insert(0, '/home/ec2-user/projects/maestro-platform/maestro-engine/src')

from symphony.artifact_extractor import (
    ArtifactExtractor,
    UserStory,
    ArchitectureComponent,
    CodeBlock,
    TestCase,
    get_artifact_extractor,
)


# Module-level fixtures
@pytest.fixture
def extractor():
    """Create a fresh extractor"""
    ext = ArtifactExtractor()
    ext.reset_counters()
    return ext


@pytest.fixture
def sample_story_response():
    """Sample LLM response with user stories"""
    return """
### Story: User Login

**As a** registered user
**I want** to log in with my email and password
**So that** I can access my personalized dashboard

**Acceptance Criteria:**
- Given valid credentials, When I submit the login form, Then I am redirected to my dashboard
- Given invalid credentials, When I submit the login form, Then I see an error message

**Priority:** High
**Story Points:** 5

### Story: Password Reset

**As a** user who forgot my password
**I want** to reset my password via email
**So that** I can regain access to my account

**Acceptance Criteria:**
- Given my registered email, When I request a password reset, Then I receive an email with a reset link

**Priority:** Medium
**Story Points:** 3
"""


@pytest.fixture
def sample_architecture_response():
    """Sample LLM response with architecture"""
    return """
## Architecture Overview

The system uses a microservices architecture with the following components.

### [API Gateway]
- **Responsibility:** Route requests to backend services
- **Technology:** FastAPI with uvicorn
- **Interfaces:** REST API
- **Dependencies:** Auth Service, User Service

### [Auth Service]
- **Responsibility:** Handle authentication and authorization
- **Technology:** Python with JWT
- **Interfaces:** /auth/login, /auth/refresh
- **Dependencies:** User Database

## Data Flow

1. User sends request to API Gateway
2. Gateway validates token with Auth Service
3. Request forwarded to appropriate service

### API: User Login
- **Method:** POST
- **Path:** /api/v1/auth/login

### Decision: Token Storage
**Context:** We need to decide where to store JWT tokens
**Options:**
1. HTTP-only cookies - More secure
2. LocalStorage - Easier to implement
**Decision:** HTTP-only cookies
**Rationale:** Better security against XSS
"""


@pytest.fixture
def sample_code_response():
    """Sample LLM response with code"""
    return '''
Here is the implementation:

```python
# file: src/auth/service.py
"""
Authentication Service

Handles user authentication and token management.
"""

from typing import Optional
from datetime import datetime, timedelta
import jwt


class AuthService:
    """Service for handling authentication"""

    def __init__(self, secret_key: str, token_expiry: int = 3600):
        self.secret_key = secret_key
        self.token_expiry = token_expiry

    def create_token(self, user_id: str) -> str:
        """Create a JWT token for a user"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(seconds=self.token_expiry)
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def verify_token(self, token: str) -> Optional[str]:
        """Verify token and return user_id"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload.get("user_id")
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
```

```python
# file: src/auth/router.py
"""API router for authentication endpoints"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
async def login(request: LoginRequest):
    """Handle user login"""
    # Implementation here
    return {"status": "ok"}
```
'''


@pytest.fixture
def sample_test_response():
    """Sample LLM response with test cases"""
    return """
## Test Strategy

We will use pytest for unit and integration tests.

### TC-001: Test User Login Success
**Type:** Integration
**Priority:** High
**Related Story:** US-001

**Preconditions:**
- User exists in database
- User has valid password

**Test Steps:**
1. Send POST request to /auth/login with valid credentials
2. Verify response status is 200
3. Verify response contains access token

**Expected Result:**
- User receives valid JWT token

```python
# file: tests/test_auth.py
import pytest
from fastapi.testclient import TestClient


class TestAuthEndpoints:
    def test_login_success(self):
        assert True
```

### TC-002: Test Login Invalid Credentials
**Type:** Unit
**Priority:** High
**Related Story:** US-001

**Preconditions:**
- User exists in database

**Test Steps:**
1. Send POST request with wrong password
2. Verify response status is 401

**Expected Result:**
- User receives authentication error
"""


class TestExtractStories:
    """Test user story extraction"""

    def test_extract_stories_formatted(self, extractor, sample_story_response):
        """Test extracting formatted stories"""
        stories = extractor.extract_stories(sample_story_response)

        assert len(stories) == 2

        login_story = stories[0]
        assert "Login" in login_story.title
        assert login_story.as_a == "registered user"
        assert "log in" in login_story.i_want.lower()
        assert login_story.priority == "High"
        assert login_story.story_points == 5
        assert len(login_story.acceptance_criteria) >= 1

    def test_extract_stories_simple_format(self, extractor):
        """Test extracting stories from simple format"""
        simple_text = """
        As a user, I want to log in so that I can access my account.
        As an admin, I need to manage users so that I can control access.
        """
        stories = extractor.extract_stories(simple_text)

        # At least one story should be extracted
        assert len(stories) >= 1
        assert stories[0].as_a in ["user", "admin"]

    def test_story_ids_increment(self, extractor, sample_story_response):
        """Test story IDs are unique and incrementing"""
        stories = extractor.extract_stories(sample_story_response)

        ids = [s.id for s in stories]
        assert ids[0] != ids[1]
        assert "US-001" in ids


class TestExtractArchitecture:
    """Test architecture extraction"""

    def test_extract_components(self, extractor, sample_architecture_response):
        """Test extracting architecture components"""
        arch = extractor.extract_architecture(sample_architecture_response)

        assert len(arch["components"]) >= 2

        gateway = next(
            (c for c in arch["components"] if "Gateway" in c["name"]),
            None
        )
        assert gateway is not None
        assert "FastAPI" in gateway["technology"]

    def test_extract_data_flow(self, extractor, sample_architecture_response):
        """Test extracting data flow"""
        arch = extractor.extract_architecture(sample_architecture_response)

        assert arch["data_flow"] != ""
        assert "Gateway" in arch["data_flow"] or "request" in arch["data_flow"].lower()

    def test_extract_api_contracts(self, extractor, sample_architecture_response):
        """Test extracting API contracts"""
        arch = extractor.extract_architecture(sample_architecture_response)

        assert len(arch["api_contracts"]) >= 1

    def test_extract_decisions(self, extractor, sample_architecture_response):
        """Test extracting architectural decisions"""
        arch = extractor.extract_architecture(sample_architecture_response)

        assert len(arch["decisions"]) >= 1
        decision = arch["decisions"][0]
        assert "title" in decision


class TestExtractCode:
    """Test code extraction"""

    def test_extract_code_blocks(self, extractor, sample_code_response):
        """Test extracting code blocks"""
        code = extractor.extract_code(sample_code_response)

        assert len(code) >= 2

    def test_extract_filename(self, extractor, sample_code_response):
        """Test filename extraction from code blocks"""
        code = extractor.extract_code(sample_code_response)

        filenames = [c.filename for c in code]
        assert any("service.py" in f for f in filenames)

    def test_extract_language(self, extractor, sample_code_response):
        """Test language detection"""
        code = extractor.extract_code(sample_code_response)

        for block in code:
            assert block.language == "python"

    def test_infer_filename_from_class(self, extractor):
        """Test filename inference from class name"""
        filename = extractor._infer_filename(
            "python",
            "class AuthService:\n    pass"
        )
        assert "auth_service" in filename.lower()


class TestExtractTests:
    """Test test case extraction"""

    def test_extract_test_cases(self, extractor, sample_test_response):
        """Test extracting test cases"""
        tests = extractor.extract_tests(sample_test_response)

        assert len(tests) >= 2

    def test_test_case_fields(self, extractor, sample_test_response):
        """Test test case field extraction"""
        tests = extractor.extract_tests(sample_test_response)

        test = tests[0]
        assert test.id == "TC-001"
        assert "Login" in test.name
        assert test.test_type in ["unit", "integration", "e2e"]
        assert test.priority in ["High", "Medium", "Low"]

    def test_test_steps_extracted(self, extractor, sample_test_response):
        """Test that test steps are extracted"""
        tests = extractor.extract_tests(sample_test_response)

        test = tests[0]
        assert len(test.steps) >= 1


class TestExtractAll:
    """Test extract_all convenience method"""

    def test_extract_all_sarah(self, extractor, sample_story_response):
        """Test extract_all for Sarah (Product Owner)"""
        result = extractor.extract_all(sample_story_response, "sarah")

        assert result["type"] == "user_stories"
        assert "stories" in result
        assert result["count"] >= 1

    def test_extract_all_marcus(self, extractor, sample_architecture_response):
        """Test extract_all for Marcus (Architect)"""
        result = extractor.extract_all(sample_architecture_response, "marcus")

        assert result["type"] == "architecture"
        assert "components" in result

    def test_extract_all_alex(self, extractor, sample_code_response):
        """Test extract_all for Alex (Developer)"""
        result = extractor.extract_all(sample_code_response, "alex")

        assert result["type"] == "code"
        assert "files" in result

    def test_extract_all_priya(self, extractor, sample_test_response):
        """Test extract_all for Priya (QA)"""
        result = extractor.extract_all(sample_test_response, "priya")

        assert result["type"] == "test_cases"
        assert "tests" in result

    def test_extract_all_unknown_persona(self, extractor):
        """Test extract_all for unknown persona returns raw"""
        result = extractor.extract_all("Some content", "unknown")

        assert result["type"] == "raw"
        assert "content" in result


class TestSingleton:
    """Test singleton pattern"""

    def test_get_artifact_extractor_singleton(self):
        """Test singleton returns same instance"""
        import symphony.artifact_extractor as module
        module._extractor = None

        ext1 = get_artifact_extractor()
        ext2 = get_artifact_extractor()

        assert ext1 is ext2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
