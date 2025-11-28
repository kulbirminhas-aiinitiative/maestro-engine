# Technical Debt Ticket: pkg_resources Deprecation Warning

## Summary
The `pkg_resources` module from setuptools is deprecated and will be removed as early as **2025-11-30**. We're getting warnings from `google.rpc` package on service startup.

## Warning Message
```
/home/ec2-user/.local/lib/python3.11/site-packages/google/rpc/__init__.py:18: UserWarning:
pkg_resources is deprecated as an API. See https://setuptools.pypa.io/en/latest/pkg_resources.html.
The pkg_resources package is slated for removal as early as 2025-11-30.
Refrain from using this package or pin to Setuptools<81.
```

## Impact
- **Urgency**: HIGH - Deprecation deadline is 2025-11-30
- **Services Affected**: BFF, potentially other Python services
- **Risk**: Service startup failures after setuptools upgrade

## Root Cause
The `google-rpc` package (dependency of gRPC libraries) uses the deprecated `pkg_resources` API internally.

## Recommended Actions

### Option 1: Update google-rpc package (Preferred)
```bash
pip install --upgrade google-api-core grpcio grpcio-status
```

### Option 2: Pin setuptools version (Temporary)
```bash
pip install "setuptools<81"
```

### Option 3: Suppress warning (Not Recommended)
Add to application startup:
```python
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pkg_resources")
```

## Acceptance Criteria
- [ ] No `pkg_resources` deprecation warnings on service startup
- [ ] All services start successfully
- [ ] Unit tests pass
- [ ] No regression in gRPC functionality

## References
- [Setuptools Deprecation Notice](https://setuptools.pypa.io/en/latest/pkg_resources.html)
- [google-rpc GitHub Issues](https://github.com/googleapis/python-api-core)

## Priority
**P1** - Address before 2025-11-30 deadline
