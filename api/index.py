from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from datetime import datetime


app = Flask(__name__)

CORS(app)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TINY_API_URL = "https://api.tiny.com.br/public-api/v3"

TINY_TOKEN = "f751b8c151b478f9472103ef94669425592b01d1"


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def tiny_headers():

    if not TINY_TOKEN:
        raise RuntimeError(
            "A variável de ambiente TINY_TOKEN não está configurada."
        )

    return {
        "Authorization": f"Bearer {TINY_TOKEN}",
        "Content-Type": "application/json"
    }


def limpar_documento(valor):

    if not valor:
        return ""

    return "".join(
        caractere
        for caractere in str(valor)
        if caractere.isdigit()
    )


# ============================================================
# BUSCAR CONTATO PELO CPF/CNPJ
# ============================================================

def buscar_contato(cpf_cnpj):

    documento = limpar_documento(cpf_cnpj)

    if not documento:
        raise ValueError(
            "CPF/CNPJ do cliente não informado."
        )

    url = f"{TINY_API_URL}/contatos"

    params = {
        "cpfCnpj": documento,
        "limit": 100,
        "offset": 0
    }

    response = requests.get(
        url,
        headers=tiny_headers(),
        params=params,
        timeout=30
    )

    if not response.ok:

        try:
            erro = response.json()
        except Exception:
            erro = response.text

        raise RuntimeError({
            "mensagem": "Erro ao consultar contato no Tiny.",
            "status": response.status_code,
            "resposta_tiny": erro
        })

    dados = response.json()

    contatos = dados.get("itens", [])

    if not contatos:

        raise ValueError(
            f"Nenhum contato encontrado no Tiny para o CPF/CNPJ {documento}."
        )

    # Como estamos pesquisando pelo documento,
    # validamos novamente para evitar pegar outro registro.
    for contato in contatos:

        documento_tiny = limpar_documento(
            contato.get("cpfCnpj")
        )

        if documento_tiny == documento:

            return contato

    raise ValueError(
        f"O Tiny retornou contatos, mas nenhum possui o CPF/CNPJ {documento}."
    )


# ============================================================
# BUSCAR PRODUTO PELO CÓDIGO
# ============================================================

def buscar_produto(codigo):

    codigo = str(codigo).strip()

    if not codigo:
        raise ValueError(
            "Produto sem código."
        )

    url = f"{TINY_API_URL}/produtos"

    params = {
        "codigo": codigo,
        "limit": 100,
        "offset": 0
    }

    response = requests.get(
        url,
        headers=tiny_headers(),
        params=params,
        timeout=30
    )

    if not response.ok:

        try:
            erro = response.json()
        except Exception:
            erro = response.text

        raise RuntimeError({
            "mensagem": f"Erro ao consultar produto {codigo} no Tiny.",
            "status": response.status_code,
            "resposta_tiny": erro
        })

    dados = response.json()

    produtos = dados.get("itens", [])

    if not produtos:

        raise ValueError(
            f"Nenhum produto encontrado no Tiny com o código {codigo}."
        )

    # Procuramos correspondência exata
    for produto in produtos:

        sku = str(
            produto.get("sku", "")
        ).strip()

        if sku == codigo:

            return produto

    raise ValueError(
        f"O Tiny retornou produtos, mas nenhum possui o SKU/código exato {codigo}."
    )


# ============================================================
# CRIAR ORÇAMENTO
# ============================================================

