# MAESTRO Services Testing Framework

## Overview

This testing framework provides comprehensive test coverage for all MAESTRO microservices with industry-standard practices and tools.

## Test Structure

### Test Types

1. **Unit Tests** (`test-*-service.py`)
   - Individual service component testing
   - API endpoint validation
   - Business logic verification
   - Mock dependencies for isolation

2. **Integration Tests** (`test-integration-*.py`)
   - Service-to-service communication
   - End-to-end workflow validation
   - Database connectivity testing
   - Cross-service data flow

3. **Regression Tests** (`test-regression-*.py`)
   - API endpoint stability
   - Performance regression detection
   - Backward compatibility validation
   - Response format consistency

### Test Files

```
tests/
├── conftest.py                              # Pytest configuration and fixtures
├── test-orchestration-gateway.py           # Orchestration Gateway unit tests
├── test-intelligence-service.py            # Intelligence Service unit tests
├── test-template-registry.py               # Template Registry unit tests
├── test-execution-service.py               # Execution Service unit tests
├── test-monitoring-service.py              # Monitoring Service unit tests
├── test-quality-service.py                 # Quality Service unit tests
├── test-integration-service-communication.py # Integration tests
├── test-regression-api-endpoints.py        # Regression tests
└── README.md                               # This file
```

## Quick Start

### Using Make (Recommended)

```bash
# Run all tests
make test

# Run specific test types
make test-unit
make test-integration
make test-regression
make test-smoke

# Run tests for specific service
make test SERVICE=orchestration

# Generate coverage report
make coverage

# Clean test artifacts
make clean-tests
```

### Using Python Test Runner

```bash
# Run all tests
python run_tests.py

# Run specific test types
python run_tests.py --type unit
python run_tests.py --type integration
python run_tests.py --type regression

# Run smoke tests
python run_tests.py --smoke

# Run full test suite
python run_tests.py --full

# Run tests for specific service
python run_tests.py --service orchestration

# Verbose output
python run_tests.py --verbose

# Parallel execution
python run_tests.py --parallel
```

### Using Pytest Directly

```bash
# Run all tests
pytest tests/

# Run unit tests only
pytest tests/test-*-service.py

# Run with coverage
pytest tests/ --cov=services --cov-report=html

# Run with markers
pytest tests/ -m "unit or smoke"

# Run specific test file
pytest tests/test-orchestration-gateway.py -v
```

## Test Configuration

### Pytest Configuration (`pytest.ini`)

Key configurations:
- Test discovery patterns
- Coverage reporting (70% minimum)
- Timeout settings (300s default)
- Logging configuration
- Test markers for categorization

### Environment Setup

#### Test Databases (Docker)

Start test databases:
```bash
docker-compose -f docker-compose.test-db.yml up -d
```

Services provided:
- **Redis** (localhost:6379)
- **MongoDB** (localhost:27017)

#### Service URLs

Default test service endpoints:
- Orchestration Gateway: `http://localhost:8000`
- Intelligence Service: `http://localhost:9501`
- Template Registry: `http://localhost:9500`
- Execution Service: `http://localhost:9502`
- Monitoring Service: `http://localhost:9503`
- Quality Service: `http://localhost:9504`

## Test Markers

Use pytest markers to run specific test categories:

```bash
# Critical tests only
pytest -m critical

# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# Performance tests
pytest -m performance

# Tests requiring database
pytest -m requires_db

# Tests requiring external services
pytest -m requires_services
```

## Coverage Reporting

### Generate Coverage Reports

```bash
# HTML report (recommended)
make coverage
# Opens tests/coverage_html/index.html

# Terminal report
pytest tests/ --cov=services --cov-report=term-missing

# XML report (for CI/CD)
pytest tests/ --cov=services --cov-report=xml
```

### Coverage Targets

- **Minimum Coverage**: 70%
- **Target Coverage**: 85%
- **Critical Services**: 90%

## Continuous Integration

### CI/CD Integration

