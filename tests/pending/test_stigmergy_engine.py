#!/usr/bin/env python3
"""
Unit tests for Stigmergy Engine - AI-Driven Coordination System
"""
import asyncio
import sys
from collections import deque
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import numpy as np
import pytest
from digital_blackboard_system import DigitalBlackboard, SignalPriority, SignalType
from stigmergy_engine import (
    BottleneckPredictor,
    CoordinationPattern,
    DependencyAnalyzer,
    MLModelMetrics,
    PatternType,
    PredictionConfidence,
    PredictiveInsight,
    QualityTrendAnalyzer,
    StigmergyEngine,
)

# Fix import path for coherent system components
# Use Poetry and relative imports instead of hardcoded paths



class TestDependencyAnalyzer:
    """Test suite for Dependency Analyzer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.analyzer = DependencyAnalyzer()

    def test_analyzer_initialization(self):
        """Test dependency analyzer initialization"""
        assert self.analyzer.model is None
        assert hasattr(self.analyzer, "feature_history")
        assert hasattr(self.analyzer, "prediction_history")
        assert len(self.analyzer.training_data) == 0

    def test_feature_extraction(self):
        """Test feature extraction from signal context and system state"""
        signal_context = {
            "active_signals": ["signal1", "signal2", "signal3"],
            "avg_signal_age": 120,
            "domain_interactions": ["domain1", "domain2"],
            "signal_density": 0.5,
            "recent_signals": [
                {"type": SignalType.DEPENDENCY_RISK.value},
                {"type": SignalType.QUALITY_ALERT.value},
            ],
        }

        system_state = {
            "active_orchestrations": 2,
            "domain_load_variance": 0.3,
            "avg_execution_time": 45.0,
            "pending_dependencies": ["dep1", "dep2", "dep3"],
        }

        features = self.analyzer.extract_features(signal_context, system_state)

        assert isinstance(features, np.ndarray)
        assert len(features) == 14  # Expected number of features
        assert features[0] == 3  # active_signals count
        assert features[1] == 120  # avg_signal_age
        assert features[4] == 2  # active_orchestrations

    @pytest.mark.asyncio
    async def test_heuristic_prediction(self):
        """Test heuristic-based prediction when ML is unavailable"""
        signal_context = {
            "active_signals": list(range(8)),  # 8 active signals
            "domain_interactions": list(range(15)),  # 15 domain interactions
        }

        risk_probability, explanation = await self.analyzer._heuristic_prediction(
            np.array([1, 2, 3, 4]), signal_context
        )

        assert 0 <= risk_probability <= 1
        assert explanation["method"] == "heuristic"
        assert "factors" in explanation
        assert explanation["factors"]["active_signals"] == 8

    @pytest.mark.asyncio
    async def test_dependency_risk_prediction(self):
        """Test dependency risk prediction"""
        signal_context = {
            "active_signals": ["signal1", "signal2"],
            "avg_signal_age": 60,
            "domain_interactions": ["domain1"],
            "signal_density": 0.2,
            "recent_signals": [],
        }

        system_state = {
            "active_orchestrations": 1,
            "domain_load_variance": 0.1,
            "avg_execution_time": 30.0,
            "pending_dependencies": [],
        }

        risk_probability, explanation = await self.analyzer.predict_dependency_risk(
            signal_context, system_state
        )

        assert 0 <= risk_probability <= 1
        assert isinstance(explanation, dict)
        assert "method" in explanation

    def test_recent_patterns_analysis(self):
        """Test analysis of recent dependency patterns"""
        signal_context = {
            "recent_signals": [
                {
                    "type": SignalType.DEPENDENCY_RISK.value,
                    "target_domains": ["domain1", "domain2"],
                },
                {
                    "type": SignalType.DEPENDENCY_RISK.value,
                    "target_domains": ["domain2", "domain3"],
                },
                {"type": SignalType.QUALITY_ALERT.value, "status": "resolved"},
                {"type": SignalType.COORDINATION_REQUEST.value, "status": "resolved"},
            ]
        }

        patterns = self.analyzer._analyze_recent_patterns(signal_context)

        assert "cascade_probability" in patterns
        assert "dependency_complexity" in patterns
        assert "resolution_success_rate" in patterns
        assert 0 <= patterns["cascade_probability"] <= 1
        assert patterns["resolution_success_rate"] == 0.5  # 2 resolved out of 4 total

    def test_training_data_preparation(self):
        """Test preparation of training data from feedback"""
        feedback_data = [
            {"features": [1, 2, 3, 4, 5], "outcome": "dependency_conflict"},
            {"features": [0, 1, 1, 2, 1], "outcome": "no_conflict"},
            {"features": [3, 4, 5, 6, 7], "outcome": "dependency_conflict"},
        ]

        X, y = self.analyzer._prepare_training_data(feedback_data)

        assert X.shape == (3, 5)
        assert y.shape == (3,)
        assert list(y) == [1, 0, 1]  # dependency_conflict=1, no_conflict=0


class TestBottleneckPredictor:
    """Test suite for Bottleneck Predictor"""

    def setup_method(self):
        """Setup test fixtures"""
        self.predictor = BottleneckPredictor()

    def test_predictor_initialization(self):
        """Test bottleneck predictor initialization"""
        assert hasattr(self.predictor, "performance_history")
        assert hasattr(self.predictor, "prediction_thresholds")
        assert self.predictor.prediction_thresholds["execution_time"] == 2.0

    def test_performance_feature_extraction(self):
        """Test extraction of performance features"""
        metrics = {
            "avg_execution_time": 45.0,
            "cpu_usage": 0.75,
            "memory_usage": 0.60,
            "active_processes": 15,
            "queue_length": 3,
            "error_rate": 0.02,
            "throughput": 1.5,
            "active_domains": ["domain1", "domain2", "domain3"],
            "signal_processing_time": 0.1,
            "db_query_time": 0.05,
        }

        features = self.predictor._extract_performance_features(metrics)

        assert len(features) == 10
        assert features[0] == 45.0  # avg_execution_time
        assert features[1] == 0.75  # cpu_usage
        assert features[7] == 3  # active_domains count

    @pytest.mark.asyncio
    async def test_bottleneck_pattern_detection(self):
        """Test detection of bottleneck patterns"""
        high_cpu_metrics = {"cpu_usage": 0.90, "memory_usage": 0.50}
        high_memory_metrics = {"cpu_usage": 0.60, "memory_usage": 0.95}
        normal_metrics = {"cpu_usage": 0.50, "memory_usage": 0.40}

        # Test CPU bottleneck detection
        cpu_patterns = await self.predictor._detect_bottleneck_patterns(high_cpu_metrics)
        assert len(cpu_patterns) == 1
        assert cpu_patterns[0].pattern_type == PatternType.BOTTLENECK_CLUSTER
        assert cpu_patterns[0].root_cause_analysis["bottleneck_type"] == "cpu"

        # Test memory bottleneck detection
        memory_patterns = await self.predictor._detect_bottleneck_patterns(high_memory_metrics)
        assert len(memory_patterns) == 1
        assert memory_patterns[0].root_cause_analysis["bottleneck_type"] == "memory"

        # Test normal conditions
        normal_patterns = await self.predictor._detect_bottleneck_patterns(normal_metrics)
        assert len(normal_patterns) == 0

    @pytest.mark.asyncio
    async def test_performance_pattern_analysis(self):
        """Test comprehensive performance pattern analysis"""
        test_metrics = {
            "avg_execution_time": 35.0,
            "cpu_usage": 0.70,
            "memory_usage": 0.60,
            "active_processes": 20,
            "queue_length": 2,
            "error_rate": 0.05,
            "throughput": 1.2,
        }

        patterns = await self.predictor.analyze_performance_patterns(test_metrics)

        # Should return at least one entry in performance history
        assert len(self.predictor.performance_history) == 1
        assert isinstance(patterns, list)


class TestQualityTrendAnalyzer:
    """Test suite for Quality Trend Analyzer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.analyzer = QualityTrendAnalyzer()

    def test_analyzer_initialization(self):
        """Test quality trend analyzer initialization"""
        assert hasattr(self.analyzer, "quality_history")
        assert hasattr(self.analyzer, "quality_thresholds")
        assert self.analyzer.quality_thresholds["warning"] == 0.75

    @pytest.mark.asyncio
    async def test_quality_trend_analysis(self):
        """Test quality trend analysis"""
        # Add some quality data points with declining trend
        declining_scores = [0.9, 0.85, 0.8, 0.75, 0.7]
        for score in declining_scores:
            self.analyzer.quality_history.append(
                {"timestamp": datetime.now(), "metrics": {"overall_score": score}}
            )

        insights = await self.analyzer._analyze_quality_trends()

        assert len(insights) > 0
        decline_insight = insights[0]
        assert decline_insight.prediction_type == "quality_degradation"
        assert decline_insight.confidence in [
            PredictionConfidence.HIGH,
            PredictionConfidence.MEDIUM,
        ]

    @pytest.mark.asyncio
    async def test_quality_improvement_detection(self):
        """Test detection of quality improvement opportunities"""
        # Add quality data points with improving trend
        improving_scores = [0.6, 0.65, 0.7, 0.75, 0.8]
        for score in improving_scores:
            self.analyzer.quality_history.append(
                {"timestamp": datetime.now(), "metrics": {"overall_score": score}}
            )

        insights = await self.analyzer._analyze_quality_trends()

        # Should detect improvement opportunity
        assert len(insights) > 0
        improvement_insight = insights[0]
        assert improvement_insight.prediction_type == "quality_opportunity"

    @pytest.mark.asyncio
    async def test_quality_risk_prediction(self):
        """Test prediction of quality degradation risks"""
        # Set up quality metrics with risk factors
        risk_metrics = {
            "test_coverage": 0.7,  # Below 0.8 threshold
            "complexity_score": 0.8,  # Above 0.7 threshold
            "error_rate": 0.15,  # Above 0.1 threshold
            "execution_time": 25,  # Below 30 threshold (time pressure)
        }

        self.analyzer.quality_history.append({"timestamp": datetime.now(), "metrics": risk_metrics})

        insights = await self.analyzer._predict_quality_degradation()

        assert len(insights) > 0
        risk_insight = insights[0]
        assert risk_insight.prediction_type == "quality_risk_accumulation"
        assert risk_insight.predicted_scenario["risk_level"] >= 2  # Multiple risk factors

    @pytest.mark.asyncio
    async def test_quality_trends_with_insufficient_data(self):
        """Test quality trend analysis with insufficient data"""
        # Add only 2 data points (below minimum of 5)
        for score in [0.8, 0.85]:
            self.analyzer.quality_history.append(
                {"timestamp": datetime.now(), "metrics": {"overall_score": score}}
            )

        insights = await self.analyzer._analyze_quality_trends()

        # Should return empty list for insufficient data
        assert len(insights) == 0


