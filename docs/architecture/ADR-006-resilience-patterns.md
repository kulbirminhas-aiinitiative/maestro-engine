# ADR-006: Resilience Patterns

**Status**: Accepted
**Date**: 2025-10-04
**Decision Makers**: MAESTRO Architecture Team
**Stakeholders**: All service teams, operations

---

## Context

The MAESTRO platform has **no fault tolerance mechanisms** currently:

**Problems Identified**:
- ❌ Service calls fail permanently (no retry)
- ❌ Cascading failures (one service down → entire platform down)
- ❌ No timeouts (requests hang forever)
- ❌ No graceful degradation
- ❌ No fallback mechanisms
- ❌ No bulkhead isolation to prevent resource exhaustion

**Example Failure Scenario**:
```
1. Frontend calls maestro-engine
2. maestro-engine calls quality-fabric
3. quality-fabric is down or slow
4. maestro-engine hangs waiting for response
5. Frontend times out after 60+ seconds
6. User sees generic error "Something went wrong"
7. No automatic recovery
8. All subsequent requests also fail
```

This creates a **cascading failure** that can bring down the entire platform.

---

## Decision

**We will implement comprehensive resilience patterns across all services.**

### 1. Circuit Breaker Pattern

**Purpose**: Stop calling failing services to prevent cascading failures

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Service is failing, fail fast without calling
- **HALF_OPEN**: Testing if service recovered

**Implementation**: `src/resilience/circuit_breaker.py`

```python
from src.resilience import CircuitBreaker

# Create circuit breaker for quality-fabric
quality_circuit = CircuitBreaker(
    failure_threshold=5,  # Open after 5 failures
    success_threshold=2,  # Close after 2 successes in half-open
    timeout=60,           # Try half-open after 60 seconds
    name="quality-fabric"
)

# Use it
try:
    result = await quality_circuit.call(quality_client.validate, code=code)
except CircuitBreakerOpenError:
    # Fail fast - don't wait for timeout
    logger.warning("Quality validation unavailable, using cached result")
    result = get_cached_validation_result()
```

**Benefits**:
- Prevents wasting resources on failing services
- Fast failure (milliseconds vs. seconds)
- Automatic recovery testing
- Metrics for monitoring

### 2. Retry with Exponential Backoff

**Purpose**: Automatically retry failed requests with increasing delays

**Implementation**: `src/resilience/retry.py`

```python
from src.resilience import retry_with_backoff

async def fetch_template(template_id: str):
    async def _fetch():
        response = await http_client.get(f"/templates/{template_id}")
        response.raise_for_status()
        return response.json()

    return await retry_with_backoff(
        _fetch,
        max_retries=3,
        initial_delay=1.0,        # 1 second first retry
        backoff_factor=2.0,       # 2 seconds, 4 seconds, 8 seconds
        max_delay=30.0,
        retryable_exceptions=(httpx.HTTPError, httpx.TimeoutException)
    )
```

**Retry Schedule**:
- Attempt 1: Immediate
- Attempt 2: +1 second
- Attempt 3: +2 seconds
- Attempt 4: +4 seconds
- Fail if all retries exhausted

**Benefits**:
- Handles transient failures automatically
- Doesn't hammer failing services
- Exponential backoff reduces load
- Configurable per service

### 3. Timeout Pattern

**Purpose**: Prevent requests from hanging forever

**Implementation**: `src/resilience/timeout.py`

```python
from src.resilience import timeout

async def execute_persona(persona_id: str, requirement: str):
    try:
        async with timeout(300.0, "persona execution"):
            return await persona_executor.execute(persona_id, requirement)
    except TimeoutError:
        logger.error(f"Persona {persona_id} timed out after 300s")
        raise
```

**Timeout Configuration** (from `config/default.yaml`):
```yaml
resilience:
  timeouts:
    template_fetch: 10        # 10 seconds
    quality_validation: 120   # 2 minutes
    persona_execution: 300    # 5 minutes
    workflow_total: 900       # 15 minutes
```

**Benefits**:
- Prevents resource exhaustion from hanging requests
- Predictable response times
- Cascading timeout support

### 4. Bulkhead Pattern

**Purpose**: Limit concurrent requests to prevent resource exhaustion

**Implementation**: `src/resilience/bulkhead.py`

