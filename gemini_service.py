import google.generativeai as genai
import os
import json
from datetime import datetime, timedelta, date as DateObject
import re
from typing import Union, Optional # Adicione esta linha

# Configurar API Key da Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("API Key da Gemini não encontrada. Defina GEMINI_API_KEY no arquivo .env")
genai.configure(api_key=GEMINI_API_KEY)

generation_config = {
    "temperature": 0.6, # Ajustar para mais ou menos criatividade/precisão
    "top_p": 0.9,
    "top_k": 40,
    "max_output_tokens": 2048, # Suficiente para um JSON pequeno
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash-latest", # Um modelo rápido e eficiente para essa tarefa
    generation_config=generation_config,
    safety_settings=safety_settings
)

def parse_relative_date(text_date: str) -> Optional[DateObject]:
    """Converte 'hoje', 'ontem', 'anteontem' para datas."""
    today = datetime.now().date()
    text_date_lower = text_date.lower()
    if "hoje" in text_date_lower:
        return today
    elif "ontem" in text_date_lower:
        return today - timedelta(days=1)
    elif "anteontem" in text_date_lower:
        return today - timedelta(days=2)
    # Adicionar mais casos se necessário (ex: "amanhã", "semana passada")
    return None

def normalize_date_string(date_str: str) -> str | None:
    """
    Tenta normalizar uma string de data para YYYY-MM-DD.
    Aceita DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY e casos relativos.
    """
    relative_date = parse_relative_date(date_str)
    if relative_date:
        return relative_date.strftime("%Y-%m-%d")

    # Remover palavras desnecessárias e normalizar separadores
    date_str_cleaned = re.sub(r"(em|no dia|dia)\s+", "", date_str.lower())
    date_str_cleaned = date_str_cleaned.replace("/", "-").replace(".", "-")

    # Tentar formatos comuns
    # Formato com ano de 2 dígitos (ex: 10-05-25) -> 2025
    if re.match(r"^\d{1,2}-\d{1,2}-\d{2}$", date_str_cleaned):
        try:
            dt_obj = datetime.strptime(date_str_cleaned, "%d-%m-%y")
            return dt_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Formato com ano de 4 dígitos (ex: 10-05-2025)
    if re.match(r"^\d{1,2}-\d{1,2}-\d{4}$", date_str_cleaned):
        try:
            dt_obj = datetime.strptime(date_str_cleaned, "%d-%m-%Y")
            return dt_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass
    # Formato YYYY-MM-DD
    if re.match(r"^\d{4}-\d{1,2}-\d{1,2}$", date_str_cleaned):
        try:
            dt_obj = datetime.strptime(date_str_cleaned, "%Y-%m-%d")
            return dt_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def extract_transaction_data(text_input: str, transaction_type: str) -> dict:
    """
    Usa a Gemini API para extrair valor, data e descrição.
    Retorna um dicionário com 'valor', 'data' (YYYY-MM-DD), 'descricao', ou 'error'.
    """
    prompt = f"""
    Você é um assistente inteligente especializado em extrair informações financeiras de texto em linguagem natural para um sistema de controle de dívidas.
    Analise o texto a seguir, que se refere a um(a) '{transaction_type}', e extraia o VALOR monetário, a DATA da transação e uma DESCRIÇÃO.

    Regras de Extração:
    1. VALOR: Deve ser um número decimal. Extraia apenas o número (ex: "200", "150.75"). Se houver "reais", "R$", ignore.
    2. DATA:
        - Converta datas relativas como "hoje", "ontem", "anteontem" para o formato YYYY-MM-DD. Considere a data atual: {datetime.now().date().strftime('%Y-%m-%d')}.
        - Se for uma data específica (ex: "10/05/2025", "dia 5 do mês passado"), converta para YYYY-MM-DD.
        - Se nenhuma data for explicitamente mencionada, assuma a data de HOJE ({datetime.now().date().strftime('%Y-%m-%d')}).
    3. DESCRIÇÃO: Capture o propósito da transação (ex: "pagar o conserto do carro", "lanche", "referente ao aluguel"). Se não houver descrição clara, pode ser uma string vazia ou um valor padrão como "{transaction_type.capitalize()}".

    Formato de Saída (JSON estrito):
    {{
      "valor": <numero_decimal_ou_inteiro>,
      "data": "<YYYY-MM-DD>",
      "descricao": "<texto_da_descricao_opcional>"
    }}

    Exemplos:
    - Texto: "Emprestei 200 reais ontem para pagar o conserto do carro" (Empréstimo, Hoje é {datetime.now().date().strftime('%Y-%m-%d')})
      JSON: {{"valor": 200, "data": "{(datetime.now().date() - timedelta(days=1)).strftime('%Y-%m-%d')}", "descricao": "pagar o conserto do carro"}}
    - Texto: "Ela pagou 150.50 reais hoje" (Pagamento, Hoje é {datetime.now().date().strftime('%Y-%m-%d')})
      JSON: {{"valor": 150.50, "data": "{datetime.now().date().strftime('%Y-%m-%d')}", "descricao": "Pagamento"}}
    - Texto: "emprestei 50 pila pro joao dia 10/05/2025 para o cinema" (Empréstimo)
      JSON: {{"valor": 50, "data": "2025-05-10", "descricao": "para o cinema"}}
    - Texto: "recebi 70 dela em 01-04-2025" (Pagamento)
      JSON: {{"valor": 70, "data": "2025-04-01", "descricao": "Pagamento"}}
    - Texto: "R$300 para a festa de aniversário" (Empréstimo, sem data explícita, Hoje é {datetime.now().date().strftime('%Y-%m-%d')})
      JSON: {{"valor": 300, "data": "{datetime.now().date().strftime('%Y-%m-%d')}", "descricao": "para a festa de aniversário"}}
    - Texto: "Pagou a dívida de 25 pratas." (Pagamento, sem data explícita, Hoje é {datetime.now().date().strftime('%Y-%m-%d')})
      JSON: {{"valor": 25, "data": "{datetime.now().date().strftime('%Y-%m-%d')}", "descricao": "Pagou a dívida"}}


    Texto do usuário para '{transaction_type}': "{text_input}"
    JSON extraído:
    """
    try:
        response = model.generate_content([prompt]) # Passar o prompt como uma lista de partes se necessário
        
        # Limpeza básica da resposta da API (remover ```json ... ```)
        cleaned_response_text = response.text.strip()
        if cleaned_response_text.startswith("```json"):
            cleaned_response_text = cleaned_response_text[7:]
        if cleaned_response_text.endswith("```"):
            cleaned_response_text = cleaned_response_text[:-3]
        
        data = json.loads(cleaned_response_text)

        # Validação e normalização dos dados extraídos
        if not isinstance(data.get("valor"), (int, float)) or data.get("valor") <= 0:
            return {"error": "Valor monetário inválido ou não encontrado."}
        
        data_str = data.get("data")
        normalized_date = None
        if data_str:
            normalized_date = normalize_date_string(str(data_str))
        
        if not normalized_date: # Se ainda não conseguiu normalizar, ou se Gemini retornou algo estranho
            # Tentar um fallback mais simples ou assumir hoje
            test_date_norm = normalize_date_string(text_input) # Tenta achar data no texto original se Gemini falhou
            if test_date_norm:
                normalized_date = test_date_norm
            else:
                 normalized_date = datetime.now().date().strftime("%Y-%m-%d") # Fallback final

        data["data"] = normalized_date

        if "descricao" not in data or not data["descricao"]:
            data["descricao"] = transaction_type.capitalize() # Descrição padrão

        return data

    except json.JSONDecodeError:
        error_msg = f"A IA retornou um formato JSON inválido. Resposta: {response.text if 'response' in locals() else 'N/A'}"
        print(error_msg)
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Erro ao processar sua solicitação com a IA: {str(e)}. Resposta da IA (se houver): {response.text if 'response' in locals() else 'N/A'}"
        print(error_msg)
        return {"error": error_msg}

