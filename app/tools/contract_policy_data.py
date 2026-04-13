import sqlite3
from pathlib import Path


class DataContractPolicyAgent:
    def __init__(self, db_path="app/database/credito.db"):
        self.db_path = db_path

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
            SELECT descricao, perc_desc_principal_max, perc_desc_juros_max, altera_prazo, max_prazo
            FROM politicas_negociacao
            WHERE ? BETWEEN score_min AND score_max 
            AND ? BETWEEN atraso_min AND atraso_max
        """
        cursor.execute(query, (score, dias_atraso))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None

    def get_contract_policy_data(self, cpf: str):
        contract_data = self.get_contract_data(cpf)

        if not contract_data:
            return {
                "error": "Contract not found", 
                "instruction": "Informe que no momento não foi possível encontrar um contrato ativo para o CPF informado"
                }

        policy_data = self.get_policy_data(contract_data["score"], contract_data["dias_atraso"])

        if not policy_data:
            return {
                "error": "Negotiation policy not found", 
                "instruction": "Informe que no momento não existe uma proposta de negociação para o contrato informado"
                }

        return {
            "status": "success",	
            "contract_data": contract_data,
            "policy_data": policy_data
            }

    def get_client_limits(self, cpf: str):
        """
        Retorna limites no formato esperado pelo Negociador (valores numéricos + faixas de proposta)
        ou None se não houver contrato/política.
        """
        bundle = self.get_contract_policy_data(cpf)
        if bundle.get("error") or bundle.get("status") != "success":
            return None
        cd = bundle["contract_data"]
        pd = bundle["policy_data"]
        vo = float(cd["valor_original"])
        ja = float(cd["juros_acumulado"])
        pmax = float(pd["perc_desc_principal_max"]) / 100.0
        jmax = float(pd["perc_desc_juros_max"]) / 100.0

        def tier(mult: float) -> float:
            desc_p = vo * pmax * mult
            desc_j = ja * jmax * mult
            return vo + ja - desc_p - desc_j

        return {
            "principal": vo,
            "juros": ja,
            "proposta_1": round(tier(0.33), 2),
            "proposta_2": round(tier(0.66), 2),
            "proposta_3": round(tier(1.0), 2),
            "contract_data": cd,
            "policy_data": pd,
        }