```python
from src.resilience import Bulkhead

# Limit concurrent quality validations to 3
quality_bulkhead = Bulkhead(max_concurrent=3, name="quality-validation")

async def validate_code(code: str):
    return await quality_bulkhead.call(quality_client.validate, code=code)
```

**Bulkhead Configuration**:
```yaml
resilience:
  bulkheads:
    template_service: 10      # Max 10 concurrent template fetches
    quality_fabric: 3         # Max 3 concurrent validations
    persona_execution: 4      # Max 4 concurrent persona executions
```

**Benefits**:
- Prevents one failing service from consuming all threads
- Isolation between different types of requests
- Predictable resource usage

### 5. Fallback Pattern

**Purpose**: Provide degraded service when primary fails

**Implementation**: `src/resilience/fallback.py`

```python
from src.resilience import with_fallback

async def get_template(template_id: str):
    async def get_from_service():
        return await template_client.get(template_id)

    async def get_default_template():
        return load_default_template()

    return await with_fallback(
        primary=get_from_service,
        fallback=get_default_template,
        fallback_exceptions=(httpx.HTTPError, CircuitBreakerOpenError)
    )
```

**Fallback Chain**:
```python
from src.resilience import FallbackChain

chain = FallbackChain()
chain.add(get_from_primary_db)
chain.add(get_from_replica_db)
chain.add(get_from_cache)
chain.add(get_default_value)

data = await chain.execute(key="my-data")
```

**Benefits**:
- Graceful degradation instead of complete failure
- Better user experience
- Maintains availability

---

## Implementation

### Module Structure

```
src/resilience/
├── __init__.py           # Exports all patterns
├── circuit_breaker.py    # Circuit Breaker implementation
├── retry.py              # Retry with exponential backoff
├── timeout.py            # Timeout enforcement
├── bulkhead.py           # Concurrency limiting
└── fallback.py           # Fallback pattern
```

**Full Implementation**: ✅ Complete

### Configuration

**File**: `config/default.yaml`

```yaml
resilience:
  # Circuit breakers
  circuit_breakers:
    template_service:
      failure_threshold: 5
      success_threshold: 2
      timeout: 60

    quality_fabric:
      failure_threshold: 3
      success_threshold: 2
      timeout: 120

  # Retry policies
  retry_policies:
    template_service:
      max_retries: 3
      initial_delay: 1.0
      backoff_factor: 2.0
      max_delay: 30.0

    quality_fabric:
      max_retries: 2
      initial_delay: 2.0
      backoff_factor: 2.0
      max_delay: 60.0

  # Timeouts (seconds)
  timeouts:
    template_fetch: 10
    quality_validation: 120
    persona_execution: 300
    workflow_total: 900

  # Bulkheads (max concurrent)
  bulkheads:
    template_service: 10
    quality_fabric: 3
    persona_execution: 4
```

### Combined Usage Example

```python
from src.resilience import (
    CircuitBreaker,
    retry_with_backoff,
    timeout,
    Bulkhead,
    with_fallback
)

# Setup resilience patterns
circuit = CircuitBreaker(failure_threshold=5, timeout=60)
bulkhead = Bulkhead(max_concurrent=3)

async def resilient_api_call(url: str):
    """API call with full resilience protection."""

    async def call_with_circuit_breaker():
        async def call_with_retry():
            async def call_with_timeout():
                async with timeout(10.0, "API call"):
                    return await http_client.get(url)

            return await retry_with_backoff(
                call_with_timeout,
                max_retries=3,
                initial_delay=1.0
            )

        return await circuit.call(call_with_retry)

    async def fallback():
        return get_cached_response(url)

    return await bulkhead.call(
        with_fallback,
        primary=call_with_circuit_breaker,
        fallback=fallback
    )
```

**Layers of Protection**:
1. **Bulkhead**: Limits concurrent calls
2. **Fallback**: Provides cached data if all else fails
3. **Circuit Breaker**: Fails fast if service is down
4. **Retry**: Handles transient failures
5. **Timeout**: Prevents hanging

---

## Consequences

### Positive ✅

- **Fault Tolerance**: Service failures don't cascade
- **Automatic Recovery**: Circuit breakers reset automatically
- **Predictable Behavior**: Timeouts prevent hanging
- **Resource Protection**: Bulkheads prevent exhaustion
- **Graceful Degradation**: Fallbacks provide basic functionality
- **Observability**: All patterns log metrics
- **Production Ready**: Battle-tested patterns