# Exemplo de uso (para teste local)
if __name__ == "__main__":
    # Certifique-se de ter GEMINI_API_KEY no seu .env para testar
    test_cases_emprestimo = [
        "Emprestei 200 reais ontem para pagar o conserto do carro",
        "emprestei 50 pila pro joao dia 10/05/2025 para o cinema",
        "150 reais para maria em 01-04-2025, lanche",
        "dei 25 para fulano hoje cedo",
        "emprestimo de 300 para ciclano",
        "R$ 123,45 para a compra de material dia 2 de fevereiro de 2024", # Testa data por extenso
        "500 em 1/3/25", # Testa ano com 2 dígitos
    ]
    test_cases_pagamento = [
        "Ela pagou 150 reais hoje",
        "joao me pagou 25.50 em 12/05/2025 referente ao cinema",
        "recebi 70 da maria ontem",
        "pagamento de 100 do ciclano"
    ]

    print("--- TESTES EMPRÉSTIMO ---")
    for text in test_cases_emprestimo:
        print(f"Input: {text}")
        extracted = extract_transaction_data(text, "emprestimo")
        print(f"Extracted: {json.dumps(extracted, indent=2, ensure_ascii=False)}\n")

    print("\n--- TESTES PAGAMENTO ---")
    for text in test_cases_pagamento:
        print(f"Input: {text}")
        extracted = extract_transaction_data(text, "pagamento")
        print(f"Extracted: {json.dumps(extracted, indent=2, ensure_ascii=False)}\n")