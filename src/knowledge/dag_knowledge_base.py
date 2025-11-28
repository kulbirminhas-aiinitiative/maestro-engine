#!/usr/bin/env python3
"""
DAG Knowledge Base - Data Dictionary

Comprehensive knowledge base for AI DAG generation.
Defines all available components, templates, patterns, and best practices
that the AI agent can use when generating workflows.
"""

from typing import Dict, List
from dataclasses import dataclass

# ============================================================================
# TECHNICAL COMPONENTS DICTIONARY
# ============================================================================

TECHNICAL_COMPONENTS = {
    "authentication": {
        "name": "Authentication System",
        "description": "User authentication and authorization",
        "typical_phases": ["requirements", "design", "implementation", "testing"],
        "dependencies": ["database"],
        "tech_options": {
            "jwt": "JSON Web Tokens",
            "oauth": "OAuth 2.0",
            "saml": "SAML SSO",
            "session": "Session-based auth"
        },
        "estimated_duration": "1-2 weeks",
        "complexity": "medium"
    },

    "database": {
        "name": "Database Layer",
        "description": "Data storage and persistence",
        "typical_phases": ["design", "schema_design", "implementation", "migration"],
        "dependencies": [],
        "tech_options": {
            "postgresql": "PostgreSQL relational database",
            "mongodb": "MongoDB NoSQL database",
            "mysql": "MySQL relational database",
            "redis": "Redis in-memory cache"
        },
        "estimated_duration": "1-2 weeks",
        "complexity": "medium"
    },

    "api": {
        "name": "API Layer",
        "description": "Backend API and services",
        "typical_phases": ["design", "implementation", "documentation", "testing"],
        "dependencies": ["database"],
        "tech_options": {
            "rest": "RESTful API",
            "graphql": "GraphQL API",
            "grpc": "gRPC microservices"
        },
        "estimated_duration": "2-3 weeks",
        "complexity": "medium"
    },

    "frontend": {
        "name": "Frontend UI",
        "description": "User interface and client application",
        "typical_phases": ["design", "component_development", "integration", "testing"],
        "dependencies": ["api"],
        "tech_options": {
            "react": "React with TypeScript",
            "vue": "Vue.js framework",
            "angular": "Angular framework",
            "nextjs": "Next.js full-stack"
        },
        "estimated_duration": "3-4 weeks",
        "complexity": "medium"
    },

    "mobile": {
        "name": "Mobile Application",
        "description": "Native or cross-platform mobile apps",
        "typical_phases": ["design", "ios_development", "android_development", "testing"],
        "dependencies": ["api"],
        "tech_options": {
            "react_native": "React Native",
            "flutter": "Flutter framework",
            "native_ios": "Native iOS (Swift)",
            "native_android": "Native Android (Kotlin)"
        },
        "estimated_duration": "4-6 weeks",
        "complexity": "high",
        "parallel_opportunities": ["ios", "android"]
    },

    "realtime": {
        "name": "Real-time Communication",
        "description": "WebSocket, SSE, or real-time features",
        "typical_phases": ["design", "server_implementation", "client_implementation", "testing"],
        "dependencies": ["api", "database"],
        "tech_options": {
            "websocket": "WebSocket protocol",
            "sse": "Server-Sent Events",
            "socket_io": "Socket.IO library"
        },
        "estimated_duration": "2-3 weeks",
        "complexity": "high"
    },

    "file_storage": {
        "name": "File Storage System",
        "description": "File upload, storage, and retrieval",
        "typical_phases": ["design", "implementation", "integration", "testing"],
        "dependencies": ["api"],
        "tech_options": {
            "s3": "AWS S3",
            "gcs": "Google Cloud Storage",
            "local": "Local file system"
        },
        "estimated_duration": "1 week",
        "complexity": "low"
    },

    "payment": {
        "name": "Payment Processing",
        "description": "Billing and payment integration",
        "typical_phases": ["integration", "testing", "compliance"],
        "dependencies": ["api", "database"],
        "tech_options": {
            "stripe": "Stripe",
            "paypal": "PayPal",
            "square": "Square"
        },
        "estimated_duration": "2-3 weeks",
        "complexity": "high"
    },

    "search": {
        "name": "Search Functionality",
        "description": "Full-text search and indexing",
        "typical_phases": ["design", "implementation", "indexing", "optimization"],
        "dependencies": ["database"],
        "tech_options": {
            "elasticsearch": "Elasticsearch",
            "algolia": "Algolia",
            "postgres_fts": "PostgreSQL Full-Text Search"
        },
        "estimated_duration": "1-2 weeks",
        "complexity": "medium"
    },

    "notification": {
        "name": "Notification System",
        "description": "Email, SMS, push notifications",
        "typical_phases": ["design", "implementation", "integration", "testing"],
        "dependencies": ["api"],
        "tech_options": {
            "email": "Email (SendGrid, AWS SES)",
            "sms": "SMS (Twilio)",
            "push": "Push notifications (FCM, APNS)"
        },
        "estimated_duration": "1-2 weeks",
        "complexity": "medium"
    },

    "caching": {
        "name": "Caching Layer",
        "description": "Performance optimization through caching",
        "typical_phases": ["design", "implementation", "optimization"],
        "dependencies": ["api"],
        "tech_options": {
            "redis": "Redis",
            "memcached": "Memcached",
            "cdn": "CDN caching"
        },
        "estimated_duration": "1 week",
        "complexity": "low"
    },

    "queue": {
        "name": "Message Queue",
        "description": "Asynchronous job processing",
        "typical_phases": ["design", "implementation", "worker_setup", "monitoring"],
        "dependencies": ["api"],
        "tech_options": {
            "rabbitmq": "RabbitMQ",
            "redis_queue": "Redis Queue",
            "aws_sqs": "AWS SQS"
        },
        "estimated_duration": "1-2 weeks",
        "complexity": "medium"
    },

    "analytics": {
        "name": "Analytics & Tracking",
        "description": "User analytics and event tracking",
        "typical_phases": ["integration", "dashboard", "reporting"],
        "dependencies": ["frontend", "api"],
        "tech_options": {
            "google_analytics": "Google Analytics",
            "mixpanel": "Mixpanel",
            "amplitude": "Amplitude"
        },
        "estimated_duration": "1 week",
        "complexity": "low"
    },

    "admin_dashboard": {
        "name": "Admin Dashboard",
        "description": "Administrative interface",
        "typical_phases": ["design", "implementation", "permissions", "testing"],
        "dependencies": ["api", "authentication"],
        "tech_options": {
            "react_admin": "React Admin",
            "custom": "Custom dashboard"
        },
        "estimated_duration": "2-3 weeks",
        "complexity": "medium"
    },

    "deployment": {
        "name": "Deployment Infrastructure",
        "description": "CI/CD and cloud deployment",
        "typical_phases": ["infrastructure_setup", "ci_cd_pipeline", "deployment", "monitoring"],
        "dependencies": [],
        "tech_options": {
            "aws": "AWS (EC2, ECS, Lambda)",
            "gcp": "Google Cloud Platform",
            "azure": "Microsoft Azure",
            "docker": "Docker containers",
            "kubernetes": "Kubernetes orchestration"
        },
        "estimated_duration": "1-2 weeks",
        "complexity": "medium"
    },

    "testing": {
        "name": "Testing Infrastructure",
        "description": "Automated testing setup",
        "typical_phases": ["unit_tests", "integration_tests", "e2e_tests"],
        "dependencies": [],
        "tech_options": {
            "jest": "Jest (JavaScript)",
            "pytest": "Pytest (Python)",
            "playwright": "Playwright (E2E)"
        },
        "estimated_duration": "1-2 weeks per component",
        "complexity": "medium"
    }
}

