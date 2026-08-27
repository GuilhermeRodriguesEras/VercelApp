from flask import Flask, request, jsonify
from flask_cors import CORS

import requests
import os
import traceback
from datetime import datetime


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TINY_API_URL = (
    "https://api.tiny.com.br/public-api/v3"
)

TINY_TOKEN = "f751b8c151b478f9472103ef94669425592b01d1"


# ============================================================
# HEADERS TINY
# ============================================================

def tiny_headers():

    if not TINY_TOKEN:

        raise RuntimeError(
            "A variável TINY_TOKEN não está configurada na Vercel."
        )

    return {
        "Authorization":
            f"Bearer {TINY_TOKEN}",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }


# ============================================================
# LIMPAR CPF / CNPJ
# ============================================================

def limpar_documento(valor):

    if not valor:
        return ""

    return "".join(
        caractere
        for caractere in str(valor)
        if caractere.isdigit()
    )


# ============================================================
# CONVERTER RESPOSTA TINY
# ============================================================

def resposta_json(response):

    try:
        return response.json()

    except Exception:

        return {
            "mensagem": response.text
        }


# ============================================================
# BUSCAR CONTATO
# ============================================================

def buscar_contato(cpf_cnpj):

    documento = limpar_documento(
        cpf_cnpj
    )


    if not documento:

        raise ValueError(
            "CPF/CNPJ não informado."
        )


    url = (
        f"{TINY_API_URL}/contatos"
    )


    params = {

        "cpfCnpj":
            documento,

        "limit":
            100,

        "offset":
            0
    }


    response = requests.get(

        url,

        headers=tiny_headers(),

        params=params,

        timeout=30
    )


    dados = resposta_json(
        response
    )


    if not response.ok:

        print("====================================")
        print("ERRO AO CONSULTAR CONTATO NO TINY")
        print("URL:", response.url)
        print("STATUS:", response.status_code)
        print("RESPOSTA:", response.text)
        print("====================================")

        raise RuntimeError({

            "mensagem":
                "Erro ao consultar o contato no Tiny.",

            "status":
                response.status_code,

            "resposta_tiny":
                dados
        })

    contatos = dados.get(
        "itens",
        []
    )


    if not contatos:

        raise ValueError(
            "Nenhum contato encontrado no Tiny para o CPF/CNPJ informado."
        )


    # A API documenta cpfCnpj como parâmetro de pesquisa.
    # Ainda validamos o documento retornado antes de usar o ID.

    for contato in contatos:

        documento_tiny = limpar_documento(
            contato.get("cpfCnpj")
        )


        if documento_tiny == documento:

            return contato


    raise ValueError(
        "O Tiny retornou contatos, mas nenhum corresponde exatamente ao CPF/CNPJ informado."
    )


# ============================================================
# BUSCAR PRODUTO PELO CÓDIGO
# ============================================================

def buscar_produto(codigo):

    codigo = str(
        codigo or ""
    ).strip()


    if not codigo:

        raise ValueError(
            "Produto sem código."
        )


    url = (
        f"{TINY_API_URL}/produtos"
    )


    params = {

        "codigo":
            codigo,

        "limit":
            100,

        "offset":
            0
    }


    response = requests.get(

        url,

        headers=tiny_headers(),

        params=params,

        timeout=30
    )


    dados = resposta_json(
        response
    )


    if not response.ok:

        raise RuntimeError({

            "mensagem":
                f"Erro ao consultar o produto {codigo} no Tiny.",

            "status":
                response.status_code,

            "resposta_tiny":
                dados
        })


    produtos = dados.get(
        "itens",
        []
    )


    if not produtos:

        raise ValueError(

            f'Nenhum produto encontrado no Tiny com o código "{codigo}".'

        )


    # Na resposta de produtos, o código aparece como SKU.
    # Fazemos a comparação exata.

    for produto in produtos:

        sku = str(
            produto.get("sku", "")
        ).strip()


        if sku == codigo:

            return produto


    raise ValueError(

        f'O Tiny retornou produtos, mas nenhum possui o SKU "{codigo}".'

    )


# ============================================================
# TESTAR TINY
# ============================================================

@app.route(
    "/api/testar-tiny",
    methods=["GET"]
)
def testar_tiny():

    try:

        if not TINY_TOKEN:

            return jsonify({

                "conectado":
                    False,

                "erro":
                    "TINY_TOKEN não está configurado na Vercel."

            }), 500


        response = requests.get(

            f"{TINY_API_URL}/contatos",

            headers=tiny_headers(),

            params={
                "limit": 1,
                "offset": 0
            },

            timeout=30
        )


        dados = resposta_json(
            response
        )


        return jsonify({

            "conectado":
                response.ok,

            "status_tiny":
                response.status_code,

            "resposta_tiny":
                dados

        }), response.status_code


    except Exception as erro:

        print(
            traceback.format_exc()
        )


        return jsonify({

            "conectado":
                False,

            "erro":
                str(erro)

        }), 500


