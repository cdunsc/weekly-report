# Dashboard Redesign - Design Spec

## Objetivo

Redesign completo do frontend do dashboard de relatorio semanal (/opt/weekly-report/).
Direção: dark profissional, sobrio, corporativo. Sem mudanças no backend ou estrutura de dados.

## Decisões

- Tema: Dark profissional
- Navegação: Sidebar fixa lateral (estilo Grafana/Datadog)
- Accent: Azul corporativo, cores semanticas apenas para status
- Tipografia: Inter (Google Fonts)
- Gráficos: Chart.js aprimorado com tooltips ricos, animações, data labels
- Abordagem: Redesign in-place (mesmo dashboard.html + templates)

---

## 1. Layout Geral e Sidebar

### Estrutura

```
┌──────────┬─────────────────────────────────────┐
│          │  Header (titulo + periodo + logout)  │
│  Sidebar │─────────────────────────────────────│
│  fixa    │                                     │
│  220px   │  Conteudo principal                 │
│          │  (max-width: 1400px, padding 24px)  │
│  Logo    │                                     │
│  ──────  │  Cards, graficos, tabelas...        │
│  Cloud   │                                     │
│  TI Corp │                                     │
│  Segur.  │                                     │
│  Diario  │                                     │
│          │                                     │
└──────────┴─────────────────────────────────────┘
```

### Sidebar

- Fundo: `#0d1117`
- Largura fixa: 220px
- Logo "Surf Telecom" no topo
- Itens de menu com icones Unicode simples
- Item ativo: borda esquerda azul `#2563eb` + fundo `rgba(37,99,235,0.1)`
- Hover: mesmo fundo sutil
- Separadores finos entre grupos

### Area Principal

- Fundo: `#161b22`
- Header interno: titulo da secao + periodo + botao logout discreto
- Conteudo com padding generoso, scroll vertical

### Paleta Dark

```
--bg-body:      #0d1117
--bg-main:      #161b22
--bg-card:      #1c2128
--bg-card-hover:#21262d
--border:       #30363d
--text:         #e6edf3
--text-muted:   #7d8590
--accent:       #2563eb
--accent-hover: #3b82f6
--accent-soft:  rgba(37,99,235,0.1)
```

---

## 2. Cards de KPI

### Layout

Grid de 5 cards por linha (Abertos, Fechados, Backlog, 1a Resposta, Resolucao).

### Estilo

```
┌─────────────────────┐
│  label (muted,12px) │
│  42     (bold,32px) │
│  ▲ 12% vs semana    │
└─────────────────────┘
```

- Fundo: `--bg-card`, borda `--border` 1px solid
- Border-radius: 8px
- Flat: sem sombras, sem gradientes
- Hover: `--bg-card-hover`, transição 0.15s
- Variação semanal: seta + percentual vs semana anterior

### Cores semanticas (apenas no valor)

- SLA dentro da meta: `#2ea043` (verde)
- SLA em alerta: `#d29922` (amarelo)
- SLA fora da meta: `#f85149` (vermelho)

### Responsivo

- < 1200px: 3 colunas
- < 768px: 2 colunas

---

## 3. Graficos (Chart.js)

### Layout

Grid de 2 colunas, cada grafico dentro de um card.

### Melhorias

- **Tooltips customizados:** fundo `--bg-card`, borda `--border`, border-radius 6px, sombra sutil. Mostra valor + percentual + variacao vs semana anterior
- **Animacoes:** duration 800ms, easing easeOutQuart
- **Grid lines:** `rgba(48,54,61,0.5)`
- **Labels eixos:** `--text-muted`, 11px
- **Legenda:** bottom, `--text-muted`
- **Paleta azul:** `#2563eb`, `#3b82f6`, `#60a5fa`, `#93c5fd`
- **Cores semanticas em graficos SLA:** verde/amarelo/vermelho
- **Data labels visiveis:** plugin chartjs-plugin-datalabels, valores nas barras/fatias
- **Hover:** opacidade aumenta, cursor pointer
- **Line charts (custos):** fill gradiente sutil azul

### Tipos mantidos

- Doughnut, Bar horizontal, Bar stacked, Line

### Responsivo

- < 768px: 1 coluna

---

## 4. Tabelas

### Estilo

