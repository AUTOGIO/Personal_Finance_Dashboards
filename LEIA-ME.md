# Personal_Finance · Fase 1 — Concluída

**Status:** ✅ Operacional · Congelado para manutenção semanal  
**Dashboards:** `bloomberg-terminal.html` (patrimônio) · `command-center.html` (ops iMac)

---

## Ritual semanal (Domingo 20h — lembrete no Calendar.app)

Ordem recomendada — **dois workbooks, não sincronizam sozinhos**:

1. Exportar extratos (MP, Inter, BB, BCB, assinaturas) → salvar em `raw/`
2. **Patrimônio** — atualizar `data/wealthcommand.xlsx` (aba **CALC** = fonte única)
3. Rodar `make open` — confirmar `[ok] all N spot-checks passed`
4. **Command center** — atualizar células de input em `data/command-center.xlsx`
   (BALANCES, FX_OPS, TRANSACTIONS, PIX, SUBSCRIPTIONS, REPOS, PROJECTS, CONFIG)
5. Rodar `python3 scripts/generate_command_center.py` — confirmar `[ok] all N ops spot-checks passed` e `[ok] wrote command-center.html` (sem MISMATCH)
6. Conferir ambos os dashboards; divergências entre eles → investigar, **não forçar igual**

Detalhe completo (EN): `USER_GUIDE.md` §4 · prompts para IA: `AI_GUIDE.md` → Weekly workflows

**Sincronizar nos dois workbooks** quando mudar: assinaturas, transações de cartão, saldos.
Divergências entre dashboards → usar checklist de reconciliação em `USER_GUIDE.md` §4
(source ownership, data "as-of", moeda, diferenças esperadas, disposição de gaps).

---

## Estrutura de pastas

```
Personal_Finance/
├── bloomberg-terminal.html       dashboard patrimônio
├── command-center.html           dashboard ops
├── Makefile                      make regen / check / workspace / open / clean
├── data/
│   ├── wealthcommand.xlsx        patrimônio · aba CALC = fonte única
│   └── command-center.xlsx       ops · 11 abas
├── scripts/
│   ├── regenerate_dashboard.py
│   ├── generate_command_center.py
│   ├── check_integrity.py
│   └── backup.sh
├── reports/                      snapshots pontuais (docx)
└── raw/                          extratos brutos por instituição
```

**Local canônico:** `~/Documents/GitHub/Personal_Finance` (fora do iCloud).

Ver `README.md` para o detalhe de cada pasta e a resposta de "qual é a fonte da verdade".

**NFC-e (aba 11):** snapshot de 2026-08-19 — `nfce/notas/` está vazio; refresh
só depois de recuperar os XMLs (Time Machine, manual).

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