# ============================================================
# GERAR PROPOSTA
# ============================================================

@app.route(
    "/api/gerar-proposta",
    methods=["POST"]
)
def gerar_proposta():

    try:

        # ====================================================
        # RECEBER JSON
        # ====================================================

        dados_front = request.get_json(
                silent=True
            )


        if not dados_front:

            return jsonify({

                "erro":
                    "O backend não recebeu um JSON válido."

            }), 400


        # ====================================================
        # CLIENTE
        # ====================================================

        cliente = dados_front.get(
            "cliente",
            {}
        )


        nome_cliente = (
            cliente.get("nome")
            or ""
        )


        cpf_cnpj = (
            cliente.get("cpf_cnpj")
            or ""
        )


        if not cpf_cnpj:

            return jsonify({

                "erro":
                    "CPF/CNPJ do cliente não foi informado."

            }), 400


        # ====================================================
        # LOCALIZAR CONTATO NO TINY
        # ====================================================

        contato = buscar_contato(
            cpf_cnpj
        )


        contato_id = contato.get(
            "id"
        )


        if not contato_id:

            return jsonify({

                "erro":
                    "O contato foi encontrado, mas o Tiny não retornou o ID."

            }), 502


        # ====================================================
        # CARRINHO
        # ====================================================

        carrinho = dados_front.get(
            "carrinho",
            []
        )


        if not isinstance(
            carrinho,
            list
        ) or not carrinho:

            return jsonify({

                "erro":
                    "O carrinho está vazio."

            }), 400


        itens_tiny = []


        # ====================================================
        # PRODUTOS
        # ====================================================

        for numero, item in enumerate(
            carrinho,
            start=1
        ):

            codigo = (
                item.get("codigo")
                or ""
            )


            descricao = (
                item.get("descricao")
                or ""
            )


            if not codigo:

                return jsonify({

                    "erro":
                        f"O item {numero} não possui código."

                }), 400


            # -----------------------------------------------
            # QUANTIDADE
            # -----------------------------------------------

            try:

                quantidade = float(
                    item.get(
                        "quantidade",
                        1
                    )
                )

            except Exception:

                return jsonify({

                    "erro":
                        f'Quantidade inválida para "{descricao}".'

                }), 400


            if quantidade <= 0:

                return jsonify({

                    "erro":
                        f'A quantidade de "{descricao}" deve ser maior que zero.'

                }), 400


            # -----------------------------------------------
            # PREÇO
            # -----------------------------------------------

            try:

                preco = float(
                    item.get(
                        "preco_unitario",
                        0
                    )
                )

            except Exception:

                return jsonify({

                    "erro":
                        f'Preço inválido para "{descricao}".'

                }), 400


            if preco < 0:

                return jsonify({

                    "erro":
                        f'O preço de "{descricao}" não pode ser negativo.'

                }), 400


            # -----------------------------------------------
            # BUSCAR PRODUTO NO TINY
            # -----------------------------------------------

            produto = buscar_produto(
                codigo
            )


            produto_id = produto.get(
                "id"
            )


            if not produto_id:

                return jsonify({

                    "erro":
                        f'O produto "{codigo}" foi encontrado no Tiny, mas não possui ID.'

                }), 502


            # -----------------------------------------------
            # ITEM NO FORMATO DA API V3
            # -----------------------------------------------

            item_tiny = {

                "produto": {
                    "id":
                        produto_id
                },

                "quantidade":
                    quantidade,

                "valorUnitario":
                    f"{preco:.2f}"
            }


            # Descrição complementar é suportada pela API.

            if descricao:

                item_tiny[
                    "descrComplementarOrc"
                ] = descricao


            itens_tiny.append(
                item_tiny
            )


        # ====================================================
        # ENDEREÇO
        # ====================================================

        endereco = dados_front.get(
            "endereco",
            {}
        )


        # ====================================================
        # PAYLOAD TINY
        # ====================================================

        payload_tiny = {

            "contato": {

                "id":
                    contato_id
            },

            "data":
                datetime.now().strftime(
                    "%Y-%m-%d"
                ),

            "observacao":
                dados_front.get(
                    "observacoes",
                    ""
                ),

            "condicoesComerciais": {

                "textoLivre":
                    dados_front.get(
                        "condicoes_pagamento",
                        ""
                    )
            },

            "itens":
                itens_tiny
        }


        # ====================================================
        # ENDEREÇO ALTERNATIVO
        # ====================================================

        tem_endereco = any([

            endereco.get("logradouro"),

            endereco.get("numero"),

            endereco.get("bairro"),

            endereco.get("cidade"),

            endereco.get("cep"),

            endereco.get("uf")
        ])


        if tem_endereco:

            payload_tiny[
                "enderecoAlternativo"
            ] = {

                "endereco":
                    endereco.get(
                        "logradouro",
                        ""
                    ),

                "enderecoNro":
                    endereco.get(
                        "numero",
                        ""
                    ),

                "bairro":
                    endereco.get(
                        "bairro",
                        ""
                    ),

                "municipio":
                    endereco.get(
                        "cidade",
                        ""
                    ),

                "cep":
                    endereco.get(
                        "cep",
                        ""
                    ),

                "uf":
                    endereco.get(
                        "uf",
                        ""
                    ),

                "fone":
                    dados_front.get(
                        "telefone",
                        ""
                    ),

                "nomeDestinatario":
                    nome_cliente,

                "cpfCnpj":
                    cpf_cnpj
            }


        # ====================================================
        # LOG
        # ====================================================

        print(
            "PAYLOAD TINY:"
        )

        print(
            payload_tiny
        )


        # ====================================================
        # CRIAR ORÇAMENTO
        # ====================================================

        response = requests.post(

            f"{TINY_API_URL}/orcamentos",

            headers=tiny_headers(),

            json=payload_tiny,

            timeout=30
        )


        dados_tiny = resposta_json(
            response
        )


        print(
            "STATUS TINY:",
            response.status_code
        )


        print(
            "RESPOSTA TINY:",
            dados_tiny
        )


        # ====================================================
        # ERRO
        # ====================================================

        if not response.ok:

            return jsonify({

                "erro":
                    "O Tiny recusou a criação da proposta.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados_tiny

            }), response.status_code


        # ====================================================
        # SUCESSO
        # ====================================================

        return jsonify(
            dados_tiny
        ), 200


    except ValueError as erro:

        return jsonify({

            "erro":
                str(erro)

        }), 400


    except RuntimeError as erro:

        detalhe = (
            erro.args[0]
            if erro.args
            else str(erro)
        )


        if isinstance(
            detalhe,
            dict
        ):

            return jsonify({

                "erro":
                    detalhe.get(
                        "mensagem",
                        "Erro ao consultar o Tiny."
                    ),

                "status_tiny":
                    detalhe.get(
                        "status"
                    ),

                "resposta_tiny":
                    detalhe.get(
                        "resposta_tiny"
                    )

            }), 502


        return jsonify({

            "erro":
                str(detalhe)

        }), 502


    except requests.RequestException as erro:

        print(
            traceback.format_exc()
        )


        return jsonify({

            "erro":
                "Falha de comunicação com o Tiny.",

            "detalhes":
                str(erro)

        }), 502


    except Exception as erro:

        print(
            traceback.format_exc()
        )


        return jsonify({

            "erro":
                "Erro interno ao gerar a proposta.",

            "detalhes":
                str(erro)

        }), 500


