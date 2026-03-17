class DataPolicyAgent:
    def __init__(self, db_path="app/database/credito.db"):
        self.db_path = db_path

    def get_client_data(self, cpf: str):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row # Permite acessar colunas pelo nome
        cursor = conn.cursor()
        
        query = """
            SELECT c.nome, c.score, d.valor_principal, d.dias_atraso
            FROM clientes c
            JOIN dividas d ON c.id = d.cliente_id
            WHERE c.cpf = ?
        """
        cursor.execute(query, (cpf,))
        result = cursor.fetchone()
        conn.close()
        
        return dict(result) if result else None

    def fetch_full_context(self, cpf: str):
        # 1. Busca dados determinísticos no MySQL
        cliente = self.db.query(f"SELECT score, divida_total FROM clientes WHERE cpf = '{cpf}'")
        
        # 2. Busca regras de negócio no arquivo RAG/Markdown
        regras = self.read_rag_rules(cliente['score'])
        
        # 3. Retorna um "pacote de contexto" pronto para os agentes de IA
        return {
            "perfil": cliente,
            "limites_negociacao": regras,
            "data_consulta": "2026-03-17"
        }