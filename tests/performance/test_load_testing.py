"""
Performance and load testing for MAESTRO microservices.

This module provides comprehensive performance testing including
response times, throughput, concurrent users, and stress testing.
"""

import concurrent.futures
import os
import statistics
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import pytest
import requests


@dataclass
class PerformanceMetrics:
    """Performance metrics data class"""

    response_times: List[float]
    success_count: int
    error_count: int
    total_requests: int
    duration: float
    throughput: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float


@pytest.fixture(scope="session")
def performance_config():
    """Performance testing configuration"""
    return {
        "orchestration_gateway": os.environ.get("GW_URL", "http://localhost:8000"),
        "intelligence_service": os.environ.get("INTELLIGENCE_URL", "http://localhost:9501"),
        "template_registry": os.environ.get("TEMPLATE_URL", "http://localhost:9500"),
        "timeout": 30,
        "max_workers": 10,
        "test_duration": 30,  # seconds
        "ramp_up_time": 5,  # seconds
    }


class LoadTester:
    """Load testing utility class"""

    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.timeout = timeout

    def single_request(self, endpoint: str, method: str = "GET", **kwargs) -> Dict[str, Any]:
        """Make a single request and measure performance"""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()

        try:
            if method.upper() == "GET":
                response = self.session.get(url, **kwargs)
            elif method.upper() == "POST":
                response = self.session.post(url, **kwargs)
            elif method.upper() == "PUT":
                response = self.session.put(url, **kwargs)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, **kwargs)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            end_time = time.time()
            response_time = end_time - start_time

            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "response_time": response_time,
                "content_length": len(response.content),
                "error": None,
            }

        except Exception as e:
            end_time = time.time()
            response_time = end_time - start_time

            return {
                "success": False,
                "status_code": 0,
                "response_time": response_time,
                "content_length": 0,
                "error": str(e),
            }

    def load_test(
        self,
        endpoint: str,
        num_requests: int,
        max_workers: int = 10,
        method: str = "GET",
        **kwargs,
    ) -> PerformanceMetrics:
        """Perform load test with concurrent requests"""
        results = []
        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for _ in range(num_requests):
                future = executor.submit(self.single_request, endpoint, method, **kwargs)
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)

        end_time = time.time()
        duration = end_time - start_time

        return self._calculate_metrics(results, duration)

    def stress_test(
        self,
        endpoint: str,
        duration: int,
        max_workers: int = 10,
        ramp_up_time: int = 5,
        method: str = "GET",
        **kwargs,
    ) -> PerformanceMetrics:
        """Perform stress test for specified duration"""
        results = []
        start_time = time.time()
        end_time = start_time + duration

        # Gradually ramp up concurrent workers
        current_workers = 1
        ramp_up_interval = ramp_up_time / max_workers if max_workers > 1 else 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            last_ramp_up = start_time

            while time.time() < end_time:
                # Ramp up workers gradually
                if (
                    time.time() - last_ramp_up
                ) > ramp_up_interval and current_workers < max_workers:
                    current_workers += 1
                    last_ramp_up = time.time()

                # Submit requests up to current worker limit
                active_futures = [f for f in futures if not f.done()]
                while len(active_futures) < current_workers and time.time() < end_time:
                    future = executor.submit(self.single_request, endpoint, method, **kwargs)
                    futures.append(future)
                    active_futures = [f for f in futures if not f.done()]

                # Collect completed results
                for future in concurrent.futures.as_completed(futures, timeout=0.1):
                    try:
                        result = future.result()
                        results.append(result)
                        futures.remove(future)
                    except concurrent.futures.TimeoutError:
                        break

                time.sleep(0.1)  # Small delay to prevent busy waiting

            # Wait for remaining futures to complete
            for future in concurrent.futures.as_completed(futures, timeout=10):
                result = future.result()
                results.append(result)

        actual_duration = time.time() - start_time
        return self._calculate_metrics(results, actual_duration)

    def _calculate_metrics(
        self, results: List[Dict[str, Any]], duration: float
    ) -> PerformanceMetrics:
        """Calculate performance metrics from results"""
        response_times = [r["response_time"] for r in results]
        success_count = sum(1 for r in results if r["success"])
        error_count = len(results) - success_count
        total_requests = len(results)

        if not response_times:
            return PerformanceMetrics(
                response_times=[],
                success_count=0,
                error_count=0,
                total_requests=0,
                duration=duration,
                throughput=0,
                avg_response_time=0,
                p95_response_time=0,
                p99_response_time=0,
            )

        throughput = total_requests / duration if duration > 0 else 0
        avg_response_time = statistics.mean(response_times)
        p95_response_time = (
            statistics.quantiles(response_times, n=20)[18]
            if len(response_times) >= 20
            else max(response_times)
        )
        p99_response_time = (
            statistics.quantiles(response_times, n=100)[98]
            if len(response_times) >= 100
            else max(response_times)
        )

        return PerformanceMetrics(
            response_times=response_times,
            success_count=success_count,
            error_count=error_count,
            total_requests=total_requests,
            duration=duration,
            throughput=throughput,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
        )


