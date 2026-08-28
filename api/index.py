from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

import requests
import os
import json
import secrets
import time
from urllib.parse import urlencode


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
# TINY / OLIST API V3
# ============================================================

TINY_API_URL = "https://api.tiny.com.br/public-api/v3"

TINY_AUTH_URL = (
    "https://accounts.tiny.com.br/"
    "realms/tiny/protocol/openid-connect/auth"
)

TINY_TOKEN_URL = (
    "https://accounts.tiny.com.br/"
    "realms/tiny/protocol/openid-connect/token"
)


# ============================================================
# VARIÁVEIS DE AMBIENTE
# ============================================================

TINY_CLIENT_ID = os.environ.get(
    "TINY_CLIENT_ID"
)

TINY_CLIENT_SECRET = os.environ.get(
    "TINY_CLIENT_SECRET"
)

TINY_REDIRECT_URI = os.environ.get(
    "TINY_REDIRECT_URI"
)


# ============================================================
# UPSTASH REDIS
#
# Quando o Upstash é conectado à Vercel, normalmente essas
# variáveis são disponibilizadas automaticamente.
# ============================================================

REDIS_URL = (
    os.environ.get("UPSTASH_REDIS_REST_URL")
    or
    os.environ.get("KV_REST_API_URL")
)

REDIS_TOKEN = (
    os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    or
    os.environ.get("KV_REST_API_TOKEN")
)


# ============================================================
# CHAVES REDIS
# ============================================================

TINY_TOKEN_KEY = "tiny:oauth:tokens"

OAUTH_STATE_KEY = "tiny:oauth:state"


# ============================================================
# ERRO PERSONALIZADO
# ============================================================

class TinyAPIError(Exception):

    def __init__(
        self,
        mensagem,
        status=None,
        resposta=None
    ):

        super().__init__(mensagem)

        self.mensagem = mensagem
        self.status = status
        self.resposta = resposta


# ============================================================
# REDIS
# ============================================================

def redis_disponivel():

    return bool(
        REDIS_URL
        and REDIS_TOKEN
    )


def redis_request(
    comando,
    *argumentos
):

    if not redis_disponivel():

        raise RuntimeError(
            "Upstash Redis não está configurado."
        )


    url = REDIS_URL.rstrip("/") + "/"


    payload = [
        comando,
        *argumentos
    ]


    response = requests.post(
        url,
        headers={
            "Authorization":
                f"Bearer {REDIS_TOKEN}",

            "Content-Type":
                "application/json"
        },
        json=payload,
        timeout=10
    )


    if not response.ok:

        raise RuntimeError(
            "Erro ao acessar Upstash Redis: "
            f"HTTP {response.status_code} "
            f"{response.text}"
        )


    dados = response.json()

    return dados.get("result")


def redis_get(chave):

    return redis_request(
        "GET",
        chave
    )


def redis_set(
    chave,
    valor,
    expiracao=None
):

    if expiracao:

        return redis_request(
            "SET",
            chave,
            valor,
            "EX",
            str(expiracao)
        )


    return redis_request(
        "SET",
        chave,
        valor
    )


def redis_delete(chave):

    return redis_request(
        "DEL",
        chave
    )


# ============================================================
# TOKENS
# ============================================================

def carregar_tokens():

    valor = redis_get(
        TINY_TOKEN_KEY
    )


    if not valor:

        return None


    try:

        return json.loads(
            valor
        )

    except Exception:

        print(
            "ERRO: tokens armazenados no Redis "
            "não são um JSON válido."
        )

        return None


def salvar_tokens(
    access_token,
    refresh_token,
    expires_in
):

    agora = int(
        time.time()
    )


    # Margem de segurança de 60 segundos.
    expires_at = (
        agora
        + int(expires_in or 3600)
        - 60
    )


    dados = {

        "access_token":
            access_token,

        "refresh_token":
            refresh_token,

        "expires_at":
            expires_at,

        "updated_at":
            agora
    }


    redis_set(

        TINY_TOKEN_KEY,

        json.dumps(
            dados
        )
    )


    print(
        "Tokens OAuth salvos no Upstash Redis."
    )


