import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from .seed_data_clientes import CLIENTES
    from .seed_data_contratos import CONTRATOS
    from .seed_data_politicas import POLITICAS
except ImportError:
    from seed_data_clientes import CLIENTES
    from seed_data_contratos import CONTRATOS
    from seed_data_politicas import POLITICAS

def seed_clientes_contratos(cursor: sqlite3.Cursor) -> None:
    cliente_ids_por_cpf: dict[str, int] = {}

    for cliente in CLIENTES:
        senha_hash = cliente.get("senha_hash")
        if not senha_hash:
            raise ValueError(
                f"Cliente {cliente.get('cpf')} sem senha_hash no seed_data_clientes"
            )
        cursor.execute(
            "INSERT INTO clientes (nome, cpf, score, senha_hash) VALUES (?, ?, ?, ?)",
            (
                cliente["nome"],
                cliente["cpf"],
                int(cliente["score"]),
                senha_hash,
            ),
        )
        cliente_ids_por_cpf[str(cliente["cpf"])] = int(cursor.lastrowid)

    for contrato in CONTRATOS:
        cpf = str(contrato["cpf"])
        cliente_id = cliente_ids_por_cpf.get(cpf)
        if cliente_id is None:
            raise ValueError(f"Contrato sem cliente correspondente para CPF: {cpf}")

        cursor.execute(
            """
            INSERT INTO contratos (
                cliente_id,
                valor_original,
                juros_acumulado,
                numero_parcelas,
                parcelas_abertas,
                dias_atraso,
                situacao
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cliente_id,
                float(contrato["valor_original"]),
                float(contrato["juros_acumulado"]),
                int(contrato["numero_parcelas"]),
                int(contrato["parcelas_abertas"]),
                int(contrato["dias_atraso"]),
                contrato["situacao"],
            ),
        )


def seed_politicas(cursor: sqlite3.Cursor) -> None:
    cursor.executemany(
        """
        INSERT INTO politicas_negociacao (
            descricao, score_min, score_max, atraso_min, atraso_max,
            perc_desc_principal_max, perc_desc_juros_max, altera_prazo, max_prazo
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        POLITICAS,
    )


def setup_database(reset_db: bool = True) -> Path:
    base_dir = Path(__file__).resolve().parent
    db_path = base_dir / "credito.db"
    schema_path = base_dir / "schema.sql"

    base_dir.mkdir(parents=True, exist_ok=True)

    if reset_db and db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        print("--- Criando Tabelas (schema.sql) ---")
        if not schema_path.exists():
            raise FileNotFoundError(f"schema.sql não encontrado em: {schema_path}")
        schema_sql = schema_path.read_text(encoding="utf-8")
        cursor.executescript(schema_sql)

        print("--- Populando Dados de Clientes e Contratos ---")
        seed_clientes_contratos(cursor)
        print("--- Populando Dados de Políticas ---")
        seed_politicas(cursor)

        conn.commit()
        print(f"OK: banco de dados criado em: {db_path}")
        return db_path
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()