@pytest.mark.performance
class TestResponseTimePerformance:
    """Test response time performance of individual endpoints"""

    def test_health_endpoint_response_time(self, performance_config):
        """Test health endpoint response time"""
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)
            result = tester.single_request("/v1/health")

            if result["success"]:
                assert (
                    result["response_time"] < 1.0
                ), f"Health endpoint too slow for {service_name}: {result['response_time']:.3f}s"
            else:
                pytest.skip(f"Health endpoint not available for {service_name}")

    def test_version_endpoint_response_time(self, performance_config):
        """Test version endpoint response time"""
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)
            result = tester.single_request("/v1/version")

            if result["success"]:
                assert (
                    result["response_time"] < 1.0
                ), f"Version endpoint too slow for {service_name}: {result['response_time']:.3f}s"

    def test_metrics_endpoint_response_time(self, performance_config):
        """Test metrics endpoint response time"""
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)
            result = tester.single_request("/v1/metrics")

            if result["success"]:
                assert (
                    result["response_time"] < 2.0
                ), f"Metrics endpoint too slow for {service_name}: {result['response_time']:.3f}s"


@pytest.mark.performance
class TestConcurrentLoadPerformance:
    """Test performance under concurrent load"""

    def test_health_endpoint_concurrent_load(self, performance_config):
        """Test health endpoint under concurrent load"""
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)

            # Check if service is available first
            result = tester.single_request("/v1/health")
            if not result["success"]:
                pytest.skip(f"Service {service_name} not available")

            # Perform load test
            metrics = tester.load_test("/v1/health", num_requests=50, max_workers=5)

            # Assertions
            assert metrics.success_count > 0, f"No successful requests for {service_name}"
            assert (
                metrics.error_count / metrics.total_requests < 0.1
            ), f"Too many errors for {service_name}: {metrics.error_count}/{metrics.total_requests}"
            assert (
                metrics.avg_response_time < 2.0
            ), f"Average response time too slow for {service_name}: {metrics.avg_response_time:.3f}s"
            assert (
                metrics.p95_response_time < 5.0
            ), f"95th percentile too slow for {service_name}: {metrics.p95_response_time:.3f}s"

    def test_template_creation_concurrent_load(self, performance_config):
        """Test template creation under concurrent load"""
        template_url = performance_config.get("template_registry")
        if not template_url:
            pytest.skip("Template registry service not configured")

        tester = LoadTester(template_url)

        # Check if service is available
        result = tester.single_request("/v1/health")
        if not result["success"]:
            pytest.skip("Template registry service not available")

        # Create test templates concurrently
        template_data = {
            "name": f"perf-test-template-{int(time.time())}",
            "description": "Performance test template",
            "technology_stack": ["Python", "FastAPI"],
            "repo_url": "https://github.com/test/perf-template",
            "version": "1.0.0",
            "tags": ["performance", "test"],
        }

        def create_unique_template():
            unique_data = template_data.copy()
            unique_data["name"] = (
                f"perf-test-{threading.current_thread().ident}-{int(time.time() * 1000)}"
            )
            return tester.single_request("/v1/templates", method="POST", json=unique_data)

        # Perform concurrent template creation
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_unique_template) for _ in range(10)]
            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Calculate metrics
        response_times = [r["response_time"] for r in results]
        success_count = sum(1 for r in results if r["success"])

        assert success_count >= 8, f"Too many failed template creations: {success_count}/10"
        assert (
            statistics.mean(response_times) < 3.0
        ), f"Template creation too slow: {statistics.mean(response_times):.3f}s"

    def test_orchestration_request_performance(self, performance_config):
        """Test orchestration request performance"""
        gateway_url = performance_config.get("orchestration_gateway")
        if not gateway_url:
            pytest.skip("Orchestration gateway not configured")

        tester = LoadTester(gateway_url)

        # Check if service is available
        result = tester.single_request("/v1/health")
        if not result["success"]:
            pytest.skip("Orchestration gateway not available")

        # Test orchestration request
        orchestration_data = {
            "requirement": "Create a simple API for performance testing",
            "project_type": "api",
            "complexity": "low",
            "metadata": {"test": "performance"},
        }

        metrics = tester.load_test(
            "/v1/orchestrate",
            num_requests=10,
            max_workers=3,
            method="POST",
            json=orchestration_data,
        )

        # Assertions for orchestration requests
        assert (
            metrics.error_count / metrics.total_requests < 0.2
        ), f"Too many orchestration errors: {metrics.error_count}/{metrics.total_requests}"
        assert (
            metrics.avg_response_time < 5.0
        ), f"Orchestration too slow: {metrics.avg_response_time:.3f}s"