# ============================================================
# HEADERS TINY
# ============================================================

def headers_tiny(
    access_token
):

    return {

        "Authorization":
            f"Bearer {access_token}",

        "Content-Type":
            "application/json",

        "Accept":
            "application/json"
    }


# ============================================================
# CONVERTER RESPOSTA
# ============================================================

def resposta_json(
    response
):

    try:

        return response.json()

    except Exception:

        return response.text


# ============================================================
# OAUTH - AUTORIZAR
# ============================================================

@app.route(
    "/api/oauth/autorizar",
    methods=["GET"]
)
def oauth_autorizar():

    if not TINY_CLIENT_ID:

        return jsonify({

            "erro":
                "TINY_CLIENT_ID não configurado na Vercel."

        }), 500


    if not TINY_CLIENT_SECRET:

        return jsonify({

            "erro":
                "TINY_CLIENT_SECRET não configurado na Vercel."

        }), 500


    if not TINY_REDIRECT_URI:

        return jsonify({

            "erro":
                "TINY_REDIRECT_URI não configurado na Vercel."

        }), 500


    if not redis_disponivel():

        return jsonify({

            "erro":
                "Upstash Redis não configurado.",

            "REDIS_URL":
                bool(REDIS_URL),

            "REDIS_TOKEN":
                bool(REDIS_TOKEN)

        }), 500


    # ========================================================
    # STATE DE SEGURANÇA
    # ========================================================

    state = secrets.token_urlsafe(
        32
    )


    # Estado válido por 10 minutos.

    redis_set(
        OAUTH_STATE_KEY,
        state,
        600
    )


    parametros = {

        "client_id":
            TINY_CLIENT_ID,

        "redirect_uri":
            TINY_REDIRECT_URI,

        "response_type":
            "code",

        "state":
            state
    }


    url = (
        TINY_AUTH_URL
        + "?"
        + urlencode(parametros)
    )


    print(
        "Iniciando autorização OAuth Tiny."
    )


    return redirect(
        url
    )


# ============================================================
# OAUTH - CALLBACK
# ============================================================

@app.route(
    "/api/oauth/callback",
    methods=["GET"]
)
def oauth_callback():

    codigo = request.args.get(
        "code"
    )

    state = request.args.get(
        "state"
    )

    erro = request.args.get(
        "error"
    )


    if erro:

        return jsonify({

            "erro":
                "O Tiny recusou a autorização.",

            "detalhes":
                erro,

            "descricao":
                request.args.get(
                    "error_description"
                )

        }), 400


    if not codigo:

        return jsonify({

            "erro":
                "Código de autorização não recebido."

        }), 400


    if not state:

        return jsonify({

            "erro":
                "State OAuth não recebido."

        }), 400


    # ========================================================
    # VALIDAR STATE
    # ========================================================

    state_salvo = redis_get(
        OAUTH_STATE_KEY
    )


    if not state_salvo:

        return jsonify({

            "erro":
                "State OAuth expirado ou inexistente.",

            "orientacao":
                "Acesse /api/oauth/autorizar novamente."

        }), 400


    if not secrets.compare_digest(
        str(state_salvo),
        str(state)
    ):

        return jsonify({

            "erro":
                "State OAuth inválido."

        }), 400


    # Impede reutilização.

    redis_delete(
        OAUTH_STATE_KEY
    )


    # ========================================================
    # TROCAR CODE POR TOKENS
    # ========================================================

    try:

        response = requests.post(

            TINY_TOKEN_URL,

            data={

                "grant_type":
                    "authorization_code",

                "client_id":
                    TINY_CLIENT_ID,

                "client_secret":
                    TINY_CLIENT_SECRET,

                "redirect_uri":
                    TINY_REDIRECT_URI,

                "code":
                    codigo
            },

            headers={

                "Accept":
                    "application/json",

                "Content-Type":
                    "application/x-www-form-urlencoded"
            },

            timeout=30
        )


        dados = resposta_json(
            response
        )


        print(
            "OAuth Tiny HTTP:",
            response.status_code
        )


        if not response.ok:

            print(
                "Resposta OAuth:",
                dados
            )


            return jsonify({

                "erro":
                    "Tiny recusou a troca do código.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados

            }), 502


        access_token = dados.get(
            "access_token"
        )

        refresh_token = dados.get(
            "refresh_token"
        )

        expires_in = dados.get(
            "expires_in",
            3600
        )


        if not access_token:

            return jsonify({

                "erro":
                    "Tiny não retornou access_token.",

                "resposta_tiny":
                    dados

            }), 502


        if not refresh_token:

            return jsonify({

                "erro":
                    "Tiny não retornou refresh_token.",

                "resposta_tiny":
                    dados

            }), 502


        # ====================================================
        # SALVAR NO UPSTASH
        # ====================================================

        salvar_tokens(

            access_token,

            refresh_token,

            expires_in
        )


        return jsonify({

            "sucesso":
                True,

            "mensagem":
                (
                    "Aplicação autorizada com sucesso. "
                    "Os tokens foram armazenados "
                    "automaticamente no Upstash Redis."
                ),

            "expira_em_segundos":
                expires_in,

            "proximo_passo":
                (
                    "A integração já pode utilizar "
                    "/api/gerar-proposta."
                )

        }), 200


    except requests.RequestException as e:

        return jsonify({

            "erro":
                "Erro de comunicação com o OAuth do Tiny.",

            "detalhes":
                str(e)

        }), 502


