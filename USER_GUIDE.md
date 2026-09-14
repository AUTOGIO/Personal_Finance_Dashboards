# Guia do Usuário — Ecossistema de Finanças Pessoais (USER_GUIDE)

> **Resumo Executivo:** Este guia prático e sem jargões explica o funcionamento do ecossistema de finanças pessoais local, composto por **duas planilhas Excel** e **dois dashboards HTML estáticos**, além do ritual semanal de manutenção, comandos essenciais do terminal, modelos de prompts para IA e dicas operacionais.

---

## 1. Visão Geral do Sistema

O ecossistema opera com a filosofia de **dois pares de planilha + painel visual**:

| Par | Planilha (Fonte) | Dashboard (Poster) | Foco Principal |
| :--- | :--- | :--- | :--- |
| **Dashboard de Patrimônio** | `data/wealthcommand.xlsx` | `bloomberg-terminal.html` | Acompanhamento global do patrimônio líquido, investimentos, fluxo de capital internacional, assinaturas gerais e inflação pessoal (NFC-e). |
| **Dashboard Operacional (iMac Ops)** | `data/command-center.xlsx` | `command-center.html` | Gestão operacional do ecossistema, status de repositórios git, projetos ativos, limites de alertas e métricas de hardware. |

### Regra de Ouro da Fonte da Verdade
* **Os painéis HTML são gerados a partir das planilhas.** Nunca edite valores diretamente nos arquivos `.html`, pois qualquer alteração manual será sobrescrita na próxima execução dos scripts geradores.
* **`wealthcommand.xlsx`:** Apenas a aba **`CALC`** é a fonte da verdade. Todas as métricas do `bloomberg-terminal.html` derivam exclusivamente dela.
* **`command-center.xlsx`:** Todas as **11 abas de entrada** são fontes da verdade (mapeamento 1:1 com as páginas do `command-center.html`).

---

## 2. Ritual Semanal de Atualização (Passo a Passo com Exemplos)

O ritual de manutenção semanal é recomendado para os **domingos às 20h** e segue 4 fases sequenciais:

```
┌──────────────┐     ┌──────────────────┐     ┌────────────────┐     ┌──────────────────────┐
│  1. COLETA   │ ──► │  2. WEALTH PASS  │ ──► │  3. OPS PASS   │ ──► │ 4. RECONCILIAÇÃO     │
│ (pasta raw/) │     │ (wealthcommand)  │     │ (command-ctr)  │     │ (Revisão nos Painéis)│
└──────────────┘     └──────────────────┘     └────────────────┘     └──────────────────────┘
```

### Fase 1: Coleta de Extratos (`Collect`)
1. Baixe os extratos bancários brutos em PDF/CSV, faturas de cartão de crédito e comprovantes de câmbio das instituições (Mercado Pago, Banco Inter, Banco do Brasil, Wise, etc.).
2. Salve os arquivos originais sem alteração na pasta `raw/` organizada por instituição (ex: `raw/mercado_pago/`, `raw/banco_inter/`).

### Fase 2: Passo do Patrimônio (`Wealth Pass`)
1. Abra a planilha `data/wealthcommand.xlsx` no Microsoft Excel.
2. Navegue até a aba **`CALC`**.
3. Atualize os saldos bancários, totais de capital investido e a seção de assinaturas (Seção 4D).
4. No terminal, execute:
   ```bash
   make open
   ```
5. **Confirmação:** Garanta que a mensagem final exiba `[ok] all N spot-checks passed`. O dashboard será aberto automaticamente no navegador.

