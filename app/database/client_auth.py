import sqlite3
from pathlib import Path

from app.security.passwords import hash_password, verify_password

DEFAULT_SEED_PASSWORD = "12345"


class ClientAuthStore:
    """Autenticação de clientes (CPF + senha em hash no banco)."""

    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            self.db_path = Path(__file__).resolve().parent / "credito.db"
        else:
            self.db_path = Path(db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='clientes'"
            )
            if cur.fetchone() is None:
                return

            cur.execute("PRAGMA table_info(clientes)")
            cols = {row[1] for row in cur.fetchall()}
            if "senha_hash" not in cols:
                cur.execute("ALTER TABLE clientes ADD COLUMN senha_hash TEXT")

            cur.execute(
                "SELECT id FROM clientes WHERE senha_hash IS NULL OR senha_hash = ''"
            )
            missing = cur.fetchall()
            if missing:
                default_hash = hash_password(DEFAULT_SEED_PASSWORD)
                cur.executemany(
                    "UPDATE clientes SET senha_hash = ? WHERE id = ?",
                    [(default_hash, row[0]) for row in missing],
                )

            conn.commit()
        finally:
            conn.close()

    def authenticate(self, cpf: str, senha: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT senha_hash FROM clientes WHERE cpf = ?",
                (cpf,),
            )
            row = cur.fetchone()
            if not row:
                return False
            return verify_password(senha, row[0] or "")
        finally:
            conn.close()

    def get_cliente_id(self, cpf: str) -> int | None:
        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM clientes WHERE cpf = ?", (cpf,))
            row = cur.fetchone()
            return int(row[0]) if row else None
        finally:
            conn.close()