# ============================================================
# RENOVAR ACCESS TOKEN
# ============================================================

def renovar_access_token(
    tokens
):

    refresh_token = tokens.get(
        "refresh_token"
    )


    if not refresh_token:

        raise TinyAPIError(
            "Refresh token não encontrado."
        )


    try:

        response = requests.post(

            TINY_TOKEN_URL,

            data={

                "grant_type":
                    "refresh_token",

                "client_id":
                    TINY_CLIENT_ID,

                "client_secret":
                    TINY_CLIENT_SECRET,

                "refresh_token":
                    refresh_token
            },

            headers={

                "Accept":
                    "application/json",

                "Content-Type":
                    "application/x-www-form-urlencoded"
            },

            timeout=30
        )


        dados = resposta_json(
            response
        )


        print(
            "Renovação OAuth Tiny HTTP:",
            response.status_code
        )


        if not response.ok:

            raise TinyAPIError(

                "Não foi possível renovar o access token.",

                response.status_code,

                dados
            )


        novo_access_token = dados.get(
            "access_token"
        )


        # Alguns fluxos retornam um novo refresh token.
        # Se não retornar, mantemos o anterior.

        novo_refresh_token = (

            dados.get(
                "refresh_token"
            )

            or

            refresh_token
        )


        expires_in = dados.get(
            "expires_in",
            3600
        )


        if not novo_access_token:

            raise TinyAPIError(
                "Tiny não retornou novo access_token."
            )


        salvar_tokens(

            novo_access_token,

            novo_refresh_token,

            expires_in
        )


        return {

            "access_token":
                novo_access_token,

            "refresh_token":
                novo_refresh_token,

            "expires_in":
                expires_in
        }


    except requests.RequestException as e:

        raise TinyAPIError(

            "Erro de comunicação durante "
            "a renovação do token.",

            None,

            str(e)
        )


# ============================================================
# OBTER ACCESS TOKEN VÁLIDO
# ============================================================

def obter_access_token():

    tokens = carregar_tokens()


    if not tokens:

        raise TinyAPIError(

            "A aplicação ainda não foi autorizada no Tiny.",

            401,

            {
                "autorizacao":
                    "/api/oauth/autorizar"
            }
        )


    access_token = tokens.get(
        "access_token"
    )

    expires_at = int(
        tokens.get(
            "expires_at",
            0
        )
    )


    agora = int(
        time.time()
    )


    if (
        access_token
        and
        agora < expires_at
    ):

        return access_token


    print(
        "Access token expirado. Renovando..."
    )


    novos_tokens = renovar_access_token(
        tokens
    )


    return novos_tokens[
        "access_token"
    ]


# ============================================================
# REQUEST AUTENTICADO AO TINY
# ============================================================