# ============================================================================
# WORKFLOW TEMPLATES
# ============================================================================

WORKFLOW_TEMPLATES = {
    "saas_app": {
        "name": "SaaS Application",
        "description": "Multi-tenant SaaS application with subscriptions",
        "typical_components": [
            "authentication", "database", "api", "frontend",
            "payment", "admin_dashboard", "deployment"
        ],
        "required_phases": [
            "requirements", "architecture", "frontend", "backend",
            "integration", "testing", "deployment"
        ],
        "typical_duration": "8-12 weeks",
        "complexity": "complex",
        "parallel_opportunities": ["frontend", "backend"],
        "use_cases": [
            "subscription-based services",
            "multi-tenant platforms",
            "B2B applications"
        ]
    },

    "microservice_api": {
        "name": "Microservice API",
        "description": "RESTful API microservice",
        "typical_components": [
            "api", "database", "caching", "queue", "deployment"
        ],
        "required_phases": [
            "requirements", "design", "implementation", "testing", "deployment", "monitoring"
        ],
        "typical_duration": "4-6 weeks",
        "complexity": "medium",
        "parallel_opportunities": [],
        "use_cases": [
            "backend services",
            "API gateways",
            "microservice architecture"
        ]
    },

    "mobile_app": {
        "name": "Mobile Application",
        "description": "iOS and Android mobile application",
        "typical_components": [
            "mobile", "api", "database", "authentication",
            "notification", "analytics", "deployment"
        ],
        "required_phases": [
            "requirements", "design", "ios", "android", "backend_api", "testing", "deployment"
        ],
        "typical_duration": "10-16 weeks",
        "complexity": "complex",
        "parallel_opportunities": ["ios", "android", "backend_api"],
        "use_cases": [
            "consumer mobile apps",
            "cross-platform applications",
            "native mobile experiences"
        ]
    },

    "enterprise_system": {
        "name": "Enterprise System",
        "description": "Large-scale enterprise application",
        "typical_components": [
            "authentication", "database", "api", "frontend",
            "admin_dashboard", "analytics", "deployment",
            "security", "compliance", "audit_logging"
        ],
        "required_phases": [
            "requirements", "architecture", "security_design",
            "implementation", "integration", "testing",
            "compliance", "deployment"
        ],
        "typical_duration": "16-24 weeks",
        "complexity": "enterprise",
        "parallel_opportunities": ["frontend", "backend", "security"],
        "use_cases": [
            "large organizations",
            "regulated industries",
            "mission-critical systems"
        ]
    },

    "realtime_platform": {
        "name": "Real-time Platform",
        "description": "Real-time communication platform",
        "typical_components": [
            "realtime", "database", "api", "frontend",
            "file_storage", "notification", "deployment"
        ],
        "required_phases": [
            "requirements", "architecture", "backend_realtime",
            "frontend", "integration", "load_testing", "deployment"
        ],
        "typical_duration": "8-12 weeks",
        "complexity": "high",
        "parallel_opportunities": ["frontend", "backend_realtime"],
        "use_cases": [
            "chat applications",
            "collaborative tools",
            "live streaming"
        ]
    },

    "ecommerce_platform": {
        "name": "E-commerce Platform",
        "description": "Online shopping platform",
        "typical_components": [
            "frontend", "api", "database", "authentication",
            "payment", "file_storage", "search", "admin_dashboard",
            "analytics", "deployment"
        ],
        "required_phases": [
            "requirements", "architecture", "product_catalog",
            "shopping_cart", "payment_integration", "admin_panel",
            "testing", "deployment"
        ],
        "typical_duration": "12-16 weeks",
        "complexity": "complex",
        "parallel_opportunities": ["frontend", "backend", "admin_panel"],
        "use_cases": [
            "online stores",
            "marketplace platforms",
            "retail applications"
        ]
    }
}

