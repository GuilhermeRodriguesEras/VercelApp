import json
import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TINY_TOKEN = "f751b8c151b478f9472103ef94669425592b01d1"


class ItemProposta(BaseModel):
    descricao: str
    codigo: Optional[str] = ""
    quantidade: float
    unidade: Optional[str] = "UN"
    preco_unitario: float


class ClienteProposta(BaseModel):
    nome: str
    cpf_cnpj: Optional[str] = ""
    aos_cuidados: Optional[str] = ""


class PropostaTinyPayload(BaseModel):
    natureza_operacao: str
    cliente: ClienteProposta
    vendedor: Optional[str] = ""
    introducao: Optional[str] = ""
    carrinho: List[ItemProposta]
    outros_itens_texto: Optional[str] = ""
    frete: Optional[float] = 0
    desconto: Optional[float] = 0
    forma_envio: Optional[str] = "A Combinar"
    validade_dias: Optional[int] = 3
    descricao_prazo_entrega: Optional[str] = ""
    observacoes: Optional[str] = ""
    assinatura: Optional[str] = ""


@app.get("/teste")
def teste():
    return {
        "status": "ok",
        "tiny_token_configurado": bool(TINY_TOKEN)
    }


@app.post("/{full_path:path}")
def criar_proposta(payload: PropostaTinyPayload, full_path: str):

    try:

        itens = []

        for item in payload.carrinho:

            itens.append({
                "item": {
                    "codigo": item.codigo,
                    "descricao": item.descricao,
                    "unidade": item.unidade,
                    "quantidade": item.quantidade,
                    "valor_unitario": item.preco_unitario
                }
            })

        proposta = {
            "natureza_operacao": payload.natureza_operacao,

            "cliente": {
                "nome": payload.cliente.nome,
                "cpf_cnpj": payload.cliente.cpf_cnpj,
                "aos_cuidados": payload.cliente.aos_cuidados
            },

            "vendedor": payload.vendedor,
            "introducao": payload.introducao,

            "itens": itens,

            "outros_itens": payload.outros_itens_texto,

            "valor_frete": payload.frete,
            "valor_desconto": payload.desconto,

            "forma_envio": payload.forma_envio,

            "validade": payload.validade_dias,

            "prazo_entrega": payload.descricao_prazo_entrega,

            "obs": payload.observacoes,

            "assinatura": payload.assinatura
        }

        print("PROPOSTA ENVIADA:")
        print(json.dumps(proposta, indent=4, ensure_ascii=False))

        response = requests.post(
            "https://api.tiny.com.br/api2/propostas.incluir.php",
            data={
                "token": TINY_TOKEN,
                "formato": "JSON",
                "proposta": json.dumps(proposta)
            },
            timeout=30
        )

        print("HTTP TINY:", response.status_code)
        print("RESPOSTA TINY:", response.text)

        return JSONResponse(
            status_code=response.status_code,
            content={
                "tiny_http_status": response.status_code,
                "tiny_response": response.json()
            }
        )

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "status": "erro",
                "detalhe": str(e)
            }
        )