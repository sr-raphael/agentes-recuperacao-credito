import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("API_KEY"))

# Usamos o Flash para velocidade e baixo custo na auditoria
model = genai.GenerativeModel(os.getenv("AGENT_MODEL"))

# --- 1. AGENTE DE POLÍTICA (Mock) ---
def agente_politica_credito(dias_atraso):
    if dias_atraso > 360:
        return {"desconto_maximo": 60, "parcelas_max": 12}
    return {"desconto_maximo": 15, "parcelas_max": 6}

# --- 2. AGENTE AUDITOR (O "Cérebro" de Compliance) ---
def agente_auditor(proposta_negociador, regras_originais):
    """
    Analisa se o negociador respeitou os limites da política.
    Retorna True se aprovado, ou a razão da falha.
    """
    prompt_auditoria = f"""
    Você é um Auditor de Compliance Bancário.
    REGRAS RÍGIDAS: {regras_originais}
    PROPOSTA DO NEGOCIADOR: "{proposta_negociador}"

    TAREFA:
    1. O desconto oferecido é MAIOR que o permitido?
    2. O número de parcelas excede o permitido?
    3. A linguagem é agressiva ou inadequada?

    Responda APENAS em JSON no formato:
    {{"aprovado": boolean, "motivo": "string", "correcao_sugerida": "string"}}
    """
    
    # Configuração para garantir que o Gemini responda em JSON puro
    response = model.generate_content(
        prompt_auditoria, 
        generation_config={"response_mime_type": "application/json"}
    )
    import json
    return json.loads(response.text)

# --- 3. FLUXO ORQUESTRADO ---
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

# Teste
print(processar_negociacao("Preciso de 80% de desconto agora ou não pago."))