"""Testes para cálculo de SLA do OTRS collector."""

from collectors.otrs_collector import OTRSCollector, CLOSED_STATES


def _make_ticket(created, closed="", state="novo", first_response_minutes="", resolution_minutes="", service="", customer="", owner=""):
    return {
        "number": "2026010100001",
        "created": created,
        "closed": closed,
        "first_response": "",
        "state": state,
        "priority": "3 normal",
        "queue": "CLOUD",
        "owner": owner,
        "subject": "Test ticket",
        "resolution_minutes": resolution_minutes,
        "first_response_minutes": first_response_minutes,
        "service": service,
        "customer": customer,
    }


class TestSLACalculation:
    def _make_collector(self):
        config = {
            "panel_url": "https://example.com",
            "username": "test",
            "password": "test",
            "queues": [{"name": "TEST", "queue_id": 1}],
        }
        return OTRSCollector(config)

    def test_all_within_sla(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-20 10:00:00", first_response_minutes="60", resolution_minutes="120"),
            _make_ticket("2026-03-21 10:00:00", first_response_minutes="120", resolution_minutes="600"),
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26", sla_first_response_hours=24, sla_resolution_hours=72)
        assert result["opened"] == 2
        assert result["pct_first_response"] == 100.0
        assert result["pct_resolution"] == 100.0

    def test_sla_breach(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-20 10:00:00", first_response_minutes="1500", resolution_minutes="5000"),
            _make_ticket("2026-03-21 10:00:00", first_response_minutes="60", resolution_minutes="120"),
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26", sla_first_response_hours=24, sla_resolution_hours=72)
        assert result["pct_first_response"] == 50.0
        assert result["pct_resolution"] == 50.0

    def test_no_tickets_in_period(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-10 10:00:00"),  # Before period
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26")
        assert result["opened"] == 0
        assert result["pct_first_response"] is None

    def test_backlog_counts_open_tickets(self):
        collector = self._make_collector()
        tickets = [
            _make_ticket("2026-03-20 10:00:00", state="novo"),
            _make_ticket("2026-03-21 10:00:00", state="Fechado com êxito", closed="2026-03-22 10:00:00"),
        ]
        result = collector._calc_metrics(tickets, "2026-03-20", "2026-03-26")
        assert result["backlog"] == 1