def tiny_request(
    metodo,
    endpoint,
    **kwargs
):

    access_token = obter_access_token()


    response = requests.request(

        metodo,

        f"{TINY_API_URL}{endpoint}",

        headers=headers_tiny(
            access_token
        ),

        timeout=30,

        **kwargs
    )


    # ========================================================
    # 401 → TOKEN PODE TER EXPIRADO
    # ========================================================

    if response.status_code == 401:

        print(
            "Tiny retornou HTTP 401."
        )

        print(
            "Tentando renovar o access token..."
        )


        tokens = carregar_tokens()


        if not tokens:

            raise TinyAPIError(

                "Tokens OAuth não encontrados.",

                401,

                resposta_json(
                    response
                )
            )


        novos_tokens = renovar_access_token(
            tokens
        )


        response = requests.request(

            metodo,

            f"{TINY_API_URL}{endpoint}",

            headers=headers_tiny(

                novos_tokens[
                    "access_token"
                ]
            ),

            timeout=30,

            **kwargs
        )


    return response


# ============================================================
# LIMPAR CPF/CNPJ
# ============================================================

def limpar_documento(
    valor
):

    if not valor:

        return ""


    return "".join(

        c

        for c in str(
            valor
        )

        if c.isdigit()
    )


# ============================================================
# LOCALIZAR CONTATO
# ============================================================

def localizar_contato(
    cpf_cnpj
):

    documento = limpar_documento(
        cpf_cnpj
    )


    if not documento:

        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )


    response = tiny_request(

        "GET",

        "/contatos",

        params={

            "cpfCnpj":
                documento,

            "limit":
                100,

            "offset":
                0
        }
    )


    dados = resposta_json(
        response
    )


    print(
        "Consulta contato:",
        response.status_code
    )


    if not response.ok:

        raise TinyAPIError(

            "Erro ao consultar contato no Tiny.",

            response.status_code,

            dados
        )


    contatos = dados.get(
        "itens",
        []
    )


    if not contatos:

        return None


    for contato in contatos:

        documento_tiny = limpar_documento(

            contato.get(
                "cpfCnpj"
            )
        )


        if documento_tiny == documento:

            return contato


    if len(contatos) == 1:

        return contatos[0]


    return contatos[0]

def localizar_ou_criar_contato(cpf_cnpj, cliente, dados_front):

    documento = limpar_documento(cpf_cnpj)

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )

    # 1. TENTA ENCONTRAR
    contato = localizar_contato(documento)

    if contato:
        print(
            "Contato já existente no Tiny. ID:",
            contato.get("id")
        )
        return contato

    # 2. NÃO ENCONTROU → CRIA
    endereco = dados_front.get("endereco", {})

    payload_contato = {
        "nome": cliente.get("nome"),
        "cpfCnpj": documento,
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
    }

    print("")
    print("========================================")
    print("CRIANDO CONTATO NO TINY")
    print(json.dumps(
        payload_contato,
        indent=2,
        ensure_ascii=False
    ))
    print("========================================")

    response = tiny_request(
        "POST",
        "/contatos",
        json=payload_contato
    )

    dados = resposta_json(response)

    print(
        "POST /contatos:",
        response.status_code
    )

    if response.ok:

        contato_id = (
            dados.get("id")
            or
            dados.get("data", {}).get("id")
        )

        if not contato_id:
            raise TinyAPIError(
                "Tiny criou o contato, mas não retornou o ID.",
                response.status_code,
                dados
            )

        return {
            "id": contato_id,
            "cpfCnpj": documento,
            "nome": cliente.get("nome"),
            "criado_agora": True
        }

    # 3. CASO O TINY DIGA QUE JÁ EXISTE,
    #    TENTA LOCALIZAR NOVAMENTE
    texto_erro = json.dumps(
        dados,
        ensure_ascii=False
    ).lower()

    if (
        "já existe" in texto_erro
        or
        "ja existe" in texto_erro
        or
        "duplic" in texto_erro
    ):

        print(
            "Tiny informou que o contato já existe."
        )

        contato = localizar_contato(documento)

        if contato:
            return contato

    raise TinyAPIError(
        "Erro ao criar contato no Tiny.",
        response.status_code,
        dados
    )


