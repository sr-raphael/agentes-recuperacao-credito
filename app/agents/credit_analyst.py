import sqlite3
from pathlib import Path
from typing import Any


class CreditAnalystAgent:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            self.db_path = Path(__file__).resolve().parent.parent / "database" / "credito.db"
        else:
            self.db_path = Path(db_path)

    def get_contract_data(self, cpf: str):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT c.nome, c.score, ct.valor_original,
            ct.juros_acumulado, ct.numero_parcelas, ct.parcelas_abertas,
            ct.dias_atraso, ct.situacao
            FROM clientes c
            JOIN contratos ct ON c.id = ct.cliente_id
            WHERE c.cpf = ?
        """
        cursor.execute(query, (cpf,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return None

        data = dict(result)
        data["nome"] = data["nome"].strip().split()[0]
        return data

    def get_policy_data(self, score: int, dias_atraso: int):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = """
            SELECT descricao, perc_desc_principal_max, perc_desc_juros_max
            FROM politicas_negociacao
            WHERE ? BETWEEN score_min AND score_max
            AND ? BETWEEN atraso_min AND atraso_max
        """
        cursor.execute(query, (score, dias_atraso))
        result = cursor.fetchone()
        conn.close()

        return dict(result) if result else None

    def get_credit_limits(
        self, contract_data: dict[str, Any], policy_data: dict[str, Any]
    ) -> dict[str, Any]:
        vr_orig = float(contract_data["valor_original"])
        juros = float(contract_data["juros_acumulado"])
        perc_desc_max = float(policy_data["perc_desc_principal_max"]) / 100.0
        juros_desc_max = float(policy_data["perc_desc_juros_max"]) / 100.0

        def tier(mult: float) -> float:
            desc_princ = vr_orig * perc_desc_max * mult
            desc_juros = juros * juros_desc_max * mult
            return vr_orig + juros - desc_princ - desc_juros

        return {
            "principal": vr_orig,
            "juros": juros,
            "proposta_1": round(tier(0.33), 2),
            "proposta_2": round(tier(0.66), 2),
            "proposta_3": round(tier(1.0), 2),
        }

    def get_credit_analyst_data(self, cpf: str):
        """
        Retorna limites no formato esperado pelo Negociador
        ou dict com 'error' se não houver contrato/política.
        """
        contract_data = self.get_contract_data(cpf)
        if not contract_data:
            return {
                "error": "Contract not found",
                "instruction": (
                    "Informe que no momento não foi possível encontrar "
                    "um contrato ativo para o CPF informado"
                ),
            }

        policy_data = self.get_policy_data(
            contract_data["score"], contract_data["dias_atraso"]
        )
        if not policy_data:
            return {
                "error": "Negotiation policy not found",
                "instruction": (
                    "Informe que no momento não existe uma proposta de negociação "
                    "para o contrato informado"
                ),
            }

        proposal_limits = self.get_credit_limits(contract_data, policy_data)
        return {
            "status": "success",
            "contract_data": contract_data,
            "policy_data": policy_data,
            "proposal_limits": proposal_limits,
        }
