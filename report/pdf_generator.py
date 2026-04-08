"""
Gerador de relatório mensal em PDF usando ReportLab.
"""

import logging
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# Cores corporativas
SURF_BLUE = colors.HexColor("#1a5276")
SURF_LIGHT_BLUE = colors.HexColor("#2980b9")
SURF_DARK = colors.HexColor("#2c3e50")
SURF_GREEN = colors.HexColor("#27ae60")
SURF_RED = colors.HexColor("#e74c3c")
SURF_ORANGE = colors.HexColor("#f39c12")
SURF_GRAY = colors.HexColor("#bdc3c7")
SURF_LIGHT_GRAY = colors.HexColor("#ecf0f1")
TABLE_HEADER_BG = colors.HexColor("#1a5276")
TABLE_ALT_ROW = colors.HexColor("#eaf2f8")


def _build_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "CoverTitle", parent=styles["Title"],
        fontSize=28, textColor=colors.white, alignment=TA_CENTER,
        spaceAfter=12, fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "CoverSubtitle", parent=styles["Normal"],
        fontSize=14, textColor=colors.white, alignment=TA_CENTER,
        spaceAfter=6, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "SectionTitle", parent=styles["Heading1"],
        fontSize=16, textColor=SURF_BLUE, spaceBefore=16, spaceAfter=8,
        fontName="Helvetica-Bold", borderWidth=0, borderPadding=0,
        leftIndent=0,
    ))
    styles.add(ParagraphStyle(
        "SubSection", parent=styles["Heading2"],
        fontSize=13, textColor=SURF_DARK, spaceBefore=12, spaceAfter=6,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        "BodyText2", parent=styles["Normal"],
        fontSize=10, textColor=SURF_DARK, spaceAfter=6,
        fontName="Helvetica", leading=14,
    ))
    styles.add(ParagraphStyle(
        "TableHeader", parent=styles["Normal"],
        fontSize=9, textColor=colors.white, fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "TableCell", parent=styles["Normal"],
        fontSize=9, textColor=SURF_DARK, fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        "TableCellRight", parent=styles["Normal"],
        fontSize=9, textColor=SURF_DARK, fontName="Helvetica",
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        "KPIValue", parent=styles["Normal"],
        fontSize=22, textColor=SURF_BLUE, fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "KPILabel", parent=styles["Normal"],
        fontSize=9, textColor=SURF_DARK, fontName="Helvetica",
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.gray, fontName="Helvetica",
    ))

    return styles


def _header_footer(canvas, doc):
    """Header e footer em todas as páginas (exceto capa)."""
    canvas.saveState()

    # Header - linha azul
    canvas.setStrokeColor(SURF_BLUE)
    canvas.setLineWidth(2)
    canvas.line(1.5 * cm, A4[1] - 1.2 * cm, A4[0] - 1.5 * cm, A4[1] - 1.2 * cm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SURF_DARK)
    canvas.drawString(1.5 * cm, A4[1] - 1.0 * cm, "Surf Telecom - Relatorio Mensal de TI e Cloud")

    # Footer
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.gray)
    canvas.drawString(1.5 * cm, 1.0 * cm,
                      f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, f"Pagina {doc.page}")

    canvas.restoreState()


def _cover_page(canvas, doc):
    """Capa do relatório."""
    canvas.saveState()

    # Fundo azul
    canvas.setFillColor(SURF_BLUE)
    canvas.rect(0, 0, A4[0], A4[1], fill=1)

    # Faixa branca decorativa
    canvas.setFillColor(colors.white)
    canvas.setFillAlpha(0.1)
    canvas.rect(0, A4[1] * 0.35, A4[0], A4[1] * 0.3, fill=1)
    canvas.setFillAlpha(1.0)

    canvas.restoreState()


def _fmt_brl(value):
    """Formata valor como moeda BRL."""
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_usd(value):
    """Formata valor como moeda USD."""
    if value is None:
        return "-"
    return f"US$ {value:,.2f}"


def _fmt_pct(value):
    """Formata percentual."""
    if value is None:
        return "-"
    return f"{value:.1f}%"


def _fmt_hours(value):
    """Formata horas."""
    if value is None:
        return "-"
    return f"{value:.1f}h"