### Fase 3: Passo Operacional (`Ops Pass`)
1. Abra a planilha `data/command-center.xlsx` no Microsoft Excel.
2. Preencha **apenas as células de input coloridas em azul**:
   * **`BALANCES` (A4:G17):** Atualize saldos confirmados e datas de checagem.
   * **`FX_OPS` (A4:I45):** Registre operações de câmbio com a direção correta (`Outbound`, `Inbound`, `IB Deposit`, `IB Withdraw`, `Fund Deposit`).
   * **`TRANSACTIONS` (A4:G67):** Lance as novas despesas do cartão. **Atenção:** gastos devem ser inseridos com valores negativos (ex: `-111.58`).
   * **`PIX` (A4:F41):** Lance movimentações via PIX e tarifas de IOF.
   * **`SUBSCRIPTIONS` (A4:J27):** Atualize status e classificação (`KEEP`, `CANCEL`, `REVIEW`).
   * **`REPOS` & `PROJECTS`:** Atualize o status dos repositórios locais e prioridades de projetos.
   * **`CONFIG` (A4:D16):** Ajuste limites de alerta (piso de liquidez, teto de cartão) apenas quando houver alteração de preferências.
3. No terminal, execute a reconstrução do painel:
   ```bash
   python3 scripts/generate_command_center.py
   ```
4. **Confirmação:** Verifique se o gerador retorna a mensagem `no MISMATCH` no balanço de tags HTML.

### Fase 4: Revisão e Reconciliação (`Review & Reconcile`)
1. Com ambos os dashboards abertos no navegador, faça uma inspeção visual comparando saldos, alertas e gastos mensais.
2. **Regra de Reconciliação:** Se houver divergências de valores entre os dois painéis (como a diferença no cálculo do Net Worth decorrente do tratamento do saque na Interactive Brokers), **não force a igualdade manual dos números**. Investigue os comprovantes na pasta `raw/` e ajuste a planilha proprietária daquela métrica específica antes de rodar os geradores novamente.

---

## 3. Guia de Comandos do Terminal (`Makefile` & Scripts)

| Comando | O que faz | Quando usar |
| :--- | :--- | :--- |
| `make check` | Valida a quantidade de abas das planilhas e a integridade de arquivos críticos. | Antes de iniciar a atualização semanal ou abrir o workspace. |
| `make regen` | Executa o patcher do dashboard de patrimônio (`bloomberg-terminal.html`). | Após atualizar a aba `CALC` no `wealthcommand.xlsx`. |
| `make open` | Roda o `make regen` e abre o dashboard de patrimônio no navegador. | Para gerar e visualizar o patrimônio rapidamente. |
| `python3 scripts/generate_command_center.py` | Reconstrói do zero o `command-center.html` lendo todas as abas operacionais. | Após atualizar a planilha `command-center.xlsx`. |
| `make regen-all` | Regenera ambos os dashboards estáticos em uma única chamada. | Para atualizar os dois painéis de forma rápida. |
| `make workspace` | Executa o `make check`, regenera ambos os painéis e posiciona as janelas no Spencer (3 monitores). | Ao sentar no computador para trabalhar no projeto. |
| `make clean` | Remove arquivos temporários `.DS_Store` e caches `__pycache__`. | Para manutenção e limpeza do repositório. |

---

## 4. Prompts Práticos para Assistentes de IA

Ao utilizar assistentes virtuais (Claude, Cursor, ChatGPT, Gemini) para auxiliar no ritual semanal, utilize os modelos de prompts testados e padronizados:

### Prompt 1: Revisão Semanal com Atualização de Planilhas
> *"Leia o arquivo AI_GUIDE.md. Em seguida, realize minha revisão semanal utilizando os extratos recentes armazenados na pasta raw/. Atualize ambas as planilhas (wealthcommand.xlsx na aba CALC e as abas de input do command-center.xlsx) onde houver dados sobrepostos. Reconcilie as operações de câmbio em FX_OPS contra os comprovantes sem criar planilhas paralelas. Identifique alertas ativos, sugira classificações KEEP/CANCEL/REVIEW para assinaturas e sinalize divergências entre os dashboards para reconciliação (sem forçar igualdade manual). Execute os geradores e confirme que as validações retornaram sucesso."*

### Prompt 2: Análise Somente de Leitura (Pós-Geração)
> *"Leia o arquivo AI_GUIDE.md. Analise os dashboards gerados bloomberg-terminal.html e command-center.html. Resuma os alertas prioritários, as ações de maior impacto financeiro e eventuais divergências entre os painéis. Não edite arquivos diretamente: liste exatamente quais células de qual planilha devem ser ajustadas e o motivo."*