# ============================================================
# NORMALIZAR SKU / CÓDIGO
# ============================================================

def normalizar_sku(valor):

    if valor is None:
        return ""

    return str(valor).strip().upper()


# ============================================================
# LOCALIZAR PRODUTO POR SKU / CÓDIGO
# ============================================================

def localizar_produto_por_sku(
    sku
):

    codigo = normalizar_sku(
        sku
    )

    if not codigo:
        return None

    # Na API V3, o parâmetro de consulta é `codigo` e o
    # resultado do produto informa o código no campo `sku`.
    # Usamos o REF/SKU do site para encontrar o ID interno
    # do produto no Tiny.

    response = tiny_request(

        "GET",

        "/produtos",

        params={

            "codigo":
                codigo,

            "limit":
                100,

            "offset":
                0
        }
    )

    dados = resposta_json(
        response
    )

    print(
        "Consulta produto por SKU/código:",
        codigo,
        "HTTP",
        response.status_code
    )

    if not response.ok:

        raise TinyAPIError(

            "Erro ao consultar produto pelo SKU/código.",

            response.status_code,

            dados
        )

    produtos = dados.get(
        "itens",
        []
    )

    if not produtos:
        return None

    # Confirma o código retornado pelo Tiny. Não aceitamos
    # simplesmente o primeiro/único resultado sem conferir
    # o SKU, para evitar vincular o produto errado.

    for produto in produtos:

        candidatos = [
            produto.get("sku"),
            produto.get("codigo")
        ]

        for codigo_produto in candidatos:

            if (
                codigo_produto
                and
                normalizar_sku(
                    codigo_produto
                ) == codigo
            ):

                print(
                    "Produto encontrado pelo SKU/código:",
                    codigo,
                    "ID Tiny:",
                    produto.get("id")
                )

                return produto

    return None


# ============================================================
# TESTAR TINY
# ============================================================

@app.route(
    "/api/testar-tiny",
    methods=["GET"]
)
def testar_tiny():

    try:

        response = tiny_request(

            "GET",

            "/contatos",

            params={

                "limit":
                    1,

                "offset":
                    0
            }
        )


        dados = resposta_json(
            response
        )


        if not response.ok:

            return jsonify({

                "erro":
                    "Token rejeitado pelo Tiny.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados

            }), response.status_code


        return jsonify({

            "sucesso":
                True,

            "mensagem":
                "Autenticação com a API V3 funcionando.",

            "tiny":
                dados

        }), 200


    except TinyAPIError as e:

        return jsonify({

            "erro":
                e.mensagem,

            "status_tiny":
                e.status,

            "detalhes":
                e.resposta

        }), e.status or 500


