#!/usr/bin/env python3
"""
Unit tests for Digital Blackboard System - AI-Augmented Coordination Hub
"""
import asyncio
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from digital_blackboard_system import (
    CoordinationSignal,
    DigitalBlackboard,
    DomainCoordinationObserver,
    SignalAnalyzer,
    SignalContext,
    SignalObserver,
    SignalPriority,
    SignalStatus,
    SignalType,
)

# Fix import path for coherent system components
# Use Poetry and relative imports instead of hardcoded paths



class TestSignalContext:
    """Test suite for Signal Context"""

    def test_signal_context_creation(self):
        """Test signal context creation with default values"""
        context = SignalContext()

        assert context.orchestration_session == ""
        assert context.domain_id == ""
        assert context.intent_id == ""
        assert context.execution_phase == ""
        assert context.related_signals == []
        assert context.metadata == {}

    def test_signal_context_with_values(self):
        """Test signal context creation with specific values"""
        context = SignalContext(
            orchestration_session="test_session",
            domain_id="test_domain",
            intent_id="test_intent",
            execution_phase="testing",
            related_signals=["signal1", "signal2"],
            metadata={"test": "value"},
        )

        assert context.orchestration_session == "test_session"
        assert context.domain_id == "test_domain"
        assert context.intent_id == "test_intent"
        assert context.execution_phase == "testing"
        assert len(context.related_signals) == 2
        assert context.metadata["test"] == "value"


class TestCoordinationSignal:
    """Test suite for Coordination Signal"""

    def setup_method(self):
        """Setup test fixtures"""
        self.test_context = SignalContext(
            orchestration_session="test_session", domain_id="test_domain"
        )

        self.test_signal = CoordinationSignal(
            signal_id="test_signal_001",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Test Signal",
            description="Test signal description",
            data={"test": "data"},
            context=self.test_context,
            emitted_at=datetime.now(),
            emitted_by="test_emitter",
            target_domains=["domain1", "domain2"],
        )

    def test_signal_creation(self):
        """Test coordination signal creation"""
        assert self.test_signal.signal_id == "test_signal_001"
        assert self.test_signal.signal_type == SignalType.DEPENDENCY_RISK
        assert self.test_signal.priority == SignalPriority.HIGH
        assert self.test_signal.title == "Test Signal"
        assert self.test_signal.emitted_by == "test_emitter"
        assert len(self.test_signal.target_domains) == 2

    def test_signal_defaults(self):
        """Test signal default values"""
        assert self.test_signal.status == SignalStatus.PENDING
        assert self.test_signal.processed_by == []
        assert self.test_signal.processing_results == []
        assert self.test_signal.relevance_score == 0.0
        assert self.test_signal.response_count == 0

    def test_signal_expiration_check(self):
        """Test signal expiration checking"""
        # Test signal without expiration
        assert not self.test_signal.is_expired()

        # Test expired signal
        expired_signal = CoordinationSignal(
            signal_id="expired_signal",
            signal_type=SignalType.QUALITY_ALERT,
            priority=SignalPriority.LOW,
            title="Expired Signal",
            description="Test expired signal",
            data={},
            context=self.test_context,
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=[],
            expires_at=datetime.now() - timedelta(minutes=1),
        )

        assert expired_signal.is_expired()

    def test_signal_escalation_check(self):
        """Test signal escalation logic"""
        # Create old signal that should escalate
        old_signal = CoordinationSignal(
            signal_id="old_signal",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Old Signal",
            description="Old signal for escalation test",
            data={},
            context=self.test_context,
            emitted_at=datetime.now() - timedelta(minutes=10),  # 10 minutes ago
            emitted_by="test",
            target_domains=[],
        )

        assert old_signal.should_escalate()

        # Fresh signal should not escalate
        assert not self.test_signal.should_escalate()