@app.route(
    "/api/gerar-proposta",
    methods=["POST"]
)
def gerar_proposta():

    try:

        dados_front = request.get_json(
            silent=True
        )

        if not dados_front:

            return jsonify({
                "erro": "Nenhum JSON foi recebido."
            }), 400


        # =====================================================
        # CLIENTE
        # =====================================================

        cliente = dados_front.get(
            "cliente",
            {}
        )

        cpf_cnpj = cliente.get(
            "cpf_cnpj"
        )

        nome_cliente = cliente.get(
            "nome"
        )

        if not cpf_cnpj:

            return jsonify({
                "erro": "CPF/CNPJ do cliente não informado."
            }), 400


        # =====================================================
        # LOCALIZA O CONTATO NO TINY
        # =====================================================

        contato = buscar_contato(
            cpf_cnpj
        )

        contato_id = contato.get(
            "id"
        )

        if not contato_id:

            return jsonify({
                "erro": "O contato foi encontrado no Tiny, mas não possui ID."
            }), 500


        # =====================================================
        # CARRINHO
        # =====================================================

        carrinho = dados_front.get(
            "carrinho",
            []
        )

        if not carrinho:

            return jsonify({
                "erro": "O carrinho está vazio."
            }), 400


        itens_tiny = []


        # =====================================================
        # CONVERTE PRODUTOS
        # =====================================================

        for numero, item in enumerate(
            carrinho,
            start=1
        ):

            codigo = item.get(
                "codigo"
            )

            descricao = item.get(
                "descricao",
                ""
            )

            quantidade = item.get(
                "quantidade",
                1
            )

            preco_unitario = item.get(
                "preco_unitario",
                0
            )


            if not codigo:

                return jsonify({
                    "erro": (
                        f"O item {numero} "
                        f"({descricao}) não possui código."
                    )
                }), 400


            try:

                quantidade = float(
                    quantidade
                )

            except Exception:

                return jsonify({
                    "erro": (
                        f"Quantidade inválida "
                        f"para o produto {codigo}."
                    )
                }), 400


            try:

                preco_unitario = float(
                    preco_unitario
                )

            except Exception:

                return jsonify({
                    "erro": (
                        f"Preço inválido "
                        f"para o produto {codigo}."
                    )
                }), 400


            if quantidade <= 0:

                return jsonify({
                    "erro": (
                        f"A quantidade do produto "
                        f"{codigo} deve ser maior que zero."
                    )
                }), 400


            if preco_unitario < 0:

                return jsonify({
                    "erro": (
                        f"O preço do produto "
                        f"{codigo} não pode ser negativo."
                    )
                }), 400


            # ================================================
            # BUSCA PRODUTO NO TINY
            # ================================================

            produto = buscar_produto(
                codigo
            )

            produto_id = produto.get(
                "id"
            )

            if not produto_id:

                return jsonify({
                    "erro": (
                        f"O produto {codigo} "
                        "foi encontrado no Tiny, "
                        "mas não possui ID."
                    )
                }), 500


            # ================================================
            # ITEM NO FORMATO DA API V3
            # ================================================

            item_tiny = {

                "produto": {
                    "id": produto_id
                },

                "quantidade": quantidade,

                "valorUnitario": (
                    f"{preco_unitario:.2f}"
                )
            }


            # Opcional:
            # descrição complementar da proposta

            if descricao:

                item_tiny[
                    "descrComplementarOrc"
                ] = descricao


            itens_tiny.append(
                item_tiny
            )


        # =====================================================
        # ENDEREÇO
        # =====================================================

        endereco = dados_front.get(
            "endereco",
            {}
        )


        # =====================================================
        # PAYLOAD DA API DO TINY
        # =====================================================

        payload_tiny = {

            "contato": {
                "id": contato_id
            },

            "data": datetime.now().strftime(
                "%Y-%m-%d"
            ),

            "observacao": dados_front.get(
                "observacoes",
                ""
            ),

            "condicoesComerciais": {

                "textoLivre": dados_front.get(
                    "condicoes_pagamento",
                    ""
                )
            },

            "itens": itens_tiny
        }


        # =====================================================
        # ENDEREÇO ALTERNATIVO
        # =====================================================
        #
        # Só adicionamos se houver endereço informado.
        #
        # A API aceita esse objeto diretamente no orçamento.
        # =====================================================

        if any([
            endereco.get("logradouro"),
            endereco.get("numero"),
            endereco.get("bairro"),
            endereco.get("cidade"),
            endereco.get("cep"),
            endereco.get("uf")
        ]):

            payload_tiny[
                "enderecoAlternativo"
            ] = {

                "endereco": endereco.get(
                    "logradouro",
                    ""
                ),

                "enderecoNro": endereco.get(
                    "numero",
                    ""
                ),

                "bairro": endereco.get(
                    "bairro",
                    ""
                ),

                "municipio": endereco.get(
                    "cidade",
                    ""
                ),

                "cep": endereco.get(
                    "cep",
                    ""
                ),

                "uf": endereco.get(
                    "uf",
                    ""
                ),

                "fone": dados_front.get(
                    "telefone",
                    ""
                ),

                "nomeDestinatario": nome_cliente or "",

                "cpfCnpj": cpf_cnpj or ""
            }


        # =====================================================
        # LOG DO PAYLOAD
        # =====================================================

        print(
            "=========================================="
        )

        print(
            "PAYLOAD ENVIADO AO TINY:"
        )

        print(
            payload_tiny
        )

        print(
            "=========================================="
        )


        # =====================================================
        # POST PARA O TINY
        # =====================================================

        response = requests.post(

            f"{TINY_API_URL}/orcamentos",

            json=payload_tiny,

            headers=tiny_headers(),

            timeout=30
        )


        # =====================================================
        # SUCESSO
        # =====================================================

        if response.ok:

            try:

                resposta_tiny = response.json()
                print(resposta_tiny)

            except Exception:

                return jsonify({
                    "erro": (
                        "O Tiny retornou sucesso, "
                        "mas a resposta não é JSON."
                    ),
                    "resposta": response.text
                }), 502


            return jsonify(
                resposta_tiny
            ), response.status_code


        # =====================================================
        # ERRO DO TINY
        # =====================================================

        try:

            erro_tiny = response.json()

        except Exception:

            erro_tiny = {
                "mensagem": response.text
            }


        print(
            "=========================================="
        )

        print(
            "ERRO RETORNADO PELO TINY:"
        )

        print(
            erro_tiny
        )

        print(
            "=========================================="
        )


        return jsonify({

            "erro":
                "Falha ao criar o orçamento no Tiny.",

            "status_tiny":
                response.status_code,

            "resposta_tiny":
                erro_tiny,

            "payload_enviado":
                payload_tiny

        }), response.status_code


    except ValueError as erro:

        return jsonify({

            "erro":
                str(erro)

        }), 400


    except RuntimeError as erro:

        detalhe = erro.args[0]

        if isinstance(
            detalhe,
            dict
        ):

            return jsonify({

                "erro":
                    detalhe.get(
                        "mensagem",
                        "Erro na comunicação com o Tiny."
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
                str(erro)

        }), 502


    except requests.RequestException as erro:

        print(
            "Erro de conexão com Tiny:",
            erro
        )

        return jsonify({

            "erro":
                "Não foi possível conectar à API do Tiny.",

            "detalhes":
                str(erro)

        }), 502


    except Exception as erro:

        print(
            "Erro inesperado:",
            erro
        )

        return jsonify({

            "erro":
                "Erro interno ao gerar proposta.",

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
def obter_proposta(
    id_proposta
):

    try:

        response = requests.get(

            f"{TINY_API_URL}/orcamentos/{id_proposta}",

            headers=tiny_headers(),

            timeout=30
        )


        # =====================================================
        # SUCESSO
        # =====================================================

        if response.ok:

            try:

                dados = response.json()

            except Exception:

                return jsonify({

                    "erro":
                        "O Tiny retornou uma resposta inválida.",

                    "resposta":
                        response.text

                }), 502


            return jsonify(
                dados
            ), response.status_code


        # =====================================================
        # ERRO
        # =====================================================

        try:

            erro_tiny = response.json()

        except Exception:

            erro_tiny = {
                "mensagem": response.text
            }


        return jsonify({

            "erro":
                "Falha ao obter o orçamento no Tiny.",

            "status_tiny":
                response.status_code,

            "resposta_tiny":
                erro_tiny

        }), response.status_code


    except requests.RequestException as erro:

        return jsonify({

            "erro":
                "Falha de comunicação com a API do Tiny.",

            "detalhes":
                str(erro)

        }), 502


    except Exception as erro:

        return jsonify({

            "erro":
                "Erro interno ao obter proposta.",

            "detalhes":
                str(erro)

        }), 500


# ============================================================
# TESTE DE CONEXÃO COM TINY
# ============================================================

@app.route(
    "/api/testar-tiny",
    methods=["GET"]
)
def testar_tiny():

    try:

        response = requests.get(

            f"{TINY_API_URL}/contatos",

            headers=tiny_headers(),

            params={
                "limit": 1,
                "offset": 0
            },

            timeout=30
        )


        try:

            dados = response.json()

        except Exception:

            dados = {
                "resposta": response.text
            }


        return jsonify({

            "conectado":
                response.ok,

            "status":
                response.status_code,

            "resposta":
                dados

        }), response.status_code


    except Exception as erro:

        return jsonify({

            "conectado":
                False,

            "erro":
                str(erro)

        }), 500


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )