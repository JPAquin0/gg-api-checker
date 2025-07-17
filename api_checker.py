# api_checker.py - VERSÃO FINAL COM NOVA API DE CONSULTA DE BIN

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

# --- NOVA FUNÇÃO DE CONSULTA DE BIN ---
def get_bin_info(bin_num):
    """
    Busca informações da BIN em uma nova API, mais completa.
    """
    try:
        # Usando a API do Bincodes para dados mais precisos
        response = requests.get(f"https://api.bincodes.com/bin/?api_key=YOUR_API_KEY&bin={bin_num}&json=true")
        if response.status_code == 200:
            data = response.json()
            # Ajustamos para pegar os novos campos que esta API fornece
            bandeira = data.get('scheme', 'N/A').upper()
            banco = data.get('bank', 'N/A')
            nivel = data.get('card', 'N/A')
            return {"bandeira": bandeira, "banco": banco, "nivel": nivel}
    except Exception:
        pass
    return {"bandeira": "N/A", "banco": "N/A", "nivel": "N/A"}
# ------------------------------------

@app.get("/")
def get_api_status():
    return {"status": "online", "version": "2.1.0-bin-pro"}

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
        return JSONResponse(status_code=500, content={"status": "DIE", "nome": "Erro de Configuração", "mensagem": "ACCESS_TOKEN não configurado."})

    try:
        dados = request.json()
        token = dados.get("token")
        payment_method_id = dados.get("payment_method_id")

        if not token or not payment_method_id:
            return JSONResponse(status_code=400, content={"status": "DIE", "nome": "Dados Ausentes", "mensagem": "Token e payment_method_id são obrigatórios."})

        # --- LÓGICA DE VERIFICAÇÃO ATUALIZADA ---
        # 1. Primeiro, obtemos o ID do cartão para saber a BIN
        card_number_preview = "XXXX" # Em uma implementação real, precisaríamos do número do cartão aqui
        # Como o SDK do MP não nos dá o número direto, vamos simular
        # ou, em uma versão futura, poderíamos pedir o número do cartão no painel.
        
        # Por enquanto, a lógica principal continua
        random_user = ''.join(random.choices(string.ascii_lowercase, k=10))
        payer_email = f"user_{random_user}@test.com"
        valor_aleatorio = round(random.uniform(0.77, 1.99), 2)
        url = "https://api.mercadopago.com/v1/payments"
        payload = {"transaction_amount": valor_aleatorio, "token": token, "payment_method_id": payment_method_id, "installments": 1, "payer": {"email": payer_email}}
        headers = {"Authorization": f"Bearer {ACCESS_TOKEN}", "Content-Type": "application/json", "X-Idempotency-Key": os.urandom(16).hex()}
        
        resposta = requests.post(url, json=payload, headers=headers, timeout=60.0, proxies=proxies)
        resultado = resposta.json()
        status_code = resposta.status_code

        # Se for LIVE, agora vamos buscar os dados da BIN
        if resultado.get("status") in ["approved", "pending"] or resultado.get("status_detail") == "cc_rejected_insufficient_amount":
            bin_do_cartao = resultado.get('card', {}).get('first_six_digits')
            if bin_do_cartao:
                info_banco = get_bin_info(bin_do_cartao)
            else:
                info_banco = {"bandeira": "N/A", "banco": "N/A", "nivel": "N/A"}
        
        if status_code in [200, 201] and resultado.get("status") == "approved":
            payment_id = resultado.get("id")
            if payment_id:
                estornar_pagamento(payment_id, {"Authorization": headers["Authorization"], "Content-Type": headers["Content-Type"]})
            return {"status": "LIVE", "codigo": resultado.get("status_detail"), "nome": f"Aprovado ({info_banco['banco']})", "mensagem": f"Bandeira: {info_banco['bandeira']}, Nível: {info_banco['nivel']}"}

        status_detail = resultado.get("status_detail", "desconhecido")
        if status_detail == "cc_rejected_insufficient_amount":
            return {"status": "LIVE", "codigo": status_detail, "nome": f"Saldo Insuficiente ({info_banco['banco']})", "mensagem": f"Bandeira: {info_banco['bandeira']}, Nível: {info_banco['nivel']}"}
        
        if resultado.get("status") == "in_process":
             return {"status": "REVIEW", "codigo": status_detail, "nome": f"Antifraude ({info_banco['banco']})", "mensagem": f"Bandeira: {info_banco['bandeira']}, Nível: {info_banco['nivel']}"}
        
        return {"status": "DIE", "codigo": status_detail, "nome": f"Recusado ({resultado.get('status', 'erro')})", "mensagem": "Pagamento não aprovado pelo emissor."}

    except requests.exceptions.Timeout:
        return JSONResponse(status_code=504, content={"status": "DIE", "codigo": "PROXY_TIMEOUT", "nome": "Timeout no Proxy", "mensagem": "A conexão através do proxy demorou demais."})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "DIE", "codigo": "INTERNAL_SERVER_ERROR", "nome": "Erro Interno", "mensagem": str(e)})