def _make_table(header, rows, col_widths=None):
    """Cria uma tabela formatada."""
    styles = _build_styles()

    header_cells = [Paragraph(h, styles["TableHeader"]) for h in header]
    data = [header_cells]

    for row in rows:
        data.append(row)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, SURF_GRAY),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]

    # Alternating row colors
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))

    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle(style_commands))
    return t


def _make_kpi_box(label, value, color=SURF_BLUE):
    """Cria um box de KPI."""
    styles = _build_styles()
    kpi_style = ParagraphStyle(
        "kpi_val_dyn", parent=styles["KPIValue"], textColor=color,
    )
    return [
        [Paragraph(str(value), kpi_style)],
        [Paragraph(label, styles["KPILabel"])],
    ]


class MonthlyPDFGenerator:
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.styles = _build_styles()
        self.elements = []

    def generate(self, report_data: dict) -> str:
        """Gera o PDF completo e retorna o path."""
        period = report_data.get("period", {})
        start = period.get("start", "")
        end = period.get("end", "")

        # Monta o documento
        doc = BaseDocTemplate(
            self.output_path, pagesize=A4,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        )

        # Frames
        content_frame = Frame(
            1.5 * cm, 1.8 * cm,
            A4[0] - 3 * cm, A4[1] - 3.6 * cm,
            id="content",
        )
        cover_frame = Frame(
            2 * cm, 2 * cm,
            A4[0] - 4 * cm, A4[1] - 4 * cm,
            id="cover",
        )

        doc.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame], onPage=_cover_page),
            PageTemplate(id="content", frames=[content_frame], onPage=_header_footer),
        ])

        # === CAPA ===
        self._build_cover(start, end, report_data)

        # === RESUMO EXECUTIVO ===
        self._build_executive_summary(report_data)

        # === CHAMADOS TI ===
        self._build_tickets_section(report_data)

        # === CUSTOS CLOUD ===
        self._build_costs_section(report_data)

        # === PROJETOS MONDAY ===
        self._build_monday_section(report_data)

        # === MICROSOFT DEFENDER ===
        self._build_defender_section(report_data)

        # Build
        doc.build(self.elements)
        logger.info("PDF gerado: %s", self.output_path)
        return self.output_path

    def _build_cover(self, start, end, report_data):
        """Monta a capa."""
        s = self.styles
        el = self.elements

        # Espaçamento para centralizar na capa
        el.append(Spacer(1, 6 * cm))

        el.append(Paragraph("RELATORIO MENSAL", s["CoverTitle"]))
        el.append(Paragraph("Tecnologia da Informacao e Cloud", s["CoverSubtitle"]))
        el.append(Spacer(1, 1 * cm))

        # Período
        try:
            dt_start = datetime.strptime(start, "%Y-%m-%d")
            dt_end = datetime.strptime(end, "%Y-%m-%d")
            period_str = f"{dt_start.strftime('%d/%m/%Y')} a {dt_end.strftime('%d/%m/%Y')}"
            month_name = dt_start.strftime("%B/%Y").capitalize()
        except ValueError:
            period_str = f"{start} a {end}"
            month_name = ""

        _months_pt = {
            "January": "Janeiro", "February": "Fevereiro", "March": "Marco",
            "April": "Abril", "May": "Maio", "June": "Junho",
            "July": "Julho", "August": "Agosto", "September": "Setembro",
            "October": "Outubro", "November": "Novembro", "December": "Dezembro",
        }
        for eng, pt in _months_pt.items():
            month_name = month_name.replace(eng, pt)

        el.append(Paragraph(month_name, ParagraphStyle(
            "MonthTitle", parent=s["CoverTitle"], fontSize=20,
        )))
        el.append(Spacer(1, 0.5 * cm))
        el.append(Paragraph(period_str, s["CoverSubtitle"]))

        el.append(Spacer(1, 3 * cm))
        el.append(Paragraph("Surf Telecom", ParagraphStyle(
            "Company", parent=s["CoverSubtitle"], fontSize=12,
        )))
        el.append(Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("GenDate", parent=s["CoverSubtitle"], fontSize=10),
        ))

        el.append(NextPageTemplate("content"))
        el.append(PageBreak())

    def _build_executive_summary(self, data):
        """Resumo executivo com KPIs principais."""
        s = self.styles
        el = self.elements

        el.append(Paragraph("1. Resumo Executivo", s["SectionTitle"]))

        # KPIs em grid
        total_brl = data.get("total_cloud_cost_brl", 0)
        dollar_rate = data.get("dollar_rate", 0)

        # Total de chamados abertos/fechados (soma de todas as filas)
        total_opened = 0
        total_closed = 0
        total_backlog = 0
        for q in data.get("otrs_queues", []):
            total_opened += q.get("opened", 0)
            total_closed += q.get("closed", 0)
            total_backlog += q.get("backlog", 0)

        kpi_data = [
            [
                Paragraph(_fmt_brl(total_brl), ParagraphStyle(
                    "kv1", parent=s["KPIValue"], textColor=SURF_BLUE, fontSize=18)),
                Paragraph(str(total_opened), ParagraphStyle(
                    "kv2", parent=s["KPIValue"], textColor=SURF_LIGHT_BLUE, fontSize=18)),
                Paragraph(str(total_closed), ParagraphStyle(
                    "kv3", parent=s["KPIValue"], textColor=SURF_GREEN, fontSize=18)),
                Paragraph(str(total_backlog), ParagraphStyle(
                    "kv4", parent=s["KPIValue"], textColor=SURF_ORANGE, fontSize=18)),
            ],
            [
                Paragraph("Custo Total Cloud (BRL)", s["KPILabel"]),
                Paragraph("Chamados Abertos", s["KPILabel"]),
                Paragraph("Chamados Fechados", s["KPILabel"]),
                Paragraph("Backlog Atual", s["KPILabel"]),
            ],
        ]

        available_width = A4[0] - 3 * cm
        kpi_table = Table(kpi_data, colWidths=[available_width / 4] * 4)
        kpi_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 1, SURF_LIGHT_BLUE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, SURF_LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ]))
        el.append(kpi_table)
        el.append(Spacer(1, 0.5 * cm))

        el.append(Paragraph(
            f"Cotacao USD/BRL utilizada: R$ {dollar_rate:.4f}",
            s["BodyText2"],
        ))

    def _build_tickets_section(self, data):
        """Secao de chamados de TI e Cloud."""
        s = self.styles
        el = self.elements

        el.append(Spacer(1, 0.3 * cm))
        el.append(Paragraph("2. Chamados de TI e Cloud", s["SectionTitle"]))

        otrs_queues = data.get("otrs_queues", [])
        if not otrs_queues:
            el.append(Paragraph("Sem dados de chamados disponiveis para o periodo.", s["BodyText2"]))
            return

        # Tabela resumo por fila
        header = ["Fila", "Abertos", "Fechados", "Backlog",
                  "Tempo Medio 1a Resp.", "Tempo Medio Resolucao",
                  "SLA 1a Resp.", "SLA Resolucao"]

        rows = []
        for q in otrs_queues:
            rows.append([
                q.get("queue_name", "-"),
                str(q.get("opened", 0)),
                str(q.get("closed", 0)),
                str(q.get("backlog", 0)),
                _fmt_hours(q.get("avg_first_response_hours")),
                _fmt_hours(q.get("avg_resolution_hours")),
                _fmt_pct(q.get("pct_first_response")),
                _fmt_pct(q.get("pct_resolution")),
            ])

        available_width = A4[0] - 3 * cm
        col_w = [available_width * p for p in [0.10, 0.10, 0.10, 0.10, 0.16, 0.16, 0.14, 0.14]]
        el.append(_make_table(header, rows, col_widths=col_w))
        el.append(Spacer(1, 0.5 * cm))

    def _build_costs_section(self, data):
        """Secao de custos consolidados."""
        s = self.styles
        el = self.elements

        el.append(Paragraph("3. Custos Cloud - Visao Consolidada", s["SectionTitle"]))

        clouds = data.get("clouds", [])
        if not clouds:
            el.append(Paragraph("Sem dados de custos disponiveis.", s["BodyText2"]))
            return

        # Tabela consolidada
        header = ["Provider", "Moeda", "Custo Original", "Custo (BRL)"]
        rows = []
        for c in clouds:
            provider = c.get("provider", "-")
            currency = c.get("currency", "USD")
            total = c.get("total_cost", 0)
            total_brl = c.get("total_cost_brl", total)

            if currency == "USD":
                original = _fmt_usd(total)
            else:
                original = _fmt_brl(total)

            rows.append([provider, currency, original, _fmt_brl(total_brl)])

        # Total
        total_brl = data.get("total_cloud_cost_brl", 0)
        rows.append(["TOTAL", "-", "-", _fmt_brl(total_brl)])

        available_width = A4[0] - 3 * cm
        col_w = [available_width * p for p in [0.25, 0.15, 0.30, 0.30]]
        t = _make_table(header, rows, col_widths=col_w)

        # Bold na ultima linha (total) - rows index + 1 (header row)
        last_row = len(rows)  # header is row 0, so last data row = len(rows)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, last_row), (-1, last_row), "Helvetica-Bold"),
            ("BACKGROUND", (0, last_row), (-1, last_row), colors.HexColor("#d5e8d4")),
        ]))

        el.append(t)
        el.append(Spacer(1, 0.5 * cm))

        # Historico mensal
        monthly = data.get("monthly_costs", {})
        if monthly:
            el.append(Paragraph("Historico Mensal de Custos", s["SubSection"]))

            # Coleta todos os meses
            all_months = set()
            for provider, months in monthly.items():
                for m in months:
                    all_months.add(m["month"])
            all_months = sorted(all_months)

            header = ["Provider"] + all_months
            rows = []
            for provider, months in monthly.items():
                month_map = {m["month"]: m for m in months}
                row = [provider]
                for month in all_months:
                    m = month_map.get(month)
                    if m:
                        if m.get("currency", "USD") == "USD":
                            row.append(_fmt_usd(m["cost"]))
                        else:
                            row.append(_fmt_brl(m["cost"]))
                    else:
                        row.append("-")
                rows.append(row)

            n_cols = len(header)
            col_w = [available_width * 0.20] + [available_width * 0.80 / max(n_cols - 1, 1)] * (n_cols - 1)
            el.append(_make_table(header, rows, col_widths=col_w))
            el.append(Spacer(1, 0.5 * cm))

    def _build_monday_section(self, data):
        """Secao de projetos Monday.com - apenas consolidado por board."""
        s = self.styles
        el = self.elements
        available_width = A4[0] - 3 * cm

        boards = data.get("monday_boards", [])
        if not boards:
            return

        el.append(Paragraph("4. Projetos - Monday.com", s["SectionTitle"]))

        # Categorias para label amigavel
        _cat_labels = {
            "cloud": "Cloud",
            "ti": "TI Corporativa",
            "seguranca": "Seguranca",
        }

        # Tabela consolidada: Board | Total | Status breakdown
        header = ["Board", "Categoria", "Total", "Concluidos", "Em Andamento", "Outros"]
        rows = []

        for board in boards:
            board_name = board.get("board_name", "")
            category = board.get("category", "")
            cat_label = _cat_labels.get(category, category.capitalize() or board_name)
            total = board.get("total_projects", 0)
            status_summary = board.get("status_summary", {})

            done = 0
            in_progress = 0
            other = 0
            for status, count in status_summary.items():
                sl = status.lower()
                if sl in ("feito", "concluído", "concluido", "done"):
                    done += count
                elif sl in ("em andamento", "em progresso", "in progress", "working on it"):
                    in_progress += count
                else:
                    other += count

            rows.append([board_name, cat_label, str(total),
                         str(done), str(in_progress), str(other)])

        col_w = [available_width * p for p in [0.28, 0.15, 0.10, 0.15, 0.17, 0.15]]
        el.append(_make_table(header, rows, col_widths=col_w))
        el.append(Spacer(1, 0.5 * cm))

        # Detalhamento de status por board
        for board in boards:
            board_name = board.get("board_name", "")
            category = board.get("category", "")
            cat_label = _cat_labels.get(category, category.capitalize() or board_name)
            total = board.get("total_projects", 0)
            status_summary = board.get("status_summary", {})

            if not status_summary:
                continue

            el.append(Paragraph(f"{cat_label} — {board_name}", s["SubSection"]))

            header_s = ["Status", "Quantidade"]
            rows_s = []
            for status, count in sorted(status_summary.items(), key=lambda x: x[1], reverse=True):
                rows_s.append([status, str(count)])
            rows_s.append(["TOTAL", str(total)])

            t = _make_table(header_s, rows_s,
                            col_widths=[available_width * 0.60, available_width * 0.40])
            last_row = len(rows_s)
            t.setStyle(TableStyle([
                ("FONTNAME", (0, last_row), (-1, last_row), "Helvetica-Bold"),
                ("BACKGROUND", (0, last_row), (-1, last_row), colors.HexColor("#d5e8d4")),
            ]))
            el.append(t)
            el.append(Spacer(1, 0.3 * cm))

    def _build_defender_section(self, data):
        """Secao do Microsoft Defender."""
        s = self.styles
        el = self.elements
        available_width = A4[0] - 3 * cm

        defender = data.get("defender", {})
        if not defender:
            return

        summary = defender.get("summary", {})
        if not summary:
            return

        el.append(Paragraph("5. Microsoft Defender", s["SectionTitle"]))

        # KPIs Defender
        secure_pct = summary.get("secure_score_pct", 0)
        secure_current = summary.get("secure_score_current", 0)
        secure_max = summary.get("secure_score_max", 0)
        total_alerts = summary.get("total_alerts", 0)
        active_alerts = summary.get("active_alerts", 0)
        total_devices = summary.get("total_devices", 0)
        total_vulns = summary.get("total_vulnerabilities", 0)

        kpi_data = [
            [
                Paragraph(f"{secure_pct:.1f}%", ParagraphStyle(
                    "dkv1", parent=s["KPIValue"], textColor=SURF_BLUE, fontSize=18)),
                Paragraph(str(total_alerts), ParagraphStyle(
                    "dkv2", parent=s["KPIValue"], textColor=SURF_ORANGE, fontSize=18)),
                Paragraph(str(total_devices), ParagraphStyle(
                    "dkv3", parent=s["KPIValue"], textColor=SURF_LIGHT_BLUE, fontSize=18)),
                Paragraph(str(total_vulns), ParagraphStyle(
                    "dkv4", parent=s["KPIValue"], textColor=SURF_RED, fontSize=18)),
            ],
            [
                Paragraph(f"Secure Score ({secure_current:.0f}/{secure_max:.0f})", s["KPILabel"]),
                Paragraph(f"Alertas ({active_alerts} ativos)", s["KPILabel"]),
                Paragraph("Dispositivos", s["KPILabel"]),
                Paragraph("Vulnerabilidades", s["KPILabel"]),
            ],
        ]

        kpi_table = Table(kpi_data, colWidths=[available_width / 4] * 4)
        kpi_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 1, SURF_LIGHT_BLUE),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, SURF_LIGHT_GRAY),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
        ]))
        el.append(kpi_table)
        el.append(Spacer(1, 0.5 * cm))

        # Alertas por severidade
        alert_sev = summary.get("alert_severity", {})
        if any(v > 0 for v in alert_sev.values()):
            el.append(Paragraph("Alertas por Severidade", s["SubSection"]))
            header = ["Severidade", "Quantidade"]
            rows = []
            for sev in ["high", "medium", "low", "informational"]:
                count = alert_sev.get(sev, 0)
                if count > 0:
                    rows.append([sev.capitalize(), str(count)])
            el.append(_make_table(header, rows,
                                  col_widths=[available_width * 0.60, available_width * 0.40]))
            el.append(Spacer(1, 0.3 * cm))

        # Dispositivos - exposicao
        exposure = summary.get("device_exposure", {})
        if any(v > 0 for v in exposure.values()):
            el.append(Paragraph("Dispositivos por Nivel de Exposicao", s["SubSection"]))
            header = ["Nivel", "Quantidade"]
            rows = []
            for level in ["high", "medium", "low", "none"]:
                count = exposure.get(level, 0)
                if count > 0:
                    rows.append([level.capitalize(), str(count)])
            el.append(_make_table(header, rows,
                                  col_widths=[available_width * 0.60, available_width * 0.40]))
            el.append(Spacer(1, 0.3 * cm))

        # Vulnerabilidades por severidade
        vuln_sev = summary.get("vuln_severity", {})
        if any(v > 0 for v in vuln_sev.values()):
            el.append(Paragraph("Vulnerabilidades por Severidade", s["SubSection"]))
            header = ["Severidade", "Quantidade"]
            rows = []
            for sev in ["critical", "high", "medium", "low"]:
                count = vuln_sev.get(sev, 0)
                if count > 0:
                    rows.append([sev.capitalize(), str(count)])
            el.append(_make_table(header, rows,
                                  col_widths=[available_width * 0.60, available_width * 0.40]))
            el.append(Spacer(1, 0.3 * cm))

        # Secure Score por categoria
        score_data = defender.get("secure_score", {})
        categories = score_data.get("categories", [])
        if categories:
            el.append(Paragraph("Secure Score por Categoria", s["SubSection"]))
            header = ["Categoria", "Score", "Maximo", "%"]
            rows = []
            for cat in categories:
                rows.append([
                    cat.get("category", "-"),
                    str(round(cat.get("current", 0), 1)),
                    str(round(cat.get("max", 0), 1)),
                    _fmt_pct(cat.get("pct")),
                ])
            el.append(_make_table(header, rows,
                                  col_widths=[available_width * 0.40,
                                              available_width * 0.20,
                                              available_width * 0.20,
                                              available_width * 0.20]))
            el.append(Spacer(1, 0.3 * cm))


