#!/usr/bin/env python3
"""
Unit Tests for SolutionReviewerPersona
Tests the comprehensive solution evaluation and pass/fail decision making logic.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from personas.classes.solution_reviewer_persona import SolutionReviewerPersona

# Use Poetry and relative imports instead of hardcoded paths



class TestSolutionReviewerPersona:
    """Test SolutionReviewerPersona functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_persona_data = {
            "persona_metadata": {
                "persona_name": "Senior Solution Reviewer",
                "persona_id": "solution_reviewer_v2",
            },
            "capabilities": ["solution_evaluation", "quality_assessment"],
            "specializations": ["architecture_review", "quality_assurance"],
        }

        # Create temporary persona file
        self.temp_persona_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(self.mock_persona_data, self.temp_persona_file)
        self.temp_persona_file.close()

        self.reviewer = SolutionReviewerPersona(self.temp_persona_file.name)

    def teardown_method(self):
        """Clean up test fixtures"""
        Path(self.temp_persona_file.name).unlink(missing_ok=True)

    def test_persona_initialization(self):
        """Test persona initialization and data loading"""
        assert self.reviewer.persona_path == self.temp_persona_file.name
        assert self.reviewer.persona_data == self.mock_persona_data

    def test_load_persona_definition(self):
        """Test persona definition loading"""
        loaded_data = self.reviewer._load_persona_definition()
        assert loaded_data["persona_metadata"]["persona_name"] == "Senior Solution Reviewer"
        assert loaded_data["persona_metadata"]["persona_id"] == "solution_reviewer_v2"

    def test_conduct_solution_review_pass(self):
        """Test solution review with high quality scores - should PASS"""
        mock_deliverables = {
            "requirement_analysis": {
                "analysis": {"functional_requirements": ["req1", "req2", "req3"]}
            },
            "solution_architecture": {"architecture": "complete"},
            "ux_design_analysis": {"design": "comprehensive"},
            "program_management": {"management": "thorough"},
            "iterative_development": {
                "qa_implementation": {
                    "qa_implementation": {
                        "quality_score": 95,
                        "critical_issues": 0,
                        "test_strategy_defined": True,
                        "automated_tests_created": True,
                        "performance_tests_implemented": True,
                        "security_tests_conducted": True,
                        "accessibility_validated": True,
                    }
                },
                "total_iterations": 3,
                "qa_signoff_granted": True,
            },
        }

        result = self.reviewer.conduct_solution_review(mock_deliverables, "test requirement")

        assert "solution_review" in result
        assert "detailed_findings" in result
        assert result["solution_review"]["review_decision"] == "PASS"
        assert result["solution_review"]["deployment_readiness"] == True
        assert result["solution_review"]["overall_score"] >= 90
        assert result["detailed_findings"]["compliance_status"] == "COMPLIANT"

    def test_conduct_solution_review_conditional_pass(self):
        """Test solution review with good quality scores - should CONDITIONAL_PASS"""
        mock_deliverables = {
            "requirement_analysis": {"analysis": {"functional_requirements": ["req1", "req2"]}},
            "solution_architecture": {"architecture": "complete"},
            "ux_design_analysis": {"design": "adequate"},
            "program_management": {"management": "sufficient"},
            "iterative_development": {
                "qa_implementation": {
                    "qa_implementation": {
                        "quality_score": 80,
                        "critical_issues": 0,
                        "test_strategy_defined": True,
                        "automated_tests_created": True,
                        "performance_tests_implemented": False,
                        "security_tests_conducted": True,
                        "accessibility_validated": False,
                    }
                },
                "total_iterations": 2,
            },
        }

        result = self.reviewer.conduct_solution_review(mock_deliverables, "test requirement")

        assert result["solution_review"]["review_decision"] == "CONDITIONAL_PASS"
        assert result["solution_review"]["deployment_readiness"] == True
        assert 75 <= result["solution_review"]["overall_score"] < 90

    def test_conduct_solution_review_rework(self):
        """Test solution review with poor quality - should REWORK"""
        mock_deliverables = {
            "requirement_analysis": {"analysis": {"functional_requirements": ["req1", "req2"]}},
            "solution_architecture": {
                "architecture": "complete",
                "technical_docs": ["doc1", "doc2"],
            },
            "iterative_development": {
                "qa_implementation": {
                    "qa_implementation": {
                        "quality_score": 75,
                        "critical_issues": 1,
                        "test_strategy_defined": True,
                        "automated_tests_created": True,
                        "unit_tests_pass": True,
                        "integration_tests_pass": True,
                    }
                }
            },
        }

        result = self.reviewer.conduct_solution_review(mock_deliverables, "test requirement")

        assert result["solution_review"]["review_decision"] == "REWORK"
        assert result["solution_review"]["deployment_readiness"] == False
        assert len(result["solution_review"]["critical_issues"]) > 0
        assert 60 <= result["solution_review"]["overall_score"] < 75

    def test_conduct_solution_review_fail(self):
        """Test solution review with very poor quality - should FAIL"""
        mock_deliverables = {
            "requirement_analysis": {},
            "iterative_development": {
                "qa_implementation": {
                    "qa_implementation": {
                        "quality_score": 30,  # Very low score
                        "critical_issues": 5,  # High critical issues
                        "test_strategy_defined": False,
                        "automated_tests_created": False,
                        "performance_tests_implemented": False,
                        "security_tests_conducted": False,
                    }
                }
            },
        }

        result = self.reviewer.conduct_solution_review(mock_deliverables, "test requirement")

        assert result["solution_review"]["review_decision"] == "FAIL"
        assert result["solution_review"]["deployment_readiness"] == False
        assert len(result["solution_review"]["critical_issues"]) > 0
        assert result["solution_review"]["overall_score"] < 60

    def test_evaluate_technical_quality_high_score(self):
        """Test technical quality evaluation with high QA score"""
        mock_iterative_dev = {
            "qa_implementation": {"qa_implementation": {"quality_score": 90, "critical_issues": 0}}
        }

        score = self.reviewer._evaluate_technical_quality(mock_iterative_dev)
        assert score == 90.0

    def test_evaluate_technical_quality_with_penalties(self):
        """Test technical quality evaluation with critical issues penalty"""
        mock_iterative_dev = {
            "qa_implementation": {
                "qa_implementation": {
                    "quality_score": 80,
                    "critical_issues": 2,  # Should penalize 20 points
                }
            }
        }

        score = self.reviewer._evaluate_technical_quality(mock_iterative_dev)
        assert score == 60.0  # 80 - (2 * 10)

    def test_evaluate_technical_quality_empty_data(self):
        """Test technical quality evaluation with no data"""
        score = self.reviewer._evaluate_technical_quality({})
        assert score == 50.0  # Default fallback score

    def test_evaluate_documentation_quality_complete(self):
        """Test documentation quality evaluation with all sections"""
        mock_deliverables = {
            "requirement_analysis": {"complete": True},
            "solution_architecture": {"complete": True},
            "ux_design_analysis": {"complete": True},
            "program_management": {"complete": True},
        }

        score = self.reviewer._evaluate_documentation_quality(mock_deliverables)
        assert score == 100.0

    def test_evaluate_documentation_quality_partial(self):
        """Test documentation quality evaluation with missing sections"""
        mock_deliverables = {
            "requirement_analysis": {"complete": True},
            "solution_architecture": {"complete": True},
            # Missing ux_design_analysis and program_management
        }

        score = self.reviewer._evaluate_documentation_quality(mock_deliverables)
        assert score == 50.0  # 2 out of 4 sections

    def test_evaluate_test_coverage_complete(self):
        """Test test coverage evaluation with all tests implemented"""
        mock_iterative_dev = {
            "qa_implementation": {
                "qa_implementation": {
                    "test_strategy_defined": True,
                    "automated_tests_created": True,
                    "performance_tests_implemented": True,
                    "security_tests_conducted": True,
                    "accessibility_validated": True,
                }
            }
        }

        score = self.reviewer._evaluate_test_coverage(mock_iterative_dev)
        assert score == 100.0  # 20+30+20+20+10

    def test_evaluate_test_coverage_partial(self):
        """Test test coverage evaluation with some tests missing"""
        mock_iterative_dev = {
            "qa_implementation": {
                "qa_implementation": {
                    "test_strategy_defined": True,
                    "automated_tests_created": True,
                    "performance_tests_implemented": False,
                    "security_tests_conducted": False,
                    "accessibility_validated": False,
                }
            }
        }

        score = self.reviewer._evaluate_test_coverage(mock_iterative_dev)
        assert score == 50.0  # 20+30 only

    def test_evaluate_test_coverage_empty(self):
        """Test test coverage evaluation with no data"""
        score = self.reviewer._evaluate_test_coverage({})
        assert score == 60.0  # Default fallback

    def test_evaluate_business_alignment(self):
        """Test business alignment evaluation"""
        requirement_analysis = {"analysis": {"functional_requirements": ["req1", "req2"]}}
        iterative_dev = {"total_iterations": 3}  # Shows improvement/responsiveness

        score = self.reviewer._evaluate_business_alignment(requirement_analysis, iterative_dev)
        assert score == 100.0  # 80 base + 10 for requirements + 10 for iterations

    def test_make_decision_pass_scenario(self):
        """Test decision making for PASS scenario"""
        decision = self.reviewer._make_decision(
            overall_score=92.0, technical=95.0, docs=90.0, tests=85.0, business=90.0
        )

        assert decision["decision"] == "PASS"
        assert decision["deployment_ready"] == True
        assert len(decision["critical_issues"]) == 0

    def test_make_decision_rework_scenario(self):
        """Test decision making for REWORK scenario"""
        decision = self.reviewer._make_decision(
            overall_score=65.0,
            technical=50.0,  # Below threshold
            docs=80.0,
            tests=60.0,  # Below threshold
            business=70.0,
        )

        assert decision["decision"] == "REWORK"
        assert decision["deployment_ready"] == False
        assert len(decision["critical_issues"]) > 0
        assert "Technical implementation below acceptable standards" in decision["critical_issues"]

    def test_assess_risks_high_score(self):
        """Test risk assessment for high quality solution"""
        iterative_dev = {"qa_signoff_granted": True}
        risks = self.reviewer._assess_risks(90.0, iterative_dev)

        assert risks["risk_level"] == "LOW"
        assert len(risks["identified_risks"]) == 0
        assert risks["mitigation_required"] == False

    def test_assess_risks_low_score(self):
        """Test risk assessment for low quality solution"""
        iterative_dev = {"qa_signoff_granted": False}
        risks = self.reviewer._assess_risks(55.0, iterative_dev)

        assert risks["risk_level"] == "CRITICAL"
        assert len(risks["identified_risks"]) > 0
        assert risks["mitigation_required"] == True

    def test_solution_review_integration(self):
        """Test complete solution review integration"""
        comprehensive_deliverables = {
            "requirement_analysis": {
                "analysis": {
                    "functional_requirements": ["user_auth", "data_storage", "api_endpoints"]
                }
            },
            "solution_architecture": {
                "architecture_type": "microservices",
                "components": ["auth_service", "data_service", "api_gateway"],
            },
            "ux_design_analysis": {
                "user_flows": ["login", "dashboard", "settings"],
                "wireframes": True,
            },
            "program_management": {"project_plan": "comprehensive", "risk_assessment": "complete"},
            "iterative_development": {
                "qa_implementation": {
                    "qa_implementation": {
                        "quality_score": 88,
                        "critical_issues": 1,
                        "test_strategy_defined": True,
                        "automated_tests_created": True,
                        "performance_tests_implemented": True,
                        "security_tests_conducted": True,
                        "accessibility_validated": False,
                    }
                },
                "total_iterations": 4,
                "qa_signoff_granted": True,
            },
        }

        result = self.reviewer.conduct_solution_review(
            comprehensive_deliverables, "Comprehensive web application"
        )

        # Verify all major sections are present
        assert "solution_review" in result
        assert "detailed_findings" in result

        # Verify review decision is appropriate
        review = result["solution_review"]
        assert review["review_decision"] in ["PASS", "CONDITIONAL_PASS", "REWORK"]
        assert isinstance(review["overall_score"], (int, float))
        assert isinstance(review["technical_quality_score"], (int, float))
        assert isinstance(review["documentation_quality_score"], (int, float))
        assert isinstance(review["test_coverage_score"], (int, float))
        assert isinstance(review["business_alignment_score"], (int, float))

        # Verify detailed findings structure
        findings = result["detailed_findings"]
        assert "strengths" in findings
        assert "areas_for_improvement" in findings
        assert "compliance_status" in findings
        assert "risk_assessment" in findings

        # Verify risk assessment structure
        risk_assessment = findings["risk_assessment"]
        assert "risk_level" in risk_assessment
        assert "identified_risks" in risk_assessment
        assert "mitigation_required" in risk_assessment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
