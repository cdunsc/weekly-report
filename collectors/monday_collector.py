"""
Coletor de projetos Monday.com via API GraphQL v2.
Workspace: Infraestrutura
Boards: Projetos Cloud, Projetos TI Corporativa, Projetos DADOS (+ subelementos)
"""

import logging

import requests

from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)


MONDAY_API = "https://api.monday.com/v2"

QUERY = """
{
  boards(ids: [%BOARD_IDS%]) {
    id
    name
    groups { id title }
    items_page(limit: 100) {
      items {
        id
        name
        group { title }
        column_values {
          id
          column { title }
          text
        }
        subitems {
          id
          name
          column_values {
            id
            column { title }
            text
          }
        }
      }
    }
  }
}
"""


class MondayCollector:
    def __init__(self, config: dict):
        self.token = config["api_token"]
        # Suporta formato novo (boards com filtros) e legado (board_ids)
        raw_boards = config.get("boards", [])
        if raw_boards:
            self.board_ids = [b["id"] for b in raw_boards]
            self._filters = {str(b["id"]): b for b in raw_boards}
        else:
            self.board_ids = config.get("board_ids", [])
            self._filters = {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30),
           before_sleep=before_sleep_log(logger, logging.WARNING))
    def _query(self, query: str) -> dict:
        resp = requests.post(
            MONDAY_API,
            json={"query": query},
            headers={
                "Content-Type": "application/json",
                "Authorization": self.token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if "errors" in data:
            raise RuntimeError(f"Monday API error: {data['errors']}")
        return data["data"]

    def collect(self) -> list[dict]:
        """
        Coleta projetos de todos os boards configurados.

        Returns:
            list de dicts, um por board, com itens e métricas.
        """
        ids_str = ", ".join(str(bid) for bid in self.board_ids)
        query = QUERY.replace("%BOARD_IDS%", ids_str)

        data = self._query(query)
        boards = []

        for board in data.get("boards", []):
            items = []
            status_counts = {}

            for item in board["items_page"]["items"]:
                cols = {}
                for cv in item["column_values"]:
                    title = cv["column"]["title"]
                    cols[title] = cv["text"]

                status = cols.get("Status") or "Sem status"
                pessoa = cols.get("Pessoa") or ""
                data_col = cols.get("Data") or ""

                # Subitems
                subitems = []
                sub_done = 0
                sub_total = 0
                for sub in item.get("subitems", []):
                    sub_cols = {}
                    for sv in sub["column_values"]:
                        sub_cols[sv["column"]["title"]] = sv["text"]
                    sub_status = sub_cols.get("Status") or "Sem status"
                    sub_pessoa = sub_cols.get("Pessoa") or ""
                    subitems.append({
                        "name": sub["name"],
                        "status": sub_status,
                        "person": sub_pessoa,
                        "progress": sub_cols.get("Progresso") or "",
                        "start_date": sub_cols.get("Data Inicio") or "",
                        "due_date": sub_cols.get("Prev. Conclusão") or "",
                        "new_due_date": sub_cols.get("Nova Prev. Conclusão") or "",
                        "conclusion": sub_cols.get("Conclusão") or "",
                    })
                    sub_total += 1
                    if sub_status in ("Feito", "Concluído", "Done"):
                        sub_done += 1

                status_counts[status] = status_counts.get(status, 0) + 1

                items.append({
                    "name": item["name"],
                    "group": item["group"]["title"],
                    "status": status,
                    "person": pessoa,
                    "date": data_col,
                    "subitems": subitems,
                    "subitems_total": sub_total,
                    "subitems_done": sub_done,
                })

            # Aplica filtro por responsável nos subitens
            board_cfg = self._filters.get(str(board["id"]), {})
            filter_person = board_cfg.get("filter_person", "").lower()
            if filter_person:
                # Extrai somente os subitens da pessoa, agrupados pelo item pai
                filtered_subitems = []
                for it in items:
                    person_subs = [
                        s for s in it.get("subitems", [])
                        if filter_person in s.get("person", "").lower()
                    ]
                    for s in person_subs:
                        s["parent_name"] = it["name"]
                    filtered_subitems.extend(person_subs)

                # Recalcula status_counts dos subitens filtrados
                status_counts = {}
                for s in filtered_subitems:
                    status_counts[s["status"]] = status_counts.get(s["status"], 0) + 1

                boards.append({
                    "board_name": board["name"],
                    "board_id": board["id"],
                    "category": board_cfg.get("category", ""),
                    "projects": [],
                    "total_projects": len(filtered_subitems),
                    "status_summary": status_counts,
                    "filtered_subitems": filtered_subitems,
                    "filter_person": board_cfg.get("filter_person", ""),
                })
            else:
                boards.append({
                    "board_name": board["name"],
                    "board_id": board["id"],
                    "category": board_cfg.get("category", ""),
                    "projects": items,
                    "total_projects": len(items),
                    "status_summary": status_counts,
                })

        return boards