def _header_footer_weekly(canvas, doc):
    """Header e footer para relatório semanal."""
    canvas.saveState()

    canvas.setStrokeColor(SURF_BLUE)
    canvas.setLineWidth(2)
    canvas.line(1.5 * cm, A4[1] - 1.2 * cm, A4[0] - 1.5 * cm, A4[1] - 1.2 * cm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(SURF_DARK)
    canvas.drawString(1.5 * cm, A4[1] - 1.0 * cm, "Surf Telecom - Relatorio Semanal de TI e Cloud")

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.gray)
    canvas.drawString(1.5 * cm, 1.0 * cm,
                      f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, f"Pagina {doc.page}")

    canvas.restoreState()


class WeeklyPDFGenerator(MonthlyPDFGenerator):
    """Gerador de relatório semanal em PDF, mesmo layout do mensal."""

    def generate(self, report_data: dict) -> str:
        period = report_data.get("period", {})
        start = period.get("start", "")
        end = period.get("end", "")

        doc = BaseDocTemplate(
            self.output_path, pagesize=A4,
            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
            topMargin=1.8 * cm, bottomMargin=1.8 * cm,
        )

        content_frame = Frame(
            1.5 * cm, 1.8 * cm,
            A4[0] - 3 * cm, A4[1] - 3.6 * cm,
            id="content",
        )
        cover_frame = Frame(
            2 * cm, 2 * cm,
            A4[0] - 4 * cm, A4[1] - 4 * cm,
            id="cover",
        )

        doc.addPageTemplates([
            PageTemplate(id="cover", frames=[cover_frame], onPage=_cover_page),
            PageTemplate(id="content", frames=[content_frame], onPage=_header_footer_weekly),
        ])

        self._build_cover_weekly(start, end)
        self._build_executive_summary(report_data)
        self._build_tickets_section(report_data)
        self._build_costs_section(report_data)
        self._build_monday_section(report_data)
        self._build_defender_section(report_data)

        doc.build(self.elements)
        logger.info("PDF semanal gerado: %s", self.output_path)
        return self.output_path

    def _build_cover_weekly(self, start, end):
        s = self.styles
        el = self.elements

        el.append(Spacer(1, 6 * cm))
        el.append(Paragraph("RELATORIO SEMANAL", s["CoverTitle"]))
        el.append(Paragraph("Tecnologia da Informacao e Cloud", s["CoverSubtitle"]))
        el.append(Spacer(1, 1 * cm))

        try:
            dt_start = datetime.strptime(start, "%Y-%m-%d")
            dt_end = datetime.strptime(end, "%Y-%m-%d")
            period_str = f"{dt_start.strftime('%d/%m/%Y')} a {dt_end.strftime('%d/%m/%Y')}"
        except ValueError:
            period_str = f"{start} a {end}"

        el.append(Paragraph(period_str, ParagraphStyle(
            "WeekPeriod", parent=s["CoverTitle"], fontSize=20,
        )))

        el.append(Spacer(1, 3 * cm))
        el.append(Paragraph("Surf Telecom", ParagraphStyle(
            "Company", parent=s["CoverSubtitle"], fontSize=12,
        )))
        el.append(Paragraph(
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            ParagraphStyle("GenDate", parent=s["CoverSubtitle"], fontSize=10),
        ))

        el.append(NextPageTemplate("content"))
        el.append(PageBreak())

