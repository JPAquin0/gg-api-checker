from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import requests

app = FastAPI()

ACCESS_TOKEN = "APP_USR-1375322433970930-071316-4001ac4bae9b7991abab0a72c0155ed4-290194608"  # Sua chave de produção

@app.post("/verificar")
async def verificar_token(request: Request):
    dados = await request.json()
    token = dados.get("token")

    if not token:
        return JSONResponse(status_code=400, content={"status": "DIE", "codigo": "MP-100", "nome": "Token ausente", "mensagem": "Token não foi recebido pelo backend."})

    # Criar pagamento simulado de R$0,98
    url = "https://api.mercadopago.com/v1/payments"
    payload = {
        "transaction_amount": 0.98,
        "token": token,
        "installments": 1,
        "payer": {
            "email": "checkout@ggholder.com"  # E-mail fictício para teste
        }
    }

    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        resposta = requests.post(url, json=payload, headers=headers)
        resultado = resposta.json()

        if resposta.status_code == 201 and resultado.get("status") == "approved":
            return {
                "status": "LIVE",
                "codigo": resultado.get("status_detail"),
                "nome": "Aprovado",
                "mensagem": "Pagamento de R$0,98 aprovado."
            }
        else:
            return {
                "status": "LIVE",
                "codigo": resultado.get("status_detail", "desconhecido"),
                "nome": resultado.get("status", "erro"),
                "mensagem": resultado.get("error_message") or "Pagamento não aprovado."
            }

    except Exception as erro:
        return {
            "status": "DIE",
            "codigo": "MP-500",
            "nome": "Erro interno",
            "mensagem": str(erro)
        }