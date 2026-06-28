import json
import sqlite3
from pathlib import Path
from typing import Any


class NegotiationHistoryStore:
    """Persistência de turnos em historico_negociacao."""

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
                "SELECT name FROM sqlite_master WHERE type='table' AND name='historico_negociacao'"
            )
            if cur.fetchone() is None:
                return

            cur.execute("PRAGMA table_info(historico_negociacao)")
            cols = {row[1] for row in cur.fetchall()}
            if "session_id" not in cols:
                cur.execute(
                    "ALTER TABLE historico_negociacao ADD COLUMN session_id TEXT DEFAULT ''"
                )
            if "etapa" not in cols:
                cur.execute(
                    "ALTER TABLE historico_negociacao ADD COLUMN etapa TEXT"
                )
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_historico_cliente_session "
                "ON historico_negociacao(cliente_id, session_id)"
            )
            conn.commit()
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

    def save_turn(
        self,
        cpf: str,
        session_id: str,
        transcript: list[dict[str, str]],
        resultado_auditoria: str,
        *,
        etapa: str = "",
        acordo_fechado: bool = False,
    ) -> int | None:
        cliente_id = self.get_cliente_id(cpf)
        if cliente_id is None:
            return None

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO historico_negociacao (
                    cliente_id, session_id, etapa, transcricao_json,
                    acordo_fechado, resultado_auditoria
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    cliente_id,
                    session_id,
                    etapa,
                    json.dumps(transcript, ensure_ascii=False),
                    int(acordo_fechado),
                    resultado_auditoria,
                ),
            )
            conn.commit()
            return int(cur.lastrowid)
        finally:
            conn.close()

    def get_last_etapa(self, cpf: str, session_id: str) -> str | None:
        cliente_id = self.get_cliente_id(cpf)
        if cliente_id is None:
            return None

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT etapa
                FROM historico_negociacao
                WHERE cliente_id = ? AND session_id = ? AND etapa IS NOT NULL AND etapa != ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (cliente_id, session_id),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None
        finally:
            conn.close()

    def get_session_transcript(
        self, cpf: str, session_id: str
    ) -> list[dict[str, str]] | None:
        cliente_id = self.get_cliente_id(cpf)
        if cliente_id is None:
            return None

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT transcricao_json
                FROM historico_negociacao
                WHERE cliente_id = ? AND session_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (cliente_id, session_id),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return None
            data = json.loads(row[0])
            if not isinstance(data, list):
                return None
            return [
                {"role": str(m.get("role", "user")), "content": str(m.get("content", ""))}
                for m in data
                if isinstance(m, dict)
            ]
        finally:
            conn.close()

    def list_sessions(self, cpf: str, limit: int = 20) -> list[dict[str, Any]]:
        cliente_id = self.get_cliente_id(cpf)
        if cliente_id is None:
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT session_id,
                       MIN(data_interacao) AS iniciada_em,
                       MAX(data_interacao) AS ultima_em,
                       COUNT(*) AS turnos
                FROM historico_negociacao
                WHERE cliente_id = ?
                GROUP BY session_id
                ORDER BY ultima_em DESC
                LIMIT ?
                """,
                (cliente_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def clear_all_sessions(self, cpf: str) -> tuple[int, int] | None:
        """
        Remove todo o histórico de negociação do cliente.
        Retorna (sessoes_removidas, turnos_removidos) ou None se CPF não existir.
        """
        cliente_id = self.get_cliente_id(cpf)
        if cliente_id is None:
            return None

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(DISTINCT session_id), COUNT(*)
                FROM historico_negociacao
                WHERE cliente_id = ?
                """,
                (cliente_id,),
            )
            sessoes, turnos = cur.fetchone() or (0, 0)
            cur.execute(
                "DELETE FROM historico_negociacao WHERE cliente_id = ?",
                (cliente_id,),
            )
            conn.commit()
            return int(sessoes or 0), int(turnos or 0)
        finally:
            conn.close()
