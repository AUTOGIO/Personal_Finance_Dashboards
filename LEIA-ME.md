# Personal_Finance · Fase 1 — Concluída

**Status:** ✅ Operacional · Congelado para manutenção semanal  
**Dashboard:** `bloomberg-terminal.html` (raiz do repo) → abrir em qualquer navegador

---

## O que foi construído

| Componente | Detalhe |
|---|---|
| Dashboard HTML | 10 tabs · Bloomberg-terminal dark theme · SVG inline (sem lib) · sem servidor |
| Overview | KPIs mensais H1 2026 · gráficos MP + contas |
| Weekly Tracker | Semana a semana · MP Card + Inter · toggle transfers |
| Card Transactions | 146 txs (MP Cartão completo) · filtro por merchant/categoria |
| Subscriptions | Decision matrix · Cancel / Keep / Review |
| Banks | Inter extrato · CCS completo · Pix keys · Câmbio BCB |
| Online Spend | Breakdown categorizado · ML Purchases itemizados |
| Cancel Tracker | localStorage · 11 itens · status persistido |
| Cash Bridge | Waterfall R$122K gap explicado |

**Período:** Jan–Jun 2026 · **Contas:** Mercado Pago · Banco Inter · BB Brasil · BCB Registrato

---

## Ritual semanal (Domingo 20h — lembrete no Calendar.app)

1. Exportar extrato MP → PDF ou CSV, salvar em `raw/mercado_pago/`
2. Screenshots de transações (BB, Inter) se houver, salvar em `raw/<banco>/screenshots/`
3. Atualizar as linhas correspondentes em `data/wealthcommand.xlsx` (aba CALC = fonte única)
4. Rodar `make open` (regenera o dashboard e abre no navegador)
5. Conferir os KPIs no topo de cada aba

---

## Estrutura de pastas

```
Personal_Finance/
├── bloomberg-terminal.html       dashboard — abrir direto no navegador
├── Makefile                      make regen / make open / make clean
├── data/wealthcommand.xlsx       workbook · aba CALC = fonte única
├── scripts/regenerate_dashboard.py
├── reports/                      snapshots pontuais (docx), não auto-atualizados
└── raw/                          extratos brutos por instituição (MP, Inter, BB, BCB, ML/iFood, NFC-e)
```

Ver `README.md` para o detalhe de cada pasta e a resposta de "qual é a fonte da verdade".

---

## Patrimônio confirmado (Jul 2026)

| Conta | Saldo |
|---|---|
| Banco Inter 662710-2 | R$ 18.934,67 (13/07 · total) |
| Mercado Pago | R$ 4.262,23 (12/07) |
| BB Brasil (conta corrente) | R$ 0,00 (13/07 · Rende Fácil não no extrato) |
| **Liquidez BR (BB+MP+Inter)** | **R$ 23.196,90** |
| BB Americas (Miami) | US$ 250.000 |
| Interactive Brokers | crescendo |

Nota: o saldo R$ 42.112,59 (30/06) era do **Inter** (conta 6627102), não do BB.

Renda: R$ 18.000/mês · Dívida: R$ 0,00

---

## Remessas internacionais H1 2026 (BCB confirmado)

| Destino | Total |
|---|---|
| BB Americas (Miami) | USD 110.929 |
| Interactive Brokers (Topázio + Wise) | USD 38.801 |
| Reino Unido (Wise) | USD 17.350 |
| Fundos BRL (Nat. 67043) | R$ 175.766 |

---

## Fase 2 — Critérios para ir nativo (Swift)

Só iniciar quando TODOS verdadeiros:

- [ ] 3 ciclos semanais de upload manual concluídos
- [ ] Ponto de dor identificado: leitura de PDFs / upload de screenshots é o gargalo
- [ ] Tempo disponível para SwiftUI + Vision + Foundation Models
- [ ] HTML não resolve mais

Stack Fase 2:
Vision (OCR local) → Foundation Models (categorização) → SwiftUI
+ App Intents (Siri: "mostrar gastos desta semana")
+ Language Model Protocol (troca Foundation Models / Claude / LM Studio)

NÃO fazer antes: App Intents, SwiftUI, MLX, Metal, AUTOGIO ecosystem.

---

## Contas BCB ativas (CCS 29/06/2026)

BB · Ágora CTVM · Bradesco · XP Investimentos · Caixa Econômica
Banco Inter · Mercado Pago · BIPA · Celcoin · Wise Brasil

---

*Fase 1 concluída Jul 2026*
