import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("API_KEY"))

# Usamos o Flash para velocidade e baixo custo na auditoria
model = genai.GenerativeModel(os.getenv("AGENT_MODEL"))



# Teste
print(processar_negociacao("Preciso de 80% de desconto agora ou não pago."))