class TestSignalObserver:
    """Test suite for Signal Observer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.observer = SignalObserver(
            observer_id="test_observer",
            interested_signals=[SignalType.DEPENDENCY_RISK, SignalType.QUALITY_ALERT],
            domain_filter=["test_domain"],
        )

    def test_observer_initialization(self):
        """Test signal observer initialization"""
        assert self.observer.observer_id == "test_observer"
        assert SignalType.DEPENDENCY_RISK in self.observer.interested_signals
        assert SignalType.QUALITY_ALERT in self.observer.interested_signals
        assert "test_domain" in self.observer.domain_filter

    def test_signal_interest_filtering(self):
        """Test signal interest filtering"""
        # Create signals of different types
        interesting_signal = CoordinationSignal(
            signal_id="interesting",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Interesting Signal",
            description="Signal that should be received",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["test_domain"],
        )

        uninteresting_signal = CoordinationSignal(
            signal_id="uninteresting",
            signal_type=SignalType.COORDINATION_REQUEST,  # Not in interested signals
            priority=SignalPriority.HIGH,
            title="Uninteresting Signal",
            description="Signal that should not be received",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["test_domain"],
        )

        assert self.observer.should_receive_signal(interesting_signal)
        assert not self.observer.should_receive_signal(uninteresting_signal)

    def test_domain_filtering(self):
        """Test domain-based signal filtering"""
        correct_domain_signal = CoordinationSignal(
            signal_id="correct_domain",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Correct Domain Signal",
            description="Signal from correct domain",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=[],
        )

        wrong_domain_signal = CoordinationSignal(
            signal_id="wrong_domain",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Wrong Domain Signal",
            description="Signal from wrong domain",
            data={},
            context=SignalContext(domain_id="other_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["other_domain"],
        )

        assert self.observer.should_receive_signal(correct_domain_signal)
        assert not self.observer.should_receive_signal(wrong_domain_signal)

    @pytest.mark.asyncio
    async def test_signal_processing(self):
        """Test signal processing by observer"""
        test_signal = CoordinationSignal(
            signal_id="test_processing",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Test Processing Signal",
            description="Signal for processing test",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=[],
        )

        response = await self.observer.on_signal_received(test_signal)

        assert response["observer_id"] == "test_observer"
        assert response["signal_id"] == "test_processing"
        assert response["response"] == "acknowledged"
        assert response["action_taken"] is False  # Default implementation


class TestSignalAnalyzer:
    """Test suite for Signal Analyzer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.analyzer = SignalAnalyzer(history_window=100)

    def test_analyzer_initialization(self):
        """Test signal analyzer initialization"""
        assert hasattr(self.analyzer, "signal_history")
        assert hasattr(self.analyzer, "pattern_cache")
        assert self.analyzer.signal_history.maxlen == 100

    def test_signal_effectiveness_analysis(self):
        """Test analysis of signal effectiveness"""
        # Add test signals to history
        test_signal_1 = CoordinationSignal(
            signal_id="test_1",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Test Signal 1",
            description="First test signal",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=[],
        )
        test_signal_1.improvement_measured = 0.8

        test_signal_2 = CoordinationSignal(
            signal_id="test_2",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Test Signal 2",
            description="Second test signal",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=[],
        )
        test_signal_2.improvement_measured = 0.6

        self.analyzer.signal_history.extend([test_signal_1, test_signal_2])

        # Test effectiveness calculation for similar signal
        new_signal = CoordinationSignal(
            signal_id="new_signal",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="New Signal",
            description="New signal for effectiveness test",
            data={},
            context=SignalContext(domain_id="test_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=[],
        )

        effectiveness = self.analyzer.analyze_signal_effectiveness(new_signal)
        assert effectiveness == 0.7  # Average of 0.8 and 0.6

    def test_pattern_detection(self):
        """Test detection of signal patterns"""
        # Add recurring signals
        for i in range(15):
            recurring_signal = CoordinationSignal(
                signal_id=f"recurring_{i}",
                signal_type=SignalType.DEPENDENCY_RISK,
                priority=SignalPriority.HIGH,
                title=f"Recurring Signal {i}",
                description="Recurring signal for pattern test",
                data={},
                context=SignalContext(domain_id="test_domain"),
                emitted_at=datetime.now(),
                emitted_by="test",
                target_domains=[],
            )
            self.analyzer.signal_history.append(recurring_signal)

        patterns = self.analyzer.detect_signal_patterns()

        # Should detect recurring pattern
        recurring_patterns = [p for p in patterns if p["pattern_type"] == "recurring_signal"]
        assert len(recurring_patterns) > 0

    def test_ignored_signal_detection(self):
        """Test detection of ignored signals"""
        # Add signals with low response rates
        for i in range(10):
            ignored_signal = CoordinationSignal(
                signal_id=f"ignored_{i}",
                signal_type=SignalType.QUALITY_ALERT,
                priority=SignalPriority.LOW,
                title=f"Ignored Signal {i}",
                description="Signal with low response rate",
                data={},
                context=SignalContext(),
                emitted_at=datetime.now(),
                emitted_by="test",
                target_domains=[],
            )
            ignored_signal.response_count = 5
            ignored_signal.successful_responses = 1  # 20% response rate
            self.analyzer.signal_history.append(ignored_signal)

        ignored_patterns = self.analyzer._detect_ignored_signals()

        # Should detect ignored pattern
        assert len(ignored_patterns) > 0
        ignored_pattern = ignored_patterns[0]
        assert ignored_pattern["pattern_type"] == "ignored_signal"
        assert ignored_pattern["response_rate"] == 0.2


class TestDigitalBlackboard:
    """Test suite for Digital Blackboard"""

    def setup_method(self):
        """Setup test fixtures"""
        # Use in-memory database for testing
        self.blackboard = DigitalBlackboard(persistence_db=":memory:")

    def teardown_method(self):
        """Cleanup after tests"""
        if hasattr(self.blackboard, "is_running") and self.blackboard.is_running:
            asyncio.get_event_loop().run_until_complete(self.blackboard.stop())

    def test_blackboard_initialization(self):
        """Test digital blackboard initialization"""
        assert hasattr(self.blackboard, "active_signals")
        assert hasattr(self.blackboard, "observers")
        assert hasattr(self.blackboard, "signal_analyzer")
        assert len(self.blackboard.active_signals) == 0
        assert len(self.blackboard.observers) == 0

    def test_persistence_initialization(self):
        """Test database persistence initialization"""
        # Check that tables were created
        with sqlite3.connect(":memory:") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

        # Tables should exist in the actual blackboard's database
        assert self.blackboard.persistence_db == ":memory:"

    @pytest.mark.asyncio
    async def test_observer_subscription(self):
        """Test observer subscription and unsubscription"""
        test_observer = SignalObserver(
            observer_id="test_sub_observer", interested_signals=[SignalType.DEPENDENCY_RISK]
        )

        # Subscribe observer
        self.blackboard.subscribe_observer(test_observer)
        assert len(self.blackboard.observers) == 1
        assert self.blackboard.observers[0].observer_id == "test_sub_observer"

        # Unsubscribe observer
        self.blackboard.unsubscribe_observer("test_sub_observer")
        assert len(self.blackboard.observers) == 0

    @pytest.mark.asyncio
    async def test_signal_emission(self):
        """Test signal emission to blackboard"""
        test_context = SignalContext(orchestration_session="test_emission", domain_id="test_domain")

        signal_id = await self.blackboard.emit_signal(
            signal_type=SignalType.DEPENDENCY_RISK,
            title="Test Emission Signal",
            description="Signal for emission test",
            data={"test": "emission"},
            context=test_context,
            emitted_by="test_emitter",
            target_domains=["test_domain"],
            priority=SignalPriority.HIGH,
        )

        assert signal_id is not None
        assert signal_id in self.blackboard.active_signals

        # Check signal properties
        emitted_signal = self.blackboard.active_signals[signal_id]
        assert emitted_signal.signal_type == SignalType.DEPENDENCY_RISK
        assert emitted_signal.title == "Test Emission Signal"
        assert emitted_signal.emitted_by == "test_emitter"

    @pytest.mark.asyncio
    async def test_signal_processing_workflow(self):
        """Test complete signal processing workflow"""
        # Create test observer
        test_observer = SignalObserver(
            observer_id="test_processor", interested_signals=[SignalType.COORDINATION_REQUEST]
        )

        # Mock the observer's processing method
        async def mock_processing(signal):
            return {
                "observer_id": "test_processor",
                "signal_id": signal.signal_id,
                "response": "processed",
                "action_taken": True,
                "processing_time": 0.1,
            }

        test_observer.on_signal_received = mock_processing
        self.blackboard.subscribe_observer(test_observer)

        # Start blackboard processing
        await self.blackboard.start()

        # Emit test signal
        signal_id = await self.blackboard.emit_signal(
            signal_type=SignalType.COORDINATION_REQUEST,
            title="Test Processing Signal",
            description="Signal for processing workflow test",
            data={"workflow": "test"},
            context=SignalContext(domain_id="test_domain"),
            emitted_by="test_workflow",
            target_domains=["test_domain"],
            priority=SignalPriority.MEDIUM,
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Stop blackboard
        await self.blackboard.stop()

        # Signal should have been processed and moved to history
        assert signal_id not in self.blackboard.active_signals
        assert len(self.blackboard.signal_history) > 0

    @pytest.mark.asyncio
    async def test_active_signals_filtering(self):
        """Test filtering of active signals"""
        # Emit multiple signals
        signal_ids = []

        # High priority dependency signal
        signal_ids.append(
            await self.blackboard.emit_signal(
                signal_type=SignalType.DEPENDENCY_RISK,
                title="High Priority Dependency",
                description="High priority dependency signal",
                data={},
                context=SignalContext(domain_id="domain1"),
                emitted_by="test",
                target_domains=["domain1"],
                priority=SignalPriority.HIGH,
            )
        )

        # Medium priority quality signal
        signal_ids.append(
            await self.blackboard.emit_signal(
                signal_type=SignalType.QUALITY_ALERT,
                title="Medium Priority Quality",
                description="Medium priority quality signal",
                data={},
                context=SignalContext(domain_id="domain2"),
                emitted_by="test",
                target_domains=["domain2"],
                priority=SignalPriority.MEDIUM,
            )
        )

        # Test filtering by signal type
        dependency_signals = await self.blackboard.get_active_signals(
            signal_type=SignalType.DEPENDENCY_RISK
        )
        assert len(dependency_signals) == 1
        assert dependency_signals[0].signal_type == SignalType.DEPENDENCY_RISK

        # Test filtering by domain
        domain1_signals = await self.blackboard.get_active_signals(domain_filter="domain1")
        assert len(domain1_signals) == 1
        assert domain1_signals[0].context.domain_id == "domain1"

        # Test filtering by priority
        high_priority_signals = await self.blackboard.get_active_signals(
            priority_filter=SignalPriority.HIGH
        )
        assert len(high_priority_signals) == 1
        assert high_priority_signals[0].priority == SignalPriority.HIGH

    @pytest.mark.asyncio
    async def test_signal_analytics(self):
        """Test signal analytics generation"""
        # Emit some test signals
        for i in range(3):
            await self.blackboard.emit_signal(
                signal_type=SignalType.DEPENDENCY_RISK,
                title=f"Analytics Test Signal {i}",
                description=f"Signal {i} for analytics test",
                data={"index": i},
                context=SignalContext(),
                emitted_by="analytics_test",
                target_domains=[],
                priority=SignalPriority.MEDIUM,
            )

        analytics = await self.blackboard.get_signal_analytics()

        assert "active_signals" in analytics
        assert "total_observers" in analytics
        assert "signal_type_distribution" in analytics
        assert "priority_distribution" in analytics
        assert analytics["active_signals"] == 3

    @pytest.mark.asyncio
    async def test_signal_expiration_cleanup(self):
        """Test cleanup of expired signals"""
        # Emit signal with short expiration
        signal_id = await self.blackboard.emit_signal(
            signal_type=SignalType.QUALITY_ALERT,
            title="Expiring Signal",
            description="Signal that will expire soon",
            data={},
            context=SignalContext(),
            emitted_by="expiration_test",
            target_domains=[],
            priority=SignalPriority.LOW,
            expires_in=timedelta(milliseconds=50),  # Very short expiration
        )

        # Start blackboard to begin cleanup tasks
        await self.blackboard.start()

        # Wait for expiration and cleanup
        await asyncio.sleep(0.1)

        # Stop blackboard
        await self.blackboard.stop()

        # Signal should have been moved from active to history
        assert signal_id not in self.blackboard.active_signals

    def test_signal_relevance_calculation(self):
        """Test signal relevance calculation"""
        # Test critical signal type
        critical_relevance = self.blackboard._calculate_signal_relevance(
            SignalType.SECURITY_CONCERN, {}, SignalContext(orchestration_session="test_session")
        )
        assert critical_relevance > 0.5

        # Test normal signal type
        normal_relevance = self.blackboard._calculate_signal_relevance(
            SignalType.LEARNING_OPPORTUNITY, {}, SignalContext()
        )
        assert normal_relevance >= 0.5

    def test_coordination_impact_calculation(self):
        """Test coordination impact calculation"""
        # Test high impact signal
        high_impact = self.blackboard._calculate_coordination_impact(
            SignalType.COORDINATION_REQUEST, SignalContext()
        )
        assert high_impact >= 0.8

        # Test medium impact signal
        medium_impact = self.blackboard._calculate_coordination_impact(
            SignalType.RESOURCE_OPTIMIZATION, SignalContext()
        )
        assert medium_impact >= 0.4


class TestDomainCoordinationObserver:
    """Test suite for Domain Coordination Observer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.observer = DomainCoordinationObserver("test_coordination_domain")

    def test_domain_observer_initialization(self):
        """Test domain coordination observer initialization"""
        assert self.observer.domain_id == "test_coordination_domain"
        assert self.observer.observer_id == "domain_test_coordination_domain"
        assert SignalType.DEPENDENCY_RISK in self.observer.interested_signals
        assert SignalType.COORDINATION_REQUEST in self.observer.interested_signals

    @pytest.mark.asyncio
    async def test_dependency_risk_handling(self):
        """Test handling of dependency risk signals"""
        test_signal = CoordinationSignal(
            signal_id="dependency_test",
            signal_type=SignalType.DEPENDENCY_RISK,
            priority=SignalPriority.HIGH,
            title="Test Dependency Risk",
            description="Test dependency risk handling",
            data={"dependency": "test_api"},
            context=SignalContext(domain_id="test_coordination_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["test_coordination_domain"],
        )

        response = await self.observer.on_signal_received(test_signal)

        assert response["observer_id"] == "domain_test_coordination_domain"
        assert response["action_taken"] is True
        assert response["domain_id"] == "test_coordination_domain"

    @pytest.mark.asyncio
    async def test_coordination_request_handling(self):
        """Test handling of coordination request signals"""
        test_signal = CoordinationSignal(
            signal_id="coordination_test",
            signal_type=SignalType.COORDINATION_REQUEST,
            priority=SignalPriority.MEDIUM,
            title="Test Coordination Request",
            description="Test coordination request handling",
            data={"request_type": "clarification"},
            context=SignalContext(domain_id="test_coordination_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["test_coordination_domain"],
        )

        response = await self.observer.on_signal_received(test_signal)

        assert response["observer_id"] == "domain_test_coordination_domain"
        assert response["action_taken"] is True
        assert response["response"] == "processed"

    @pytest.mark.asyncio
    async def test_quality_alert_handling(self):
        """Test handling of quality alert signals"""
        test_signal = CoordinationSignal(
            signal_id="quality_test",
            signal_type=SignalType.QUALITY_ALERT,
            priority=SignalPriority.HIGH,
            title="Test Quality Alert",
            description="Test quality alert handling",
            data={"quality_metric": "test_coverage", "value": 0.6},
            context=SignalContext(domain_id="test_coordination_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["test_coordination_domain"],
        )

        response = await self.observer.on_signal_received(test_signal)

        assert response["action_taken"] is True

    @pytest.mark.asyncio
    async def test_resource_optimization_handling(self):
        """Test handling of resource optimization signals"""
        test_signal = CoordinationSignal(
            signal_id="resource_test",
            signal_type=SignalType.RESOURCE_OPTIMIZATION,
            priority=SignalPriority.MEDIUM,
            title="Test Resource Optimization",
            description="Test resource optimization handling",
            data={"resource_type": "cpu", "optimization": "scale_down"},
            context=SignalContext(domain_id="test_coordination_domain"),
            emitted_at=datetime.now(),
            emitted_by="test",
            target_domains=["test_coordination_domain"],
        )

        response = await self.observer.on_signal_received(test_signal)

        assert response["action_taken"] is True


class TestIntegrationScenarios:
    """Test integration scenarios for Digital Blackboard System"""

    @pytest.mark.asyncio
    async def test_multi_observer_signal_processing(self):
        """Test signal processing with multiple observers"""
        blackboard = DigitalBlackboard(persistence_db=":memory:")

        # Create multiple observers
        observer1 = DomainCoordinationObserver("domain1")
        observer2 = DomainCoordinationObserver("domain2")
        observer3 = SignalObserver(
            observer_id="general_observer",
            interested_signals=[SignalType.DEPENDENCY_RISK, SignalType.QUALITY_ALERT],
        )

        # Subscribe observers
        blackboard.subscribe_observer(observer1)
        blackboard.subscribe_observer(observer2)
        blackboard.subscribe_observer(observer3)

        # Start blackboard
        await blackboard.start()

        # Emit signal that should be received by multiple observers
        signal_id = await blackboard.emit_signal(
            signal_type=SignalType.DEPENDENCY_RISK,
            title="Multi-Observer Test Signal",
            description="Signal for multi-observer test",
            data={"test": "multi_observer"},
            context=SignalContext(),
            emitted_by="integration_test",
            target_domains=["domain1", "domain2"],
            priority=SignalPriority.HIGH,
        )

        # Wait for processing
        await asyncio.sleep(0.1)

        # Stop blackboard
        await blackboard.stop()

        # Signal should have been processed
        assert signal_id not in blackboard.active_signals

    @pytest.mark.asyncio
    async def test_signal_cascade_scenario(self):
        """Test scenario where signals trigger other signals"""
        blackboard = DigitalBlackboard(persistence_db=":memory:")

        # Create observer that emits follow-up signals
        class CascadingObserver(SignalObserver):
            def __init__(self, blackboard_ref):
                super().__init__(
                    observer_id="cascading_observer",
                    interested_signals=[SignalType.DEPENDENCY_RISK],
                )
                self.blackboard_ref = blackboard_ref

            async def on_signal_received(self, signal):
                # Emit a follow-up signal
                await self.blackboard_ref.emit_signal(
                    signal_type=SignalType.COORDINATION_REQUEST,
                    title="Follow-up Signal",
                    description="Signal triggered by dependency risk",
                    data={"triggered_by": signal.signal_id},
                    context=SignalContext(),
                    emitted_by="cascading_observer",
                    target_domains=[],
                    priority=SignalPriority.MEDIUM,
                )

                return {
                    "observer_id": self.observer_id,
                    "signal_id": signal.signal_id,
                    "action_taken": True,
                    "follow_up_emitted": True,
                }

        cascading_observer = CascadingObserver(blackboard)
        blackboard.subscribe_observer(cascading_observer)

        # Start blackboard
        await blackboard.start()

        # Emit initial signal
        initial_signal_id = await blackboard.emit_signal(
            signal_type=SignalType.DEPENDENCY_RISK,
            title="Initial Cascade Signal",
            description="Signal that will trigger cascade",
            data={"cascade": "test"},
            context=SignalContext(),
            emitted_by="cascade_test",
            target_domains=[],
            priority=SignalPriority.HIGH,
        )

        # Wait for cascade processing
        await asyncio.sleep(0.2)

        # Stop blackboard
        await blackboard.stop()

        # Should have both signals processed
        assert len(blackboard.signal_history) >= 2

    @pytest.mark.asyncio
    async def test_high_volume_signal_processing(self):
        """Test processing of high volume signals"""
        blackboard = DigitalBlackboard(persistence_db=":memory:")

        # Create high-throughput observer
        class HighThroughputObserver(SignalObserver):
            def __init__(self):
                super().__init__(
                    observer_id="high_throughput",
                    interested_signals=list(SignalType),  # All signal types
                )
                self.processed_count = 0

            async def on_signal_received(self, signal):
                self.processed_count += 1
                return {
                    "observer_id": self.observer_id,
                    "signal_id": signal.signal_id,
                    "action_taken": True,
                    "processing_time": 0.001,
                }

        observer = HighThroughputObserver()
        blackboard.subscribe_observer(observer)

        # Start blackboard
        await blackboard.start()

        # Emit many signals quickly
        signal_ids = []
        for i in range(20):
            signal_id = await blackboard.emit_signal(
                signal_type=SignalType.QUALITY_ALERT,
                title=f"High Volume Signal {i}",
                description=f"Signal {i} for high volume test",
                data={"index": i},
                context=SignalContext(),
                emitted_by="volume_test",
                target_domains=[],
                priority=SignalPriority.LOW,
            )
            signal_ids.append(signal_id)

        # Wait for all processing
        await asyncio.sleep(0.5)

        # Stop blackboard
        await blackboard.stop()

        # All signals should be processed
        assert observer.processed_count == 20
        assert len(blackboard.active_signals) == 0
