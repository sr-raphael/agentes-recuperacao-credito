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

API: POST /v1/negociar · Health: GET /health · Docs: /docs
