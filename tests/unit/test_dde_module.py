#!/usr/bin/env python3
"""
Unit Tests for DDE Module

MD-2044: [EPIC 4] DDE Stream Completion
Validates all 6 sub-tasks:
- MD-2090: ExecutionManifest
- MD-2091: RoutingEngine
- MD-2093: ArtifactStamper
- MD-2098: DDEAuditor
- MD-2101: ContractEnforcer
- MD-2102: CircuitBreaker
"""

import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase, main

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from dde.execution_manifest import (
    ExecutionManifest,
    NodeExecution,
    ExecutionStatus,
    ErrorInfo,
)
from dde.routing_engine import (
    RoutingEngine,
    InterfaceContract,
    InterfaceField,
    FieldType,
    DAG,
    DAGNode,
)
from dde.artifact_stamper import (
    ArtifactStamper,
    ArtifactStamp,
    VerificationStatus,
    ArtifactQuery,
)
from dde.auditor import (
    DDEAuditor,
    DDEAuditEvent,
    DDEAuditEventType,
    DDEAuditCategory,
)
from dde.contract_enforcer import (
    ContractEnforcer,
    EnforcementMode,
    ValidationSeverity,
)
from dde.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerConfig,
    CircuitBreakerError,
)


class TestExecutionManifest(TestCase):
    """Tests for MD-2090: ExecutionManifest"""

    def setUp(self):
        self.manifest = ExecutionManifest(
            workflow_id="test-workflow-001",
            workflow_name="Test Workflow",
        )

    def test_record_start(self):
        """Test node execution start recording"""
        execution_id = self.manifest.record_start(
            node_id="node-1",
            inputs={"input1": "value1"},
        )

        self.assertIsNotNone(execution_id)
        self.assertTrue(execution_id.startswith("node-1:"))

        execution = self.manifest.get_execution(execution_id)
        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)
        self.assertEqual(execution.iteration, 1)

    def test_record_completion(self):
        """Test node execution completion recording"""
        execution_id = self.manifest.record_start(node_id="node-1")
        self.manifest.record_completion(
            execution_id,
            outputs={"output1": "result"},
        )

        execution = self.manifest.get_execution(execution_id)
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)
        self.assertIsNotNone(execution.duration_ms)

    def test_record_failure(self):
        """Test node execution failure recording"""
        execution_id = self.manifest.record_start(node_id="node-1")
        self.manifest.record_failure(
            execution_id,
            error=ValueError("Test error"),
            recoverable=True,
        )

        execution = self.manifest.get_execution(execution_id)
        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIsNotNone(execution.error_info)
        self.assertEqual(execution.error_info.error_type, "ValueError")
        self.assertTrue(execution.error_info.recoverable)

    def test_iteration_tracking(self):
        """Test iteration count increments correctly"""
        # First execution
        id1 = self.manifest.record_start(node_id="node-1")
        self.manifest.record_completion(id1)

        # Second execution (retry)
        id2 = self.manifest.record_start(node_id="node-1")

        exec1 = self.manifest.get_execution(id1)
        exec2 = self.manifest.get_execution(id2)

        self.assertEqual(exec1.iteration, 1)
        self.assertEqual(exec2.iteration, 2)

    def test_persist_restore(self):
        """Test manifest persistence and restoration"""
        # Create some executions
        id1 = self.manifest.record_start(node_id="node-1")
        self.manifest.record_completion(id1, outputs={"result": 42})

        # Persist
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            storage_path = f.name

        try:
            self.manifest.persist(storage_path)

            # Restore
            restored = ExecutionManifest.restore(storage_path)

            self.assertEqual(restored.workflow_id, self.manifest.workflow_id)
            self.assertEqual(restored._total_nodes, 1)
            self.assertEqual(restored._completed_nodes, 1)

            exec_restored = restored.get_execution(id1)
            self.assertIsNotNone(exec_restored)
            self.assertEqual(exec_restored.outputs["result"], 42)
        finally:
            os.unlink(storage_path)

    def test_performance_under_10ms(self):
        """Test that record_start completes under 10ms"""
        times = []
        for i in range(100):
            start = time.perf_counter()
            self.manifest.record_start(node_id=f"node-{i}")
            elapsed = (time.perf_counter() - start) * 1000
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        self.assertLess(avg_time, 10, f"Average time {avg_time:.2f}ms exceeds 10ms target")
        print(f"  record_start: avg={avg_time:.2f}ms, max={max_time:.2f}ms")


