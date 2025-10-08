#!/usr/bin/env python3
"""
Unit tests for Phase-Aware Complexity Analyzer
"""
from unittest.mock import MagicMock, patch

import pytest
from shared.intelligence.complexity_analyzer import ComplexityAnalysis
from shared.intelligence.phase_complexity_analyzer import (
    ComplexityLevel,
    CrossPhaseComplexityFactor,
    PhaseComplexityAnalysis,
    PhaseComplexityAnalyzer,
)
from shared.orchestration.multi_phase_engine import ProjectPhase


class TestPhaseComplexityAnalyzer:
    """Test suite for Phase-Aware Complexity Analyzer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.analyzer = PhaseComplexityAnalyzer()

    def test_analyzer_initialization(self):
        """Test analyzer initialization"""
        assert self.analyzer is not None
        assert hasattr(self.analyzer, "base_analyzer")
        assert hasattr(self.analyzer, "phase_patterns")

    def test_analyze_phase_complexity_requirements(self):
        """Test requirements phase complexity analysis"""
        requirement = "Build e-commerce platform with user management, payment processing, and inventory tracking"

        result = self.analyzer.analyze_phase_complexity(
            requirement, ProjectPhase.REQUIREMENTS_ANALYSIS
        )

        assert isinstance(result, PhaseComplexityAnalysis)
        assert result.phase == ProjectPhase.REQUIREMENTS_ANALYSIS
        assert result.complexity_level in [
            ComplexityLevel.SIMPLE,
            ComplexityLevel.MODERATE,
            ComplexityLevel.COMPLEX,
        ]
        assert result.effort_estimate_hours > 0

    def test_analyze_phase_complexity_design(self):
        """Test design phase complexity analysis"""
        requirement = (
            "Design scalable microservices architecture with API gateway and service discovery"
        )

        result = self.analyzer.analyze_phase_complexity(requirement, ProjectPhase.SYSTEM_DESIGN)

        assert isinstance(result, PhaseComplexityAnalysis)
        assert result.phase == ProjectPhase.SYSTEM_DESIGN
        assert "architecture" in result.phase_specific_factors
        assert len(result.recommendations) > 0

    def test_analyze_phase_complexity_implementation(self):
        """Test implementation phase complexity analysis"""
        requirement = "Implement REST API with authentication, database integration, and real-time notifications"

        result = self.analyzer.analyze_phase_complexity(requirement, ProjectPhase.IMPLEMENTATION)

        assert isinstance(result, PhaseComplexityAnalysis)
        assert result.phase == ProjectPhase.IMPLEMENTATION
        assert result.complexity_score > 0
        assert "implementation" in result.phase_specific_factors

    def test_analyze_phase_complexity_testing(self):
        """Test testing phase complexity analysis"""
        requirement = "Test distributed system with integration tests, performance tests, and security validation"

        result = self.analyzer.analyze_phase_complexity(requirement, ProjectPhase.TESTING)

        assert isinstance(result, PhaseComplexityAnalysis)
        assert result.phase == ProjectPhase.TESTING
        assert "testing" in result.phase_specific_factors

    def test_cross_phase_complexity_factors(self):
        """Test cross-phase complexity factor analysis"""
        requirement = "Build AI-powered recommendation system with machine learning models"

        factors = self.analyzer.analyze_cross_phase_complexity_factors(requirement)

        assert isinstance(factors, dict)
        # Should identify ML as a cross-phase complexity factor
        ml_factors = [
            f
            for f in factors.values()
            if "machine_learning" in str(f).lower() or "ai" in str(f).lower()
        ]
        assert len(ml_factors) > 0

    def test_requirements_phase_analysis(self):
        """Test specific requirements phase analysis"""
        requirement = "User authentication with OAuth, role-based access control, and audit logging"

        analysis = self.analyzer._analyze_requirements_phase(requirement)

        assert isinstance(analysis, dict)
        assert "functional_requirements" in analysis
        assert "non_functional_requirements" in analysis
        assert "complexity_indicators" in analysis

    def test_design_phase_analysis(self):
        """Test specific design phase analysis"""
        requirement = (
            "Microservices architecture with event-driven communication and data consistency"
        )

        analysis = self.analyzer._analyze_design_phase(requirement)

        assert isinstance(analysis, dict)
        assert "architecture_complexity" in analysis
        assert "component_complexity" in analysis
        assert "integration_complexity" in analysis

    def test_implementation_phase_analysis(self):
        """Test specific implementation phase analysis"""
        requirement = "React frontend with Redux state management and WebSocket real-time updates"

        analysis = self.analyzer._analyze_implementation_phase(requirement)

        assert isinstance(analysis, dict)
        assert "technology_complexity" in analysis
        assert "integration_complexity" in analysis
        assert "development_complexity" in analysis

    def test_testing_phase_analysis(self):
        """Test specific testing phase analysis"""
        requirement = (
            "Comprehensive testing including unit, integration, performance, and security tests"
        )

        analysis = self.analyzer._analyze_testing_phase(requirement)

        assert isinstance(analysis, dict)
        assert "test_coverage_complexity" in analysis
        assert "test_automation_complexity" in analysis
        assert "test_environment_complexity" in analysis

    def test_complexity_level_calculation(self):
        """Test complexity level calculation"""
        # Mock base analysis
        mock_base_analysis = ComplexityAnalysis(
            complexity_score=15.0,
            complexity_level=ComplexityLevel.MODERATE,
            functional_domains=[],
            technical_domains=[],
            integration_points=[],
            risk_factors=[],
            estimated_effort_hours=40.0,
        )

        # Mock phase analysis
        mock_phase_analysis = {
            "complexity_indicators": {"score": 8},
            "development_complexity": {"score": 6},
            "integration_complexity": {"score": 4},
        }

        # Mock cross-phase analysis
        mock_cross_phase = {}

        level = self.analyzer._calculate_phase_complexity_level(
            mock_base_analysis, mock_phase_analysis, mock_cross_phase, ProjectPhase.IMPLEMENTATION
        )

        assert level in [ComplexityLevel.SIMPLE, ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX]

    def test_effort_estimation(self):
        """Test effort estimation for phases"""
        base_effort = 40.0
        phase_multipliers = {"implementation": 1.5, "testing": 0.8}

        effort = self.analyzer._estimate_phase_effort(
            base_effort, ProjectPhase.IMPLEMENTATION, phase_multipliers, ComplexityLevel.MODERATE
        )

        assert effort > 0
        assert effort >= base_effort  # Should be at least base effort

    def test_pattern_matching(self):
        """Test pattern matching for different technologies"""
        # Test web patterns
        web_patterns = self.analyzer._match_patterns(
            "React frontend with REST API", self.analyzer.phase_patterns["web_development"]
        )
        assert len(web_patterns) > 0

        # Test AI/ML patterns
        ai_patterns = self.analyzer._match_patterns(
            "Machine learning model with TensorFlow", self.analyzer.phase_patterns["ai_ml"]
        )
        assert len(ai_patterns) > 0

        # Test database patterns
        db_patterns = self.analyzer._match_patterns(
            "PostgreSQL database with Redis cache", self.analyzer.phase_patterns["database"]
        )
        assert len(db_patterns) > 0

    def test_risk_factor_identification(self):
        """Test risk factor identification"""
        # High-risk requirement
        high_risk_req = (
            "Blockchain integration with custom consensus algorithm and zero-downtime deployment"
        )
        risks = self.analyzer._identify_phase_risks(high_risk_req, ProjectPhase.IMPLEMENTATION)

        assert len(risks) > 0
        assert any("blockchain" in risk.lower() or "consensus" in risk.lower() for risk in risks)

        # Low-risk requirement
        low_risk_req = "Simple CRUD application with basic authentication"
        low_risks = self.analyzer._identify_phase_risks(low_risk_req, ProjectPhase.IMPLEMENTATION)

        assert len(low_risks) <= len(risks)  # Should have fewer risks

    def test_recommendation_generation(self):
        """Test recommendation generation"""
        # Complex requirement
        complex_req = "Distributed system with microservices, event sourcing, and CQRS pattern"
        recommendations = self.analyzer._generate_phase_recommendations(
            complex_req, ProjectPhase.SYSTEM_DESIGN, ComplexityLevel.COMPLEX
        )

        assert len(recommendations) > 0
        assert any(
            "design" in rec.lower() or "architecture" in rec.lower() for rec in recommendations
        )

    def test_technology_complexity_assessment(self):
        """Test technology-specific complexity assessment"""
        # Test modern tech stack
        modern_tech = "React with TypeScript, GraphQL, and serverless architecture"
        complexity = self.analyzer._assess_technology_complexity(modern_tech)

        assert complexity > 0

        # Test legacy tech stack
        legacy_tech = "PHP with MySQL and basic HTML/CSS"
        legacy_complexity = self.analyzer._assess_technology_complexity(legacy_tech)

        # Modern should generally be more complex
        assert complexity >= legacy_complexity

    def test_integration_complexity_analysis(self):
        """Test integration complexity analysis"""
        requirement = "Integrate with payment gateway, email service, and third-party analytics"

        integration_analysis = self.analyzer._analyze_integration_complexity(requirement)

        assert "external_integrations" in integration_analysis
        assert "integration_points" in integration_analysis
        assert integration_analysis["complexity_score"] > 0

    def test_scalability_requirements_analysis(self):
        """Test scalability requirements analysis"""
        # High scalability requirement
        high_scale = "Support 1 million concurrent users with 99.9% uptime"
        scalability = self.analyzer._analyze_scalability_requirements(high_scale)

        assert scalability["complexity_score"] > 5
        assert "high_availability" in scalability["factors"]

        # Low scalability requirement
        low_scale = "Support 100 concurrent users"
        low_scalability = self.analyzer._analyze_scalability_requirements(low_scale)

        assert scalability["complexity_score"] > low_scalability["complexity_score"]

    def test_security_complexity_analysis(self):
        """Test security complexity analysis"""
        # High security requirement
        high_security = "GDPR compliance, end-to-end encryption, and multi-factor authentication"
        security = self.analyzer._analyze_security_complexity(high_security)

        assert security["complexity_score"] > 5
        assert "encryption" in security["requirements"]

    def test_performance_requirements_analysis(self):
        """Test performance requirements analysis"""
        # Strict performance requirement
        perf_req = "Response time under 100ms with sub-second page loads"
        performance = self.analyzer._analyze_performance_requirements(perf_req)

        assert performance["complexity_score"] > 3
        assert "response_time" in performance["metrics"]

    @pytest.mark.parametrize(
        "phase,requirement,expected_min_score",
        [
            (ProjectPhase.REQUIREMENTS_ANALYSIS, "Simple CRUD app", 1),
            (ProjectPhase.SYSTEM_DESIGN, "Microservices architecture", 5),
            (ProjectPhase.IMPLEMENTATION, "React with TypeScript", 3),
            (ProjectPhase.TESTING, "Unit and integration tests", 2),
        ],
    )
    def test_phase_complexity_parametrized(self, phase, requirement, expected_min_score):
        """Test phase complexity with different inputs"""
        result = self.analyzer.analyze_phase_complexity(requirement, phase)

        assert result.complexity_score >= expected_min_score
        assert result.phase == phase

    def test_complexity_caching(self):
        """Test complexity analysis caching"""
        requirement = "Test caching requirement"

        # First call
        result1 = self.analyzer.analyze_phase_complexity(requirement, ProjectPhase.IMPLEMENTATION)

        # Second call with same parameters
        result2 = self.analyzer.analyze_phase_complexity(requirement, ProjectPhase.IMPLEMENTATION)

        # Results should be identical (assuming caching is implemented)
        assert result1.complexity_score == result2.complexity_score
        assert result1.complexity_level == result2.complexity_level

    def test_error_handling_invalid_phase(self):
        """Test error handling for invalid phase"""
        with pytest.raises((ValueError, TypeError)):
            self.analyzer.analyze_phase_complexity("Test requirement", "invalid_phase")

    def test_error_handling_empty_requirement(self):
        """Test error handling for empty requirement"""
        result = self.analyzer.analyze_phase_complexity("", ProjectPhase.IMPLEMENTATION)

        # Should handle gracefully
        assert result is not None
        assert result.complexity_score >= 0
