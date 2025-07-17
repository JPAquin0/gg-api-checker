import os
import httpx
import random
import string
import asyncio
import json
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

try:
    with open("database_bins.json", 'r', encoding="utf-8") as f:
        DB_BINS = json.load(f)
except FileNotFoundError:
    DB_BINS = {}

def get_bin_info(bin_num):
    if bin_num in DB_BINS:
        info = DB_BINS[bin_num]
        return f"[{info.get('banco', 'N/A')}, {info.get('bandeira', 'N/A')}, {info.get('nivel', 'N/A')}]"
    try:
        response = httpx.get(f"https://bins.dev/api/{bin_num}", timeout=10)
        response.raise_for_status()
        data = response.json()
        banco = data.get('bank', 'N/A').upper()
        bandeira = data.get('scheme', 'N/A').upper()
        nivel = data.get('brand', 'N/A').upper()
        return f"[{banco}, {bandeira}, {nivel}]"
    except Exception:
        return "[API Pública - N/A]"

@app.get("/")
def get_api_status():
    return {"status": "online", "version": "3.0.1-PRO"}

async def estornar_pagamento(payment_id, headers):
    try:
        refund_url = f"https://api.mercadopago.com/v1/payments/{payment_id}/refunds"
        async with httpx.AsyncClient() as client:
            await client.post(refund_url, headers=headers, json={})
    except Exception:
        pass

@app.post("/verificar")
async def verificar_cartao(card_data: CardData):
    await asyncio.sleep(random.uniform(1.5, 3.0))
    if not ACCESS_TOKEN:
        return JSONResponse(status_code=500, content={"status": "DIE", "nome": "Erro de Configuração", "mensagem": "ACCESS_TOKEN não configurado."})

    try:
        url = "https://api.mercadopago.com/v1/payments"
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json", "X-Idempotency-Key": os.urandom(16).hex()}
        payload = {
            "transaction_amount": round(random.uniform(0.77, 1.99), 2),
            "token": card_data.token,
            "payment_method_id": card_data.payment_method_id,
            "installments": 1,
            "payer": {"email": f"user_{''.join(random.choices(string.ascii_lowercase, k=10))}@test.com"}
        }
        
        async with httpx.AsyncClient(proxies=proxies) as client:
            resposta = await client.post(url, json=payload, headers=headers, timeout=60.0)
        
        resultado = resposta.json()
        status_code = resposta.status_code
        bin_do_cartao = resultado.get('card', {}).get('first_six_digits')
        info_banco = get_bin_info(bin_do_cartao) if bin_do_cartao else "[N/A]"

        if status_code in [200, 201] and resultado.get("status") == "approved":
            payment_id = resultado.get("id")
            if payment_id:
                await estornar_pagamento(payment_id, {"Authorization": headers["Authorization"], "Content-Type": headers["Content-Type"]})
            return {"status": "LIVE", "codigo": resultado.get("status_detail"), "nome": "Aprovado (Estornado)", "mensagem": f"R${payload['transaction_amount']:.2f} {info_banco}"}

        status_detail = resultado.get("status_detail", "desconhecido")
        if status_detail == "cc_rejected_insufficient_amount":
            return {"status": "LIVE", "codigo": status_detail, "nome": "Saldo Insuficiente", "mensagem": info_banco}
        
        if resultado.get("status") == "in_process":
            return {"status": "REVIEW", "codigo": status_detail, "nome": "Antifraude", "mensagem": f"Cartão com potencial. {info_banco}"}
        
        return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado."}

    except httpx.TimeoutException:
        return JSONResponse(status_code=504, content={"status": "DIE", "codigo": "PROXY_TIMEOUT", "nome": "Timeout no Proxy", "mensagem": "A conexão via proxy demorou demais."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno", "mensagem": str(e)})

@app.get("/testar-proxy")
async def testar_proxy():
    if not PROXY_URL:
        return {"status": "inativo", "erro": "PROXY_URL não configurado."}
    try:
        async with httpx.AsyncClient(proxies=proxies) as client:
            resposta = await client.get("https://www.google.com", timeout=30.0)
        return {"status": "ativo"} if resposta.status_code == 200 else {"status": "inativo"}
    except Exception:
        return {"status": "inativo"}
