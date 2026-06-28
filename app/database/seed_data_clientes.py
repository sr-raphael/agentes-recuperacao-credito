# bcrypt hash de "12345" (senha padrão de demo para todos os clientes seed)
SENHA_HASH_DEMO = "$2b$12$eKkP38KmRCzKRYFP/1whU.RYD3kcxMDAKZA7Nvm.fDSdX3oPn6YTW"

CLIENTES = [
    # Cliente 1: Bom score, atraso curto
    {
        "nome": "Flavio Silva",
        "cpf": "59126335000",
        "score": 850,
        "senha_hash": SENHA_HASH_DEMO,
    },
    # Cliente 2: Bom score, atraso longo
    {
        "nome": "Guilherme Dias",
        "cpf": "70388578009",
        "score": 900,
        "senha_hash": SENHA_HASH_DEMO,
    },
    # Cliente 3: Score medio, atraso curto
    {
        "nome": "Vagner Pereira",
        "cpf": "42014252076",
        "score": 420,
        "senha_hash": SENHA_HASH_DEMO,
    },
    # Cliente 4: Score medio, atraso longo
    {
        "nome": "Joaquim Oliveira",
        "cpf": "40591273020",
        "score": 450,
        "senha_hash": SENHA_HASH_DEMO,
    },
    # Cliente 5: Score baixo, atraso curto
    {
        "nome": "Mariana Santos",
        "cpf": "66710722058",
        "score": 150,
        "senha_hash": SENHA_HASH_DEMO,
    },
    # Cliente 6: Score baixo, atraso longo
    {
        "nome": "Rodrigo Ferreira",
        "cpf": "22526801052",
        "score": 190,
        "senha_hash": SENHA_HASH_DEMO,
    },
]