@pytest.mark.performance
@pytest.mark.slow
class TestStressPerformance:
    """Test performance under stress conditions"""

    def test_health_endpoint_stress(self, performance_config):
        """Test health endpoint under stress"""
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)

            # Check if service is available first
            result = tester.single_request("/v1/health")
            if not result["success"]:
                pytest.skip(f"Service {service_name} not available")

            # Perform stress test
            metrics = tester.stress_test(
                "/v1/health", duration=15, max_workers=8, ramp_up_time=3  # 15 seconds
            )

            # Stress test assertions (more lenient)
            assert (
                metrics.success_count > 0
            ), f"No successful requests under stress for {service_name}"
            assert (
                metrics.error_count / metrics.total_requests < 0.25
            ), f"Too many errors under stress for {service_name}: {metrics.error_count}/{metrics.total_requests}"
            assert (
                metrics.throughput > 1.0
            ), f"Throughput too low under stress for {service_name}: {metrics.throughput:.2f} req/s"

    def test_memory_usage_stability(self, performance_config):
        """Test memory usage stability during load"""
        # This is a simplified test - in production you'd monitor actual memory usage
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)

            # Check if service is available first
            result = tester.single_request("/v1/health")
            if not result["success"]:
                pytest.skip(f"Service {service_name} not available")

            # Measure baseline response time
            baseline_result = tester.single_request("/v1/health")
            baseline_time = baseline_result["response_time"]

            # Perform extended load test
            metrics = tester.stress_test("/v1/health", duration=20, max_workers=5, ramp_up_time=2)

            # Check that response times haven't degraded significantly
            final_result = tester.single_request("/v1/health")
            final_time = final_result["response_time"]

            # Response time shouldn't degrade by more than 50% after load
            degradation_factor = final_time / baseline_time if baseline_time > 0 else 1
            assert (
                degradation_factor < 1.5
            ), f"Response time degraded too much for {service_name}: {degradation_factor:.2f}x"


@pytest.mark.performance
class TestThroughputPerformance:
    """Test throughput performance"""

    def test_health_endpoint_throughput(self, performance_config):
        """Test health endpoint throughput"""
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)

            # Check if service is available first
            result = tester.single_request("/v1/health")
            if not result["success"]:
                pytest.skip(f"Service {service_name} not available")

            # Measure throughput
            metrics = tester.load_test("/v1/health", num_requests=100, max_workers=10)

            # Throughput assertions
            assert (
                metrics.throughput > 5.0
            ), f"Throughput too low for {service_name}: {metrics.throughput:.2f} req/s"
            assert (
                metrics.success_count >= 95
            ), f"Success rate too low for {service_name}: {metrics.success_count}/100"

    def test_read_vs_write_throughput(self, performance_config):
        """Test read vs write operation throughput"""
        template_url = performance_config.get("template_registry")
        if not template_url:
            pytest.skip("Template registry service not configured")

        tester = LoadTester(template_url)

        # Check if service is available
        result = tester.single_request("/v1/health")
        if not result["success"]:
            pytest.skip("Template registry service not available")

        # Test read throughput
        read_metrics = tester.load_test("/v1/templates", num_requests=50, max_workers=5)

        # Test write throughput (create templates)
        template_data = {
            "name": "throughput-test-template",
            "description": "Throughput test template",
            "technology_stack": ["Python"],
            "repo_url": "https://github.com/test/throughput",
            "version": "1.0.0",
        }

        def create_unique_template():
            unique_data = template_data.copy()
            unique_data["name"] = (
                f"throughput-{threading.current_thread().ident}-{int(time.time() * 1000)}"
            )
            return tester.single_request("/v1/templates", method="POST", json=unique_data)

        # Measure write throughput
        start_time = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_unique_template) for _ in range(15)]
            write_results = [future.result() for future in concurrent.futures.as_completed(futures)]
        write_duration = time.time() - start_time

        write_success_count = sum(1 for r in write_results if r["success"])
        write_throughput = len(write_results) / write_duration

        # Read operations should be faster than write operations
        assert (
            read_metrics.throughput > write_throughput
        ), f"Read throughput should be higher than write throughput: {read_metrics.throughput:.2f} vs {write_throughput:.2f}"

        # Both should meet minimum requirements
        assert (
            read_metrics.throughput > 5.0
        ), f"Read throughput too low: {read_metrics.throughput:.2f}"
        assert write_throughput > 1.0, f"Write throughput too low: {write_throughput:.2f}"


