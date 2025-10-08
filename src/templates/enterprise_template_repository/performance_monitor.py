"""
MAESTRO Enterprise Template Repository - Performance Monitoring & Optimization
===========================================================================

Advanced performance monitoring, optimization, and analytics system for the enterprise
template repository. Provides real-time performance metrics, automated optimization,
and comprehensive analytics with predictive insights.

Features:
- Real-time performance monitoring with metrics collection
- Automated performance optimization and tuning
- Query performance analysis and optimization recommendations
- Storage tier optimization based on usage patterns
- Predictive analytics for performance forecasting
- Alert system for performance degradation
- Resource utilization tracking and optimization
- Performance benchmarking and historical analysis

Author: MAESTRO Enterprise Architecture Team
Version: 1.0
"""

import asyncio
import json
import logging
import pickle
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from statistics import mean, median, stdev
from typing import Any, Dict, List, Optional, Tuple

import asyncpg
import numpy as np
import psutil

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure"""

    timestamp: datetime
    metric_type: str
    metric_name: str
    value: float
    metadata: Dict[str, Any]
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None


@dataclass
class QueryPerformance:
    """Query performance analysis data"""

    query_hash: str
    query_text: str
    execution_time: float
    rows_examined: int
    rows_returned: int
    cpu_usage: float
    memory_usage: float
    frequency: int
    last_executed: datetime
    optimization_suggestions: List[str]


@dataclass
class StorageTierMetrics:
    """Storage tier performance metrics"""

    tier: str
    total_templates: int
    avg_access_time: float
    hit_rate: float
    storage_utilization: float
    migration_candidates: List[str]


@dataclass
class SystemResourceMetrics:
    """System resource utilization metrics"""

    cpu_usage: float
    memory_usage: float
    disk_io_read: float
    disk_io_write: float
    network_io: float
    database_connections: int
    cache_hit_rate: float


class PerformanceMonitor:
    """Enterprise performance monitoring and optimization system"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.db_pool = None
        self.metrics_buffer = deque(maxlen=10000)
        self.query_cache = {}
        self.performance_history = defaultdict(list)
        self.optimization_rules = self._load_optimization_rules()
        self.alert_thresholds = self._load_alert_thresholds()
        self.running = False

    async def initialize(self):
        """Initialize performance monitoring system"""
        try:
            self.db_pool = await asyncpg.create_pool(**self.db_config, max_size=20)
            await self._create_performance_tables()
            await self._initialize_baseline_metrics()
            logger.info("Performance monitoring system initialized")
        except Exception as e:
            logger.error(f"Failed to initialize performance monitor: {e}")
            raise

    async def _create_performance_tables(self):
        """Create performance monitoring tables"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS performance_metrics (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    metric_type VARCHAR(100) NOT NULL,
                    metric_name VARCHAR(200) NOT NULL,
                    value DECIMAL(15,4) NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    threshold_warning DECIMAL(15,4),
                    threshold_critical DECIMAL(15,4),
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS query_performance (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    query_hash VARCHAR(64) NOT NULL,
                    query_text TEXT NOT NULL,
                    execution_time DECIMAL(10,4) NOT NULL,
                    rows_examined INTEGER DEFAULT 0,
                    rows_returned INTEGER DEFAULT 0,
                    cpu_usage DECIMAL(5,2) DEFAULT 0,
                    memory_usage DECIMAL(10,2) DEFAULT 0,
                    frequency INTEGER DEFAULT 1,
                    last_executed TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    optimization_suggestions JSONB DEFAULT '[]',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    UNIQUE(query_hash)
                );

                CREATE TABLE IF NOT EXISTS storage_optimization (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    template_id UUID NOT NULL,
                    current_tier INTEGER NOT NULL,
                    recommended_tier INTEGER NOT NULL,
                    optimization_reason TEXT NOT NULL,
                    performance_impact DECIMAL(5,2) DEFAULT 0,
                    cost_impact DECIMAL(10,2) DEFAULT 0,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    applied_at TIMESTAMPTZ,
                    FOREIGN KEY (template_id) REFERENCES templates(id)
                );

                CREATE TABLE IF NOT EXISTS performance_alerts (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    alert_type VARCHAR(100) NOT NULL,
                    severity VARCHAR(20) NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
                    title VARCHAR(200) NOT NULL,
                    description TEXT NOT NULL,
                    metric_value DECIMAL(15,4) NOT NULL,
                    threshold_value DECIMAL(15,4) NOT NULL,
                    metadata JSONB DEFAULT '{}',
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    resolved_at TIMESTAMPTZ
                );

                CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp
                    ON performance_metrics(timestamp, metric_type);
                CREATE INDEX IF NOT EXISTS idx_query_performance_frequency
                    ON query_performance(frequency DESC, execution_time DESC);
                CREATE INDEX IF NOT EXISTS idx_performance_alerts_severity
                    ON performance_alerts(severity, resolved, created_at);
            """
            )

    async def _initialize_baseline_metrics(self):
        """Initialize baseline performance metrics"""
        # Get initial database statistics
        async with self.db_pool.acquire() as conn:
            # Template count baseline
            template_count = await conn.fetchval("SELECT COUNT(*) FROM templates")
            await self._record_metric("database", "template_count", template_count, {})

            # Database size baseline
            db_size = await conn.fetchval(
                """
                SELECT pg_database_size(current_database())
            """
            )
            await self._record_metric("database", "size_bytes", db_size, {})

            # Index statistics
            index_stats = await conn.fetch(
                """
                SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
            """
            )

            for stat in index_stats:
                await self._record_metric(
                    "index",
                    f"scan_count_{stat['indexname']}",
                    stat["idx_scan"] or 0,
                    {"table": stat["tablename"]},
                )

    def _load_optimization_rules(self) -> Dict[str, Any]:
        """Load performance optimization rules"""
        return {
            "query_optimization": {
                "slow_query_threshold": 1.0,  # seconds
                "high_frequency_threshold": 100,  # executions per hour
                "index_suggestions": {
                    "name_search": ["name", "language", "framework"],
                    "quality_filter": ["quality_score", "security_score"],
                    "usage_analysis": ["usage_count", "last_used"],
                },
            },
            "storage_optimization": {
                "hot_tier_criteria": {"access_frequency": 10, "quality_score": 85},  # per day
                "warm_tier_criteria": {"access_frequency": 1, "age_days": 30},  # per week
                "cold_tier_criteria": {"access_frequency": 0.1, "age_days": 90},  # per month
            },
            "resource_optimization": {
                "connection_pool_size": {"min": 5, "max": 50, "optimal_utilization": 0.7},
                "cache_size": {"min_mb": 100, "max_mb": 2048, "hit_rate_target": 0.95},
                "batch_size": {"min": 10, "max": 1000, "optimal": 100},
            },
        }

    def _load_alert_thresholds(self) -> Dict[str, Any]:
        """Load performance alert thresholds"""
        return {
            "response_time": {"warning": 0.5, "critical": 2.0},
            "cpu_usage": {"warning": 70.0, "critical": 90.0},
            "memory_usage": {"warning": 80.0, "critical": 95.0},
            "disk_usage": {"warning": 80.0, "critical": 95.0},
            "error_rate": {"warning": 0.01, "critical": 0.05},
            "database_connections": {"warning": 80, "critical": 95},
            "query_time": {"warning": 1.0, "critical": 5.0},
        }

    async def start_monitoring(self):
        """Start performance monitoring"""
        if self.running:
            return

        self.running = True
        logger.info("Starting performance monitoring")

        # Start monitoring tasks
        tasks = [
            asyncio.create_task(self._monitor_system_resources()),
            asyncio.create_task(self._monitor_database_performance()),
            asyncio.create_task(self._monitor_query_performance()),
            asyncio.create_task(self._optimize_storage_tiers()),
            asyncio.create_task(self._process_alerts()),
            asyncio.create_task(self._generate_reports()),
        ]

        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in performance monitoring: {e}")
        finally:
            self.running = False

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        self.running = False
        logger.info("Performance monitoring stopped")

    async def _monitor_system_resources(self):
        """Monitor system resource utilization"""
        while self.running:
            try:
                # CPU usage
                cpu_percent = psutil.cpu_percent(interval=1)
                await self._record_metric("system", "cpu_usage_percent", cpu_percent, {})

                # Memory usage
                memory = psutil.virtual_memory()
                await self._record_metric(
                    "system",
                    "memory_usage_percent",
                    memory.percent,
                    {
                        "total_gb": round(memory.total / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                    },
                )

                # Disk I/O
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    await self._record_metric(
                        "system", "disk_read_mb_per_sec", disk_io.read_bytes / (1024**2), {}
                    )
                    await self._record_metric(
                        "system", "disk_write_mb_per_sec", disk_io.write_bytes / (1024**2), {}
                    )

                # Network I/O
                net_io = psutil.net_io_counters()
                if net_io:
                    await self._record_metric("system", "network_bytes_sent", net_io.bytes_sent, {})
                    await self._record_metric("system", "network_bytes_recv", net_io.bytes_recv, {})

                # Check thresholds and generate alerts
                await self._check_resource_thresholds(cpu_percent, memory.percent)

                await asyncio.sleep(30)  # Monitor every 30 seconds

            except Exception as e:
                logger.error(f"Error monitoring system resources: {e}")
                await asyncio.sleep(60)

    async def _monitor_database_performance(self):
        """Monitor database performance metrics"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Connection statistics
                    conn_stats = await conn.fetch(
                        """
                        SELECT count(*) as total_connections,
                               count(*) FILTER (WHERE state = 'active') as active_connections,
                               count(*) FILTER (WHERE state = 'idle') as idle_connections
                        FROM pg_stat_activity
                        WHERE datname = current_database()
                    """
                    )

                    if conn_stats:
                        stats = conn_stats[0]
                        await self._record_metric(
                            "database", "total_connections", stats["total_connections"], {}
                        )
                        await self._record_metric(
                            "database", "active_connections", stats["active_connections"], {}
                        )
                        await self._record_metric(
                            "database", "idle_connections", stats["idle_connections"], {}
                        )

                    # Table statistics
                    table_stats = await conn.fetch(
                        """
                        SELECT schemaname, relname, n_tup_ins, n_tup_upd, n_tup_del,
                               n_tup_hot_upd, seq_scan, seq_tup_read, idx_scan, idx_tup_fetch
                        FROM pg_stat_user_tables
                        WHERE schemaname = 'public'
                    """
                    )

                    for stat in table_stats:
                        table_name = stat["relname"]
                        await self._record_metric(
                            "table", f"{table_name}_inserts", stat["n_tup_ins"] or 0, {}
                        )
                        await self._record_metric(
                            "table", f"{table_name}_updates", stat["n_tup_upd"] or 0, {}
                        )
                        await self._record_metric(
                            "table", f"{table_name}_seq_scans", stat["seq_scan"] or 0, {}
                        )
                        await self._record_metric(
                            "table", f"{table_name}_idx_scans", stat["idx_scan"] or 0, {}
                        )

                    # Database size
                    db_size = await conn.fetchval("SELECT pg_database_size(current_database())")
                    await self._record_metric("database", "size_bytes", db_size, {})

                await asyncio.sleep(60)  # Monitor every minute

            except Exception as e:
                logger.error(f"Error monitoring database performance: {e}")
                await asyncio.sleep(120)

    async def _monitor_query_performance(self):
        """Monitor and analyze query performance"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Get slow queries from pg_stat_statements if available
                    slow_queries = await conn.fetch(
                        """
                        SELECT query, calls, total_time, mean_time, max_time, rows
                        FROM pg_stat_statements
                        WHERE mean_time > $1
                        ORDER BY mean_time DESC
                        LIMIT 20
                    """,
                        self.optimization_rules["query_optimization"]["slow_query_threshold"]
                        * 1000,
                    )

                    for query_stat in slow_queries:
                        query_hash = str(hash(query_stat["query"]))

                        # Analyze and store query performance
                        await self._analyze_query_performance(
                            query_hash,
                            query_stat["query"],
                            query_stat["mean_time"] / 1000.0,  # Convert to seconds
                            query_stat["rows"] or 0,
                            query_stat["calls"] or 0,
                        )

                    # Monitor current running queries
                    active_queries = await conn.fetch(
                        """
                        SELECT pid, query, state, query_start,
                               extract(epoch from (now() - query_start)) as duration
                        FROM pg_stat_activity
                        WHERE state = 'active' AND query NOT LIKE '%pg_stat_activity%'
                    """
                    )

                    for active_query in active_queries:
                        if active_query["duration"] and active_query["duration"] > 10:
                            await self._record_metric(
                                "query",
                                "long_running_query",
                                active_query["duration"],
                                {"pid": active_query["pid"], "query": active_query["query"][:100]},
                            )

                await asyncio.sleep(120)  # Monitor every 2 minutes

            except Exception as e:
                logger.error(f"Error monitoring query performance: {e}")
                await asyncio.sleep(180)

    async def _analyze_query_performance(
        self,
        query_hash: str,
        query_text: str,
        execution_time: float,
        rows_returned: int,
        frequency: int,
    ):
        """Analyze individual query performance and generate optimization suggestions"""
        optimization_suggestions = []

        # Check if query is slow
        if execution_time > self.optimization_rules["query_optimization"]["slow_query_threshold"]:
            optimization_suggestions.append(
                "Query execution time exceeds threshold - consider adding indexes"
            )

        # Check for sequential scans
        if "seq scan" in query_text.lower():
            optimization_suggestions.append(
                "Sequential scan detected - consider adding appropriate indexes"
            )

        # Check for high frequency queries
        if frequency > self.optimization_rules["query_optimization"]["high_frequency_threshold"]:
            optimization_suggestions.append(
                "High frequency query - consider caching results or optimizing joins"
            )

        # Suggest specific indexes based on query patterns
        if "WHERE" in query_text.upper():
            for pattern, columns in self.optimization_rules["query_optimization"][
                "index_suggestions"
            ].items():
                if any(col in query_text.lower() for col in columns):
                    optimization_suggestions.append(
                        f"Consider composite index on: {', '.join(columns)}"
                    )

        # Store query performance data
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO query_performance
                (query_hash, query_text, execution_time, rows_returned, frequency,
                 last_executed, optimization_suggestions)
                VALUES ($1, $2, $3, $4, $5, NOW(), $6)
                ON CONFLICT (query_hash) DO UPDATE SET
                    execution_time = EXCLUDED.execution_time,
                    rows_returned = EXCLUDED.rows_returned,
                    frequency = query_performance.frequency + 1,
                    last_executed = NOW(),
                    optimization_suggestions = EXCLUDED.optimization_suggestions
            """,
                query_hash,
                query_text[:1000],
                execution_time,
                rows_returned,
                frequency,
                json.dumps(optimization_suggestions),
            )

    async def _optimize_storage_tiers(self):
        """Optimize template storage tier placement"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Get templates with usage statistics
                    templates = await conn.fetch(
                        """
                        SELECT t.id, t.name, t.storage_tier, t.quality_score,
                               t.created_at, COALESCE(tu.usage_count, 0) as usage_count,
                               tu.last_used,
                               extract(days from (NOW() - t.created_at)) as age_days
                        FROM templates t
                        LEFT JOIN template_usage tu ON t.id = tu.template_id
                        ORDER BY t.created_at DESC
                    """
                    )

                    for template in templates:
                        current_tier = template["storage_tier"] or 3  # Default to cold
                        recommended_tier = await self._calculate_optimal_tier(template)

                        if current_tier != recommended_tier:
                            # Record optimization recommendation
                            reason = await self._generate_tier_optimization_reason(
                                template, current_tier, recommended_tier
                            )

                            await conn.execute(
                                """
                                INSERT INTO storage_optimization
                                (template_id, current_tier, recommended_tier, optimization_reason)
                                VALUES ($1, $2, $3, $4)
                            """,
                                template["id"],
                                current_tier,
                                recommended_tier,
                                reason,
                            )

                            # Apply optimization if auto-optimization is enabled
                            if self._should_auto_optimize_tier(
                                template, current_tier, recommended_tier
                            ):
                                await self._apply_tier_optimization(
                                    template["id"], recommended_tier
                                )

                await asyncio.sleep(3600)  # Run every hour

            except Exception as e:
                logger.error(f"Error in storage tier optimization: {e}")
                await asyncio.sleep(1800)

    async def _calculate_optimal_tier(self, template: Dict) -> int:
        """Calculate optimal storage tier for template"""
        usage_count = template["usage_count"] or 0
        age_days = template["age_days"] or 0
        quality_score = template["quality_score"] or 0

        # Calculate daily usage frequency
        daily_usage = usage_count / max(age_days, 1)

        # Hot tier criteria
        if (
            daily_usage
            >= self.optimization_rules["storage_optimization"]["hot_tier_criteria"][
                "access_frequency"
            ]
            or quality_score
            >= self.optimization_rules["storage_optimization"]["hot_tier_criteria"]["quality_score"]
        ):
            return 1  # Hot tier

        # Warm tier criteria
        elif (
            daily_usage * 7
            >= self.optimization_rules["storage_optimization"]["warm_tier_criteria"][
                "access_frequency"
            ]
            and age_days
            <= self.optimization_rules["storage_optimization"]["warm_tier_criteria"]["age_days"]
        ):
            return 2  # Warm tier

        # Cold tier (default)
        else:
            return 3  # Cold tier

    async def _generate_tier_optimization_reason(
        self, template: Dict, current_tier: int, recommended_tier: int
    ) -> str:
        """Generate human-readable reason for tier optimization"""
        usage_count = template["usage_count"] or 0
        age_days = template["age_days"] or 0
        quality_score = template["quality_score"] or 0

        if recommended_tier < current_tier:
            return f"Move to higher tier: High usage ({usage_count} times), Quality score: {quality_score}"
        else:
            return f"Move to lower tier: Low usage ({usage_count} times in {age_days} days)"

    def _should_auto_optimize_tier(
        self, template: Dict, current_tier: int, recommended_tier: int
    ) -> bool:
        """Determine if tier optimization should be applied automatically"""
        # Only auto-optimize if the benefit is clear and risk is low
        quality_score = template["quality_score"] or 0

        # Auto-optimize to hot tier for high-quality templates
        if recommended_tier == 1 and quality_score >= 90:
            return True

        # Auto-optimize to cold tier for old, unused templates
        if recommended_tier == 3 and template["age_days"] > 180 and template["usage_count"] == 0:
            return True

        return False

    async def _apply_tier_optimization(self, template_id: str, new_tier: int):
        """Apply storage tier optimization"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE templates SET storage_tier = $1 WHERE id = $2
            """,
                new_tier,
                template_id,
            )

            await conn.execute(
                """
                UPDATE storage_optimization
                SET applied_at = NOW()
                WHERE template_id = $1 AND applied_at IS NULL
            """,
                template_id,
            )

        logger.info(f"Applied tier optimization: Template {template_id} moved to tier {new_tier}")

    async def _check_resource_thresholds(self, cpu_usage: float, memory_usage: float):
        """Check resource usage against thresholds and generate alerts"""
        # CPU usage alerts
        if cpu_usage >= self.alert_thresholds["cpu_usage"]["critical"]:
            await self._create_alert(
                "resource",
                "critical",
                "Critical CPU Usage",
                f"CPU usage is at {cpu_usage:.1f}%",
                cpu_usage,
                self.alert_thresholds["cpu_usage"]["critical"],
            )
        elif cpu_usage >= self.alert_thresholds["cpu_usage"]["warning"]:
            await self._create_alert(
                "resource",
                "high",
                "High CPU Usage",
                f"CPU usage is at {cpu_usage:.1f}%",
                cpu_usage,
                self.alert_thresholds["cpu_usage"]["warning"],
            )

        # Memory usage alerts
        if memory_usage >= self.alert_thresholds["memory_usage"]["critical"]:
            await self._create_alert(
                "resource",
                "critical",
                "Critical Memory Usage",
                f"Memory usage is at {memory_usage:.1f}%",
                memory_usage,
                self.alert_thresholds["memory_usage"]["critical"],
            )
        elif memory_usage >= self.alert_thresholds["memory_usage"]["warning"]:
            await self._create_alert(
                "resource",
                "high",
                "High Memory Usage",
                f"Memory usage is at {memory_usage:.1f}%",
                memory_usage,
                self.alert_thresholds["memory_usage"]["warning"],
            )

    async def _create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        description: str,
        metric_value: float,
        threshold_value: float,
        metadata: Dict = None,
    ):
        """Create performance alert"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO performance_alerts
                (alert_type, severity, title, description, metric_value, threshold_value, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                alert_type,
                severity,
                title,
                description,
                metric_value,
                threshold_value,
                json.dumps(metadata or {}),
            )

        logger.warning(f"Performance Alert [{severity.upper()}]: {title} - {description}")

    async def _process_alerts(self):
        """Process and manage performance alerts"""
        while self.running:
            try:
                async with self.db_pool.acquire() as conn:
                    # Get unresolved critical alerts
                    critical_alerts = await conn.fetch(
                        """
                        SELECT * FROM performance_alerts
                        WHERE severity = 'critical' AND resolved = FALSE
                        ORDER BY created_at DESC
                    """
                    )

                    for alert in critical_alerts:
                        # Auto-resolve alerts older than 1 hour if conditions improved
                        if alert["created_at"] < datetime.now() - timedelta(hours=1):
                            await self._check_alert_resolution(alert)

                    # Clean up old resolved alerts (older than 30 days)
                    await conn.execute(
                        """
                        DELETE FROM performance_alerts
                        WHERE resolved = TRUE AND resolved_at < NOW() - INTERVAL '30 days'
                    """
                    )

                await asyncio.sleep(300)  # Process every 5 minutes

            except Exception as e:
                logger.error(f"Error processing alerts: {e}")
                await asyncio.sleep(600)

    async def _check_alert_resolution(self, alert: Dict):
        """Check if alert conditions have been resolved"""
        alert_type = alert["alert_type"]

        if alert_type == "resource":
            # Get current resource usage
            cpu_usage = psutil.cpu_percent()
            memory_usage = psutil.virtual_memory().percent

            # Check if conditions have improved
            if (
                "CPU" in alert["title"]
                and cpu_usage < alert["threshold_value"] * 0.8
                or "Memory" in alert["title"]
                and memory_usage < alert["threshold_value"] * 0.8
            ):
                await self._resolve_alert(alert["id"])

    async def _resolve_alert(self, alert_id: str):
        """Resolve performance alert"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE performance_alerts
                SET resolved = TRUE, resolved_at = NOW()
                WHERE id = $1
            """,
                alert_id,
            )

        logger.info(f"Performance alert {alert_id} resolved")

    async def _generate_reports(self):
        """Generate performance reports"""
        while self.running:
            try:
                # Generate hourly performance summary
                await self._generate_hourly_summary()

                # Generate daily optimization report (runs once per day)
                current_hour = datetime.now().hour
                if current_hour == 2:  # Run at 2 AM
                    await self._generate_daily_optimization_report()

                await asyncio.sleep(3600)  # Generate every hour

            except Exception as e:
                logger.error(f"Error generating reports: {e}")
                await asyncio.sleep(1800)

    async def _generate_hourly_summary(self):
        """Generate hourly performance summary"""
        async with self.db_pool.acquire() as conn:
            # Calculate average metrics for the last hour
            metrics = await conn.fetch(
                """
                SELECT metric_type, metric_name,
                       AVG(value) as avg_value,
                       MIN(value) as min_value,
                       MAX(value) as max_value,
                       COUNT(*) as sample_count
                FROM performance_metrics
                WHERE timestamp >= NOW() - INTERVAL '1 hour'
                GROUP BY metric_type, metric_name
                ORDER BY metric_type, metric_name
            """
            )

            summary = {"timestamp": datetime.now().isoformat(), "period": "1_hour", "metrics": []}

            for metric in metrics:
                summary["metrics"].append(
                    {
                        "type": metric["metric_type"],
                        "name": metric["metric_name"],
                        "avg": float(metric["avg_value"]),
                        "min": float(metric["min_value"]),
                        "max": float(metric["max_value"]),
                        "samples": metric["sample_count"],
                    }
                )

            # Store summary
            await self._record_metric("summary", "hourly_performance", 0, summary)

    async def _generate_daily_optimization_report(self):
        """Generate daily optimization recommendations"""
        async with self.db_pool.acquire() as conn:
            # Get optimization opportunities
            optimization_report = {
                "date": datetime.now().date().isoformat(),
                "query_optimizations": [],
                "storage_optimizations": [],
                "resource_recommendations": [],
            }

            # Top slow queries
            slow_queries = await conn.fetch(
                """
                SELECT query_text, execution_time, frequency, optimization_suggestions
                FROM query_performance
                WHERE execution_time > 1.0
                ORDER BY execution_time * frequency DESC
                LIMIT 10
            """
            )

            for query in slow_queries:
                optimization_report["query_optimizations"].append(
                    {
                        "query": query["query_text"][:200],
                        "execution_time": float(query["execution_time"]),
                        "frequency": query["frequency"],
                        "suggestions": json.loads(query["optimization_suggestions"] or "[]"),
                    }
                )

            # Storage optimization opportunities
            storage_opts = await conn.fetch(
                """
                SELECT COUNT(*) as count, current_tier, recommended_tier, optimization_reason
                FROM storage_optimization
                WHERE applied_at IS NULL
                GROUP BY current_tier, recommended_tier, optimization_reason
                ORDER BY count DESC
                LIMIT 10
            """
            )

            for opt in storage_opts:
                optimization_report["storage_optimizations"].append(
                    {
                        "count": opt["count"],
                        "from_tier": opt["current_tier"],
                        "to_tier": opt["recommended_tier"],
                        "reason": opt["optimization_reason"],
                    }
                )

            # Store optimization report
            await self._record_metric("report", "daily_optimization", 0, optimization_report)

            logger.info(
                f"Generated daily optimization report with {len(optimization_report['query_optimizations'])} query optimizations"
            )

    async def _record_metric(
        self, metric_type: str, metric_name: str, value: float, metadata: Dict[str, Any]
    ):
        """Record performance metric"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO performance_metrics
                    (metric_type, metric_name, value, metadata)
                    VALUES ($1, $2, $3, $4)
                """,
                    metric_type,
                    metric_name,
                    value,
                    json.dumps(metadata),
                )
        except Exception as e:
            logger.error(f"Failed to record metric: {e}")

    async def get_performance_dashboard(self) -> Dict[str, Any]:
        """Get real-time performance dashboard data"""
        async with self.db_pool.acquire() as conn:
            # Current system metrics
            latest_metrics = await conn.fetch(
                """
                SELECT DISTINCT ON (metric_type, metric_name)
                       metric_type, metric_name, value, timestamp, metadata
                FROM performance_metrics
                WHERE timestamp >= NOW() - INTERVAL '5 minutes'
                ORDER BY metric_type, metric_name, timestamp DESC
            """
            )

            # Active alerts
            alerts = await conn.fetch(
                """
                SELECT alert_type, severity, title, description, created_at
                FROM performance_alerts
                WHERE resolved = FALSE
                ORDER BY
                    CASE severity
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'medium' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT 20
            """
            )

            # Top slow queries
            slow_queries = await conn.fetch(
                """
                SELECT query_text, execution_time, frequency, last_executed
                FROM query_performance
                WHERE execution_time > 0.5
                ORDER BY execution_time * frequency DESC
                LIMIT 10
            """
            )

            # Storage tier distribution
            storage_distribution = await conn.fetch(
                """
                SELECT storage_tier, COUNT(*) as count
                FROM templates
                GROUP BY storage_tier
                ORDER BY storage_tier
            """
            )

            return {
                "current_metrics": [dict(m) for m in latest_metrics],
                "active_alerts": [dict(a) for a in alerts],
                "slow_queries": [dict(q) for q in slow_queries],
                "storage_distribution": [dict(s) for s in storage_distribution],
                "system_status": await self._get_system_status(),
            }

    async def _get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage("/").percent,
            "database_connections": len(self.db_pool._queue._getters) if self.db_pool else 0,
            "uptime_seconds": time.time() - psutil.boot_time(),
            "timestamp": datetime.now().isoformat(),
        }

    async def get_optimization_recommendations(self) -> Dict[str, Any]:
        """Get comprehensive optimization recommendations"""
        async with self.db_pool.acquire() as conn:
            # Query optimizations
            query_recommendations = await conn.fetch(
                """
                SELECT query_text, execution_time, frequency, optimization_suggestions
                FROM query_performance
                WHERE optimization_suggestions != '[]'
                ORDER BY execution_time * frequency DESC
                LIMIT 20
            """
            )

            # Storage optimizations
            storage_recommendations = await conn.fetch(
                """
                SELECT template_id, current_tier, recommended_tier,
                       optimization_reason, performance_impact
                FROM storage_optimization
                WHERE applied_at IS NULL
                ORDER BY performance_impact DESC NULLS LAST
                LIMIT 20
            """
            )

            # Resource optimization analysis
            resource_analysis = await self._analyze_resource_optimization()

            return {
                "query_optimizations": [dict(q) for q in query_recommendations],
                "storage_optimizations": [dict(s) for s in storage_recommendations],
                "resource_analysis": resource_analysis,
                "generated_at": datetime.now().isoformat(),
            }

    async def _analyze_resource_optimization(self) -> Dict[str, Any]:
        """Analyze resource usage and provide optimization recommendations"""
        # Get recent resource metrics
        current_resources = await self._get_system_status()

        recommendations = []

        # CPU optimization
        if current_resources["cpu_usage"] > 70:
            recommendations.append(
                {
                    "type": "cpu",
                    "priority": "high",
                    "recommendation": "Consider scaling horizontally or optimizing query performance",
                    "current_value": current_resources["cpu_usage"],
                    "target_value": 60,
                }
            )

        # Memory optimization
        if current_resources["memory_usage"] > 80:
            recommendations.append(
                {
                    "type": "memory",
                    "priority": "high",
                    "recommendation": "Optimize caching strategy or increase memory allocation",
                    "current_value": current_resources["memory_usage"],
                    "target_value": 70,
                }
            )

        # Database connection optimization
        if current_resources["database_connections"] > 40:
            recommendations.append(
                {
                    "type": "database",
                    "priority": "medium",
                    "recommendation": "Optimize connection pooling or review long-running queries",
                    "current_value": current_resources["database_connections"],
                    "target_value": 30,
                }
            )

        return {
            "current_status": current_resources,
            "recommendations": recommendations,
            "optimization_score": max(0, 100 - len(recommendations) * 15),
        }

    async def cleanup(self):
        """Cleanup resources"""
        if self.running:
            await self.stop_monitoring()

        if self.db_pool:
            await self.db_pool.close()

        logger.info("Performance monitor cleanup completed")


# Performance monitoring utilities
class PerformanceAnalyzer:
    """Advanced performance analysis utilities"""

    @staticmethod
    def calculate_percentiles(values: List[float]) -> Dict[str, float]:
        """Calculate performance percentiles"""
        if not values:
            return {}

        sorted_values = sorted(values)
        length = len(sorted_values)

        return {
            "p50": sorted_values[int(length * 0.5)],
            "p90": sorted_values[int(length * 0.9)],
            "p95": sorted_values[int(length * 0.95)],
            "p99": sorted_values[int(length * 0.99)],
            "min": min(sorted_values),
            "max": max(sorted_values),
            "mean": mean(sorted_values),
            "median": median(sorted_values),
            "std_dev": stdev(sorted_values) if length > 1 else 0,
        }

    @staticmethod
    def detect_performance_anomalies(metrics: List[float], threshold: float = 2.0) -> List[int]:
        """Detect performance anomalies using statistical methods"""
        if len(metrics) < 10:
            return []

        mean_val = mean(metrics)
        std_val = stdev(metrics)

        anomalies = []
        for i, value in enumerate(metrics):
            z_score = abs(value - mean_val) / std_val if std_val > 0 else 0
            if z_score > threshold:
                anomalies.append(i)

        return anomalies

    @staticmethod
    def predict_performance_trend(
        metrics: List[Tuple[datetime, float]], periods_ahead: int = 10
    ) -> List[float]:
        """Simple linear regression for performance trend prediction"""
        if len(metrics) < 5:
            return []

        # Convert timestamps to hours since first measurement
        first_time = metrics[0][0]
        x_values = [(m[0] - first_time).total_seconds() / 3600 for m in metrics]
        y_values = [m[1] for m in metrics]

        # Simple linear regression
        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        sum_x2 = sum(x * x for x in x_values)

        # Calculate slope and intercept
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n

        # Predict future values
        last_x = x_values[-1]
        predictions = []
        for i in range(1, periods_ahead + 1):
            future_x = last_x + i
            predicted_y = slope * future_x + intercept
            predictions.append(max(0, predicted_y))  # Ensure non-negative

        return predictions


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        db_config = {
            "host": "localhost",
            "port": 5432,
            "database": "maestro_templates",
            "user": "postgres",
            "password": "your_password",
        }

        monitor = PerformanceMonitor(db_config)
        await monitor.initialize()

        # Start monitoring (this would run indefinitely)
        # await monitor.start_monitoring()

        # Get dashboard data
        dashboard = await monitor.get_performance_dashboard()
        print("Performance Dashboard:", json.dumps(dashboard, indent=2, default=str))

        await monitor.cleanup()

    # asyncio.run(main())
