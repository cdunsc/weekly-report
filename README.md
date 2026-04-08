# Weekly Report - Automação de Relatórios TI

Automação de relatórios semanais e mensais da equipe Cloud/TI, com coleta de métricas de chamados, custos de cloud, projetos e segurança.

## Funcionalidades

### Collectors (coleta de dados)
| Collector | Fonte | Dados |
|---|---|---|
| `aws_collector.py` | AWS Cost Explorer | Custos diários (USD) |
| `oci_collector.py` | OCI Usage API | Custos diários (BRL) |
| `oci_finops_collector.py` | OCI Usage API | Análise FinOps detalhada |
| `golden_collector.py` | Portal Golden Cloud (scraping) | Custos (BRL) |
| `otrs_collector.py` | OTRS/Znuny | Chamados abertos, fechados, backlog, SLA |
| `monday_collector.py` | Monday.com API | Projetos Cloud, TI, Segurança |
| `defender_collector.py` | Microsoft Defender (Graph API) | Alertas e vulnerabilidades |

### Entrega
- **Dashboard web**: http://cloudteam.surf.com.br/dashboard (nginx)
- **E-mail**: Microsoft Graph API (OAuth2)
- **Teams**: Adaptive Card via Power Automate webhook
- **PDF**: Relatórios semanais e mensais em PDF

### Scripts utilitários
| Script | Função |
|---|---|
| `deadline_alert.py` | Alertas de prazo de projetos Monday.com |
| `security_deadline_alert.py` | Alertas de prazo de segurança |
| `security_report.py` | Relatório de segurança (Defender) |
| `refresh_defender.py` | Atualiza dados do Defender |
| `manage_users.py` | Gestão de usuários do dashboard |
| `export_ad_users.py` | Exporta usuários do AD |
| `export_exchange_users.py` | Exporta usuários do Exchange |
| `generate_demo.py` | Gera dados demo para testes |
| `rebuild_history.py` | Reconstrói histórico de semanas |

## Estrutura

```
/opt/weekly-report/
├── main.py                  # Orquestrador principal
├── api_server.py            # API Flask (porta 8080)
├── auth.py                  # Autenticação do dashboard
├── config.yaml              # Configuração (segredos via .env)
├── env_loader.py            # Carrega variáveis de ambiente
├── monthly_report.py        # Gerador de relatório mensal
├── weekly_pdf_report.py     # Gerador de PDF semanal
├── collectors/              # Módulos de coleta de dados
├── report/
│   ├── generator.py         # Gerador de relatório HTML
│   ├── pdf_generator.py     # Gerador de PDF
│   └── templates/           # Templates Jinja2
├── delivery/                # Módulos de entrega (email, teams)
├── scripts/                 # Scripts utilitários
├── data/                    # Dados gerados (history.json, etc.)
├── static/                  # Assets do dashboard
└── dashboard/               # Frontend do dashboard
```

## Configuração

1. Copie `.env.example` para `.env` e preencha as credenciais
2. Instale dependências: `pip install -r requirements.txt`
3. Configure `config.yaml` conforme necessário

### Variáveis de ambiente (.env)
- **AWS**: credenciais via `~/.aws/credentials`
- **OCI**: credenciais via `~/.oci/config`
- **Golden Cloud**: `GOLDEN_CLOUD_USERNAME`, `GOLDEN_CLOUD_PASSWORD`
- **OTRS**: `OTRS_USERNAME`, `OTRS_PASSWORD`
- **Monday.com**: `MONDAY_API_TOKEN`
- **E-mail (Graph)**: `EMAIL_TENANT_ID`, `EMAIL_CLIENT_ID`, `EMAIL_CLIENT_SECRET`
- **Teams**: `TEAMS_WEBHOOK_URL`
- **Defender**: usa mesmas credenciais do Graph API
- **Dashboard**: `DASHBOARD_SECRET_KEY`

## Execução

```bash
# Relatório semanal (dry-run)
python main.py --dry-run

# Relatório semanal (produção)
python main.py

# API server
python api_server.py

# Relatório mensal
python monthly_report.py
```

## Infraestrutura

- **Servidor**: Ubuntu + nginx (porta 80 → dashboard, proxy 8080 → API)
- **Serviço**: `systemd` service `weekly-report-api`
- **Cron**: execução automática às 11h (dias úteis)
- **Python**: venv em `/opt/weekly-report/venv/`
