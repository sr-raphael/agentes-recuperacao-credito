# Multi-Agentes de Recuperação de Crédito com Gemini

Sistema multi-agente para negociação de dívidas: analista de crédito (SQLite), negociador e auditor (Gemini), com chat web, autenticação JWT e persistência de métricas por turno.

## Arquitetura

```
Cliente (chat) → FastAPI → CoordinatorAgent
                              ├─ CreditAnalystAgent   (contrato + política)
                              ├─ NegotiatorAgent      (Gemini)
                              ├─ AuditorAgent         (Gemini)
                              └─ NegotiationHistoryStore (SQLite)
```

**Fluxo por turno:** guardrails de entrada → roteiro conversacional → LLM + auditoria (na etapa de negociação) → gravação em `historico_negociacao` (transcrição, métricas LLM, custo, latência).

## Pré-requisitos

- Python 3.11+
- Chave da API Gemini ([Google AI Studio](https://aistudio.google.com/))



## Configuração

1. Clone o repositório e crie o ambiente virtual:

```bash
python -m venv venv

# Git Bash / Linux
source ./venv/Scripts/activate
# PowerShell
# .\venv\Scripts\activate
```

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

1. Configure variáveis de ambiente:

```bash
cp .env.example .env
```


| Variável                 | Descrição                                         |
| ------------------------ | ------------------------------------------------- |
| `API_KEY`                | Chave Gemini                                      |
| `JWT_SECRET_KEY`         | Assinatura dos tokens JWT                         |
| `AGENT_MODEL_NEGOCIATOR` | Modelo do negociador (padrão: `gemini-2.5-flash`) |
| `AGENT_MODEL_AUDITOR`    | Modelo do auditor (padrão: `gemini-2.5-flash`)    |


1. Popule o banco de dados:

```bash
py ./app/database/seed_db.py
```



## Executar

```bash
uvicorn app.main:app --reload
```


| Recurso | URL                                                          |
| ------- | ------------------------------------------------------------ |
| Chat    | [http://127.0.0.1:8000/chat](http://127.0.0.1:8000/chat)     |
| Swagger | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)     |
| Health  | [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) |




### Login (seed)

Todos os clientes do seed usam senha `12345`.


| Cliente          | CPF         |
| ---------------- | ----------- |
| Flavio Silva     | 59126335000 |
| Guilherme Dias   | 70388578009 |
| Vagner Pereira   | 42014252076 |
| Joaquim Oliveira | 40591273020 |
| Mariana Santos   | 66710722058 |
| Rodrigo Ferreira | 22526801052 |




## API


| Método   | Rota                     | Auth   |
| -------- | ------------------------ | ------ |
| `POST`   | `/v1/auth/login`         | —      |
| `POST`   | `/v1/negociar`           | Bearer |
| `GET`    | `/v1/negociar/historico` | Bearer |
| `GET`    | `/v1/negociar/sessoes`   | Bearer |
| `DELETE` | `/v1/negociar/sessoes`   | Bearer |


O CPF do body/query deve ser o mesmo do token JWT.

Scripts Postman: `postman/pre-request.js` (login automático com CPF/senha fixos do seed).

## Métricas e gráficos

Negociações gravam por turno em `historico_negociacao`:

- `llm_metrics_json` — tokens, latência e custo por agente
- `custo_estimado_usd`, `resultado_auditoria`, `acordo_fechado`
- `faixa_proposta`, `valor_citado` — proposta inferida do texto enviado ao cliente
- `auditoria_json` — veredito completo do auditor LLM (turnos em `negociacao`)

Para gerar gráficos e KPIs do TCC:

```bash
python -m jupyter notebook notebooks/analise_metricas.ipynb
```

O notebook está organizado em:

- **A.** Resumo executivo (`kpis_resumo.csv`)
- **B.** Eficácia (funil, conversão, turnos até acordo, faixa máxima)
- **C.** Aderência (auditor, faixa/valor, motivos de rejeição)
- **D.** Segurança (bloqueios guardrail)
- **E.** Operacional LLM (tokens, latência, custo)
- **F.** Avaliação por categoria de modelos (benchmark: Leves, Mistos, Pesados a partir de `negociacoes.csv`)

Saídas em `notebooks/output/` (PNG + HTML interativo).

Loader Python: `analytics/metrics_loader.py`.

## Estrutura do projeto

```
app/
├── agents/          # Coordinator, negociador, auditor, analista de crédito
├── api/             # Rotas REST (auth, negociação)
├── database/        # Schema, seed, histórico SQLite
├── domain/          # Modelos Pydantic
├── security/        # JWT e hash de senhas
├── static/chat/     # Frontend do chat
└── utils/           # Guardrails, playbook, métricas LLM
analytics/           # Carga de métricas para notebooks
notebooks/           # Análise de métricas
postman/             # Scripts de autenticação
```



## Segurança

- Senhas em bcrypt no banco; JWT válido por 1 hora
- Guardrails de entrada (`input_guardrails.py`): injection, tamanho, CPF — bloqueios em `historico_negociacao` com `motivo_bloqueio` e mensagem mascarada em `transcricao_json`
- Auditor de compliance na saída do negociador (limites de crédito)

