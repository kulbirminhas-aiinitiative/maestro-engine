"""
MAESTRO Enterprise Template Repository - Governance Dashboard
Version: 1.0
Purpose: Real-time governance dashboards with compliance monitoring and analytics
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from rbac_security import RBACSecurityManager
from template_manager import EnterpriseTemplateRepository
from workflow_engine import EnterpriseWorkflowEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of governance metrics"""

    QUALITY = "quality"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    PERFORMANCE = "performance"
    USAGE = "usage"
    WORKFLOW = "workflow"


class AlertLevel(Enum):
    """Alert severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class GovernanceMetric:
    """Individual governance metric"""

    metric_id: str
    name: str
    description: str
    metric_type: MetricType
    current_value: float
    target_value: float
    threshold_warning: float
    threshold_critical: float
    unit: str
    trend: str  # "up", "down", "stable"
    last_updated: datetime
    historical_data: List[Dict[str, Any]]


@dataclass
class ComplianceRule:
    """Compliance rule definition"""

    rule_id: str
    name: str
    description: str
    requirement: str
    evaluation_query: str
    compliance_threshold: float
    is_active: bool = True
    severity: AlertLevel = AlertLevel.WARNING


@dataclass
class GovernanceAlert:
    """Governance alert"""

    alert_id: str
    title: str
    description: str
    alert_level: AlertLevel
    metric_id: str
    current_value: float
    threshold_value: float
    created_at: datetime
    resolved_at: Optional[datetime] = None
    assigned_to: Optional[str] = None


class GovernanceDashboard:
    """
    Enterprise Governance Dashboard

    Features:
    - Real-time compliance monitoring
    - Quality metrics tracking
    - Security dashboard integration
    - Workflow performance analytics
    - Template usage analytics
    - SLA monitoring
    - Alert management
    - Compliance reporting
    """

    def __init__(
        self,
        repository: EnterpriseTemplateRepository,
        workflow_engine: EnterpriseWorkflowEngine,
        security_manager: RBACSecurityManager,
    ):
        self.repository = repository
        self.workflow_engine = workflow_engine
        self.security_manager = security_manager

        # In-memory stores (would be database-backed in production)
        self.metrics: Dict[str, GovernanceMetric] = {}
        self.compliance_rules: Dict[str, ComplianceRule] = {}
        self.alerts: Dict[str, GovernanceAlert] = {}

        # Initialize default compliance rules and metrics
        self._initialize_compliance_rules()
        self._initialize_governance_metrics()

    def _initialize_compliance_rules(self):
        """Initialize default compliance rules"""

        # Template quality compliance
        quality_rule = ComplianceRule(
            rule_id="template_quality_standard",
            name="Template Quality Standard",
            description="All approved templates must meet minimum quality threshold",
            requirement="Quality score >= 80 for all approved templates",
            evaluation_query="SELECT AVG(quality_score) FROM templates WHERE status = 'approved'",
            compliance_threshold=80.0,
            severity=AlertLevel.ERROR,
        )

        # Security compliance
        security_rule = ComplianceRule(
            rule_id="security_vulnerability_check",
            name="Security Vulnerability Check",
            description="No high/critical security vulnerabilities in approved templates",
            requirement="Security score >= 90 for all approved templates",
            evaluation_query="SELECT AVG(security_score) FROM templates WHERE status = 'approved'",
            compliance_threshold=90.0,
            severity=AlertLevel.CRITICAL,
        )

        # Approval workflow compliance
        workflow_rule = ComplianceRule(
            rule_id="approval_workflow_compliance",
            name="Approval Workflow Compliance",
            description="All templates must go through proper approval workflow",
            requirement="100% of templates have approval workflow completion",
            evaluation_query="SELECT workflow_compliance_rate FROM workflow_metrics",
            compliance_threshold=95.0,
            severity=AlertLevel.WARNING,
        )

        # Documentation compliance
        documentation_rule = ComplianceRule(
            rule_id="documentation_completeness",
            name="Documentation Completeness",
            description="All templates must have complete documentation",
            requirement="All templates have description, usage examples, and test coverage",
            evaluation_query="SELECT documentation_completeness_rate FROM documentation_metrics",
            compliance_threshold=90.0,
            severity=AlertLevel.WARNING,
        )

        self.compliance_rules = {
            "template_quality_standard": quality_rule,
            "security_vulnerability_check": security_rule,
            "approval_workflow_compliance": workflow_rule,
            "documentation_completeness": documentation_rule,
        }

    def _initialize_governance_metrics(self):
        """Initialize governance metrics tracking"""

        # Quality metrics
        quality_score_metric = GovernanceMetric(
            metric_id="average_quality_score",
            name="Average Template Quality Score",
            description="Average quality score across all approved templates",
            metric_type=MetricType.QUALITY,
            current_value=0.0,
            target_value=85.0,
            threshold_warning=80.0,
            threshold_critical=75.0,
            unit="score",
            trend="stable",
            last_updated=datetime.now(),
            historical_data=[],
        )

        # Security metrics
        security_score_metric = GovernanceMetric(
            metric_id="average_security_score",
            name="Average Security Score",
            description="Average security score across all approved templates",
            metric_type=MetricType.SECURITY,
            current_value=0.0,
            target_value=95.0,
            threshold_warning=85.0,
            threshold_critical=80.0,
            unit="score",
            trend="stable",
            last_updated=datetime.now(),
            historical_data=[],
        )

        # Usage metrics
        template_usage_metric = GovernanceMetric(
            metric_id="template_usage_rate",
            name="Template Usage Rate",
            description="Rate of template usage across the platform",
            metric_type=MetricType.USAGE,
            current_value=0.0,
            target_value=75.0,
            threshold_warning=50.0,
            threshold_critical=30.0,
            unit="percentage",
            trend="stable",
            last_updated=datetime.now(),
            historical_data=[],
        )

        # Workflow metrics
        sla_compliance_metric = GovernanceMetric(
            metric_id="sla_compliance_rate",
            name="SLA Compliance Rate",
            description="Percentage of workflows completed within SLA",
            metric_type=MetricType.WORKFLOW,
            current_value=0.0,
            target_value=95.0,
            threshold_warning=85.0,
            threshold_critical=75.0,
            unit="percentage",
            trend="stable",
            last_updated=datetime.now(),
            historical_data=[],
        )

        self.metrics = {
            "average_quality_score": quality_score_metric,
            "average_security_score": security_score_metric,
            "template_usage_rate": template_usage_metric,
            "sla_compliance_rate": sla_compliance_metric,
        }

    async def get_governance_overview(self) -> Dict[str, Any]:
        """Get comprehensive governance overview"""
        try:
            # Update all metrics
            await self._update_all_metrics()

            # Calculate overall governance score
            governance_score = await self._calculate_governance_score()

            # Get compliance status
            compliance_status = await self._get_compliance_status()

            # Get recent alerts
            recent_alerts = await self._get_recent_alerts(hours_back=24)

            # Get key statistics
            stats = await self._get_key_statistics()

            overview = {
                "governance_score": governance_score,
                "compliance_status": compliance_status,
                "key_metrics": {
                    metric_id: {
                        "name": metric.name,
                        "current_value": metric.current_value,
                        "target_value": metric.target_value,
                        "unit": metric.unit,
                        "trend": metric.trend,
                        "status": self._get_metric_status(metric),
                    }
                    for metric_id, metric in self.metrics.items()
                },
                "recent_alerts": recent_alerts,
                "statistics": stats,
                "generated_at": datetime.now().isoformat(),
            }

            return overview

        except Exception as e:
            logger.error(f"❌ Failed to get governance overview: {e}")
            return {}

    async def get_quality_dashboard(self) -> Dict[str, Any]:
        """Get quality-focused dashboard"""
        try:
            # Quality metrics from repository
            async with self.repository.db_pool.acquire() as conn:
                # Quality distribution
                quality_distribution = await conn.fetch(
                    """
                    SELECT
                        CASE
                            WHEN quality_score >= 90 THEN 'Excellent (90+)'
                            WHEN quality_score >= 80 THEN 'Good (80-89)'
                            WHEN quality_score >= 70 THEN 'Fair (70-79)'
                            ELSE 'Poor (<70)'
                        END as quality_range,
                        COUNT(*) as count
                    FROM templates
                    WHERE status = 'approved'
                    GROUP BY quality_range
                    ORDER BY MIN(quality_score) DESC
                """
                )

                # Top quality templates
                top_templates = await conn.fetch(
                    """
                    SELECT name, category, language, quality_score, usage_count
                    FROM templates
                    WHERE status = 'approved'
                    ORDER BY quality_score DESC, usage_count DESC
                    LIMIT 10
                """
                )

                # Quality trends over time (simplified)
                quality_trend = await conn.fetch(
                    """
                    SELECT
                        DATE(created_at) as date,
                        AVG(quality_score) as avg_quality
                    FROM templates
                    WHERE status = 'approved'
                        AND created_at > CURRENT_DATE - INTERVAL '30 days'
                    GROUP BY DATE(created_at)
                    ORDER BY date DESC
                    LIMIT 30
                """
                )

            # Quality issues analysis
            quality_issues = await self._analyze_quality_issues()

            dashboard = {
                "quality_overview": {
                    "average_score": self.metrics["average_quality_score"].current_value,
                    "target_score": self.metrics["average_quality_score"].target_value,
                    "trend": self.metrics["average_quality_score"].trend,
                },
                "quality_distribution": [
                    {"range": row["quality_range"], "count": row["count"]}
                    for row in quality_distribution
                ],
                "top_quality_templates": [
                    {
                        "name": row["name"],
                        "category": row["category"],
                        "language": row["language"],
                        "quality_score": float(row["quality_score"]),
                        "usage_count": row["usage_count"],
                    }
                    for row in top_templates
                ],
                "quality_trend": [
                    {"date": row["date"].isoformat(), "avg_quality": float(row["avg_quality"])}
                    for row in quality_trend
                ],
                "quality_issues": quality_issues,
                "generated_at": datetime.now().isoformat(),
            }

            return dashboard

        except Exception as e:
            logger.error(f"❌ Failed to get quality dashboard: {e}")
            return {}

    async def get_security_dashboard(self) -> Dict[str, Any]:
        """Get security-focused dashboard"""
        try:
            # Get security metrics from RBAC manager
            security_metrics = await self.security_manager.get_security_metrics()

            # Security audit log
            security_audit = await self.security_manager.get_security_audit_log(
                hours_back=24, limit=50
            )

            # Template security analysis
            async with self.repository.db_pool.acquire() as conn:
                security_analysis = await conn.fetchrow(
                    """
                    SELECT
                        AVG(security_score) as avg_security_score,
                        COUNT(CASE WHEN security_score >= 95 THEN 1 END) as high_security_count,
                        COUNT(CASE WHEN security_score < 80 THEN 1 END) as low_security_count,
                        COUNT(*) as total_templates
                    FROM templates
                    WHERE status = 'approved'
                """
                )

            # Recent security events
            security_events = [
                event
                for event in security_audit
                if event.get("event_type")
                in ["login_failed", "permission_denied", "security_violation"]
            ][:10]

            dashboard = {
                "security_overview": {
                    "average_security_score": float(security_analysis["avg_security_score"] or 0),
                    "high_security_templates": security_analysis["high_security_count"],
                    "security_violations": len(security_events),
                    "total_templates": security_analysis["total_templates"],
                },
                "user_security": security_metrics.get("user_metrics", {}),
                "authentication_metrics": security_metrics.get("security_metrics", {}),
                "recent_security_events": security_events,
                "security_alerts": [
                    alert
                    for alert in self.alerts.values()
                    if alert.alert_level in [AlertLevel.ERROR, AlertLevel.CRITICAL]
                    and not alert.resolved_at
                ],
                "generated_at": datetime.now().isoformat(),
            }

            return dashboard

        except Exception as e:
            logger.error(f"❌ Failed to get security dashboard: {e}")
            return {}

    async def get_workflow_dashboard(self) -> Dict[str, Any]:
        """Get workflow performance dashboard"""
        try:
            # Get workflow metrics
            workflow_metrics = await self.workflow_engine.get_governance_metrics()

            # Calculate additional workflow insights
            async with self.repository.db_pool.acquire() as conn:
                # Template status distribution
                status_distribution = await conn.fetch(
                    """
                    SELECT status, COUNT(*) as count
                    FROM templates
                    GROUP BY status
                """
                )

                # Recent template activity
                recent_activity = await conn.fetch(
                    """
                    SELECT
                        t.name,
                        t.status,
                        t.created_at,
                        t.updated_at,
                        t.created_by
                    FROM templates t
                    ORDER BY t.updated_at DESC
                    LIMIT 20
                """
                )

            # Workflow bottlenecks analysis
            bottlenecks = await self._analyze_workflow_bottlenecks()

            dashboard = {
                "workflow_overview": workflow_metrics.get("workflow_metrics", {}),
                "sla_performance": workflow_metrics.get("sla_metrics", {}),
                "task_metrics": workflow_metrics.get("task_metrics", {}),
                "template_status_distribution": [
                    {"status": row["status"], "count": row["count"]} for row in status_distribution
                ],
                "recent_activity": [
                    {
                        "template_name": row["name"],
                        "status": row["status"],
                        "created_at": row["created_at"].isoformat(),
                        "updated_at": row["updated_at"].isoformat(),
                        "created_by": row["created_by"],
                    }
                    for row in recent_activity
                ],
                "workflow_bottlenecks": bottlenecks,
                "generated_at": datetime.now().isoformat(),
            }

            return dashboard

        except Exception as e:
            logger.error(f"❌ Failed to get workflow dashboard: {e}")
            return {}

    async def get_compliance_report(self, report_type: str = "summary") -> Dict[str, Any]:
        """Generate compliance report"""
        try:
            # Evaluate all compliance rules
            compliance_results = {}
            overall_compliance_score = 0.0

            for rule_id, rule in self.compliance_rules.items():
                result = await self._evaluate_compliance_rule(rule)
                compliance_results[rule_id] = result
                overall_compliance_score += result["compliance_percentage"]

            overall_compliance_score /= len(self.compliance_rules) if self.compliance_rules else 1

            # Get compliance trends
            compliance_trends = await self._get_compliance_trends(days_back=30)

            # Generate recommendations
            recommendations = await self._generate_compliance_recommendations(compliance_results)

            report = {
                "report_type": report_type,
                "overall_compliance_score": round(overall_compliance_score, 2),
                "compliance_status": (
                    "compliant" if overall_compliance_score >= 80 else "non_compliant"
                ),
                "rule_evaluations": compliance_results,
                "compliance_trends": compliance_trends,
                "recommendations": recommendations,
                "generated_at": datetime.now().isoformat(),
                "reporting_period": {
                    "start_date": (datetime.now() - timedelta(days=30)).isoformat(),
                    "end_date": datetime.now().isoformat(),
                },
            }

            return report

        except Exception as e:
            logger.error(f"❌ Failed to generate compliance report: {e}")
            return {}

    async def create_alert(
        self,
        title: str,
        description: str,
        alert_level: AlertLevel,
        metric_id: str,
        current_value: float,
        threshold_value: float,
    ) -> str:
        """Create governance alert"""
        try:
            alert_id = f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.alerts)}"

            alert = GovernanceAlert(
                alert_id=alert_id,
                title=title,
                description=description,
                alert_level=alert_level,
                metric_id=metric_id,
                current_value=current_value,
                threshold_value=threshold_value,
                created_at=datetime.now(),
            )

            self.alerts[alert_id] = alert

            # Log alert creation
            logger.warning(f"🚨 Governance Alert: {title} ({alert_level.value.upper()})")

            return alert_id

        except Exception as e:
            logger.error(f"❌ Failed to create alert: {e}")
            raise

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get system performance metrics"""
        try:
            # Repository performance
            async with self.repository.db_pool.acquire() as conn:
                # Database performance metrics
                db_stats = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_templates,
                        COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_templates,
                        AVG(usage_count) as avg_usage,
                        MAX(created_at) as last_template_created
                    FROM templates
                """
                )

                # Query performance simulation (would use actual metrics)
                query_performance = {
                    "avg_query_time_ms": 45.2,
                    "p95_query_time_ms": 120.5,
                    "queries_per_second": 150.8,
                    "cache_hit_rate": 85.3,
                }

            # System resource usage (would integrate with monitoring systems)
            resource_usage = {
                "cpu_usage_percent": 35.2,
                "memory_usage_percent": 42.8,
                "disk_usage_percent": 28.5,
                "network_throughput_mbps": 125.6,
            }

            metrics = {
                "repository_metrics": {
                    "total_templates": db_stats["total_templates"],
                    "approved_templates": db_stats["approved_templates"],
                    "average_usage": float(db_stats["avg_usage"] or 0),
                    "last_activity": db_stats["last_template_created"].isoformat(),
                },
                "query_performance": query_performance,
                "resource_usage": resource_usage,
                "api_performance": {
                    "requests_per_minute": 450,
                    "avg_response_time_ms": 85,
                    "error_rate_percent": 0.2,
                },
                "generated_at": datetime.now().isoformat(),
            }

            return metrics

        except Exception as e:
            logger.error(f"❌ Failed to get performance metrics: {e}")
            return {}

    async def _update_all_metrics(self):
        """Update all governance metrics with current values"""
        try:
            # Update quality score metric
            async with self.repository.db_pool.acquire() as conn:
                quality_result = await conn.fetchrow(
                    "SELECT AVG(quality_score) as avg_score FROM templates WHERE status = 'approved'"
                )
                if quality_result and quality_result["avg_score"]:
                    await self._update_metric(
                        "average_quality_score", float(quality_result["avg_score"])
                    )

                # Update security score metric
                security_result = await conn.fetchrow(
                    "SELECT AVG(security_score) as avg_score FROM templates WHERE status = 'approved'"
                )
                if security_result and security_result["avg_score"]:
                    await self._update_metric(
                        "average_security_score", float(security_result["avg_score"])
                    )

                # Update usage rate metric
                usage_result = await conn.fetchrow(
                    "SELECT AVG(usage_count) as avg_usage FROM templates WHERE status = 'approved'"
                )
                if usage_result and usage_result["avg_usage"]:
                    # Convert to percentage (simplified)
                    usage_rate = min(100.0, float(usage_result["avg_usage"]) * 5)
                    await self._update_metric("template_usage_rate", usage_rate)

            # Update workflow SLA compliance
            workflow_metrics = await self.workflow_engine.get_governance_metrics()
            sla_compliance = workflow_metrics.get("sla_metrics", {}).get("compliance_rate", 0)
            await self._update_metric("sla_compliance_rate", sla_compliance)

        except Exception as e:
            logger.error(f"❌ Failed to update metrics: {e}")

    async def _update_metric(self, metric_id: str, new_value: float):
        """Update individual metric and check thresholds"""
        metric = self.metrics.get(metric_id)
        if not metric:
            return

        old_value = metric.current_value
        metric.current_value = new_value
        metric.last_updated = datetime.now()

        # Add to historical data
        metric.historical_data.append({"timestamp": datetime.now().isoformat(), "value": new_value})

        # Keep only last 30 days of data
        cutoff_date = datetime.now() - timedelta(days=30)
        metric.historical_data = [
            entry
            for entry in metric.historical_data
            if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
        ]

        # Calculate trend
        if len(metric.historical_data) >= 2:
            recent_values = [entry["value"] for entry in metric.historical_data[-5:]]
            if len(recent_values) >= 2:
                if recent_values[-1] > recent_values[0] * 1.05:
                    metric.trend = "up"
                elif recent_values[-1] < recent_values[0] * 0.95:
                    metric.trend = "down"
                else:
                    metric.trend = "stable"

        # Check thresholds and create alerts
        await self._check_metric_thresholds(metric)

    async def _check_metric_thresholds(self, metric: GovernanceMetric):
        """Check metric thresholds and create alerts if needed"""
        try:
            if metric.current_value <= metric.threshold_critical:
                await self.create_alert(
                    f"Critical: {metric.name}",
                    f"{metric.name} has fallen below critical threshold. Current: {metric.current_value} {metric.unit}, Threshold: {metric.threshold_critical} {metric.unit}",
                    AlertLevel.CRITICAL,
                    metric.metric_id,
                    metric.current_value,
                    metric.threshold_critical,
                )
            elif metric.current_value <= metric.threshold_warning:
                await self.create_alert(
                    f"Warning: {metric.name}",
                    f"{metric.name} has fallen below warning threshold. Current: {metric.current_value} {metric.unit}, Threshold: {metric.threshold_warning} {metric.unit}",
                    AlertLevel.WARNING,
                    metric.metric_id,
                    metric.current_value,
                    metric.threshold_warning,
                )

        except Exception as e:
            logger.error(f"❌ Failed to check metric thresholds: {e}")

    async def _calculate_governance_score(self) -> float:
        """Calculate overall governance score"""
        try:
            scores = []

            for metric in self.metrics.values():
                if metric.target_value > 0:
                    # Calculate percentage of target achieved
                    percentage = (metric.current_value / metric.target_value) * 100
                    # Cap at 100%
                    percentage = min(100, percentage)
                    scores.append(percentage)

            return round(sum(scores) / len(scores) if scores else 0, 2)

        except Exception as e:
            logger.error(f"❌ Failed to calculate governance score: {e}")
            return 0.0

    async def _get_compliance_status(self) -> Dict[str, Any]:
        """Get overall compliance status"""
        compliant_rules = 0
        total_rules = len(self.compliance_rules)

        for rule in self.compliance_rules.values():
            if rule.is_active:
                # Simplified compliance check
                compliant_rules += 1  # Would evaluate actual rule

        compliance_rate = (compliant_rules / total_rules * 100) if total_rules > 0 else 0

        return {
            "overall_status": "compliant" if compliance_rate >= 80 else "non_compliant",
            "compliance_rate": round(compliance_rate, 2),
            "compliant_rules": compliant_rules,
            "total_rules": total_rules,
            "non_compliant_rules": total_rules - compliant_rules,
        }

    async def _get_recent_alerts(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Get recent alerts"""
        cutoff_time = datetime.now() - timedelta(hours=hours_back)

        recent_alerts = [
            {
                "alert_id": alert.alert_id,
                "title": alert.title,
                "description": alert.description,
                "alert_level": alert.alert_level.value,
                "created_at": alert.created_at.isoformat(),
                "resolved": alert.resolved_at is not None,
            }
            for alert in self.alerts.values()
            if alert.created_at > cutoff_time
        ]

        return sorted(recent_alerts, key=lambda x: x["created_at"], reverse=True)

    async def _get_key_statistics(self) -> Dict[str, Any]:
        """Get key governance statistics"""
        try:
            async with self.repository.db_pool.acquire() as conn:
                stats = await conn.fetchrow(
                    """
                    SELECT
                        COUNT(*) as total_templates,
                        COUNT(CASE WHEN status = 'approved' THEN 1 END) as approved_templates,
                        COUNT(CASE WHEN quality_score >= 90 THEN 1 END) as high_quality_templates,
                        COUNT(CASE WHEN security_score >= 95 THEN 1 END) as high_security_templates,
                        SUM(usage_count) as total_usage
                    FROM templates
                """
                )

            return {
                "total_templates": stats["total_templates"],
                "approved_templates": stats["approved_templates"],
                "high_quality_templates": stats["high_quality_templates"],
                "high_security_templates": stats["high_security_templates"],
                "total_template_usage": stats["total_usage"] or 0,
                "active_alerts": len([a for a in self.alerts.values() if not a.resolved_at]),
            }

        except Exception as e:
            logger.error(f"❌ Failed to get key statistics: {e}")
            return {}

    def _get_metric_status(self, metric: GovernanceMetric) -> str:
        """Get metric status based on current value and thresholds"""
        if metric.current_value <= metric.threshold_critical:
            return "critical"
        elif metric.current_value <= metric.threshold_warning:
            return "warning"
        elif metric.current_value >= metric.target_value:
            return "excellent"
        else:
            return "good"

    async def _analyze_quality_issues(self) -> List[Dict[str, Any]]:
        """Analyze quality issues across templates"""
        try:
            async with self.repository.db_pool.acquire() as conn:
                # Find templates with quality issues
                quality_issues = await conn.fetch(
                    """
                    SELECT name, category, language, quality_score, security_score
                    FROM templates
                    WHERE status = 'approved'
                        AND (quality_score < 80 OR security_score < 85)
                    ORDER BY quality_score ASC, security_score ASC
                    LIMIT 10
                """
                )

            issues = []
            for row in quality_issues:
                issue = {
                    "template_name": row["name"],
                    "category": row["category"],
                    "language": row["language"],
                    "quality_score": float(row["quality_score"]),
                    "security_score": row["security_score"],
                    "issue_type": [],
                }

                if row["quality_score"] < 80:
                    issue["issue_type"].append("Low Quality Score")
                if row["security_score"] < 85:
                    issue["issue_type"].append("Security Concerns")

                issues.append(issue)

            return issues

        except Exception as e:
            logger.error(f"❌ Failed to analyze quality issues: {e}")
            return []

    async def _analyze_workflow_bottlenecks(self) -> List[Dict[str, Any]]:
        """Analyze workflow bottlenecks"""
        # Simplified implementation - would integrate with actual workflow data
        bottlenecks = [
            {
                "step_name": "Security Review",
                "average_time_hours": 18.5,
                "bottleneck_score": 8.5,
                "recommendations": ["Add more security reviewers", "Automate security checks"],
            },
            {
                "step_name": "Team Lead Approval",
                "average_time_hours": 12.2,
                "bottleneck_score": 6.8,
                "recommendations": ["Set clear approval criteria", "Implement auto-escalation"],
            },
        ]

        return bottlenecks

    async def _evaluate_compliance_rule(self, rule: ComplianceRule) -> Dict[str, Any]:
        """Evaluate individual compliance rule"""
        try:
            # Simplified evaluation - would execute actual query
            compliance_percentage = 85.0  # Mock value

            return {
                "rule_id": rule.rule_id,
                "rule_name": rule.name,
                "compliance_percentage": compliance_percentage,
                "threshold": rule.compliance_threshold,
                "status": (
                    "compliant"
                    if compliance_percentage >= rule.compliance_threshold
                    else "non_compliant"
                ),
                "severity": rule.severity.value,
                "last_evaluated": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Failed to evaluate compliance rule: {e}")
            return {}

    async def _get_compliance_trends(self, days_back: int = 30) -> List[Dict[str, Any]]:
        """Get compliance trends over time"""
        # Simplified implementation - would use actual historical data
        trends = []
        for i in range(days_back):
            date = datetime.now() - timedelta(days=i)
            trends.append(
                {
                    "date": date.isoformat(),
                    "compliance_score": 85 + (i % 10),  # Mock trending data
                    "total_templates": 100 + i,
                    "compliant_templates": 80 + i,
                }
            )

        return trends[::-1]  # Chronological order

    async def _generate_compliance_recommendations(
        self, compliance_results: Dict[str, Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate compliance recommendations"""
        recommendations = []

        for rule_id, result in compliance_results.items():
            if result.get("status") == "non_compliant":
                rule = self.compliance_rules.get(rule_id)
                if rule:
                    recommendations.append(
                        {
                            "priority": (
                                "high"
                                if result.get("severity") in ["error", "critical"]
                                else "medium"
                            ),
                            "title": f"Improve {rule.name}",
                            "description": f"Current compliance: {result.get('compliance_percentage', 0):.1f}%, Target: {rule.compliance_threshold:.1f}%",
                            "suggested_actions": [
                                "Review templates below threshold",
                                "Implement additional quality gates",
                                "Provide training to development teams",
                            ],
                        }
                    )

        return recommendations


# Example usage and testing
async def main():
    """Example usage of the governance dashboard"""

    # Initialize components
    repository = EnterpriseTemplateRepository()
    await repository.initialize()

    from rbac_security import RBACSecurityManager
    from workflow_engine import EnterpriseWorkflowEngine

    workflow_engine = EnterpriseWorkflowEngine(repository)
    security_manager = RBACSecurityManager(repository)

    dashboard = GovernanceDashboard(repository, workflow_engine, security_manager)

    # Get governance overview
    overview = await dashboard.get_governance_overview()
    print(f"📊 Governance Score: {overview.get('governance_score', 0)}%")

    # Get quality dashboard
    quality_dashboard = await dashboard.get_quality_dashboard()
    print(f"📈 Quality Overview: {quality_dashboard.get('quality_overview', {})}")

    # Get security dashboard
    security_dashboard = await dashboard.get_security_dashboard()
    print(f"🔒 Security Overview: {security_dashboard.get('security_overview', {})}")

    # Get workflow dashboard
    workflow_dashboard = await dashboard.get_workflow_dashboard()
    print(f"⚡ Workflow Overview: {workflow_dashboard.get('workflow_overview', {})}")

    # Generate compliance report
    compliance_report = await dashboard.get_compliance_report()
    print(f"📋 Compliance Score: {compliance_report.get('overall_compliance_score', 0)}%")

    # Get performance metrics
    performance_metrics = await dashboard.get_performance_metrics()
    print(f"🚀 Performance Metrics: {performance_metrics.get('api_performance', {})}")

    await repository.close()


if __name__ == "__main__":
    asyncio.run(main())