### Negative ⚠️

- **Increased Complexity**: More moving parts
- **Configuration Overhead**: More settings to tune
- **Debugging Challenges**: Multiple retries can confuse
- **Potential Latency**: Retries + delays add time

### Risks 🚨

**Risk**: Circuit breaker opens unnecessarily (false positives)
**Mitigation**:
- Tune thresholds based on actual traffic patterns
- Monitor circuit breaker state metrics
- Different thresholds per service based on criticality

**Risk**: Cascading circuit breakers (multiple services open simultaneously)
**Mitigation**:
- Different thresholds per service
- Longer timeout for critical services
- Fallback chains to maintain availability

**Risk**: Retry storms overwhelming services
**Mitigation**:
- Exponential backoff with jitter
- Max delay caps
- Bulkhead limits concurrent retries

---

## Monitoring & Metrics

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Circuit breaker state
circuit_breaker_state = Gauge(
    'circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=half_open, 2=open)',
    ['service']
)

# Retry attempts
retry_attempts = Counter(
    'retry_attempts_total',
    'Total retry attempts',
    ['service', 'success']
)

# Timeout occurrences
timeout_occurrences = Counter(
    'timeout_occurrences_total',
    'Total timeouts',
    ['service', 'operation']
)

# Request duration
request_duration = Histogram(
    'request_duration_seconds',
    'Request duration',
    ['service', 'operation']
)
```

### Alerts

```yaml
groups:
  - name: resilience
    rules:
      - alert: CircuitBreakerOpen
        expr: circuit_breaker_state{service="quality-fabric"} == 2
        for: 1m
        annotations:
          summary: "Circuit breaker open for {{ $labels.service }}"

      - alert: HighRetryRate
        expr: rate(retry_attempts_total[5m]) > 0.5
        for: 5m
        annotations:
          summary: "High retry rate for {{ $labels.service }}"

      - alert: FrequentTimeouts
        expr: rate(timeout_occurrences_total[5m]) > 0.1
        for: 5m
        annotations:
          summary: "Frequent timeouts for {{ $labels.service }}"
```

---

## Testing

### Unit Tests

```python
# Test circuit breaker opens after failures
async def test_circuit_breaker_opens():
    cb = CircuitBreaker(failure_threshold=3)

    # Simulate 3 failures
    for _ in range(3):
        try:
            await cb.call(failing_function)
        except:
            pass

    # Circuit should be open
    assert cb.state == CircuitState.OPEN

# Test retry succeeds on second attempt
async def test_retry_succeeds():
    attempts = 0

    async def sometimes_fails():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise Exception("First attempt fails")
        return "success"

    result = await retry_with_backoff(sometimes_fails, max_retries=2)
    assert result == "success"
    assert attempts == 2
```

### Integration Tests

```python
async def test_resilient_service_call():
    """Test full resilience stack."""
    # Simulate service degradation
    quality_service.set_failure_rate(0.3)  # 30% failure rate

    results = []
    for _ in range(10):
        try:
            result = await resilient_quality_call(code="test")
            results.append(result)
        except Exception as e:
            results.append(e)

    # Should have some successes despite failures
    successes = [r for r in results if not isinstance(r, Exception)]
    assert len(successes) >= 7  # At least 70% success rate
```

---

## Related ADRs

- **ADR-001**: Service Discovery (resilient clients need service URLs)
- **ADR-005**: Configuration Management (resilience configuration)

---

## References

- [Release It! (Michael Nygard)](https://pragprog.com/titles/mnee2/release-it-second-edition/)
- [Circuit Breaker Pattern (Martin Fowler)](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Retry Pattern (Microsoft)](https://docs.microsoft.com/en-us/azure/architecture/patterns/retry)
- [Bulkhead Pattern (Microsoft)](https://docs.microsoft.com/en-us/azure/architecture/patterns/bulkhead)
- [Timeout Pattern](https://medium.com/@_orcaman/when-to-use-timeouts-in-go-and-when-not-to-7b1e7e1b6f0e)

---

**Implementation Status**: ✅ Complete
**Module Location**: `src/resilience/`
**Configuration**: `config/default.yaml`, `config/production.yaml`
**Next Steps**: Integrate into existing service clients
