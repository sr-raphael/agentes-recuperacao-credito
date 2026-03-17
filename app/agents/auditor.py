import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("API_KEY"))
model = genai.GenerativeModel(os.getenv("AGENT_MODEL_AUDITOR"))

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