# api_checker.py

import os
import httpx
import random
import string
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

# --- Configuração da Aplicação ---
app = FastAPI()

# Permite que seu painel na Netlify acesse a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    methods=["*"],
    headers=["*"],
)

# --- Carregamento Seguro das Chaves e do Proxy ---
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PROXY_URL = os.getenv("PROXY_URL", None) # Pega a URL do proxy

# --- Endpoints da API ---

@app.get("/")
def get_api_status():
    """Endpoint para o Netlify verificar se a API está online."""
    return {
        [span_0](start_span)"status": "online",[span_0](end_span)
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "version": "v7-final-pro"
    }

@app.post("/verificar")
async def verificar_cartao(request: Request):
    """Endpoint principal que verifica o cartão."""
    await asyncio.sleep(random.uniform(1.5, 3.0)) # Delay humanizado

    if not ACCESS_TOKEN:
        [span_1](start_span)return JSONResponse(status_code=500, content={"status": "DIE", "nome": "Erro de Configuração", "mensagem": "ACCESS_TOKEN não configurado no servidor."})[span_1](end_span)

    # Monta a configuração do proxy para a requisição
    proxies = {"http://": PROXY_URL, "https://": PROXY_URL} if PROXY_URL else None

    try:
        dados = await request.json()
        token = dados.get("token")
        payment_method_id = dados.get("payment_method_id")

        if not token or not payment_method_id:
            [span_2](start_span)return JSONResponse(status_code=400, content={"status": "DIE", "nome": "Dados Ausentes", "mensagem": "O 'token' e o 'payment_method_id' são obrigatórios."})[span_2](end_span)

        # Geração de dados aleatórios para cada transação
        random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
        payer_email = f"user_{random_user}@test.com"
        [span_3](start_span)valor_aleatorio = round(random.uniform(0.77, 1.99), 2)[span_3](end_span)

        url = "https://api.mercadopago.com/v1/payments"
        payload = {
            "transaction_amount": valor_aleatorio,
            "token": token,
            "payment_method_id": payment_method_id,
            "installments": 1,
            "payer": {"email": payer_email}
        }
        headers = {
            [span_4](start_span)"Authorization": f"Bearer {ACCESS_TOKEN}",[span_4](end_span)
            "Content-Type": "application/json",
            "X-Idempotency-Key": os.urandom(16).hex()
        }

        async with httpx.AsyncClient(proxies=proxies) as client:
            resposta = await client.post(url, json=payload, headers=headers, timeout=20.0)
        
        resultado = resposta.json()
        status_code = resposta.status_code

        # --- LÓGICA DE INTERPRETAÇÃO RIGOROSA ---
        if status_code in [200, 201] and resultado.get("status") == "approved":
            [span_5](start_span)return {"status": "LIVE", "codigo": resultado.get("status_detail"), "nome": "Aprovado", "mensagem": f"Pagamento de R${valor_aleatorio:.2f} debitado com sucesso."}[span_5](end_span)

        status_detail = resultado.get("status_detail", "desconhecido")

        if status_detail == "cc_rejected_insufficient_amount":
            [span_6](start_span)return {"status": "LIVE", "codigo": status_detail, "nome": "Saldo Insuficiente", "mensagem": "Cartão válido, mas sem saldo para a cobrança."}[span_6](end_span)

        # CORREÇÃO CRÍTICA: "Em Revisão" agora é tratado como DIE
        if resultado.get("status") == "in_process":
            [span_7](start_span)return {"status": "DIE", "codigo": status_detail, "nome": "Recusado (Antifraude)", "mensagem": "Pagamento retido para análise de risco."}[span_7](end_span)

        # Resposta padrão para outros tipos de recusa
        [span_8](start_span)return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado pelo emissor."}[span_8](end_span)

    except Exception as e:
        [span_9](start_span)return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno do Servidor", "mensagem": str(e)})[span_9](end_span)
        