The testing framework supports standard CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    make setup-tests
    make start-services
    make test-full

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./tests/coverage.xml
```

### Test Artifacts

Generated artifacts:
- `tests/junit.xml` - JUnit test results
- `tests/coverage.xml` - Coverage XML report
- `tests/coverage_html/` - HTML coverage report
- `tests/pytest.log` - Detailed test logs
- `tests/last_test_results.json` - Latest test results

## Test Development Guidelines

### Writing Unit Tests

1. **Follow naming convention**: `test-{service-name}.py`
2. **Use descriptive test names**: `test_endpoint_returns_correct_data`
3. **Mock external dependencies**: Use `unittest.mock`
4. **Test edge cases**: Invalid input, error conditions
5. **Assert specific behaviors**: Don't just test for "no errors"

Example:
```python
def test_health_endpoint_returns_valid_response(self, client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
```

### Writing Integration Tests

1. **Test real service communication**
2. **Use actual endpoints (not mocks)**
3. **Handle service unavailability gracefully**
4. **Test end-to-end workflows**
5. **Verify data flow between services**

### Test Data Management

1. **Use fixtures for test data** (`conftest.py`)
2. **Clean up after tests**
3. **Avoid hardcoded values**
4. **Use factories for complex objects**

## Troubleshooting

### Common Issues

#### Services Not Available
```bash
# Check if services are running
curl http://localhost:8000/health
curl http://localhost:9500/health

# Start missing services
cd services/orchestration_gateway && python app.py
cd services/template_registry && python registry_service.py
```

#### Database Connection Errors
```bash
# Start test databases
make start-services

# Check database connectivity
docker ps | grep maestro
```

#### Import Errors in Tests
```bash
# Ensure proper Python path
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Install missing dependencies
pip install -r requirements-testing-common.txt
```

#### Test Timeouts
```bash
# Increase timeout for slow tests
pytest tests/ --timeout=600

# Run specific test with more time
pytest tests/test-integration-service-communication.py::TestServiceHealthAndDiscovery::test_all_services_health_check -v --timeout=300
```

### Debugging Failed Tests

1. **Run with verbose output**:
   ```bash
   pytest tests/test-orchestration-gateway.py -v -s
   ```

2. **Check service logs**:
   ```bash
   tail -f tests/pytest.log
   ```

3. **Run single test**:
   ```bash
   pytest tests/test-orchestration-gateway.py::TestOrchestrationGateway::test_health_endpoint -v
   ```

4. **Use debugging markers**:
   ```python
   import pytest

   @pytest.mark.skip(reason="Debugging")
   def test_problematic_function():
       pass
   ```

## Performance Testing

### Load Testing
```bash
# Run performance tests
pytest -m performance

# Concurrent test execution
pytest tests/ -n auto
```

### Benchmarking
```bash
# Response time analysis
pytest tests/test-regression-api-endpoints.py::TestAPIPerformanceRegression -v
```

## Maintenance

### Regular Tasks

1. **Update test dependencies**: Keep testing libraries current
2. **Review coverage reports**: Identify gaps in test coverage
3. **Update test data**: Keep fixtures relevant and current
4. **Refactor tests**: Maintain clean, readable test code
5. **Monitor test performance**: Identify and fix slow tests

### Best Practices

1. **Run tests before commits**
2. **Keep tests independent**
3. **Use meaningful assertions**
4. **Document complex test scenarios**
5. **Regularly update test environments**

## Support

For issues with the testing framework:

1. Check this README
2. Review test logs in `tests/pytest.log`
3. Check service health endpoints
4. Verify database connectivity
5. Ensure all dependencies are installed

## Test Results

Latest test execution results are saved to:
- `tests/last_test_results.json`
- `tests/junit.xml` (for CI/CD integration)

Example test summary:
```json
{
  "status": "passed",
  "duration": 45.2,
  "timestamp": "2023-09-16T10:30:00",
  "summary_line": "25 passed, 0 failed, 3 skipped"
}
```