# ============================================================================
# TECH STACK COMBINATIONS
# ============================================================================

TECH_STACK_COMBINATIONS = {
    "modern_web": {
        "name": "Modern Web Stack",
        "frontend": ["React", "TypeScript", "Next.js"],
        "backend": ["Node.js", "Express", "TypeScript"],
        "database": ["PostgreSQL", "Redis"],
        "deployment": ["Docker", "AWS"],
        "use_case": "Modern web applications"
    },

    "python_stack": {
        "name": "Python Full Stack",
        "frontend": ["React", "TypeScript"],
        "backend": ["Python", "FastAPI", "SQLAlchemy"],
        "database": ["PostgreSQL", "Redis"],
        "deployment": ["Docker", "AWS"],
        "use_case": "Python-based applications"
    },

    "mobile_stack": {
        "name": "Mobile Stack",
        "mobile": ["React Native", "TypeScript"],
        "backend": ["Node.js", "Express"],
        "database": ["PostgreSQL", "Firebase"],
        "deployment": ["AWS", "App Store", "Google Play"],
        "use_case": "Mobile applications"
    },

    "enterprise_stack": {
        "name": "Enterprise Stack",
        "frontend": ["Angular", "TypeScript"],
        "backend": ["Java", "Spring Boot"],
        "database": ["Oracle", "PostgreSQL"],
        "deployment": ["Kubernetes", "On-premise"],
        "use_case": "Enterprise applications"
    }
}

