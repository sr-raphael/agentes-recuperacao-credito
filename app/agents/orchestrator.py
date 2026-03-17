# --- 3. FLUXO ORQUESTRADOR ---
def processar_negociacao(mensagem_cliente):
    # Passo 1: Consulta Política
    regras = agente_politica_credito(dias_atraso=400)
    
    # Passo 2: Negociador gera proposta
    prompt_negociador = f"Negocie com o cliente: '{mensagem_cliente}'. Limites: {regras}"
    proposta = model.generate_content(prompt_negociador).text
    
    print(f"\n[NEGOCIADOR]: {proposta}")

    # Passo 3: Auditoria (A "Mágica" do Multi-Agente)
    auditoria = agente_auditor(proposta, regras)
    
    if auditoria["aprovado"]:
        return f"\n✅ [AUDITADO E APROVADO]:\n{proposta}"
    else:
        return f"\n❌ [BLOQUEADO PELO AUDITOR]: {auditoria['motivo']}\nSugestão: {auditoria['correcao_sugerida']}"
