#!/usr/bin/env python3
"""
Unit Tests for MAESTRO Quality Service

This module provides comprehensive unit tests for:
- Code quality analysis and validation
- Security scanning and vulnerability detection
- Performance testing and optimization
- Compliance checking and reporting
- Code review automation
"""

import json
import os

# Import the quality service components
import sys
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "services", "quality_service"))

from comprehensive_validator import app


class TestQualityServiceAPI:
    """Test suite for Quality Service API endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_endpoint(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "quality-service"
        assert "timestamp" in data

    def test_validate_code_endpoint(self, client):
        """Test code validation endpoint"""
        validation_request = {
            "code": "def hello_world():\n    return 'Hello, World!'",
            "language": "python",
            "validation_types": ["syntax", "style", "security"],
        }

        response = client.post("/validate", json=validation_request)
        assert response.status_code == 200
        data = response.json()
        assert "quality_score" in data
        assert "validation_results" in data

    def test_security_scan_endpoint(self, client):
        """Test security scanning endpoint"""
        scan_request = {
            "code": "import os\ndef delete_file(filename):\n    os.system(f'rm {filename}')",
            "language": "python",
            "scan_depth": "deep",
        }

        response = client.post("/security-scan", json=scan_request)
        assert response.status_code == 200
        data = response.json()
        assert "security_issues" in data
        assert "risk_level" in data


class TestCodeQualityAnalyzer:
    """Test suite for code quality analysis"""

    @pytest.fixture
    def quality_analyzer(self):
        """Create quality analyzer instance"""
        from comprehensive_validator import CodeQualityAnalyzer

        return CodeQualityAnalyzer()

    def test_python_syntax_validation(self, quality_analyzer):
        """Test Python syntax validation"""
        valid_code = """
def calculate_area(radius):
    import math
    return math.pi * radius ** 2
"""
        result = quality_analyzer.validate_syntax(valid_code, "python")
        assert result["valid"] == True
        assert result["errors"] == []

    def test_python_syntax_validation_error(self, quality_analyzer):
        """Test Python syntax validation with errors"""
        invalid_code = """