# ============================================================
# CRIAR PROPOSTA COMERCIAL
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

                "erro":
                    "JSON inválido ou vazio."

            }), 400


        # ====================================================
        # CLIENTE
        # ====================================================

        cliente = dados_front.get(
            "cliente",
            {}
        )


        cpf_cnpj = cliente.get(
            "cpf_cnpj"
        )


        if not cpf_cnpj:

            return jsonify({

                "erro":
                    "CPF/CNPJ do cliente não informado."

            }), 400


        contato = localizar_ou_criar_contato(
            cpf_cnpj,
            cliente,
            dados_front
        )
        if not contato:

            return jsonify({

                "erro":
                    "Cliente não encontrado no Tiny.",

                "cpf_cnpj":
                    limpar_documento(
                        cpf_cnpj
                    ),

                "orientacao":
                    (
                        "Cadastre o cliente no Tiny "
                        "antes de gerar a proposta."
                    )

            }), 404


        contato_id = contato.get(
            "id"
        )


        if not contato_id:

            return jsonify({

                "erro":
                    "Contato encontrado sem ID.",

                "contato":
                    contato

            }), 502


        # ====================================================
        # CARRINHO
        # ====================================================

        carrinho = dados_front.get(
            "carrinho",
            []
        )


        if not carrinho:

            return jsonify({

                "erro":
                    "Carrinho vazio."

            }), 400


        itens_tiny = []


        # ====================================================
        # PRODUTOS
        # ====================================================

        for indice, item in enumerate(
            carrinho,
            start=1
        ):

            sku = (

                item.get(
                    "sku"
                )

                or

                item.get(
                    "codigo"
                )

                or

                item.get(
                    "ref"
                )
            )


            if not sku:

                return jsonify({

                    "erro":
                        "Produto sem SKU/REF.",

                    "item":
                        indice,

                    "produto":
                        item

                }), 400


            produto = localizar_produto_por_sku(
                sku
            )


            if not produto:

                return jsonify({

                    "erro":
                        "Produto não encontrado no Tiny pelo SKU/código.",

                    "item":
                        indice,

                    "sku":
                        sku,

                    "nome_site":
                        (
                            item.get(
                                "nome"
                            )
                            or
                            item.get(
                                "descricao"
                            )
                        )

                }), 404


            produto_id = produto.get(
                "id"
            )


            if not produto_id:

                return jsonify({

                    "erro":
                        "Produto encontrado sem ID no Tiny.",

                    "produto":
                        produto

                }), 502


            quantidade = float(
                item.get(
                    "quantidade",
                    1
                )
            )


            preco = float(
                item.get(
                    "preco_unitario",
                    0
                )
            )


            item_tiny = {

                "produto": {

                    "id":
                        produto_id
                },

                "quantidade":
                    quantidade,

                "valorUnitario":
                    preco
            }


            # Mantém a descrição do site como
            # informação complementar.

            descricao = (

                item.get(
                    "descricao"
                )

                or

                item.get(
                    "nome"
                )
            )


            if descricao:

                item_tiny[
                    "descrComplementarOrc"
                ] = descricao


            itens_tiny.append(
                item_tiny
            )


        # ====================================================
        # PAYLOAD V3
        # ====================================================

        payload_tiny = {

            "contato": {

                "id":
                    contato_id
            },

            "itens":
                itens_tiny,

            "observacao":
                (
                    dados_front.get(
                        "observacoes"
                    )
                    or
                    "Somos um E-COMMERCE, "
                    "não reservamos estoque antes "
                    "da aprovação do pagamento."
                )
        }


        print("")
        print(
            "========================================"
        )

        print(
            "CRIANDO PROPOSTA NO TINY"
        )

        print(
            json.dumps(
                payload_tiny,
                indent=2,
                ensure_ascii=False
            )
        )

        print(
            "========================================"
        )


        # ====================================================
        # POST
        # ====================================================

        response_post = tiny_request(

            "POST",

            "/orcamentos",

            json=payload_tiny
        )


        dados_criacao = resposta_json(
            response_post
        )


        print(
            "POST /orcamentos:",
            response_post.status_code
        )


        if not response_post.ok:

            return jsonify({

                "erro":
                    "Tiny recusou a criação da proposta.",

                "status_tiny":
                    response_post.status_code,

                "resposta_tiny":
                    dados_criacao

            }), response_post.status_code


        # ====================================================
        # ID
        # ====================================================

        orcamento_id = None


        if isinstance(
            dados_criacao,
            dict
        ):

            orcamento_id = (

                dados_criacao.get(
                    "id"
                )

                or

                dados_criacao.get(
                    "idOrcamento"
                )
            )


        if not orcamento_id:

            return jsonify({

                "erro":
                    (
                        "Tiny respondeu sucesso, "
                        "mas não retornou o ID da proposta."
                    ),

                "resposta_tiny":
                    dados_criacao

            }), 502


        # ====================================================
        # GET
        # ====================================================

        response_get = tiny_request(

            "GET",

            f"/orcamentos/{orcamento_id}"
        )


        dados_orcamento = resposta_json(
            response_get
        )


        print(
            "GET /orcamentos/",
            orcamento_id,
            ":",
            response_get.status_code
        )


        if response_get.ok:

            return jsonify({

                "sucesso":
                    True,

                "id":
                    orcamento_id,

                "criacao":
                    dados_criacao,

                "orcamento":
                    dados_orcamento

            }), 200


        # POST funcionou, mas GET falhou.

        return jsonify({

            "sucesso":
                True,

            "id":
                orcamento_id,

            "criacao":
                dados_criacao,

            "erro_get":
                True,

            "status_get_tiny":
                response_get.status_code,

            "resposta_get_tiny":
                dados_orcamento

        }), 200


    except TinyAPIError as e:

        print("")
        print(
            "========================================"
        )

        print(
            "ERRO TINY"
        )

        print(
            "MENSAGEM:",
            e.mensagem
        )

        print(
            "STATUS:",
            e.status
        )

        print(
            "RESPOSTA:",
            e.resposta
        )

        print(
            "========================================"
        )


        return jsonify({

            "erro":
                e.mensagem,

            "status_tiny":
                e.status,

            "resposta_tiny":
                e.resposta

        }), e.status or 502


    except requests.RequestException as e:

        return jsonify({

            "erro":
                "Erro de comunicação com o Tiny.",

            "detalhes":
                str(e)

        }), 502


    except Exception as e:

        print(
            "ERRO INTERNO:",
            str(e)
        )


        return jsonify({

            "erro":
                "Erro interno no servidor.",

            "detalhes":
                str(e)

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

        response = tiny_request(

            "GET",

            f"/orcamentos/{id_proposta}"
        )


        dados = resposta_json(
            response
        )


        if not response.ok:

            return jsonify({

                "erro":
                    "Falha ao obter o orçamento.",

                "status_tiny":
                    response.status_code,

                "resposta_tiny":
                    dados

            }), response.status_code


        return jsonify(
            dados
        ), 200


    except TinyAPIError as e:

        return jsonify({

            "erro":
                e.mensagem,

            "status_tiny":
                e.status,

            "resposta_tiny":
                e.resposta

        }), e.status or 502


    except Exception as e:

        return jsonify({

            "erro":
                "Erro interno.",

            "detalhes":
                str(e)

        }), 500


# ============================================================
# STATUS
# ============================================================

@app.route(
    "/api/status",
    methods=["GET"]
)
def status():

    try:

        tokens = carregar_tokens()


        if not tokens:

            return jsonify({

                "autorizado":
                    False,

                "mensagem":
                    "Aplicação ainda não autorizada.",

                "autorizar":
                    "/api/oauth/autorizar"

            }), 200


        expires_at = int(
            tokens.get(
                "expires_at",
                0
            )
        )


        agora = int(
            time.time()
        )


        return jsonify({

            "autorizado":
                True,

            "access_token_valido":
                agora < expires_at,

            "tokens_armazenados":
                True,

            "mensagem":
                "Credenciais OAuth encontradas no Redis."

        }), 200


    except Exception as e:

        return jsonify({

            "erro":
                str(e)

        }), 500


# ============================================================
# REVOGAR TOKEN LOCAL
# ============================================================

@app.route(
    "/api/oauth/revogar",
    methods=["POST"]
)
def revogar_oauth():

    try:

        redis_delete(
            TINY_TOKEN_KEY
        )


        return jsonify({

            "sucesso":
                True,

            "mensagem":
                "Tokens removidos do Upstash Redis."

        }), 200


    except Exception as e:

        return jsonify({

            "erro":
                "Não foi possível remover os tokens.",

            "detalhes":
                str(e)

        }), 500


# ============================================================
# HOME
# ============================================================

@app.route(
    "/",
    methods=["GET"]
)
def index():

    return jsonify({

        "status":
            "online",

        "servico":
            "Gerador de Propostas Comerciais",

        "api":
            "Olist ERP API V3",

        "endpoints": {

            "autorizar":
                "/api/oauth/autorizar",

            "callback":
                "/api/oauth/callback",

            "status":
                "/api/status",

            "testar":
                "/api/testar-tiny",

            "gerar":
                "/api/gerar-proposta",

            "obter":
                "/api/obter-proposta/<id>",

            "revogar":
                "/api/oauth/revogar"
        }

    }), 200


# ============================================================
# EXECUÇÃO LOCAL
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )