"""
Coletor de chamados OTRS/Znuny via web scraping do painel.
Login no painel e exportação CSV da busca de tickets.
Suporta múltiplas filas.
Métricas: abertos, fechados, backlog, SLA (1a resposta e resolução),
          top solicitantes e breakdown por serviço.
"""

import csv
import io
import re
import requests
from collections import Counter
from datetime import datetime


# Estados considerados "fechados"
CLOSED_STATES = {
    "Fechado com êxito", "Fechado sem êxito", "fechado",
    "fechado com êxito", "fechado sem êxito",
    "fechado com solução de contorno", "Encerrado",
    "Resolvido", "Indevido",
}


class OTRSCollector:
    def __init__(self, config: dict):
        self.panel_url = config["panel_url"]
        self.username = config["username"]
        self.password = config["password"]
        # Suporta config antiga (queue_id único) e nova (queues lista)
        self.queues = config.get("queues", [])
        if not self.queues:
            self.queues = [{
                "name": config.get("queue", "CLOUD"),
                "queue_id": config.get("queue_id", 26),
            }]

    def _login(self, session: requests.Session) -> str:
        """Login no painel OTRS e retorna o ChallengeToken."""
        resp = session.post(
            f"{self.panel_url}/otrs/index.pl",
            data={
                "Action": "Login",
                "RequestedURL": "",
                "Lang": "pt_BR",
                "TimeOffset": "180",
                "User": self.username,
                "Password": self.password,
            },
            allow_redirects=True,
            timeout=30,
        )

        if "LoginFailed" in resp.url or "LoginFailed" in resp.text:
            raise RuntimeError("Falha no login OTRS — verifique usuário/senha")

        match = re.search(r'ChallengeToken=([a-zA-Z0-9]+)', resp.text)
        if not match:
            raise RuntimeError("Não foi possível extrair ChallengeToken do OTRS")

        return match.group(1)

    def _search_csv(self, session: requests.Session, token: str, queue_id: int) -> list[dict]:
        """Exporta todos os tickets de uma fila como CSV."""
        resp = session.post(
            f"{self.panel_url}/otrs/index.pl",
            data={
                "Action": "AgentTicketSearch",
                "Subaction": "Search",
                "ChallengeToken": token,
                "QueueIDs": str(queue_id),
                "ResultForm": "CSV",
                "SortBy": "Age",
                "OrderBy": "Down",
            },
            timeout=120,
        )
        resp.raise_for_status()

        content = resp.content.decode("utf-8")
        reader = csv.reader(io.StringIO(content), delimiter=";")
        header = next(reader)

        col_map = {name: i for i, name in enumerate(header)}

        # Detecta coluna de cliente/solicitante (varia conforme versão OTRS)
        customer_col = None
        for candidate in ("Nome do Cliente", "ID do Cliente", "CustomerID",
                          "Cliente", "ID de cliente do usuário", "ID Cliente",
                          "Solicitante", "Requisitante", "CustomerUserID"):
            if candidate in col_map:
                customer_col = candidate
                break

        if customer_col:
            print(f"[OTRS] Coluna de cliente detectada: '{customer_col}'")
        else:
            print(f"[OTRS] Colunas disponíveis: {list(col_map.keys())}")

        tickets = []
        for row in reader:
            if len(row) < len(header):
                continue
            ticket = {
                "number": row[col_map.get("Número do Chamado", 0)],
                "created": row[col_map.get("Criado", 2)],
                "closed": row[col_map.get("Fechado", 3)],
                "first_response": row[col_map.get("Primeira Resposta", 5)],
                "state": row[col_map.get("Estado", 6)],
                "priority": row[col_map.get("Prioridade", 7)],
                "queue": row[col_map.get("Fila", 8)],
                "owner": row[col_map.get("Atendente", 10)],
                "subject": row[col_map.get("Assunto", 16)],
                "resolution_minutes": row[col_map.get("Tempo de solução em minutos", 19)],
                "first_response_minutes": row[col_map.get("Primeira Resposta em Minutos", 21)],
                "service": row[col_map.get("Serviço", 24)],
                "customer": row[col_map[customer_col]] if customer_col else "",
            }
            tickets.append(ticket)

        return tickets

    def _calc_metrics(self, all_tickets: list, start_date: str, end_date: str,
                      sla_first_response_hours: int = 24, sla_resolution_hours: int = 72) -> dict:
        """Calcula métricas de uma fila para o período."""
        end_ts = f"{end_date} 23:59:59"
        start_ts = f"{start_date} 00:00:00"

        opened = [t for t in all_tickets
                  if t["created"] >= start_ts and t["created"] <= end_ts]

        closed = [t for t in all_tickets
                  if t["closed"] and t["closed"] >= start_ts and t["closed"] <= end_ts]

        backlog = [t for t in all_tickets if t["state"] not in CLOSED_STATES]

        first_response_hours = []
        for t in opened:
            val = t["first_response_minutes"].strip()
            if val:
                try:
                    first_response_hours.append(round(float(val) / 60, 2))
                except ValueError:
                    pass

        resolution_hours = []
        for t in opened:
            val = t["resolution_minutes"].strip()
            if val:
                try:
                    resolution_hours.append(round(float(val) / 60, 2))
                except ValueError:
                    pass

        avg_first_response = (
            round(sum(first_response_hours) / len(first_response_hours), 2)
            if first_response_hours else None
        )
        avg_resolution = (
            round(sum(resolution_hours) / len(resolution_hours), 2)
            if resolution_hours else None
        )

        # Percentual de tickets dentro do SLA
        first_response_target = sla_first_response_hours
        resolution_target = sla_resolution_hours
        fr_within = sum(1 for h in first_response_hours if h <= first_response_target)
        res_within = sum(1 for h in resolution_hours if h <= resolution_target)
        pct_first_response = (
            round(fr_within / len(first_response_hours) * 100, 1)
            if first_response_hours else None
        )
        pct_resolution = (
            round(res_within / len(resolution_hours) * 100, 1)
            if resolution_hours else None
        )

        tickets_detail = [
            {
                "id": t["number"],
                "title": t["subject"],
                "state": t["state"],
                "created": t["created"],
                "priority": t["priority"],
                "service": t["service"],
                "customer": t.get("customer", ""),
                "owner": t.get("owner", ""),
            }
            for t in opened
        ]

        # Top solicitantes (quem abriu mais chamados no período)
        customer_counter = Counter(
            t.get("customer", "").strip() or "Abertura Automática" for t in opened
        )
        top_requesters = [
            {"name": name, "count": count}
            for name, count in customer_counter.most_common(15)
        ]

        # Breakdown por serviço
        service_counter = Counter(
            t.get("service", "").strip() or "Sem Serviço" for t in opened
        )
        service_breakdown = [
            {"service": name, "count": count}
            for name, count in service_counter.most_common(20)
        ]

        # Breakdown por atendente
        owner_counter = Counter(
            t.get("owner", "").strip() or "Não Atribuído" for t in opened
        )
        owner_breakdown = [
            {"name": name, "count": count}
            for name, count in owner_counter.most_common(15)
        ]

        return {
            "period": {"start": start_date, "end": end_date},
            "opened": len(opened),
            "closed": len(closed),
            "backlog": len(backlog),
            "avg_first_response_hours": avg_first_response,
            "avg_resolution_hours": avg_resolution,
            "pct_first_response": pct_first_response,
            "pct_resolution": pct_resolution,
            "sla_first_response_met": (
                avg_first_response <= first_response_target if avg_first_response is not None else None
            ),
            "sla_resolution_met": (
                avg_resolution <= resolution_target if avg_resolution is not None else None
            ),
            "first_response_target": first_response_target,
            "resolution_target": resolution_target,
            "tickets": tickets_detail,
            "top_requesters": top_requesters,
            "service_breakdown": service_breakdown,
            "owner_breakdown": owner_breakdown,
        }

    def collect(self, start_date: str, end_date: str, daily_end_date: str = None) -> tuple[list[dict], list[dict]]:
        """
        Coleta métricas de chamados para todas as filas configuradas.

        Args:
            start_date: Data início do período semanal (YYYY-MM-DD).
            end_date: Data fim do período semanal (YYYY-MM-DD).
            daily_end_date: Se informado, também calcula métricas do período
                            start_date até daily_end_date 23:59 (D-1).

        Returns:
            Tupla (weekly_results, daily_results).
            Se daily_end_date não for informado, daily_results será lista vazia.
        """
        session = requests.Session()
        token = self._login(session)

        weekly_results = []
        daily_results = []

        for q in self.queues:
            queue_name = q["name"]
            queue_id = q["queue_id"]
            sla_fr = q.get("sla_first_response_hours", 24)
            sla_res = q.get("sla_resolution_hours", 72)

            print(f"[OTRS] Exportando fila {queue_name} (ID={queue_id})...")
            all_tickets = self._search_csv(session, token, queue_id)
            print(f"[OTRS] {queue_name}: {len(all_tickets)} tickets no total")

            # Métricas semanais
            metrics = self._calc_metrics(all_tickets, start_date, end_date,
                                         sla_first_response_hours=sla_fr,
                                         sla_resolution_hours=sla_res)
            metrics["queue_name"] = queue_name
            weekly_results.append(metrics)

            print(f"[OTRS] {queue_name}: Abertos={metrics['opened']}, "
                  f"Fechados={metrics['closed']}, Backlog={metrics['backlog']}")

            # Métricas D-1 (até 23:59 do dia anterior)
            if daily_end_date:
                daily_metrics = self._calc_metrics(all_tickets, start_date, daily_end_date,
                                                   sla_first_response_hours=sla_fr,
                                                   sla_resolution_hours=sla_res)
                daily_metrics["queue_name"] = queue_name
                daily_results.append(daily_metrics)
                print(f"[OTRS] {queue_name} (D-1 até {daily_end_date}): "
                      f"Abertos={daily_metrics['opened']}, "
                      f"Fechados={daily_metrics['closed']}, Backlog={daily_metrics['backlog']}")

        return weekly_results, daily_results