# ============================================================================
# AGENT PERSONAS
# ============================================================================

AGENT_PERSONAS = {
    "requirements_analyst": {
        "name": "Requirements Analyst",
        "skills": ["requirement gathering", "documentation", "stakeholder communication"],
        "best_for": ["research", "requirements phases"]
    },

    "solutions_architect": {
        "name": "Solutions Architect",
        "skills": ["system design", "architecture patterns", "technical planning"],
        "best_for": ["planning", "architecture phases"]
    },

    "backend_developer": {
        "name": "Backend Developer",
        "skills": ["API development", "database design", "server-side logic"],
        "best_for": ["code phases", "backend implementation"]
    },

    "frontend_developer": {
        "name": "Frontend Developer",
        "skills": ["UI development", "React/Vue/Angular", "responsive design"],
        "best_for": ["code phases", "frontend implementation"]
    },

    "fullstack_developer": {
        "name": "Full Stack Developer",
        "skills": ["frontend", "backend", "database", "deployment"],
        "best_for": ["code phases", "full-stack features"]
    },

    "mobile_developer": {
        "name": "Mobile Developer",
        "skills": ["iOS", "Android", "React Native", "mobile UX"],
        "best_for": ["code phases", "mobile development"]
    },

    "qa_engineer": {
        "name": "QA Engineer",
        "skills": ["testing", "automation", "quality assurance"],
        "best_for": ["testing phases", "quality validation"]
    },

    "devops_engineer": {
        "name": "DevOps Engineer",
        "skills": ["CI/CD", "infrastructure", "deployment", "monitoring"],
        "best_for": ["deployment phases", "infrastructure"]
    },

    "security_engineer": {
        "name": "Security Engineer",
        "skills": ["security audits", "compliance", "penetration testing"],
        "best_for": ["review phases", "security validation"]
    }
}

# ============================================================================
# BEST PRACTICES
# ============================================================================

BEST_PRACTICES = {
    "phase_ordering": {
        "always_first": ["requirements", "research"],
        "always_last": ["deployment", "monitoring"],
        "before_deployment": ["testing", "security_audit"],
        "after_architecture": ["implementation phases"]
    },

    "dependencies": {
        "frontend_needs": ["api"],
        "api_needs": ["database"],
        "testing_needs": ["implementation complete"],
        "deployment_needs": ["testing complete"]
    },

    "parallel_execution": {
        "can_parallelize": [
            ["frontend", "backend"],
            ["ios", "android"],
            ["multiple_microservices"],
            ["frontend", "backend_api", "mobile"]
        ],
        "cannot_parallelize": [
            ["requirements", "implementation"],
            ["testing", "deployment"]
        ]
    },

    "complexity_indicators": {
        "simple": ["< 5 phases", "single tech stack", "no integrations"],
        "medium": ["5-8 phases", "modern stack", "few integrations"],
        "complex": ["8-12 phases", "multiple platforms", "several integrations"],
        "enterprise": ["> 12 phases", "compliance required", "high security", "scalability"]
    }
}

# ============================================================================
# VALIDATION RULES
# ============================================================================

VALIDATION_RULES = {
    "required_phase_types": ["research", "testing", "deployment"],
    "min_phases": 3,
    "max_phases": 20,
    "max_dependencies_per_phase": 5,
    "max_chain_length": 10
}


def get_knowledge_summary() -> str:
    """Get a summary of the knowledge base"""
    return f"""
DAG Knowledge Base Summary:
- Technical Components: {len(TECHNICAL_COMPONENTS)}
- Workflow Templates: {len(WORKFLOW_TEMPLATES)}
- Tech Stack Combinations: {len(TECH_STACK_COMBINATIONS)}
- Agent Personas: {len(AGENT_PERSONAS)}
- Best Practices: {len(BEST_PRACTICES)} categories
- Validation Rules: {len(VALIDATION_RULES)} rules
"""


if __name__ == "__main__":
    print(get_knowledge_summary())
    print("\nTechnical Components:")
    for comp_id, comp_data in TECHNICAL_COMPONENTS.items():
        print(f"  - {comp_id}: {comp_data['name']} ({comp_data['complexity']})")

    print("\nWorkflow Templates:")
    for template_id, template_data in WORKFLOW_TEMPLATES.items():
        print(f"  - {template_id}: {template_data['name']} ({template_data['complexity']})")
