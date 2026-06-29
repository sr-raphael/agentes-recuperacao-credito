# Multi-Agentes de Recuperação de Crédito com Gemini

## Preparar ambiente

1. Cria ambiente virtual

source ./venv/Scripts/activate

1. Instala requirements

pip install -r requirements.txt

1. Popula database

py ./app/database/seed_db.py

## Execução do projeto

1. Executa projeto

uvicorn app.main:app --reload

1. Documentação

[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

1. Abre o chat no navegador

[http://127.0.0.1:8000/chat](http://127.0.0.1:8000/chat)

1. Login no chat: CPF do seed + senha do cliente (padrão no seed: `12345`).

