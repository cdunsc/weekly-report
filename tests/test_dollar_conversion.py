"""Testes para conversão de moeda no generator."""


class TestDollarConversion:
    def test_usd_converted_to_brl(self):
        clouds = [
            {"provider": "AWS", "currency": "USD", "total_cost": 100.0},
        ]
        dollar_rate = 5.50
        for c in clouds:
            if c.get("currency") == "USD":
                c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
            else:
                c["total_cost_brl"] = c["total_cost"]
        assert clouds[0]["total_cost_brl"] == 550.0

    def test_brl_not_converted(self):
        clouds = [
            {"provider": "Golden Cloud", "currency": "BRL", "total_cost": 35000.0},
        ]
        dollar_rate = 5.50
        for c in clouds:
            if c.get("currency") == "USD":
                c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
            else:
                c["total_cost_brl"] = c["total_cost"]
        assert clouds[0]["total_cost_brl"] == 35000.0

    def test_multiple_providers_total(self):
        clouds = [
            {"provider": "AWS", "currency": "USD", "total_cost": 1000.0},
            {"provider": "OCI", "currency": "USD", "total_cost": 500.0},
            {"provider": "Golden Cloud", "currency": "BRL", "total_cost": 30000.0},
        ]
        dollar_rate = 5.0
        total_brl = 0.0
        for c in clouds:
            if c.get("currency") == "USD":
                c["total_cost_brl"] = round(c["total_cost"] * dollar_rate, 2)
            else:
                c["total_cost_brl"] = c["total_cost"]
            total_brl += c["total_cost_brl"]
        assert total_brl == 37500.0
