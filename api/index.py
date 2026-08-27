from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os

app = Flask(__name__)
CORS(app)

TINY_API_URL = "https://api.tiny.com.br/public-api/v3"

TINY_TOKEN = "f751b8c151b478f9472103ef94669425592b01d1"

@app.route('/api/gerar-proposta', methods=['POST'])
def gerar_proposta():
    dados_front = request.json
    
    # 1. Mapeamento do payload do Frontend para o Padrão do Tiny API v3 (Orçamentos)
    itens = []
    for item in dados_front.get("carrinho", []):
        itens.append({
            "item": {
                "codigo": item.get("codigo"),
                "descricao": item.get("descricao"),
                "unidade": item.get("unidade", "UN"),
                "quantidade": item.get("quantidade"),
                "valor_unitario": item.get("preco_unitario")
            }
        })
        
    endereco = dados_front.get("endereco", {})
    cliente = dados_front.get("cliente", {})
    
    payload_tiny = {
        "cliente": {
            "nome": cliente.get("nome"),
            "cpf_cnpj": cliente.get("cpf_cnpj"),
            "email": dados_front.get("email"),
            "telefone": dados_front.get("telefone"),
            "endereco": {
                "cep": endereco.get("cep"),
                "logradouro": endereco.get("logradouro"),
                "numero": endereco.get("numero"),
                "bairro": endereco.get("bairro"),
                "municipio": endereco.get("cidade"),
                "uf": endereco.get("uf")
            }
        },
        "itens": itens,
        "obs": dados_front.get("observacoes"),
        "condicoes_pagamento": dados_front.get("condicoes_pagamento")
    }

    print(payload_tiny)
    print("-----------------------------------------------------------------")

    headers = {
        "Authorization": f"Bearer {TINY_TOKEN}",
        "Content-Type": "application/json"
    }
    
    resp = requests.post(f"{TINY_API_URL}/orcamentos", json=payload_tiny, headers=headers)
    
    print(resp)

    if resp.status_code in [200, 201]:
        return jsonify(resp.json()), resp.status_code
    else:
        return jsonify({
            "erro": "Falha ao criar o orçamento.",
            "detalhes": resp.text
        }), resp.status_code

@app.route('/api/obter-proposta/<id_proposta>', methods=['GET'])
def obter_proposta(id_proposta):
    headers = {
        "Authorization": f"Bearer {TINY_TOKEN}"
    }
    
    # 3. Fazendo a requisição GET para obter as informações do orçamento recém-criado
    resp = requests.get(f"{TINY_API_URL}/orcamentos/{id_proposta}", headers=headers)
    
    if resp.status_code == 200:
        return jsonify(resp.json()), 200
    else:
        return jsonify({
            "erro": "Falha ao obter o orçamento.",
            "detalhes": resp.text
        }), resp.status_code

if __name__ == '__main__':
    # Roda o servidor localmente na porta 5000
    app.run(debug=True, port=5000)