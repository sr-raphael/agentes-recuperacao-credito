import sqlite3
from pathlib import Path


class DataContractPolicyAgent:
    def __init__(self, db_path="app/database/credito.db"):
        self.db_path = db_path

    def get_contract_data(self, cpf: str):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Permite acessar colunas pelo nome
        cursor = conn.cursor()

        query = """
            SELECT c.nome, c.score, ct.valor_original AS valor_principal, ct.dias_atraso
            FROM clientes c
            JOIN contratos ct ON c.id = ct.cliente_id
            WHERE c.cpf = ?
        """
        cursor.execute(query, (cpf,))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None

    def get_policy_data(self, score: int, dias_atraso: int):
        return None

    

if __name__ == "__main__":
    # Caminho absoluto ao DB para funcionar de qualquer diretório de execução
    _db = Path(__file__).resolve().parent.parent / "database" / "credito.db"
    print(f"DB: {_db} (existe: {_db.exists()})")

    with sqlite3.connect(str(_db)) as _conn:
        _cur = _conn.cursor()
        _cur.execute("SELECT COUNT(*) FROM clientes")
        _n_cli = _cur.fetchone()[0]
        _cur.execute("SELECT COUNT(*) FROM contratos")
        _n_ct = _cur.fetchone()[0]
    print(f"Linhas: clientes={_n_cli}, contratos={_n_ct}")
    if _n_cli == 0 or _n_ct == 0:
        print(
            "A consulta usa JOIN com contratos: sem dados o retorno é None.\n"
            "Popule o banco: na pasta app/database rode: py seed_db.py"
        )

    agent = DataContractPolicyAgent(str(_db))
    cpf_exemplo = "12345678901"
    print(f"\nget_contract_data({cpf_exemplo!r}):")
    print(agent.get_contract_data(cpf_exemplo))

    print("\nget_contract_data('00000000000') (CPF inexistente):")
    print(agent.get_contract_data("00000000000"))

