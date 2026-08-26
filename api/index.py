import json
import requests
from fastapi import FastAPI, HTTPException, Request
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

# Captura exceções não tratadas e garante o envio de JSON com cabeçalhos CORS
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": f"Erro interno do servidor: {str(exc)}"},
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
    natureza_operacao: Optional[str] = "Venda de Mercadorias para Consumidor Final"
    cliente: ClienteProposta
    vendedor: Optional[str] = "Departamento de vendas"
    introducao: Optional[str] = ""
    carrinho: List[ItemProposta]
    outros_itens_texto: Optional[str] = ""
    frete: Optional[float] = 0.00
    desconto: Optional[float] = 0.00
    forma_envio: Optional[str] = "A Combinar"
    validade_dias: Optional[int] = 3
    descricao_prazo_entrega: Optional[str] = "IMEDIATO APÓS CONFIRMAÇÃO DO PAGAMENTO"
    observacoes: Optional[str] = "Somos um E-COMMERCE, não reservamos estoque antes da aprovação do pagamento."
    assinatura: Optional[str] = "Atenciosamente,\nDepartamento de vendas"

@app.options("/api/gerar-proposta-tiny")
@app.options("/gerar-proposta-tiny")
def options_proposta():
    return {}

@app.post("/api/gerar-proposta-tiny")
@app.post("/gerar-proposta-tiny")
def criar_proposta_e_obter_pdf(payload: PropostaTinyPayload):
    itens_tiny = []
    for item in payload.carrinho:
        itens_tiny.append({
            "item": {
                "codigo": item.codigo,
                "descricao": item.descricao,
                "unidade": item.unidade,
                "quantidade": item.quantidade,
                "valor_unitario": item.preco_unitario
            }
        })

    dados_proposta = {
        "proposta": {
            "natureza_operacao": payload.natureza_operacao,
            "cliente": {
                "nome": payload.cliente.nome,
                "cpf_cnpj": payload.cliente.cpf_cnpj,
                "aos_cuidados": payload.cliente.aos_cuidados
            },
            "vendedor": payload.vendedor,
            "introducao": payload.introducao,
            "itens": itens_tiny,
            "outros_itens": payload.outros_itens_texto,
            "valor_frete": payload.frete,
            "valor_desconto": payload.desconto,
            "forma_envio": payload.forma_envio,
            "validade": payload.validade_dias,
            "prazo_entrega": payload.descricao_prazo_entrega,
            "obs": payload.observacoes,
            "assinatura": payload.assinatura
        }
    }

    url_incluir = "https://api.tiny.com.br/api2/proposta.incluir.php"
    
    res_incluir = requests.post(
        url_incluir, 
        data={
            "token": TINY_TOKEN, 
            "formato": "JSON", 
            "proposta": json.dumps(dados_proposta)
        }
    ).json()

    if res_incluir.get("retorno", {}).get("status") != "OK":
        erros = res_incluir.get("retorno", {}).get("erros", [])
        raise HTTPException(status_code=400, detail=f"Erro no Tiny: {erros}")

    id_proposta = res_incluir["retorno"]["propostas"][0]["proposta"]["id"]

    url_link = "https://api.tiny.com.br/api2/proposta.obter.link.impressao.php"
    res_link = requests.get(
        url_link, 
        params={"token": TINY_TOKEN, "id": id_proposta, "formato": "JSON"}
    ).json()

    link_pdf = res_link.get("retorno", {}).get("link")
    
    if not link_pdf:
        raise HTTPException(status_code=500, detail="Não foi possível gerar o PDF da proposta.")

    return {"status": "sucesso", "link_pdf": link_pdf}