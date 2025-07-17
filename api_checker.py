# api_checker.py - VERSÃO FINAL E ESTÁVEL

import os
import requests
import random
import string
import time
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
proxies = {"http": PROXY_URL, "https": PROXY_URL} if PROXY_URL else None

@app.get("/")
def get_api_status():
    return {"status": "online", "version": "1.0.0-PRO"}

def estornar_pagamento(payment_id, headers):
    try:
        refund_url = f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds"
        requests.post(refund_url, headers=headers, json={}, timeout=20.0)
    except Exception:
        pass

@app.post("/verificar")
def verificar_cartao(request: Request):
    time.sleep(random.uniform(1.5, 3.0))

    if not ACCESS_TOKEN:
        return JSONResponse(status_code=500, content={"status": "DIE", "nome": "Erro de Configuração", "mensagem": "ACCESS_TOKEN não configurado no servidor."})

    try:
        dados = request.json()
        token = dados.get("token")
        payment_method_id = dados.get("payment_method_id")

        if not token or not payment_method_id:
            return JSONResponse(status_code=400, content={"status": "DIE", "nome": "Dados Ausentes", "mensagem": "O 'token' e o 'payment_method_id' são obrigatórios."})

        random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
        payer_email = f"user_{random_user}@test.com"
        valor_aleatorio = round(random.uniform(0.77, 1.99), 2)
        
        url = "https://api.mercadopago.com/v1/payments"
        payload = {"transaction_amount": valor_aleatorio, "token": token, "payment_method_id": payment_method_id, "installments": 1, "payer": {"email": payer_email}}
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json", "X-Idempotency-Key": os.urandom(16).hex()}
        
        resposta = requests.post(url, json=payload, headers=headers, timeout=60.0, proxies=proxies)
        resultado = resposta.json()
        status_code = resposta.status_code

        if status_code in [200, 201] and resultado.get("status") == "approved":
            payment_id = resultado.get("id")
            if payment_id:
                estornar_pagamento(payment_id, {"Authorization": headers["Authorization"], "Content-Type": headers["Content-Type"]})
            return {"status": "LIVE", "codigo": resultado.get("status_detail"), "nome": "Aprovado (Estornado)", "mensagem": f"Pagamento de R${valor_aleatorio:.2f} debitado e estornado."}

        status_detail = resultado.get("status_detail", "desconhecido")
        if status_detail == "cc_rejected_insufficient_amount":
            return {"status": "LIVE", "codigo": status_detail, "nome": "Saldo Insuficiente", "mensagem": "Cartão válido, mas sem saldo."}
        if resultado.get("status") == "in_process":
            return {"status": "DIE", "codigo": status_detail, "nome": "Recusado (Antifraude)", "mensagem": "Pagamento retido para análise de risco."}
        
        return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado pelo emissor."}

    except requests.exceptions.Timeout:
        return JSONResponse(status_code=504, content={"status": "DIE", "codigo": "PROXY_TIMEOUT", "nome": "Timeout no Proxy", "mensagem": "A conexão através do proxy demorou demais para responder."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno", "mensagem": str(e)})

@app.get("/testar-proxy")
def testar_proxy():
    if not PROXY_URL:
        return {"status": "inativo", "erro": "PROXY_URL não configurado."}
    
    test_url = "https://www.google.com"
    try:
        resposta = requests.get(test_url, timeout=30.0, proxies=proxies)
        if resposta.status_code == 200:
            return {"status": "ativo", "mensagem": "Conexão com o Google via proxy foi bem-sucedida."}
        else:
            return {"status": "inativo", "erro": f"Proxy conectou, mas o Google respondeu com status {resposta.status_code}"}
    except Exception as e:
        return {"status": "inativo", "erro": f"Falha ao conectar através do proxy: {e.__class__.__name__}"}
