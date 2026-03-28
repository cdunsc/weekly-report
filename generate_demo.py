#!/usr/bin/env python3
"""Gera dashboard com dados de demonstração para validação visual."""

import sys
sys.path.insert(0, "/opt/weekly-report")

from report.generator import ReportGenerator

config = {
    "dashboard": {
        "output_dir": "/var/www/html/dashboard",
        "base_url": "http://localhost/dashboard",
    }
}

otrs_data = {
    "period": {"start": "2026-03-06", "end": "2026-03-12"},
    "opened": 18,
    "closed": 14,
    "backlog": 7,
    "avg_first_response_hours": 6.3,
    "avg_resolution_hours": 42.5,
    "sla_first_response_met": True,
    "sla_resolution_met": True,
    "first_response_target": 24,
    "resolution_target": 72,
    "tickets": [],
}

cloud_costs = [
    {
        "provider": "AWS",
        "period": {"start": "2026-03-01", "end": "2026-03-14"},
        "currency": "USD",
        "total_cost": 12483.57,
        "accounts": [
            {"account_id": "111111111111", "account_name": "Produção", "cost": 8241.30},
            {"account_id": "222222222222", "account_name": "Homologação", "cost": 2891.12},
            {"account_id": "333333333333", "account_name": "Desenvolvimento", "cost": 1351.15},
        ],
        "top_services": [
            {"service": "Amazon EC2", "cost": 5420.10},
            {"service": "Amazon RDS", "cost": 3100.50},
            {"service": "Amazon S3", "cost": 1280.00},
            {"service": "AWS Lambda", "cost": 890.20},
            {"service": "Amazon CloudFront", "cost": 650.00},
        ],
    },
    {
        "provider": "OCI",
        "period": {"start": "2026-03-01", "end": "2026-03-14"},
        "currency": "USD",
        "total_cost": 4320.80,
        "top_services": [
            {"service": "Compute", "cost": 2100.50},
            {"service": "Block Storage", "cost": 980.30},
            {"service": "Networking", "cost": 640.00},
            {"service": "Database", "cost": 600.00},
        ],
    },
    {
        "provider": "Golden Cloud",
        "period": {"start": "2026-03-01", "end": "2026-03-14"},
        "currency": "BRL",
        "total_cost": 8500.00,
        "details": [
            {"item": "Compute", "cost": 5000.00},
            {"item": "Storage", "cost": 2000.00},
            {"item": "Backup", "cost": 1500.00},
        ],
        "status": "OK",
    },
]

generator = ReportGenerator(config)
result = generator.generate(otrs_data, cloud_costs)
print(f"Dashboard gerado: {result['dashboard_path']}")