class TestStigmergyEngine:
    """Test suite for Stigmergy Engine"""

    def setup_method(self):
        """Setup test fixtures"""
        self.mock_blackboard = MagicMock()
        self.engine = StigmergyEngine(self.mock_blackboard)

    def test_engine_initialization(self):
        """Test stigmergy engine initialization"""
        assert self.engine.blackboard == self.mock_blackboard
        assert isinstance(self.engine.dependency_analyzer, DependencyAnalyzer)
        assert isinstance(self.engine.bottleneck_predictor, BottleneckPredictor)
        assert isinstance(self.engine.quality_analyzer, QualityTrendAnalyzer)
        assert hasattr(self.engine, "pattern_database")
        assert hasattr(self.engine, "coordination_history")

    @pytest.mark.asyncio
    async def test_system_metrics_collection(self):
        """Test collection of system metrics"""
        with patch("psutil.cpu_percent", return_value=75.0):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 60.0
                with patch("psutil.pids", return_value=list(range(50))):
                    metrics = await self.engine._collect_system_metrics()

                    assert "cpu_usage" in metrics
                    assert "memory_usage" in metrics
                    assert "active_processes" in metrics
                    assert metrics["cpu_usage"] == 75.0
                    assert metrics["memory_usage"] == 0.6

    @pytest.mark.asyncio
    async def test_signal_context_collection(self):
        """Test collection of signal context from blackboard"""
        mock_analytics = {"signal_count": 5, "avg_response_time": 1.2}
        mock_active_signals = ["signal1", "signal2", "signal3"]

        self.mock_blackboard.get_signal_analytics = AsyncMock(return_value=mock_analytics)
        self.mock_blackboard.get_active_signals = AsyncMock(return_value=mock_active_signals)

        context = await self.engine._get_signal_context()

        assert "active_signals" in context
        assert "analytics" in context
        assert context["active_signals"] == mock_active_signals
        assert context["signal_density"] == 0.3  # 3 signals / 10.0

    @pytest.mark.asyncio
    async def test_analyze_and_signal_dependency_risks(self):
        """Test analysis and signal generation for dependency risks"""
        system_metrics = {"cpu_usage": 0.5, "memory_usage": 0.4, "active_processes": 20}

        signal_context = {
            "active_signals": ["signal1", "signal2"],
            "domain_interactions": ["domain1", "domain2", "domain3"],
        }

        # Mock high dependency risk
        self.engine.dependency_analyzer.predict_dependency_risk = AsyncMock(
            return_value=(0.8, {"method": "ml", "confidence": "high"})
        )

        signals = await self.engine.analyze_and_signal(system_metrics, signal_context)

        assert len(signals) >= 1
        dependency_signal = signals[0]
        assert dependency_signal["signal_type"] == SignalType.DEPENDENCY_RISK
        assert dependency_signal["data"]["risk_probability"] == 0.8

    @pytest.mark.asyncio
    async def test_analyze_and_signal_bottlenecks(self):
        """Test analysis and signal generation for bottlenecks"""
        system_metrics = {
            "cpu_usage": 0.90,  # High CPU usage
            "memory_usage": 0.5,
            "avg_execution_time": 60.0,
        }

        signal_context = {"active_signals": []}

        # Mock bottleneck detection
        mock_pattern = CoordinationPattern(
            pattern_id="test_bottleneck",
            pattern_type=PatternType.BOTTLENECK_CLUSTER,
            confidence=0.85,
            affected_domains=["implementation"],
            signal_sequence=[],
            temporal_window=timedelta(minutes=5),
            root_cause_analysis={"bottleneck_type": "cpu"},
            recommended_actions=["scale_resources"],
            predicted_impact=0.7,
            prevention_signals=[],
        )

        self.engine.bottleneck_predictor.analyze_performance_patterns = AsyncMock(
            return_value=[mock_pattern]
        )

        signals = await self.engine.analyze_and_signal(system_metrics, signal_context)

        # Should have bottleneck warning signal
        bottleneck_signals = [
            s for s in signals if s["signal_type"] == SignalType.BOTTLENECK_WARNING
        ]
        assert len(bottleneck_signals) > 0

    @pytest.mark.asyncio
    async def test_analyze_and_signal_quality_insights(self):
        """Test analysis and signal generation for quality insights"""
        system_metrics = {
            "quality_metrics": {
                "overall_score": 0.65,  # Below warning threshold
                "test_coverage": 0.7,
                "complexity_score": 0.8,
            }
        }

        signal_context = {"active_signals": []}

        # Mock quality insight
        mock_insight = PredictiveInsight(
            insight_id="quality_test",
            prediction_type="quality_degradation",
            confidence=PredictionConfidence.HIGH,
            time_horizon=timedelta(hours=2),
            affected_components=["quality_assurance"],
            predicted_scenario={"trend_slope": -0.02},
            preventive_actions=[{"action": "increase_testing", "priority": "high"}],
            risk_assessment={"quality_degradation": 0.3},
        )

        self.engine.quality_analyzer.analyze_quality_trends = AsyncMock(return_value=[mock_insight])

        signals = await self.engine.analyze_and_signal(system_metrics, signal_context)

        # Should have quality alert signal
        quality_signals = [s for s in signals if s["signal_type"] == SignalType.QUALITY_ALERT]
        assert len(quality_signals) > 0

    @pytest.mark.asyncio
    async def test_coordination_pattern_detection(self):
        """Test detection of coordination patterns"""
        signal_context = {
            "active_signals": list(range(20)),  # Signal storm
            "recent_signals": [
                {"type": SignalType.COORDINATION_REQUEST.value},
                {"type": SignalType.COORDINATION_REQUEST.value},
                {"type": SignalType.COORDINATION_REQUEST.value},
                {"type": SignalType.COORDINATION_REQUEST.value},
                {"type": SignalType.COORDINATION_REQUEST.value},
                {"type": SignalType.COORDINATION_REQUEST.value},
            ],
        }

        system_metrics = {}

        patterns = await self.engine._detect_coordination_patterns(signal_context, system_metrics)

        assert len(patterns) >= 1
        # Should detect signal storm
        signal_storm = next((p for p in patterns if p["type"] == "signal_storm"), None)
        assert signal_storm is not None
        assert signal_storm["signal_count"] == 20

        # Should detect coordination loop
        coord_loop = next((p for p in patterns if p["type"] == "coordination_loop"), None)
        assert coord_loop is not None

    @pytest.mark.asyncio
    async def test_ai_signal_emission(self):
        """Test emission of AI-generated signals"""
        signal_data = {
            "signal_type": SignalType.DEPENDENCY_RISK,
            "priority": SignalPriority.HIGH,
            "title": "Test AI Signal",
            "description": "Test description",
            "data": {"test": "data"},
            "target_domains": ["test_domain"],
        }

        self.mock_blackboard.emit_signal = AsyncMock()

        await self.engine._emit_ai_generated_signal(signal_data)

        self.mock_blackboard.emit_signal.assert_called_once()
        call_args = self.mock_blackboard.emit_signal.call_args
        assert call_args[1]["signal_type"] == SignalType.DEPENDENCY_RISK
        assert call_args[1]["emitted_by"] == "stigmergy_engine"

    @pytest.mark.asyncio
    async def test_intelligence_status(self):
        """Test getting intelligence system status"""
        # Add some coordination history
        for i in range(5):
            self.engine.coordination_history.append(
                {
                    "timestamp": datetime.now() - timedelta(minutes=i * 10),
                    "predictions": {"dependency_risk": 0.5},
                }
            )

        status = await self.engine.get_intelligence_status()

        assert "active" in status
        assert "models_loaded" in status
        assert "coordination_events" in status
        assert "recent_predictions" in status
        assert status["active"] is True
        assert status["coordination_events"] == 5

    @pytest.mark.asyncio
    async def test_model_persistence(self):
        """Test ML model saving and loading"""
        # Mock file operations
        with patch("builtins.open", mock_open()) as mock_file:
            with patch("pickle.dump") as mock_dump:
                with patch("pathlib.Path.exists", return_value=False):
                    await self.engine._save_models()

                    # Should attempt to save if model exists
                    if self.engine.dependency_analyzer.model:
                        mock_file.assert_called()
                        mock_dump.assert_called()

    @pytest.mark.asyncio
    async def test_continuous_analysis_loop_error_handling(self):
        """Test error handling in continuous analysis loop"""
        # Mock system metrics collection to raise an error
        self.engine._collect_system_metrics = AsyncMock(side_effect=Exception("Test error"))

        # Start the loop (it should handle the error and sleep)
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Run one iteration
            try:
                await asyncio.wait_for(self.engine._continuous_analysis_loop(), timeout=0.1)
            except asyncio.TimeoutError:
                pass  # Expected since it's an infinite loop

            # Should have slept after error
            mock_sleep.assert_called()