@pytest.mark.performance
class TestScalabilityPerformance:
    """Test scalability characteristics"""

    def test_linear_scalability(self, performance_config):
        """Test that performance scales linearly with concurrent users"""
        gateway_url = performance_config.get("orchestration_gateway")
        if not gateway_url:
            pytest.skip("Orchestration gateway not configured")

        tester = LoadTester(gateway_url)

        # Check if service is available
        result = tester.single_request("/v1/health")
        if not result["success"]:
            pytest.skip("Orchestration gateway not available")

        # Test with different concurrency levels
        worker_levels = [1, 2, 4]
        throughputs = []

        for workers in worker_levels:
            metrics = tester.load_test("/v1/health", num_requests=20, max_workers=workers)
            throughputs.append(metrics.throughput)

        # Throughput should generally increase with more workers (allowing for some variance)
        for i in range(1, len(throughputs)):
            # Allow for 20% variance due to system overhead
            assert (
                throughputs[i] >= throughputs[i - 1] * 0.8
            ), f"Throughput not scaling: {throughputs[i-1]:.2f} -> {throughputs[i]:.2f} req/s"

    def test_resource_utilization_efficiency(self, performance_config):
        """Test resource utilization efficiency"""
        # This is a basic test - in production you'd monitor actual CPU/memory usage
        for service_name, url in performance_config.items():
            if service_name in [
                "timeout",
                "max_workers",
                "test_duration",
                "ramp_up_time",
            ]:
                continue

            tester = LoadTester(url)

            # Check if service is available first
            result = tester.single_request("/v1/health")
            if not result["success"]:
                pytest.skip(f"Service {service_name} not available")

            # Test efficiency by measuring response time consistency
            metrics = tester.load_test("/v1/health", num_requests=30, max_workers=5)

            if metrics.response_times:
                # Response time variance should be reasonable
                response_time_std = statistics.stdev(metrics.response_times)
                response_time_mean = statistics.mean(metrics.response_times)

                # Coefficient of variation should be less than 1 (std < mean)
                cv = response_time_std / response_time_mean if response_time_mean > 0 else 0
                assert cv < 1.0, f"Response time too variable for {service_name}: CV={cv:.2f}"


@pytest.mark.performance
@pytest.mark.benchmark
class TestBenchmarkPerformance:
    """Benchmark tests for performance comparison"""

    def test_endpoint_performance_benchmark(self, performance_config, benchmark):
        """Benchmark endpoint performance for regression testing"""
        gateway_url = performance_config.get("orchestration_gateway")
        if not gateway_url:
            pytest.skip("Orchestration gateway not configured")

        tester = LoadTester(gateway_url)

        # Check if service is available
        result = tester.single_request("/v1/health")
        if not result["success"]:
            pytest.skip("Orchestration gateway not available")

        # Benchmark the health endpoint
        def health_request():
            return tester.single_request("/v1/health")

        # Use pytest-benchmark if available
        if hasattr(benchmark, "__call__"):
            result = benchmark(health_request)
            assert result["success"], "Benchmark request failed"
        else:
            # Fallback to manual timing
            start_time = time.time()
            for _ in range(10):
                health_request()
            end_time = time.time()
            avg_time = (end_time - start_time) / 10
            assert avg_time < 1.0, f"Benchmark average time too slow: {avg_time:.3f}s"