class TestRoutingEngine(TestCase):
    """Tests for MD-2091: RoutingEngine"""

    def setUp(self):
        self.router = RoutingEngine()

    def test_register_contract(self):
        """Test contract registration"""
        contract = InterfaceContract(
            node_id="node-1",
            version="1.0.0",
            required_inputs=[
                InterfaceField("input1", FieldType.STRING),
            ],
            produced_outputs=[
                InterfaceField("output1", FieldType.OBJECT),
            ],
        )
        self.router.register_contract(contract)

        # Verify registered
        self.assertEqual(len(self.router._contracts), 1)

    def test_analyze_readiness(self):
        """Test node readiness analysis"""
        # Create DAG
        dag = DAG([
            DAGNode("node-1"),
            DAGNode("node-2", depends_on=["node-1"]),
        ])

        # node-1 should be runnable
        readiness1 = self.router.analyze_readiness("node-1", dag)
        self.assertTrue(readiness1.is_runnable)
        self.assertEqual(readiness1.score, 1.0)

        # node-2 should be blocked
        readiness2 = self.router.analyze_readiness("node-2", dag)
        self.assertFalse(readiness2.is_runnable)
        self.assertIn("node-1", readiness2.blocked_by_nodes)

    def test_get_runnable_nodes(self):
        """Test getting runnable nodes"""
        dag = DAG([
            DAGNode("node-1"),
            DAGNode("node-2"),
            DAGNode("node-3", depends_on=["node-1"]),
        ])

        runnable = self.router.get_runnable_nodes(dag)
        self.assertEqual(set(runnable), {"node-1", "node-2"})

    def test_calculate_optimal_order(self):
        """Test interface-first scheduling optimization"""
        dag = DAG([
            DAGNode("producer"),
            DAGNode("consumer-1", depends_on=["producer"]),
            DAGNode("consumer-2", depends_on=["producer"]),
            DAGNode("consumer-3", depends_on=["producer"]),
        ])

        optimal = self.router.calculate_optimal_order(dag)

        # Producer should be first (unblocks most nodes)
        self.assertEqual(optimal[0], "producer")

    def test_record_completion_updates_state(self):
        """Test that completion updates routing state"""
        dag = DAG([
            DAGNode("node-1"),
            DAGNode("node-2", depends_on=["node-1"]),
        ])

        # Initially node-2 blocked
        self.assertFalse(self.router.analyze_readiness("node-2", dag).is_runnable)

        # Complete node-1
        self.router.record_completion("node-1", {"result": "done"})

        # Now node-2 should be runnable
        self.assertTrue(self.router.analyze_readiness("node-2", dag).is_runnable)


