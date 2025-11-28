#!/usr/bin/env python3
"""
Requirement Analyzer

Parses natural language requirements into structured data for DAG generation.
Uses Claude AI to extract key information from user requirements.
"""

import logging
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from anthropic import Anthropic
import os

logger = logging.getLogger(__name__)


@dataclass
class RequirementAnalysis:
    """Structured analysis of user requirements"""
    functional_requirements: List[str]
    technical_components: List[str]
    complexity: str  # simple, medium, complex, enterprise
    estimated_duration: str
    key_features: List[str]
    tech_stack_hints: List[str]
    deployment_targets: List[str]
    scalability_needs: Optional[str] = None
    security_requirements: List[str] = None
    integrations: List[str] = None
    raw_requirement: str = ""


class RequirementAnalyzer:
    """
    Analyzes natural language requirements and extracts structured information.

    Uses Claude AI to intelligently parse requirements and identify:
    - Functional requirements
    - Technical components needed
    - Complexity level
    - Tech stack preferences
    - Deployment needs
    """

    ANALYSIS_PROMPT_TEMPLATE = """You are a senior technical analyst. Analyze the following project requirement and extract structured information.

PROJECT REQUIREMENT:
{requirement}

CONVERSATION CONTEXT (for additional details):
{context}

Analyze and provide a comprehensive breakdown in JSON format:

{{
  "functional_requirements": [
    "List of specific functional requirements (what the system should do)"
  ],
  "technical_components": [
    "List of technical components needed (authentication, database, API, frontend, etc.)"
  ],
  "key_features": [
    "Core features that define this project"
  ],
  "complexity": "simple|medium|complex|enterprise",
  "estimated_duration": "X-Y weeks/months",
  "tech_stack_hints": [
    "Technologies mentioned or implied (React, Python, PostgreSQL, etc.)"
  ],
  "deployment_targets": [
    "Where should this be deployed (AWS, Google Cloud, on-premise, mobile stores, etc.)"
  ],
  "scalability_needs": "Description of scale requirements if mentioned",
  "security_requirements": [
    "Security/compliance needs (authentication, encryption, GDPR, etc.)"
  ],
  "integrations": [
    "Third-party integrations mentioned (payment, auth providers, APIs, etc.)"
  ]
}}

Be thorough and extract all relevant details. If something is not mentioned, use reasonable defaults for that type of project."""

    def __init__(self):
        """Initialize requirement analyzer with Claude AI"""
        self.anthropic_client = None

        # Try to initialize Claude AI client
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            try:
                self.anthropic_client = Anthropic(api_key=api_key)
                logger.info("✅ RequirementAnalyzer initialized with Claude AI")
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize Claude AI: {e}")
                logger.info("Will use fallback analysis method")
        else:
            logger.warning("⚠️  ANTHROPIC_API_KEY not found, using fallback analysis")

    async def analyze_requirement(
        self,
        requirement: str,
        conversation_context: Optional[List[Dict]] = None
    ) -> RequirementAnalysis:
        """
        Analyze user requirement and extract structured information.

        Args:
            requirement: Natural language project requirement
            conversation_context: Previous conversation messages for context

        Returns:
            RequirementAnalysis with structured information
        """
        logger.info(f"Analyzing requirement: {requirement[:100]}...")

        # If Claude AI is available, use it
        if self.anthropic_client:
            return await self._analyze_with_ai(requirement, conversation_context)
        else:
            return await self._analyze_with_fallback(requirement)

    async def _analyze_with_ai(
        self,
        requirement: str,
        conversation_context: Optional[List[Dict]] = None
    ) -> RequirementAnalysis:
        """Use Claude AI to analyze requirements"""

        # Format conversation context
        context_str = ""
        if conversation_context:
            recent_context = conversation_context[-5:]  # Last 5 messages
            context_str = "\n".join([
                f"{msg.get('role', 'unknown')}: {msg.get('content', '')[:200]}"
                for msg in recent_context
            ])

        # Build prompt
        prompt = self.ANALYSIS_PROMPT_TEMPLATE.format(
            requirement=requirement,
            context=context_str or "No additional context"
        )

        try:
            # Call Claude AI
            response = self.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=2000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            # Extract JSON from response
            response_text = response.content[0].text

            # Parse JSON (find JSON block in response)
            import json
            import re

            # Try to extract JSON from markdown code block or direct JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON object directly
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                json_str = json_match.group(0) if json_match else response_text

            analysis_data = json.loads(json_str)

            # Create RequirementAnalysis object
            analysis = RequirementAnalysis(
                functional_requirements=analysis_data.get('functional_requirements', []),
                technical_components=analysis_data.get('technical_components', []),
                complexity=analysis_data.get('complexity', 'medium'),
                estimated_duration=analysis_data.get('estimated_duration', '4-8 weeks'),
                key_features=analysis_data.get('key_features', []),
                tech_stack_hints=analysis_data.get('tech_stack_hints', []),
                deployment_targets=analysis_data.get('deployment_targets', []),
                scalability_needs=analysis_data.get('scalability_needs'),
                security_requirements=analysis_data.get('security_requirements', []),
                integrations=analysis_data.get('integrations', []),
                raw_requirement=requirement
            )

            logger.info(f"✅ AI analysis complete: {len(analysis.functional_requirements)} requirements, "
                       f"complexity={analysis.complexity}")

            return analysis

        except Exception as e:
            logger.error(f"Error in AI analysis: {e}")
            logger.info("Falling back to rule-based analysis")
            return await self._analyze_with_fallback(requirement)

    async def _analyze_with_fallback(self, requirement: str) -> RequirementAnalysis:
        """Fallback analysis using keyword matching and heuristics"""

        requirement_lower = requirement.lower()

        # Extract functional requirements (simple sentence splitting)
        sentences = re.split(r'[.!?]\s+', requirement)
        functional_reqs = [s.strip() for s in sentences if len(s.strip()) > 10][:10]

        # Detect technical components
        tech_components = []
        component_keywords = {
            'authentication': ['auth', 'login', 'signup', 'user management'],
            'database': ['database', 'storage', 'persist', 'data'],
            'api': ['api', 'rest', 'graphql', 'endpoint'],
            'frontend': ['frontend', 'ui', 'interface', 'web app', 'dashboard'],
            'backend': ['backend', 'server', 'service'],
            'mobile': ['mobile', 'ios', 'android', 'app'],
            'realtime': ['realtime', 'websocket', 'live', 'streaming'],
            'file_storage': ['file', 'upload', 'document', 'media'],
            'payment': ['payment', 'billing', 'subscription', 'stripe'],
            'notification': ['notification', 'email', 'sms', 'push'],
        }

        for component, keywords in component_keywords.items():
            if any(kw in requirement_lower for kw in keywords):
                tech_components.append(component)

        # Detect complexity
        complexity_indicators = {
            'enterprise': ['enterprise', 'compliance', 'audit', 'governance', 'sso'],
            'complex': ['microservice', 'distributed', 'multi-tenant', 'scale', 'kubernetes'],
            'medium': ['saas', 'api', 'dashboard', 'real-time'],
            'simple': ['simple', 'basic', 'mvp', 'prototype']
        }

        complexity = 'medium'  # default
        for level, indicators in complexity_indicators.items():
            if any(ind in requirement_lower for ind in indicators):
                complexity = level
                break

        # Extract tech stack hints
        tech_stack = []
        tech_keywords = {
            'Python': ['python', 'django', 'flask', 'fastapi'],
            'JavaScript': ['javascript', 'node', 'react', 'vue', 'angular'],
            'TypeScript': ['typescript'],
            'PostgreSQL': ['postgres', 'postgresql'],
            'MongoDB': ['mongo', 'mongodb'],
            'Redis': ['redis'],
            'Docker': ['docker', 'container'],
            'Kubernetes': ['kubernetes', 'k8s'],
            'AWS': ['aws', 'amazon web services'],
            'React': ['react'],
            'React Native': ['react native'],
        }

        for tech, keywords in tech_keywords.items():
            if any(kw in requirement_lower for kw in keywords):
                tech_stack.append(tech)

        # Detect deployment targets
        deployment_targets = []
        if any(kw in requirement_lower for kw in ['aws', 'amazon']):
            deployment_targets.append('AWS')
        if any(kw in requirement_lower for kw in ['google cloud', 'gcp']):
            deployment_targets.append('Google Cloud')
        if any(kw in requirement_lower for kw in ['azure']):
            deployment_targets.append('Azure')
        if any(kw in requirement_lower for kw in ['mobile', 'ios', 'android']):
            deployment_targets.extend(['App Store', 'Google Play'])
        if not deployment_targets:
            deployment_targets = ['Cloud (AWS/GCP/Azure)']

        # Estimate duration based on complexity
        duration_map = {
            'simple': '2-4 weeks',
            'medium': '4-8 weeks',
            'complex': '8-16 weeks',
            'enterprise': '16-24 weeks'
        }
        estimated_duration = duration_map.get(complexity, '4-8 weeks')

        # Extract security requirements
        security_reqs = []
        if 'auth' in requirement_lower or 'login' in requirement_lower:
            security_reqs.append('User authentication')
        if 'encrypt' in requirement_lower:
            security_reqs.append('Data encryption')
        if 'gdpr' in requirement_lower or 'compliance' in requirement_lower:
            security_reqs.append('Compliance (GDPR/SOC2)')
        if 'oauth' in requirement_lower:
            security_reqs.append('OAuth integration')

        # Extract integrations
        integrations = []
        integration_keywords = {
            'Stripe': ['stripe', 'payment'],
            'Google OAuth': ['google oauth', 'google login'],
            'Twilio': ['twilio', 'sms'],
            'SendGrid': ['sendgrid', 'email'],
            'Slack': ['slack'],
        }

        for integration, keywords in integration_keywords.items():
            if any(kw in requirement_lower for kw in keywords):
                integrations.append(integration)

        analysis = RequirementAnalysis(
            functional_requirements=functional_reqs,
            technical_components=tech_components,
            complexity=complexity,
            estimated_duration=estimated_duration,
            key_features=tech_components[:5],  # Use components as features
            tech_stack_hints=tech_stack,
            deployment_targets=deployment_targets,
            security_requirements=security_reqs,
            integrations=integrations,
            raw_requirement=requirement
        )

        logger.info(f"✅ Fallback analysis complete: {len(analysis.technical_components)} components, "
                   f"complexity={analysis.complexity}")

        return analysis


# Standalone test
async def test_requirement_analyzer():
    """Test requirement analyzer"""
    analyzer = RequirementAnalyzer()

    test_requirements = [
        "Build a SaaS application with user authentication, subscription billing, and admin dashboard. Deploy on AWS.",
        "I need a real-time chat app with file sharing, mobile support (iOS/Android), and Google OAuth. Should handle 10k concurrent users.",
        "Create a simple todo list app with React frontend and Python backend.",
    ]

    for requirement in test_requirements:
        print(f"\n{'='*80}")
        print(f"Requirement: {requirement}")
        print(f"{'='*80}")

        analysis = await analyzer.analyze_requirement(requirement)

        print(f"\nComplexity: {analysis.complexity}")
        print(f"Duration: {analysis.estimated_duration}")
        print(f"\nTechnical Components: {', '.join(analysis.technical_components)}")
        print(f"Tech Stack: {', '.join(analysis.tech_stack_hints)}")
        print(f"Deployment: {', '.join(analysis.deployment_targets)}")
        print(f"Security: {', '.join(analysis.security_requirements or [])}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_requirement_analyzer())
