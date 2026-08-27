import json
import requests
import traceback
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

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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

@app.options("/{full_path:path}")
def options_proposta(full_path: str):
    return JSONResponse(status_code=200, content={"status": "ok"})

@app.post("/{full_path:path}")
def criar_proposta_e_obter_pdf(payload: PropostaTinyPayload, full_path: str):
    try:
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
        
        response_incluir = requests.post(
            url_incluir, 
            data={
                "token": TINY_TOKEN, 
                "formato": "JSON", 
                "proposta": json.dumps(dados_proposta)
            },
            headers=HTTP_HEADERS,
            timeout=15
        )

        try:
            res_incluir = response_incluir.json()
        except Exception:
            print(f"Erro ao converter JSON do Tiny. HTTP Status: {response_incluir.status_code}")
            print(f"Conteúdo retornado pelo Tiny: {response_incluir.text}")
            return JSONResponse(
                status_code=502,
                content={
                    "status": "erro",
                    "detalhe": f"Tiny retornou resposta inválida (HTTP {response_incluir.status_code}): {response_incluir.text[:300]}"
                }
            )

        status_tiny = res_incluir.get("retorno", {}).get("status")
        if status_tiny != "OK":
            erros = res_incluir.get("retorno", {}).get("erros", [])
            print("Erro retornado pelo Tiny:", erros)
            return JSONResponse(
                status_code=400,
                content={"status": "erro", "detalhe": f"Erro no Tiny: {erros}"}
            )

        propostas = res_incluir.get("retorno", {}).get("propostas", [])
        if not propostas:
            return JSONResponse(
                status_code=400,
                content={"status": "erro", "detalhe": "Tiny não retornou o ID da proposta."}
            )

        id_proposta = propostas[0]["proposta"]["id"]

        url_link = "https://api.tiny.com.br/api2/proposta.obter.link.impressao.php"
        response_link = requests.get(
            url_link, 
            params={"token": TINY_TOKEN, "id": id_proposta, "formato": "JSON"},
            headers=HTTP_HEADERS,
            timeout=15
        )
        
        try:
            res_link = response_link.json()
        except Exception:
            return JSONResponse(
                status_code=502,
                content={
                    "status": "erro",
                    "detalhe": f"Erro ao obter PDF no Tiny (HTTP {response_link.status_code}): {response_link.text[:300]}"
                }
            )

        link_pdf = res_link.get("retorno", {}).get("link")
        
        if not link_pdf:
            return JSONResponse(
                status_code=500,
                content={"status": "erro", "detalhe": "Não foi possível obter o link do PDF no Tiny."}
            )

        return JSONResponse(status_code=200, content={"status": "sucesso", "link_pdf": link_pdf})

    except Exception as e:
        print("Exceção não tratada:", traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"status": "erro", "detalhe": str(e)}
        )