# ============================================================
# OBTER PROPOSTA
# ============================================================

@app.route(
    "/api/obter-proposta/<int:id_proposta>",
    methods=["GET"]
)
def obter_proposta(id_proposta):

    try:

        response = requests.get(

            f"{TINY_API_URL}/orcamentos/{id_proposta}",

            headers=tiny_headers(),

            timeout=30
        )


        dados_tiny = resposta_json(
            response
        )


        print(
            "GET ORÇAMENTO:",
            id_proposta
        )


        print(
            "STATUS TINY:",
            response.status_code
        )


        if not response.ok:

            return jsonify({

                "erro":
                    "Não foi possível obter o orçamento no Tiny.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados_tiny

            }), response.status_code


        return jsonify(
            dados_tiny
        ), 200


    except requests.RequestException as erro:

        return jsonify({

            "erro":
                "Falha de comunicação com o Tiny.",

            "detalhes":
                str(erro)

        }), 502


    except Exception as erro:

        print(
            traceback.format_exc()
        )


        return jsonify({

            "erro":
                "Erro interno ao consultar o orçamento.",

            "detalhes":
                str(erro)

        }), 500


# ============================================================
# ROTA INICIAL
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def home():

    return jsonify({

        "status":
            "ok",

        "servico":
            "Backend integração Tray -> Olist ERP",

        "rotas": [

            "/api/testar-tiny",

            "/api/gerar-proposta",

            "/api/obter-proposta/<id>"
        ]

    })


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )