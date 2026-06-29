"""Geração mock de PIX copia-e-cola e boleto (sem valor legal)."""

from __future__ import annotations

import hashlib
import re
from typing import Literal

from app.utils.negotiation_playbook import format_brl

PaymentMethod = Literal["pix", "boleto"]

_MOCK_DISCLAIMER = (
    "⚠️ DOCUMENTO SEM VALOR LEGAL — gerado apenas para demonstração do sistema. "
    "Não utilize para pagamento real."
)


def _seed(cpf: str, session_id: str) -> str:
    raw = f"{cpf}:{session_id}:demo-mock"
    return hashlib.sha256(raw.encode()).hexdigest()


def _mock_amount_cents(valor: float) -> str:
    cents = max(1, int(round(float(valor) * 100)))
    return str(cents).zfill(10)[-10:]


def mock_pix_copia_cola(cpf: str, session_id: str, valor: float) -> str:
    """PIX copia-e-cola fictício (formato EMV inspirado, não válido para pagamento)."""
    seed = _seed(cpf, session_id)
    txid = f"DEMO{seed[:20].upper()}"
    amount = _mock_amount_cents(valor)
    # Payload simplificado; CRC final é placeholder (demo).
    return (
        "00020126580014br.gov.bcb.pix"
        f"0136{txid}"
        "520400005303986"
        f"54{len(amount):02d}{amount}"
        "5802BR5913RECUP CREDITO6009SAO PAULO"
        "62070503***"
        "6304DEMO"
    )


def mock_boleto_linha_digitavel(cpf: str, session_id: str, valor: float) -> str:
    """Linha digitável fictícia de boleto bancário (47 posições, sem valor legal)."""
    seed = _seed(cpf, session_id)
    digits = re.sub(r"\D", "", seed)[:43]
    digits = digits.ljust(43, "0")

    # Montagem no padrão visual: blocos + DV + valor (apenas demonstração).
    bloco1 = f"2379{seed[0:5]}.{seed[5:10]}"
    bloco2 = f"{seed[10:15]}.{seed[15:21]}"
    bloco3 = f"{seed[21:26]}.{seed[26:32]}"
    dv = str(int(seed[32:34], 16) % 10)
    valor_cents = _mock_amount_cents(valor)
    bloco4 = f"{dv} {valor_cents[:5]} {valor_cents[5:]}"

    linha = f"{bloco1} {bloco2} {bloco3} {bloco4}"
    # Garante aparência de linha digitável mesmo se seed variar
    compact = re.sub(r"\D", "", linha)[:47].ljust(47, "0")
    return (
        f"{compact[0:5]}.{compact[5:10]} "
        f"{compact[10:15]}.{compact[15:21]} "
        f"{compact[21:26]}.{compact[26:32]} "
        f"{compact[32]} {compact[33:38]} {compact[38:47]}"
    )


def build_payment_confirmation(
    method: PaymentMethod,
    credit_context: dict,
    *,
    cpf: str,
    session_id: str,
) -> str:
    contract = credit_context.get("contract_data") or {}
    limits = credit_context.get("proposal_limits") or {}
    nome = contract.get("nome", "Cliente")
    valor = float(limits.get("proposta_1") or 0)
    if valor <= 0:
        valor = float(contract.get("valor_original") or 0) + float(
            contract.get("juros_acumulado") or 0
        )

    if method == "pix":
        codigo = mock_pix_copia_cola(cpf, session_id, valor)
        return (
            f"{nome}, segue o PIX copia e cola referente ao acordo simulado "
            f"({format_brl(valor)}):\n\n"
            f"{codigo}\n\n"
            f"{_MOCK_DISCLAIMER}"
        )

    linha = mock_boleto_linha_digitavel(cpf, session_id, valor)
    return (
        f"{nome}, segue a linha digitável do boleto simulado "
        f"({format_brl(valor)}):\n\n"
        f"{linha}\n\n"
        f"{_MOCK_DISCLAIMER}"
    )