class TestArtifactStamper(TestCase):
    """Tests for MD-2093: ArtifactStamper"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.stamper = ArtifactStamper(
            storage_base_path=os.path.join(self.temp_dir, "artifacts"),
            metadata_store_path=os.path.join(self.temp_dir, "metadata"),
        )

    def test_stamp_content(self):
        """Test artifact stamping"""
        content = b"Hello, World!"
        stamp = self.stamper.stamp(
            content=content,
            workflow_id="workflow-1",
            node_id="node-1",
            execution_id="exec-1",
            created_by="test-agent",
            filename="hello.txt",
        )

        self.assertIsNotNone(stamp.artifact_id)
        self.assertEqual(stamp.size_bytes, len(content))
        self.assertTrue(stamp.content_hash)
        self.assertTrue(os.path.exists(stamp.storage_path))

    def test_verify_valid(self):
        """Test artifact verification - valid"""
        content = b"Test content"
        stamp = self.stamper.stamp(
            content=content,
            workflow_id="workflow-1",
            node_id="node-1",
            execution_id="exec-1",
            created_by="test-agent",
        )

        result = self.stamper.verify(stamp.artifact_id)
        self.assertEqual(result.status, VerificationStatus.VALID)

    def test_verify_corrupted(self):
        """Test artifact verification - corrupted"""
        content = b"Original content"
        stamp = self.stamper.stamp(
            content=content,
            workflow_id="workflow-1",
            node_id="node-1",
            execution_id="exec-1",
            created_by="test-agent",
        )

        # Corrupt the file
        with open(stamp.storage_path, "wb") as f:
            f.write(b"Corrupted!")

        result = self.stamper.verify(stamp.artifact_id)
        self.assertEqual(result.status, VerificationStatus.CORRUPTED)

    def test_provenance_chain(self):
        """Test provenance chain tracking"""
        # Create parent artifact
        parent = self.stamper.stamp(
            content=b"Parent",
            workflow_id="workflow-1",
            node_id="node-1",
            execution_id="exec-1",
            created_by="agent-1",
        )

        # Create child with provenance
        child = self.stamper.stamp(
            content=b"Child",
            workflow_id="workflow-1",
            node_id="node-2",
            execution_id="exec-2",
            created_by="agent-2",
            provenance=[parent.artifact_id],
        )

        chain = self.stamper.get_provenance_chain(child.artifact_id)
        self.assertEqual(len(chain), 2)

    def test_search(self):
        """Test artifact search"""
        # Create multiple artifacts
        for i in range(5):
            self.stamper.stamp(
                content=f"Content {i}".encode(),
                workflow_id="workflow-1",
                node_id=f"node-{i % 2}",
                execution_id=f"exec-{i}",
                created_by="agent-1",
            )

        # Search by node
        query = ArtifactQuery(workflow_id="workflow-1", node_id="node-0")
        results = self.stamper.search(query)
        self.assertEqual(len(results), 3)


class TestDDEAuditor(TestCase):
    """Tests for MD-2098: DDEAuditor"""

    def setUp(self):
        # Use memory-only mode for tests
        self.auditor = DDEAuditor(database_url=None, use_memory_fallback=True)

    def test_log_node_events(self):
        """Test node execution event logging"""
        workflow_id = "workflow-1"

        # Log start
        event1 = self.auditor.log_node_started(
            workflow_id=workflow_id,
            node_id="node-1",
            execution_id="exec-1",
            inputs={"input": "value"},
        )
        self.assertEqual(event1.event_type, DDEAuditEventType.NODE_STARTED)

        # Log completion
        event2 = self.auditor.log_node_completed(
            workflow_id=workflow_id,
            node_id="node-1",
            execution_id="exec-1",
            outputs={"result": 42},
            duration_ms=100,
        )
        self.assertEqual(event2.event_type, DDEAuditEventType.NODE_COMPLETED)

    def test_chain_integrity(self):
        """Test audit chain integrity"""
        workflow_id = "workflow-1"

        # Log multiple events
        self.auditor.log_node_started(workflow_id, "node-1", "exec-1")
        self.auditor.log_node_completed(workflow_id, "node-1", "exec-1")
        self.auditor.log_node_started(workflow_id, "node-2", "exec-2")

        # Get audit trail
        events = self.auditor.get_execution_audit_trail(workflow_id)
        self.assertEqual(len(events), 3)

        # Verify chain
        for i in range(1, len(events)):
            self.assertEqual(events[i].previous_hash, events[i-1].hash)

    def test_compliance_report(self):
        """Test compliance report generation"""
        workflow_id = "workflow-1"

        self.auditor.log_node_started(workflow_id, "node-1", "exec-1")
        self.auditor.log_node_completed(workflow_id, "node-1", "exec-1")

        report = self.auditor.get_compliance_report(workflow_id)

        self.assertEqual(report.workflow_id, workflow_id)
        self.assertEqual(report.total_events, 2)
        self.assertTrue(report.chain_integrity)

    def test_evidence_pack_export(self):
        """Test evidence pack export"""
        workflow_id = "workflow-1"

        self.auditor.log_node_started(workflow_id, "node-1", "exec-1")
        self.auditor.log_node_completed(workflow_id, "node-1", "exec-1")

        pack = self.auditor.export_evidence_pack(workflow_id)

        self.assertEqual(len(pack.events), 2)
        self.assertTrue(pack.integrity_verified)


class TestContractEnforcer(TestCase):
    """Tests for MD-2101: ContractEnforcer"""

    def setUp(self):
        self.enforcer = ContractEnforcer(default_mode=EnforcementMode.STRICT)

    def test_validate_inputs_valid(self):
        """Test input validation - valid"""
        contract = InterfaceContract(
            node_id="node-1",
            version="1.0.0",
            required_inputs=[
                InterfaceField("name", FieldType.STRING),
                InterfaceField("count", FieldType.NUMBER),
            ],
        )
        self.enforcer.register_contract(contract)

        result = self.enforcer.validate_inputs("node-1", {
            "name": "test",
            "count": 42,
        })

        self.assertTrue(result.valid)
        self.assertEqual(len(result.issues), 0)

    def test_validate_inputs_missing(self):
        """Test input validation - missing required"""
        contract = InterfaceContract(
            node_id="node-1",
            version="1.0.0",
            required_inputs=[
                InterfaceField("name", FieldType.STRING),
            ],
        )
        self.enforcer.register_contract(contract)

        result = self.enforcer.validate_inputs("node-1", {})

        self.assertFalse(result.valid)
        self.assertTrue(any(i.issue_type == "missing_required" for i in result.issues))

    def test_validate_inputs_type_mismatch(self):
        """Test input validation - type mismatch"""
        contract = InterfaceContract(
            node_id="node-1",
            version="1.0.0",
            required_inputs=[
                InterfaceField("count", FieldType.NUMBER),
            ],
        )
        self.enforcer.register_contract(contract)

        result = self.enforcer.validate_inputs("node-1", {"count": "not a number"})

        self.assertFalse(result.valid)
        self.assertTrue(any(i.issue_type == "type_mismatch" for i in result.issues))

    def test_enforcement_modes(self):
        """Test different enforcement modes"""
        contract = InterfaceContract(
            node_id="node-1",
            version="1.0.0",
            required_inputs=[InterfaceField("x", FieldType.STRING)],
        )
        self.enforcer.register_contract(contract)

        invalid_result = self.enforcer.validate_inputs("node-1", {})

        # WARN mode - should not block
        self.enforcer.set_enforcement_mode("node-1", EnforcementMode.WARN)
        self.assertFalse(self.enforcer.should_block(invalid_result))

        # STRICT mode - should block
        self.enforcer.set_enforcement_mode("node-1", EnforcementMode.STRICT)
        self.assertTrue(self.enforcer.should_block(invalid_result))

    def test_drift_detection(self):
        """Test contract drift detection"""
        old_contract = InterfaceContract(
            node_id="node-1",
            version="1.0.0",
            required_inputs=[InterfaceField("x", FieldType.STRING)],
        )
        self.enforcer.register_contract(old_contract)

        new_contract = InterfaceContract(
            node_id="node-1",
            version="1.1.0",
            required_inputs=[
                InterfaceField("x", FieldType.NUMBER),  # Type changed
                InterfaceField("y", FieldType.STRING),  # New field
            ],
        )

        drifts = self.enforcer.detect_drift("node-1", new_contract)

        self.assertGreater(len(drifts), 0)
        drift_types = [d.drift_type.value for d in drifts]
        self.assertIn("type_changed", drift_types)
        self.assertIn("field_added", drift_types)


class TestCircuitBreaker(TestCase):
    """Tests for MD-2102: CircuitBreaker"""

    def test_initial_state_closed(self):
        """Test initial state is CLOSED"""
        cb = CircuitBreaker(circuit_id="test")
        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_opens_after_threshold(self):
        """Test circuit opens after failure threshold"""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(circuit_id="test", config=config)

        # Record failures
        for i in range(3):
            cb.record_failure(Exception(f"Error {i}"))

        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_call_blocked_when_open(self):
        """Test calls are blocked when circuit is open"""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(circuit_id="test", config=config)

        cb.record_failure(Exception("Error"))
        self.assertEqual(cb.state, CircuitState.OPEN)

        with self.assertRaises(CircuitBreakerError):
            cb.call(lambda: "result")

    def test_fallback_invoked_when_open(self):
        """Test fallback is invoked when circuit is open"""
        config = CircuitBreakerConfig(failure_threshold=1)
        cb = CircuitBreaker(
            circuit_id="test",
            config=config,
            fallback=lambda: "fallback_result",
        )

        cb.record_failure(Exception("Error"))

        result = cb.call(lambda: "normal_result")
        self.assertEqual(result, "fallback_result")

    def test_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after timeout"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            reset_timeout_seconds=0.1,  # 100ms for testing
        )
        cb = CircuitBreaker(circuit_id="test", config=config)

        cb.record_failure(Exception("Error"))
        self.assertEqual(cb.state, CircuitState.OPEN)

        # Wait for timeout
        time.sleep(0.15)

        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

    def test_closes_after_success_in_half_open(self):
        """Test circuit closes after success in HALF_OPEN"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,  # Need 2 successes
            reset_timeout_seconds=0.01,
        )
        cb = CircuitBreaker(circuit_id="test", config=config)

        cb.record_failure(Exception("Error"))
        time.sleep(0.02)  # Wait for half-open

        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        cb.record_success()
        cb.record_success()  # Second success triggers close

        self.assertEqual(cb.state, CircuitState.CLOSED)

    def test_reopens_on_failure_in_half_open(self):
        """Test circuit reopens on failure in HALF_OPEN"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            reset_timeout_seconds=0.01,
        )
        cb = CircuitBreaker(circuit_id="test", config=config)

        cb.record_failure(Exception("Error"))
        time.sleep(0.02)

        self.assertEqual(cb.state, CircuitState.HALF_OPEN)

        cb.record_failure(Exception("Error again"))

        self.assertEqual(cb.state, CircuitState.OPEN)

    def test_stats(self):
        """Test statistics tracking"""
        cb = CircuitBreaker(circuit_id="test")

        cb.record_success()
        cb.record_success()
        cb.record_failure(Exception("Error"))

        stats = cb.get_stats()

        self.assertEqual(stats.total_calls, 0)  # No calls, just recordings
        self.assertEqual(stats.total_successes, 2)
        self.assertEqual(stats.total_failures, 1)


def run_tests():
    """Run all tests and return results."""
    import unittest
    from io import StringIO

    # Capture test output
    stream = StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)

    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestExecutionManifest))
    suite.addTests(loader.loadTestsFromTestCase(TestRoutingEngine))
    suite.addTests(loader.loadTestsFromTestCase(TestArtifactStamper))
    suite.addTests(loader.loadTestsFromTestCase(TestDDEAuditor))
    suite.addTests(loader.loadTestsFromTestCase(TestContractEnforcer))
    suite.addTests(loader.loadTestsFromTestCase(TestCircuitBreaker))

    # Run tests
    result = runner.run(suite)

    return {
        "success": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "output": stream.getvalue(),
        "failure_details": [
            {"test": str(test), "message": msg}
            for test, msg in result.failures
        ],
        "error_details": [
            {"test": str(test), "message": msg}
            for test, msg in result.errors
        ],
    }


if __name__ == "__main__":
    main()
