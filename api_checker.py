import os
import httpx
import random
import string
import asyncio
import mercadopago
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- Modelos de Dados ---
class CardTokenData(BaseModel):
    token: str
    payment_method_id: str

class RawCardData(BaseModel):
    card: str

# --- Inicialização ---
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- Configuração ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
MP_PUBLIC_KEY = os.getenv("MP_PUBLIC_KEY")
PROXY_URL = os.getenv("PROXY_URL", None)
proxies = {"http://": PROXY_URL, "https://": PROXY_URL} if PROXY_URL else None

# --- Funções Auxiliares ---
async def estornar_pagamento(payment_id, headers):
    """Estorna um pagamento para não reter o valor do cliente."""
    try:
        refund_url = f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds"
        async with httpx.AsyncClient() as client:
            # Envia a requisição de estorno
            await client.post(refund_url, headers=headers, json={}, timeout=30.0)
    except Exception as e:
        # ⚠️ MELHORIA: Evita falha silenciosa. Se o estorno falhar, você saberá.
        print(f"ALERTA: Falha crítica ao estornar o pagamento ID {payment_id}. Erro: {e}")
        pass

async def processar_pagamento(token: str, payment_method_id: str):
    """Função centralizada para processar o pagamento."""
    random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
    payer_email = f"user_{random_user}@test.com"
    valor_aleatorio = round(random.uniform(0.77, 1.99), 2)
    url = "https://api.mercadopago.com/v1/payments"
    
    payload = {
        "transaction_amount": valor_aleatorio,
        "token": token,
        "payment_method_id": payment_method_id,
        "installments": 1,
        "payer": {"email": payer_email}
    }
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": os.urandom(16).hex()
    }
    
    async with httpx.AsyncClient(proxies=proxies) as client:
        resposta = await client.post(url, json=payload, headers=headers, timeout=60.0)
    
    resultado = resposta.json()
    status_code = resposta.status_code

    if status_code in [200, 201] and resultado.get("status") == "approved":
        payment_id = resultado.get("id")
        if payment_id:
            # Chama o estorno imediatamente
            await estornar_pagamento(payment_id, {"Authorization": headers["Authorization"]})
        return {"status": "LIVE", "valor_debitado": valor_aleatorio, "codigo": resultado.get("status_detail"), "nome": "Aprovado (Estornado)", "mensagem": "Pagamento debitado e estornado com sucesso."}

    status_detail = resultado.get("status_detail", "desconhecido")
    if status_detail == "cc_rejected_insufficient_amount":
        return {"status": "LIVE", "codigo": status_detail, "nome": "Saldo Insuficiente", "mensagem": "Cartão válido, mas sem saldo."}
    if resultado.get("status") == "in_process":
        return {"status": "REVIEW", "codigo": status_detail, "nome": "Antifraude", "mensagem": "Cartão com alto potencial, mas retido para análise."}
    
    return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado pelo emissor."}

# --- Rotas da API ---
@app.get("/")
def get_api_status():
    return {"status": "online", "version": "3.0.0-unified-fixed"}

@app.post("/verificar")
async def verificar_cartao_token(card_data: CardTokenData):
    """Rota para o frontend (index.html) que já envia o token."""
    await asyncio.sleep(random.uniform(1.5, 3.0))
    if not ACCESS_TOKEN:
        return JSONResponse(status_code=500, content={"status": "DIE", "mensagem": "ACCESS_TOKEN não configurado no servidor."})
    try:
        return await processar_pagamento(card_data.token, card_data.payment_method_id)
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"status": "DIE", "codigo": "PROXY_TIMEOUT", "mensagem": "A conexão via proxy demorou demais."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "mensagem": str(e)})

@app.post("/verificar_direto")
async def verificar_cartao_direto(data: RawCardData):
    """Nova rota para o checker do Termux, que envia o cartão cru."""
    if not ACCESS_TOKEN or not MP_PUBLIC_KEY:
        return JSONResponse(status_code=500, content={"status": "DIE", "mensagem": "ACCESS_TOKEN ou MP_PUBLIC_KEY não configurados na API."})
    
    try:
        partes = data.card.split('|')
        if len(partes) != 4:
            return JSONResponse(status_code=400, content={"status": "DIE", "codigo": "INVALID_FORMAT", "mensagem": "Formato do cartão inválido. Use: NUM|MES|ANO|CVV"})
        
        numero, mes, ano, cvv = partes[0], partes[1], partes[2], partes[3]
        sdk = mercadopago.SDK(ACCESS_TOKEN)
        
        request = {
            "card_number": numero,
            "expiration_month": int(mes),
            "expiration_year": int(ano),
            "security_code": cvv,
            "cardholder": {"name": "APROVADO TESTE", "identification": {"type": "CPF", "number": "12345678909"}}
        }
        
        token_response = sdk.card_token().create(request)

        if token_response.get("status") not in [200, 201]:
            return {"status": "DIE", "codigo": "TOKENIZATION_FAILED", "nome": "Falha ao gerar token", "mensagem": token_response.get("response", {}).get("message", "Erro desconhecido do Mercado Pago ao criar o token.")}

        token = token_response["response"]["id"]
        payment_method_id = token_response["response"]["payment_method"]["id"]

        return await processar_pagamento(token, payment_method_id)
        
    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"status": "DIE", "codigo": "PROXY_TIMEOUT", "mensagem": "A conexão via proxy demorou demais."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "mensagem": str(e)})

@app.get("/testar-proxy")
async def testar_proxy():
    if not PROXY_URL:
        return {"status": "inativo", "erro": "PROXY_URL não configurado."}
    
    test_url = "https://www.google.com"
    try:
        async with httpx.AsyncClient(proxies=proxies) as client:
            resposta = await client.get(test_url, timeout=30.0)
        if resposta.status_code == 200:
            return {"status": "ativo", "mensagem": "Conexão com o Google via proxy foi bem-sucedida."}
        else:
            return {"status": "inativo", "erro": f"Proxy conectou, mas o Google respondeu com status {resposta.status_code}"}
    except Exception as e:
        return {"status": "inativo", "erro": f"Falha total ao conectar através do proxy. Erro: {e}"}

