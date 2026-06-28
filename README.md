# Multi-Agentes de Recuperação de Crédito com Gemini

1. Cria ambiente virtual
source ./venv/Scripts/activate

2. Instala requirements
pip install -r requirements.txt

3. Popula database
py ./app/database/seed_db.py

4. Executa projeto
uvicorn app.main:app --reload

5. Abre o chat no navegador
http://127.0.0.1:8000/chat

API: POST /v1/negociar · GET/DELETE /v1/negociar/sessoes · Health: GET /health · Docs: /docs

Limpar sessões de um CPF:
```http
DELETE /v1/negociar/sessoes?cpf=66710722058
```

Consultar histórico no SQLite:
```sql
SELECT h.id, c.cpf, h.session_id, h.data_interacao, h.resultado_auditoria, h.transcricao_json
FROM historico_negociacao h
JOIN clientes c ON c.id = h.cliente_id
ORDER BY h.id DESC;
```