- Header: fundo `#1c2128`, texto `--text-muted`, 11px uppercase bold
- Linhas alternadas: `--bg-main` / `--bg-card`
- Hover: `--bg-card-hover`, transição 0.1s
- Bordas: horizontal apenas, `--border` 1px
- Header sticky
- Corpo: `--text`, 13px

### Badges de status

- Aberto: dot 8px `#2563eb` + texto azul
- Fechado: dot 8px `#2ea043` + texto verde
- Pendente: dot 8px `#d29922` + texto amarelo
- Formato: dot + label, sem fundo colorido

### Campo de busca

- Fundo `--bg-card`, borda `--border`, focus borda `--accent`
- Placeholder em `--text-muted`

### Botao Exportar CSV

- Ghost: borda `--border`, texto `--text-muted`
- Hover: borda `--accent`, texto `--accent`

### Paginacao

- Botoes ghost, pagina ativa fundo `--accent` + texto branco
- Contagem de resultados a direita em `--text-muted`

---

## 5. Sub-navegacao

Abas internas (ex: Chamados Cloud, Custos Cloud, Projetos).

- Texto `--text-muted`, 13px, uppercase, letter-spacing 0.5px
- Ativa: texto `--text` + underline 2px `--accent`
- Hover: texto `--text`
- Sem fundo/borda/caixa — apenas texto + linha
- Transição underline 0.2s
- Gap 32px entre itens

Aplica-se a: Cloud (3 sub-abas), Seguranca (consolidado + boards).

---

## 6. Paginas de Login e Detalhe

### Login / Forgot / Reset / Change Password

- Fundo: `--bg-body`
- Card central: `--bg-card`, borda `--border`, border-radius 8px
- Inputs: fundo `--bg-main`, borda `--border`, focus `--accent`
- Botao primario: fundo `--accent`, hover `--accent-hover`, texto branco, sem gradiente
- Logo "Surf Telecom" acima do card
- Erro: `#f85149`, Sucesso: `#2ea043`
- Centralizado vertical e horizontal

### Paginas de Detalhe (solicitante, servico, atendente)

- Herdam layout com sidebar
- Breadcrumb: `Dashboard > Cloud > Solicitante: Nome` em `--text-muted`, ultimo item `--text`
- Breadcrumb clicavel substitui botao "Voltar"
- KPI cards no topo (3 cards: Total, Abertos, Fechados)
- Tabelas com mesmo estilo da secao 4

### Email Template

- Sem alteracao.

---

## 7. Responsividade e Mobile

### Breakpoints

- `> 1200px`: layout completo, sidebar 220px
- `992-1200px`: KPIs 3 colunas, graficos 2 colunas
- `768-992px`: sidebar oculta, hamburger, KPIs 2 colunas, graficos 1 coluna
- `< 768px`: KPIs 1 coluna, tabelas scroll horizontal, padding reduzido

### Sidebar em mobile (< 992px)

- Oculta por padrao
- Hamburger no header
- Overlay com fundo `rgba(0,0,0,0.5)`
- Fecha ao clicar fora ou X
- Slide da esquerda, 0.2s

### Tabelas em mobile

- `overflow-x: auto`
- Header sticky mantido
- Largura minima 600px

---

## Arquivos afetados

| Arquivo | Mudanca |
|---------|---------|
| `report/templates/dashboard.html` | Rewrite completo do CSS + reestruturacao HTML (sidebar, cards, graficos, tabelas) |
| `report/templates/login.html` | Nova paleta dark alinhada |
| `report/templates/forgot_password.html` | Nova paleta dark alinhada |
| `report/templates/reset_password.html` | Nova paleta dark alinhada |
| `report/templates/change_password.html` | Nova paleta dark alinhada |
| `report/templates/chamados_solicitante.html` | Sidebar + breadcrumb + nova paleta |
| `report/templates/chamados_servico.html` | Sidebar + breadcrumb + nova paleta |
| `report/templates/chamados_atendente.html` | Sidebar + breadcrumb + nova paleta |
| `report/templates/email.html` | Sem alteracao |

## Dependencias externas

- Chart.js 4.4.0 (mantido)
- chartjs-plugin-datalabels (novo, CDN)
- Google Fonts Inter (mantido)

## Fora de escopo

- Mudancas no backend (api_server.py, collectors, etc.)
- Mudancas na estrutura de dados
- Novos endpoints
- Email template