---

## 5. Dicas de Ouro (`Tips & Best Practices`)

### 💡 Dica 1: Convenção de Sinais no Cartão de Crédito
Nas abas de transações (como `TRANSACTIONS` no `command-center.xlsx`), lançamentos de compras e despesas **devem sempre ser registrados como valores negativos** (ex: `-111.58`). Valores positivos são reservados para estornos ou pagamentos.

### 💡 Dica 2: Preservação de Fórmulas Automáticas
Na planilha `command-center.xlsx`, edite apenas as células de entrada (destacadas com fundo azul). Nunca digite valores por cima de células com fórmulas de cálculo (como totais de liquidez, idades de repositórios ou contadores de status).

### 💡 Dica 3: Gestão Inteligente de Assinaturas
Classifique seus serviços recorrentes em três filas bem definidas:
* **`KEEP`:** Serviços essenciais para sua produtividade e rotina.
* **`CANCEL`:** Serviços duplicados ou sem uso (ex: contas duplicadas de IA ou rádios online) para corte imediato de custos.
* **`REVIEW`:** Serviços sob avaliação com gastos variáveis (ex: créditos de IA) que exigem reavaliação mensal.

### 💡 Dica 4: Atualização da Inflação Pessoal (NFC-e)
Para atualizar o gráfico de inflação pessoal na aba **11 NFC-E** do *Bloomberg Terminal*:
1. Baixe novas notas fiscais eletrônicas em formato XML para `nfce/notas/NFCE_XML_*/`.
2. No terminal, execute: `cd nfce && python3 personal_inflation.py --verify-ground-truth`.
3. Volte à raiz do projeto e execute `make regen`.

### 💡 Dica 5: Segurança e Backups Fora do iCloud
Mantenha o repositório principal e seus backups locais fora do iCloud para evitar conflitos de sincronização e perda de fórmulas em reparos automáticos do Excel. Execute periodicamente o script de backup do sistema:
```bash
zsh scripts/backup.sh
```

---

## 6. Resolução de Problemas (`Troubleshooting`)

* **O dashboard exibe dados antigos após editar o Excel:**
  * *Causa:* As planilhas foram salvas, mas o script gerador não foi executado.
  * *Solução:* Execute `make open` (para patrimônio) ou `python3 scripts/generate_command_center.py` (para operacional).
* **Mensagem `KeyError` ou erro ao gerar o Command Center:**
  * *Causa:* Uma aba obrigatória da planilha foi renomeada ou removida.
  * *Solução:* Execute `make check` para identificar qual aba está ausente e restaure a estrutura original de 11 abas.
* **Divergência no valor do Net Worth entre os painéis:**
  * *Causa:* Trata-se de um item aberto conhecido (ex: tratamento de saques da Interactive Brokers via Wise).
  * *Solução:* Não force a igualdade manual dos números nos arquivos HTML ou Excel. Verifique o extrato original em `raw/` e ajuste apenas a planilha proprietária daquele dado.


## Fontes por seção e projeto de inflação

| Dashboard section | Source actually read |
|---|---|
| Wealth controls and subscription decisions | `data/wealthcommand.xlsx` → `CALC` |
| Transaction log and weekly rollup | `data/wealthcommand.xlsx` → `02 CAPITAL FLOWS` |
| Lifestyle table | `data/wealthcommand.xlsx` → `05 LIFESTYLE` |
| NFC-e tab | `nfce/personal_inflation_data.json` — frozen snapshot |
| Spending tab | Newest `reports/*_spending_by_month.csv` |
| Separate command-center dashboard | `data/command-center.xlsx` through its own generator |

`make regen` apenas renderiza as fontes salvas. Para novos extratos, execute o importador de gastos antes; para classificações de produtos, use o arquivo v3 em `../edu_price_analysis/02_Models/personal_inflation_tracker-v3_classificacao.xlsx` e depois `make refresh-categories` naquele projeto. As regras de produtos e de pagamentos são independentes; não some os dois totais.