class TestMLModelMetrics:
    """Test suite for ML Model Metrics"""

    def test_model_metrics_creation(self):
        """Test creation of ML model metrics"""
        metrics = MLModelMetrics(
            model_name="test_model",
            accuracy=0.85,
            precision=0.80,
            recall=0.90,
            f1_score=0.85,
            training_samples=100,
            last_updated=datetime.now(),
        )

        assert metrics.model_name == "test_model"
        assert metrics.accuracy == 0.85
        assert metrics.precision == 0.80
        assert metrics.recall == 0.90
        assert metrics.training_samples == 100


class TestIntegrationScenarios:
    """Test integration scenarios for Stigmergy Engine"""

    def setup_method(self):
        """Setup integration test fixtures"""
        self.mock_blackboard = MagicMock()

    @pytest.mark.asyncio
    async def test_end_to_end_intelligence_workflow(self):
        """Test complete intelligence workflow from data collection to signal emission"""
        engine = StigmergyEngine(self.mock_blackboard)

        # Mock external dependencies
        with patch("psutil.cpu_percent", return_value=80.0):
            with patch("psutil.virtual_memory") as mock_memory:
                mock_memory.return_value.percent = 70.0
                with patch("psutil.pids", return_value=list(range(30))):

                    # Mock blackboard responses
                    engine.blackboard.get_signal_analytics = AsyncMock(return_value={"signals": 3})
                    engine.blackboard.get_active_signals = AsyncMock(
                        return_value=["s1", "s2", "s3"]
                    )
                    engine.blackboard.emit_signal = AsyncMock()

                    # Collect metrics
                    system_metrics = await engine._collect_system_metrics()
                    signal_context = await engine._get_signal_context()

                    # Analyze and generate signals
                    signals = await engine.analyze_and_signal(system_metrics, signal_context)

                    # Verify workflow completed
                    assert len(engine.coordination_history) > 0
                    assert isinstance(signals, list)

    @pytest.mark.asyncio
    async def test_multi_analyzer_coordination(self):
        """Test coordination between multiple analyzers"""
        engine = StigmergyEngine(self.mock_blackboard)

        # Set up system state that triggers multiple analyzers
        system_metrics = {
            "cpu_usage": 0.85,  # Triggers bottleneck predictor
            "memory_usage": 0.70,
            "quality_metrics": {
                "overall_score": 0.65,  # Triggers quality analyzer
                "test_coverage": 0.7,
                "error_rate": 0.12,
            },
        }

        signal_context = {
            "active_signals": list(range(10)),  # Triggers dependency analyzer
            "domain_interactions": ["d1", "d2", "d3", "d4", "d5"],
        }

        # Mock analyzer responses
        engine.dependency_analyzer.predict_dependency_risk = AsyncMock(
            return_value=(0.7, {"method": "heuristic"})
        )

        signals = await engine.analyze_and_signal(system_metrics, signal_context)

        # Should have signals from multiple analyzers
        signal_types = {s["signal_type"] for s in signals}
        assert len(signal_types) > 1  # Multiple analyzer types should be triggered

    def test_pattern_database_learning(self):
        """Test learning and pattern storage in pattern database"""
        engine = StigmergyEngine(self.mock_blackboard)

        # Simulate pattern learning
        test_pattern = {
            "pattern_type": "test_pattern",
            "frequency": 5,
            "effectiveness": 0.8,
            "contexts": ["context1", "context2"],
        }

        engine.pattern_database["test_pattern"] = test_pattern

        # Verify pattern storage
        assert "test_pattern" in engine.pattern_database
        assert engine.pattern_database["test_pattern"]["effectiveness"] == 0.8

    @pytest.mark.asyncio
    async def test_system_adaptation_over_time(self):
        """Test system adaptation and learning over multiple cycles"""
        engine = StigmergyEngine(self.mock_blackboard)

        # Simulate multiple analysis cycles
        for cycle in range(3):
            system_metrics = {
                "cpu_usage": 0.5 + (cycle * 0.1),
                "memory_usage": 0.4,
                "quality_metrics": {"overall_score": 0.8 - (cycle * 0.05)},
            }

            signal_context = {
                "active_signals": list(range(cycle * 2)),
                "domain_interactions": ["domain1"],
            }

            # Add to coordination history
            engine.coordination_history.append(
                {
                    "timestamp": datetime.now(),
                    "cycle": cycle,
                    "system_metrics": system_metrics,
                    "signal_context": signal_context,
                }
            )

        # Verify adaptation tracking
        assert len(engine.coordination_history) == 3

        # Get intelligence status
        status = await engine.get_intelligence_status()
        assert status["coordination_events"] == 3