def calculate_area(radius:
    import math
    return math.pi * radius ** 2
"""
        result = quality_analyzer.validate_syntax(invalid_code, "python")
        assert result["valid"] == False
        assert len(result["errors"]) > 0

    def test_style_checking_pep8(self, quality_analyzer):
        """Test PEP8 style checking"""
        code_with_style_issues = """
def calculate_area( radius ):
    import math
    return math.pi*radius**2
"""
        result = quality_analyzer.check_style(code_with_style_issues, "python")
        assert "style_issues" in result
        assert result["style_score"] <= 100

    def test_complexity_analysis(self, quality_analyzer):
        """Test code complexity analysis"""
        complex_code = """
def complex_function(x, y, z):
    if x > 0:
        if y > 0:
            if z > 0:
                for i in range(x):
                    for j in range(y):
                        if i + j > z:
                            return i * j
                        else:
                            continue
            else:
                return x + y
        else:
            return x
    else:
        return 0
"""
        result = quality_analyzer.analyze_complexity(complex_code, "python")
        assert "cyclomatic_complexity" in result
        assert result["cyclomatic_complexity"] > 5

    def test_code_duplication_detection(self, quality_analyzer):
        """Test code duplication detection"""
        code_with_duplicates = """
def process_user_data(user):
    if user.is_active:
        user.last_login = datetime.now()
        user.save()
        return True
    return False

def process_admin_data(admin):
    if admin.is_active:
        admin.last_login = datetime.now()
        admin.save()
        return True
    return False
"""
        result = quality_analyzer.detect_duplication(code_with_duplicates, "python")
        assert "duplicate_blocks" in result
        assert len(result["duplicate_blocks"]) > 0

    def test_maintainability_index(self, quality_analyzer):
        """Test maintainability index calculation"""
        maintainable_code = """
def add(a, b):
    \"\"\"Add two numbers.\"\"\"
    return a + b

def multiply(a, b):
    \"\"\"Multiply two numbers.\"\"\"
    return a * b
"""
        result = quality_analyzer.calculate_maintainability(maintainable_code, "python")
        assert "maintainability_index" in result
        assert result["maintainability_index"] > 70


class TestSecurityScanner:
    """Test suite for security scanning functionality"""

    @pytest.fixture
    def security_scanner(self):
        """Create security scanner instance"""
        from comprehensive_validator import SecurityScanner

        return SecurityScanner()

    def test_sql_injection_detection(self, security_scanner):
        """Test SQL injection vulnerability detection"""
        vulnerable_code = """
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return database.execute(query)
"""
        result = security_scanner.scan_sql_injection(vulnerable_code, "python")
        assert len(result["vulnerabilities"]) > 0
        assert any("sql_injection" in vuln["type"] for vuln in result["vulnerabilities"])

    def test_xss_vulnerability_detection(self, security_scanner):
        """Test XSS vulnerability detection"""
        vulnerable_code = """
from flask import request, render_template_string

@app.route('/search')
def search():
    query = request.args.get('q')
    return render_template_string(f"<h1>Results for {query}</h1>")
"""
        result = security_scanner.scan_xss(vulnerable_code, "python")
        assert "vulnerabilities" in result

    def test_command_injection_detection(self, security_scanner):
        """Test command injection vulnerability detection"""
        vulnerable_code = """
import os
import subprocess

def process_file(filename):
    os.system(f"cat {filename}")
    subprocess.call(f"grep pattern {filename}", shell=True)
"""
        result = security_scanner.scan_command_injection(vulnerable_code, "python")
        assert len(result["vulnerabilities"]) > 0

    def test_hardcoded_secrets_detection(self, security_scanner):
        """Test hardcoded secrets detection"""
        code_with_secrets = """
API_KEY = "sk-1234567890abcdef"
DATABASE_PASSWORD = "super_secret_password"
AWS_SECRET = "AKIA1234567890ABCDEF"

def connect_to_service():
    return requests.get("https://api.service.com",
                       headers={"Authorization": f"Bearer {API_KEY}"})
"""
        result = security_scanner.scan_hardcoded_secrets(code_with_secrets, "python")
        assert len(result["secrets"]) > 0
        assert any("api_key" in secret["type"].lower() for secret in result["secrets"])

    def test_insecure_random_detection(self, security_scanner):
        """Test insecure random number generation detection"""
        insecure_code = """
import random

def generate_token():
    return str(random.randint(100000, 999999))

def generate_session_id():
    return random.choice("abcdefghijklmnopqrstuvwxyz") * 32
"""
        result = security_scanner.scan_insecure_random(insecure_code, "python")
        assert "vulnerabilities" in result

    def test_dependency_vulnerability_scan(self, security_scanner):
        """Test dependency vulnerability scanning"""
        requirements_content = """
django==2.0.1
requests==2.18.4
pillow==5.2.0
"""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = json.dumps(
                [
                    {
                        "package": "django",
                        "vulnerability": "CVE-2018-14574",
                        "severity": "high",
                    }
                ]
            )

            result = security_scanner.scan_dependencies(requirements_content, "python")
            assert len(result["vulnerabilities"]) > 0


class TestPerformanceAnalyzer:
    """Test suite for performance analysis"""

    @pytest.fixture
    def performance_analyzer(self):
        """Create performance analyzer instance"""
        from comprehensive_validator import PerformanceAnalyzer

        return PerformanceAnalyzer()

    def test_time_complexity_analysis(self, performance_analyzer):
        """Test time complexity analysis"""
        inefficient_code = """
def find_duplicates(arr):
    duplicates = []
    for i in range(len(arr)):
        for j in range(i+1, len(arr)):
            if arr[i] == arr[j] and arr[i] not in duplicates:
                duplicates.append(arr[i])
    return duplicates
"""
        result = performance_analyzer.analyze_time_complexity(inefficient_code, "python")
        assert "complexity_rating" in result
        assert result["complexity_rating"] in ["O(n²)", "quadratic", "poor"]

    def test_memory_usage_analysis(self, performance_analyzer):
        """Test memory usage analysis"""
        memory_intensive_code = """
def process_large_data():
    data = []
    for i in range(1000000):
        data.append([j for j in range(1000)])
    return data
"""
        result = performance_analyzer.analyze_memory_usage(memory_intensive_code, "python")
        assert "memory_concerns" in result

    def test_algorithm_optimization_suggestions(self, performance_analyzer):
        """Test algorithm optimization suggestions"""
        inefficient_code = """
def linear_search(arr, target):
    for i in range(len(arr)):
        if arr[i] == target:
            return i
    return -1
"""
        result = performance_analyzer.suggest_optimizations(inefficient_code, "python")
        assert "suggestions" in result
        assert len(result["suggestions"]) > 0

    def test_database_query_analysis(self, performance_analyzer):
        """Test database query performance analysis"""
        inefficient_queries = """
# N+1 Query Problem
users = User.objects.all()
for user in users:
    posts = Post.objects.filter(author=user)

# Missing Index
users = User.objects.filter(email__contains="@gmail.com")
"""
        result = performance_analyzer.analyze_database_queries(inefficient_queries, "python")
        assert "query_issues" in result


class TestComplianceChecker:
    """Test suite for compliance checking"""

    @pytest.fixture
    def compliance_checker(self):
        """Create compliance checker instance"""
        from comprehensive_validator import ComplianceChecker

        return ComplianceChecker()

    def test_gdpr_compliance_check(self, compliance_checker):
        """Test GDPR compliance checking"""
        code_with_personal_data = """
class User:
    def __init__(self, email, ssn, address):
        self.email = email
        self.ssn = ssn  # Personal data
        self.address = address

def process_user_data(user):
    # No consent mechanism
    send_marketing_email(user.email)
    store_permanently(user.ssn)
"""
        result = compliance_checker.check_gdpr_compliance(code_with_personal_data, "python")
        assert "compliance_issues" in result
        assert "gdpr_score" in result

    def test_pci_dss_compliance_check(self, compliance_checker):
        """Test PCI DSS compliance checking"""
        payment_code = """
class PaymentProcessor:
    def process_payment(self, card_number, cvv, expiry):
        # Storing card data in plain text - PCI violation
        self.log_payment(f"Card: {card_number}, CVV: {cvv}")

        # Insecure transmission
        response = requests.post("http://payment-gateway.com",
                               data={"card": card_number})
"""
        result = compliance_checker.check_pci_compliance(payment_code, "python")
        assert "compliance_issues" in result

    def test_hipaa_compliance_check(self, compliance_checker):
        """Test HIPAA compliance checking"""
        medical_code = """
class PatientRecord:
    def __init__(self, name, diagnosis, ssn):
        self.name = name
        self.diagnosis = diagnosis  # PHI
        self.ssn = ssn

def share_patient_data(patient):
    # Sharing PHI without authorization
    email_doctor(f"Patient {patient.name} has {patient.diagnosis}")
"""
        result = compliance_checker.check_hipaa_compliance(medical_code, "python")
        assert "compliance_issues" in result

    def test_sox_compliance_check(self, compliance_checker):
        """Test SOX compliance checking"""
        financial_code = """
class FinancialTransaction:
    def process_transaction(self, amount, account):
        # No audit trail
        self.balance += amount

        # No access controls
        if amount > 10000:
            self.flag_for_review = True
"""
        result = compliance_checker.check_sox_compliance(financial_code, "python")
        assert "compliance_issues" in result


class TestCodeReviewAutomation:
    """Test suite for automated code review"""

    @pytest.fixture
    def code_reviewer(self):
        """Create code reviewer instance"""
        from comprehensive_validator import AutomatedCodeReviewer

        return AutomatedCodeReviewer()

    def test_function_documentation_review(self, code_reviewer):
        """Test function documentation review"""
        undocumented_code = """
def calculate_compound_interest(principal, rate, time, compounds_per_year):
    return principal * (1 + rate/compounds_per_year) ** (compounds_per_year * time)

def validate_email(email):
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None
"""
        result = code_reviewer.review_documentation(undocumented_code, "python")
        assert "documentation_issues" in result
        assert len(result["documentation_issues"]) > 0

    def test_naming_convention_review(self, code_reviewer):
        """Test naming convention review"""
        poorly_named_code = """
def calcArea(r):
    PI = 3.14159
    A = PI * r * r
    return A

class user_manager:
    def __init__(self):
        self.UsersData = []
"""
        result = code_reviewer.review_naming_conventions(poorly_named_code, "python")
        assert "naming_issues" in result
        assert len(result["naming_issues"]) > 0

    def test_error_handling_review(self, code_reviewer):
        """Test error handling review"""
        poor_error_handling = """
def divide_numbers(a, b):
    return a / b

def read_config_file(filename):
    with open(filename, 'r') as f:
        return json.load(f)
"""
        result = code_reviewer.review_error_handling(poor_error_handling, "python")
        assert "error_handling_issues" in result

    def test_test_coverage_analysis(self, code_reviewer):
        """Test test coverage analysis"""
        code_without_tests = """
def complex_business_logic(data):
    result = []
    for item in data:
        if item.is_valid():
            processed = item.process()
            if processed.meets_criteria():
                result.append(processed)
    return result
"""
        with patch("coverage.Coverage") as mock_coverage:
            mock_coverage.return_value.report.return_value = 45.0

            result = code_reviewer.analyze_test_coverage(code_without_tests, "python")
            assert "coverage_percentage" in result
            assert result["coverage_percentage"] < 80

    def test_code_smell_detection(self, code_reviewer):
        """Test code smell detection"""
        smelly_code = """
class GodClass:
    def __init__(self):
        self.user_data = {}
        self.payment_data = {}
        self.inventory_data = {}
        self.analytics_data = {}

    def create_user(self, user): pass
    def process_payment(self, payment): pass
    def update_inventory(self, item): pass
    def generate_report(self): pass
    def send_email(self, email): pass
    def validate_data(self, data): pass
    def log_activity(self, activity): pass
"""
        result = code_reviewer.detect_code_smells(smelly_code, "python")
        assert "code_smells" in result
        assert any("god_class" in smell["type"].lower() for smell in result["code_smells"])


class TestQualityMetrics:
    """Test suite for quality metrics calculation"""

    @pytest.fixture
    def quality_metrics(self):
        """Create quality metrics calculator"""
        from comprehensive_validator import QualityMetricsCalculator

        return QualityMetricsCalculator()

    def test_overall_quality_score(self, quality_metrics):
        """Test overall quality score calculation"""
        analysis_results = {
            "syntax_score": 100,
            "style_score": 85,
            "security_score": 90,
            "performance_score": 75,
            "maintainability_score": 80,
            "test_coverage": 85,
        }

        score = quality_metrics.calculate_overall_score(analysis_results)
        assert 0 <= score <= 100
        assert score > 70  # Should be a decent score

    def test_quality_trend_analysis(self, quality_metrics):
        """Test quality trend analysis"""
        historical_scores = [
            {"date": "2023-09-01", "score": 75},
            {"date": "2023-09-08", "score": 78},
            {"date": "2023-09-15", "score": 82},
            {"date": "2023-09-22", "score": 85},
        ]

        trend = quality_metrics.analyze_quality_trends(historical_scores)
        assert trend["direction"] == "improving"
        assert trend["average_improvement"] > 0

    def test_quality_gate_evaluation(self, quality_metrics):
        """Test quality gate evaluation"""
        quality_gates = {
            "minimum_score": 80,
            "maximum_critical_issues": 0,
            "minimum_test_coverage": 80,
            "maximum_security_vulnerabilities": 0,
        }

        results = {
            "overall_score": 85,
            "critical_issues": 0,
            "test_coverage": 82,
            "security_vulnerabilities": 1,
        }

        gate_result = quality_metrics.evaluate_quality_gates(results, quality_gates)
        assert gate_result["passed"] == False  # Should fail due to security vulnerability


class TestReportGeneration:
    """Test suite for quality report generation"""

    @pytest.fixture
    def report_generator(self):
        """Create report generator instance"""
        from comprehensive_validator import QualityReportGenerator

        return QualityReportGenerator()

    def test_html_report_generation(self, report_generator):
        """Test HTML report generation"""
        quality_data = {
            "overall_score": 82,
            "syntax_issues": [],
            "security_vulnerabilities": [
                {"type": "sql_injection", "severity": "medium", "line": 45}
            ],
            "performance_issues": [
                {
                    "type": "n_plus_one",
                    "severity": "low",
                    "description": "Consider eager loading",
                }
            ],
        }

        html_report = report_generator.generate_html_report(quality_data)
        assert "<html>" in html_report
        assert "Quality Score: 82" in html_report
        assert "sql_injection" in html_report

    def test_json_report_generation(self, report_generator):
        """Test JSON report generation"""
        quality_data = {
            "overall_score": 75,
            "timestamp": datetime.now(),
            "issues": ["issue1", "issue2"],
        }

        json_report = report_generator.generate_json_report(quality_data)
        report_data = json.loads(json_report)

        assert report_data["overall_score"] == 75
        assert "timestamp" in report_data
        assert len(report_data["issues"]) == 2

    def test_pdf_report_generation(self, report_generator):
        """Test PDF report generation"""
        quality_data = {
            "project_name": "Test Project",
            "overall_score": 88,
            "detailed_analysis": {"syntax": "good", "security": "excellent"},
        }

        with patch("reportlab.pdfgen.canvas.Canvas") as mock_canvas:
            pdf_path = report_generator.generate_pdf_report(quality_data)
            assert pdf_path.endswith(".pdf")


class TestErrorHandling:
    """Test suite for error handling and edge cases"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_invalid_language_handling(self, client):
        """Test handling of unsupported programming languages"""
        validation_request = {
            "code": "some code here",
            "language": "unsupported_language",
            "validation_types": ["syntax"],
        }

        response = client.post("/validate", json=validation_request)
        assert response.status_code == 422

    def test_malformed_code_handling(self, client):
        """Test handling of severely malformed code"""
        validation_request = {
            "code": "\x00\x01\x02invalid_binary_data",
            "language": "python",
            "validation_types": ["syntax"],
        }

        response = client.post("/validate", json=validation_request)
        # Should handle gracefully without crashing
        assert response.status_code in [200, 400, 422]

    def test_large_code_handling(self, client):
        """Test handling of very large code files"""
        large_code = "# " + "A" * 1000000  # 1MB of code
        validation_request = {
            "code": large_code,
            "language": "python",
            "validation_types": ["syntax"],
        }

        response = client.post("/validate", json=validation_request)
        # Should either succeed or fail gracefully with appropriate status
        assert response.status_code in [200, 413, 422]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
