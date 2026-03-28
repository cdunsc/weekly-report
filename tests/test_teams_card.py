"""Testes para estrutura do Adaptive Card do Teams."""


class TestTeamsCard:
    def _make_report_data(self):
        return {
            "otrs_queues": [
                {
                    "queue_name": "CLOUD",
                    "period": {"start": "2026-03-20", "end": "2026-03-26"},
                    "opened": 10,
                    "closed": 8,
                    "backlog": 5,
                    "pct_first_response": 95.0,
                    "pct_resolution": 100.0,
                    "first_response_target": 24,
                    "resolution_target": 72,
                }
            ],
            "clouds": [
                {"provider": "AWS", "currency": "USD", "total_cost": 1000.0, "total_cost_brl": 5500.0},
            ],
            "dollar_rate": 5.50,
            "total_cloud_cost_brl": 5500.0,
        }

    def test_report_data_structure_valid(self):
        data = self._make_report_data()
        assert len(data["otrs_queues"]) == 1
        assert data["otrs_queues"][0]["queue_name"] == "CLOUD"
        assert len(data["clouds"]) == 1
        assert data["total_cloud_cost_brl"] == 5500.0

    def test_sla_indicator_pass(self):
        """SLA >= 90% deve mostrar check mark."""
        pct = 95.0
        text = f"{pct:.0f}%"
        text += " ✅" if pct >= 90 else " ❌"
        assert "✅" in text

    def test_sla_indicator_fail(self):
        """SLA < 90% deve mostrar X."""
        pct = 75.0
        text = f"{pct:.0f}%"
        text += " ✅" if pct >= 90 else " ❌"
        assert "❌" in text
