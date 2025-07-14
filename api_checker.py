import os
import httpx
import random
import string
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone # <--- ADICIONADO PARA O STATUS

# Carrega as variáveis de ambiente do arquivo .env (para teste local)
load_dotenv()

app = FastAPI()

# --- Bloco de CORS Corrigido ---
# Esta configuração garante que o navegador possa fazer a "sondagem"
# com o método OPTIONS antes de enviar os dados com POST.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],  # Explicitamente permite OPTIONS
    allow_headers=["*"],
)

# Pega o Access Token das variáveis de ambiente de forma segura
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

# ---- NOVA FUNCIONALIDADE: ENDPOINT DE STATUS DA API ----
# Seu painel vai usar esta rota para verificar se a API está "viva".
@app.get("/")
def get_api_status():
    return {
        "status": "online",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version": "v4-final-with-status" # Nova versão para confirmar a atualização
    }
# ---------------------------------------------------------

@app.post("/verificar")
async def verificar_token(request: Request):
    # Verifica se o Access Token foi configurado no servidor
    if not ACCESS_TOKEN:
        return JSONResponse(
            status_code=500, 
            content={
                "status": "DIE", 
                "codigo": "BACKEND_CONFIG_ERROR", 
                "nome": "Erro de Configuração", 
                "mensagem": "ACCESS_TOKEN não foi configurado no ambiente do servidor."
            }
        )

    dados = await request.json()
    token = dados.get("token")
    payment_method_id = dados.get("payment_method_id")

    if not token or not payment_method_id:
        return JSONResponse(
            status_code=400, 
            content={
                "status": "DIE", 
                "codigo": "BAD_REQUEST", 
                "nome": "Dados Ausentes", 
                "mensagem": "O 'token' e o 'payment_method_id' são obrigatórios."
            }
        )

    # Gera um e-mail aleatório para cada verificação para evitar bloqueios
    random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
    payer_email = f"user_{random_user}@test.com"

    url = "https://api.mercadopago.com/v1/payments"
    payload = {
        "transaction_amount": 0.98,
        "token": token,
        "payment_method_id": payment_method_id,
        "installments": 1,
        "payer": {
            "email": payer_email
        }
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": os.urandom(16).hex() # Previne cobranças duplicadas
    }

    try:
        async with httpx.AsyncClient() as client:
            resposta = await client.post(url, json=payload, headers=headers, timeout=15.0)
        
        resultado = resposta.json()

        # Lógica de LIVE/DIE
        if resposta.status_code in [200, 201] and resultado.get("status") == "approved":
            return {
                "status": "LIVE",
                "codigo": resultado.get("status_detail"),
                "nome": "Aprovado",
                "mensagem": "Pagamento de R$0,98 aprovado."
            }
        elif resultado.get("status_detail") == "cc_rejected_insufficient_amount":
            return {
                "status": "LIVE",
                "codigo": resultado.get("status_detail"),
                "nome": "Saldo Insuficiente",
                "mensagem": "Cartão válido, mas sem saldo para a cobrança."
            }
        else:
            mensagem_erro = "Pagamento não aprovado."
            if resultado.get("cause") and len(resultado.get("cause", [])) > 0:
                mensagem_erro = resultado["cause"][0].get("description", mensagem_erro)
            
            return {
                "status": "DIE",
                "codigo": resultado.get("status_detail", "desconhecido"),
                "nome": resultado.get("status", "erro"),
                "mensagem": mensagem_erro
            }

    except httpx.RequestError as e:
        return {
            "status": "DIE", "codigo": "NETWORK_ERROR", "nome": "Erro de Rede",
            "mensagem": f"Não foi possível conectar à API do Mercado Pago: {e.__class__.__name__}"
        }
    except Exception as e:
        return {
            "status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno do Servidor",
            "mensagem": str(e)
        }
        