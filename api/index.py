from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

import requests
import base64
from io import BytesIO
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import secrets
import time
from urllib.parse import urlencode

app = Flask(__name__)

CORS(
    app,
    resources={
        r"/api/*": {
            "origins": "*"
        }
    }
)

TINY_API_URL = "https://api.tiny.com.br/public-api/v3"

TINY_AUTH_URL = (
    "https://accounts.tiny.com.br/"
    "realms/tiny/protocol/openid-connect/auth"
)

TINY_TOKEN_URL = (
    "https://accounts.tiny.com.br/"
    "realms/tiny/protocol/openid-connect/token"
)

TINY_CLIENT_ID = os.environ.get(
    "TINY_CLIENT_ID"
)

TINY_CLIENT_SECRET = os.environ.get(
    "TINY_CLIENT_SECRET"
)

TINY_REDIRECT_URI = os.environ.get(
    "TINY_REDIRECT_URI"
)


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

TINY_TOKEN_KEY = "tiny:oauth:tokens"

OAUTH_STATE_KEY = "tiny:oauth:state"
TINY_REFRESH_LOCK_KEY = "tiny:oauth:refresh-lock"
TINY_REFRESH_LOCK_TTL = 60
TINY_REFRESH_WAIT_SECONDS = 12

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

def resposta_json(
    response
):

    try:

        return response.json()

    except Exception:

        return response.text
    
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

    state = secrets.token_urlsafe(
        32
    )


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

    redis_delete(
        OAUTH_STATE_KEY
    )

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

def renovar_access_token(
    tokens
):

    tokens = tokens or {}

    refresh_token = tokens.get(
        "refresh_token"
    )

    if not refresh_token:
        raise TinyAPIError(
            "Refresh token não encontrado. Autorize novamente a aplicação no Tiny.",
            401,
            {
                "autorizacao":
                    "/api/oauth/autorizar"
            }
        )
    
    lock_token = secrets.token_urlsafe(32)
    lock_adquirido = False

    try:
        for _ in range(
            int(TINY_REFRESH_WAIT_SECONDS * 2)
        ):
            resultado_lock = redis_request(
                "SET",
                TINY_REFRESH_LOCK_KEY,
                lock_token,
                "NX",
                "EX",
                str(TINY_REFRESH_LOCK_TTL)
            )

            if resultado_lock == "OK":
                lock_adquirido = True

                print(
                    "Lock de renovação OAuth adquirido."
                )

                break

            time.sleep(0.5)

            tokens_atualizados = carregar_tokens()

            if not tokens_atualizados:
                continue

            novo_access = tokens_atualizados.get(
                "access_token"
            )

            novo_expires_at = int(
                tokens_atualizados.get(
                    "expires_at",
                    0
                )
            )

            if (
                novo_access
                and
                novo_access != tokens.get("access_token")
                and
                int(time.time()) < novo_expires_at
            ):
                print(
                    "Outra execução já renovou o OAuth. "
                    "Reutilizando o novo access token."
                )

                return {
                    "access_token":
                        novo_access,
                    "refresh_token":
                        tokens_atualizados.get(
                            "refresh_token"
                        ),
                    "expires_in":
                        max(
                            1,
                            novo_expires_at - int(time.time())
                        )
                }

        if not lock_adquirido:
            tokens_atualizados = carregar_tokens()

            if tokens_atualizados:
                novo_access = tokens_atualizados.get(
                    "access_token"
                )

                novo_expires_at = int(
                    tokens_atualizados.get(
                        "expires_at",
                        0
                    )
                )

                if (
                    novo_access
                    and
                    novo_access != tokens.get("access_token")
                    and
                    int(time.time()) < novo_expires_at
                ):
                    return {
                        "access_token":
                            novo_access,
                        "refresh_token":
                            tokens_atualizados.get(
                                "refresh_token"
                            ),
                        "expires_in":
                            max(
                                1,
                                novo_expires_at - int(time.time())
                            )
                    }

            raise TinyAPIError(
                "Outra requisição está renovando o acesso ao Tiny. "
                "Tente novamente em alguns segundos.",
                503,
                {
                    "motivo":
                        "lock_de_renovacao_oauth"
                }
            )

        tokens_atuais = carregar_tokens() or {}

        access_atual = tokens_atuais.get(
            "access_token"
        )

        expires_at_atual = int(
            tokens_atuais.get(
                "expires_at",
                0
            )
        )

        refresh_atual = tokens_atuais.get(
            "refresh_token"
        )

        if (
            access_atual
            and
            int(time.time()) < expires_at_atual
            and
            access_atual != tokens.get("access_token")
        ):
            print(
                "Tokens já foram renovados por outra execução. "
                "Nenhum novo refresh será realizado."
            )

            return {
                "access_token":
                    access_atual,
                "refresh_token":
                    refresh_atual,
                "expires_in":
                    max(
                        1,
                        expires_at_atual - int(time.time())
                    )
            }

        refresh_token = refresh_atual or refresh_token

        if not refresh_token:
            raise TinyAPIError(
                "Refresh token não encontrado. Autorize novamente a aplicação no Tiny.",
                401,
                {
                    "autorizacao":
                        "/api/oauth/autorizar"
                }
            )

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
            print(
                "Resposta OAuth refresh:",
                dados
            )

            texto_erro = json.dumps(
                dados,
                ensure_ascii=False
            ).lower()

            invalid_grant = (
                "invalid_grant" in texto_erro
                or
                "token is not active" in texto_erro
            )

            if invalid_grant:
                try:
                    redis_delete(
                        TINY_TOKEN_KEY
                    )
                except Exception as e:
                    print(
                        "Aviso: não foi possível remover os tokens "
                        "OAuth inválidos:",
                        str(e)
                    )

                raise TinyAPIError(
                    "O refresh token do Tiny não está mais ativo. "
                    "É necessário autorizar novamente a aplicação no Tiny.",
                    401,
                    {
                        "resposta_tiny":
                            dados,
                        "autorizacao":
                            "/api/oauth/autorizar"
                    }
                )

            raise TinyAPIError(
                "Não foi possível renovar o access token.",
                response.status_code,
                dados
            )

        novo_access_token = dados.get(
            "access_token"
        )
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
                "Tiny não retornou novo access_token.",
                502,
                dados
            )
        salvar_tokens(
            novo_access_token,
            novo_refresh_token,
            expires_in
        )

        print(
            "Renovação OAuth concluída e tokens atualizados no Redis."
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

    finally:
        if lock_adquirido:
            try:
                redis_delete(
                    TINY_REFRESH_LOCK_KEY
                )

                print(
                    "Lock de renovação OAuth liberado."
                )

            except Exception as e:
                print(
                    "Aviso: não foi possível liberar o lock OAuth:",
                    str(e)
                )

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


def localizar_contato(
    cpf_cnpj,
    nome=None,
    busca_exaustiva=False
):

    documento = limpar_documento(cpf_cnpj)

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )

    situacoes = [None, "B", "A", "I", "E"]
    vistos = set()

    for situacao in situacoes:

        params = {
            "cpfCnpj": documento,
            "limit": 100,
            "offset": 0
        }

        if situacao:
            params["situacao"] = situacao

        response = tiny_request(
            "GET",
            "/contatos",
            params=params
        )

        dados = resposta_json(response)

        print(
            "Consulta contato por CPF/CNPJ:",
            documento,
            "situação:",
            situacao or "todas",
            "HTTP:",
            response.status_code
        )

        if not response.ok:
            if situacao:
                continue

            raise TinyAPIError(
                "Erro ao consultar contato no Tiny.",
                response.status_code,
                dados
            )

        contatos = dados.get(
            "itens",
            []
        )

        if not isinstance(contatos, list):
            contatos = []

        for contato in contatos:

            contato_id = contato.get("id")

            if contato_id in vistos:
                continue

            vistos.add(contato_id)

            documento_tiny = limpar_documento(
                contato.get("cpfCnpj")
            )

            if documento_tiny == documento:
                return contato

    if nome:

        response = tiny_request(
            "GET",
            "/contatos",
            params={
                "nome": nome,
                "limit": 100,
                "offset": 0
            }
        )

        dados = resposta_json(response)

        print(
            "Fallback consulta contato por nome:",
            nome,
            "HTTP:",
            response.status_code
        )

        if response.ok:

            contatos = dados.get(
                "itens",
                []
            )

            if isinstance(contatos, list):

                for contato in contatos:

                    documento_tiny = limpar_documento(
                        contato.get("cpfCnpj")
                    )

                    if documento_tiny == documento:
                        return contato

    if busca_exaustiva:

        limit = 100
        offset = 0
        total = None
        max_paginas = 1000

        for _ in range(max_paginas):

            response = tiny_request(
                "GET",
                "/contatos",
                params={
                    "limit": limit,
                    "offset": offset
                }
            )

            dados = resposta_json(response)

            print(
                "Busca exaustiva de contato:",
                "offset=",
                offset,
                "HTTP=",
                response.status_code
            )

            if not response.ok:

                raise TinyAPIError(
                    "Erro ao percorrer contatos do Tiny para localizar o CPF/CNPJ.",
                    response.status_code,
                    dados
                )

            contatos = dados.get(
                "itens",
                []
            )

            if not isinstance(contatos, list):
                contatos = []

            for contato in contatos:

                documento_tiny = limpar_documento(
                    contato.get("cpfCnpj")
                )

                if documento_tiny == documento:

                    print(
                        "Contato localizado na busca exaustiva. ID:",
                        contato.get("id")
                    )

                    return contato

            paginacao = dados.get(
                "paginacao",
                {}
            )

            if isinstance(paginacao, dict):

                try:
                    total = int(
                        paginacao.get("total")
                    )
                except (TypeError, ValueError):
                    total = None

            if not contatos:
                break

            offset += len(contatos)

            if total is not None and offset >= total:
                break

            if len(contatos) < limit and total is None:
                break

    return None

def criar_contato(dados_front):

    cliente = dados_front.get(
        "cliente",
        {}
    )

    endereco = dados_front.get(
        "endereco",
        {}
    )

    documento = limpar_documento(
        cliente.get("cpf_cnpj")
    )

    nome = (
        cliente.get("nome")
        or cliente.get("razao_social")
        or "Cliente da loja"
    )

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )

    if not nome:
        raise TinyAPIError(
            "Nome do cliente não informado."
        )

    codigo = f"WEB-{documento}"

    endereco_tiny = {
        "endereco": endereco.get("logradouro"),
        "numero": endereco.get("numero"),
        "complemento": endereco.get("complemento"),
        "bairro": endereco.get("bairro"),
        "municipio": endereco.get("cidade"),
        "cep": endereco.get("cep"),
        "uf": endereco.get("uf"),
        "pais": "Brasil"
    }

    endereco_tiny = {
        chave: valor
        for chave, valor in endereco_tiny.items()
        if valor not in [None, ""]
    }

    payload = {
        "nome": nome,
        "codigo": codigo,
        "cpfCnpj": documento,
        "email": dados_front.get("email"),
        "telefone": dados_front.get("telefone"),
        "endereco": endereco_tiny,
        "observacoesDoContato": "Contato criado automaticamente pela solicitação de proposta comercial via site."
    }

    payload = {
        chave: valor
        for chave, valor in payload.items()
        if valor not in [None, ""]
    }

    print("")
    print("========================================")
    print("CRIANDO CONTATO NO TINY")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print("========================================")

    response = tiny_request(
        "POST",
        "/contatos",
        json=payload
    )

    dados = resposta_json(response)

    print(
        "POST /contatos:",
        response.status_code
    )
    print(
        "Resposta criação contato:",
        dados
    )

    if not response.ok:

        texto_erro = json.dumps(
            dados,
            ensure_ascii=False
        ).lower()

        documento_duplicado = (
            response.status_code == 400
            and (
                "já existe" in texto_erro
                or "ja existe" in texto_erro
                or "already exists" in texto_erro
            )
            and (
                "cnpj" in texto_erro
                or "cpf" in texto_erro
            )
        )

        if documento_duplicado:

            print(
                "Tiny informou que o CPF/CNPJ já existe. "
                "Tentando localizar o contato existente..."
            )

            contato_existente = localizar_contato(
                documento,
                nome,
                busca_exaustiva=True
            )

            if contato_existente:

                contato_id = contato_existente.get(
                    "id"
                )

                if contato_id:
                    print(
                        "Contato existente recuperado após "
                        "erro de duplicidade. ID:",
                        contato_id
                    )

                    return {
                        "id": contato_id,
                        "nome": contato_existente.get(
                            "nome",
                            nome
                        ),
                        "cpfCnpj": documento,
                        "criado_agora": False,
                        "resposta": contato_existente,
                        "recuperado_apos_duplicidade": True
                    }

        raise TinyAPIError(
            "Tiny recusou a criação do contato.",
            response.status_code,
            dados
        )

    contato_id = None

    if isinstance(dados, dict):
        contato_id = dados.get("id")

        if not contato_id and isinstance(dados.get("data"), dict):
            contato_id = dados["data"].get("id")

    if not contato_id:
        raise TinyAPIError(
            "Tiny criou o contato, mas não retornou o ID.",
            502,
            dados
        )

    return {
        "id": contato_id,
        "nome": nome,
        "cpfCnpj": documento,
        "criado_agora": True,
        "resposta": dados
    }

def obter_ou_criar_contato(dados_front):

    cliente = dados_front.get(
        "cliente",
        {}
    )

    documento = limpar_documento(
        cliente.get("cpf_cnpj")
    )

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado.",
            400
        )

    nome = (
        cliente.get("nome")
        or cliente.get("razao_social")
        or None
    )

    contato = localizar_contato(
        documento,
        nome,
        busca_exaustiva=True
    )

    if contato:

        contato_id = contato.get("id")

        if not contato_id:
            raise TinyAPIError(
                "Contato encontrado sem ID.",
                502,
                contato
            )

        print(
            "Contato encontrado no Tiny. ID:",
            contato_id
        )

        return {
            "id": contato_id,
            "criado_agora": False,
            "resposta": contato
        }

    print(
        "Contato não encontrado. Criando novo contato..."
    )

    return criar_contato(
        dados_front
    )

def localizar_produto_por_sku(
    sku
):

    if not sku:
        return None

    sku = str(sku).strip()

    if not sku:
        return None

    response = tiny_request(
        "GET",
        "/produtos",
        params={
            "codigo":
                sku,
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
        "Consulta produto SKU",
        sku,
        "HTTP",
        response.status_code
    )

    if not response.ok:
        raise TinyAPIError(
            "Erro ao consultar produto pelo SKU.",
            response.status_code,
            dados
        )

    produtos = dados.get(
        "itens",
        []
    )

    if not produtos:
        return None
    
    sku_normalizado = sku.casefold()

    for produto in produtos:
        sku_produto = produto.get(
            "sku"
        )

        if sku_produto is None:
            continue

        sku_produto_normalizado = str(
            sku_produto
        ).strip().casefold()

        if (
            sku_produto_normalizado
            and
            sku_produto_normalizado == sku_normalizado
        ):
            return produto

    return None

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


def gerar_pdf_proposta(
    dados_front,
    dados_orcamento,
    orcamento_id,
    introducao_proposta,
    observacao_padrao,
    total_carrinho,
    valor_avista,
    valor_parcela_3x,
    valor_parcela_12x,
    data_proposta,
    outros_itens_servicos
):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    def dinheiro_pdf(valor):
        try:
            valor = float(valor or 0)
        except (TypeError, ValueError):
            valor = 0.0
        return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def texto(valor):
        return escape(str(valor or ""))

    cliente = dados_front.get("cliente", {}) or {}
    endereco = dados_front.get("endereco", {}) or {}
    carrinho = dados_front.get("carrinho", []) or []

    numero_proposta = (
        dados_orcamento.get("numero")
        or dados_orcamento.get("numeroOrcamento")
        or orcamento_id
    ) if isinstance(dados_orcamento, dict) else orcamento_id

    nome_cliente = cliente.get("nome") or cliente.get("razao_social") or "Cliente"
    documento = cliente.get("cpf_cnpj", "")
    aos_cuidados = cliente.get("aos_cuidados", "")
    email = cliente.get("email", "")
    telefone = cliente.get("telefone", "")

    endereco_partes = []
    if endereco.get("logradouro"):
        endereco_partes.append(str(endereco["logradouro"]))
    if endereco.get("numero"):
        endereco_partes.append(f"Nº {endereco['numero']}")
    if endereco.get("complemento"):
        endereco_partes.append(str(endereco["complemento"]))
    linha_endereco = ", ".join(endereco_partes)

    cidade_uf = ""
    if endereco.get("cidade"):
        cidade_uf = str(endereco["cidade"])
    if endereco.get("uf"):
        cidade_uf = f"{cidade_uf} - {endereco['uf']}" if cidade_uf else str(endereco["uf"])
    if endereco.get("cep"):
        cidade_uf = f"{cidade_uf} - {endereco['cep']}" if cidade_uf else str(endereco["cep"])

    contatos = []
    if telefone:
        contatos.append(f"Fone: {telefone}")
    if email:
        contatos.append(f"E-mail: {email}")

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=12*mm, leftMargin=12*mm,
        topMargin=12*mm, bottomMargin=12*mm,
        title=f"Proposta Comercial Nº {numero_proposta}",
        author="BRFER Comércio de Ferramentas LTDA"
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="PDFBody", parent=styles["Normal"], fontName="Helvetica", fontSize=8.5, leading=11, spaceAfter=2))
    styles.add(ParagraphStyle(name="PDFSmall", parent=styles["Normal"], fontName="Helvetica", fontSize=7.5, leading=9))
    styles.add(ParagraphStyle(name="PDFTitle", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=15))
    styles.add(ParagraphStyle(name="PDFSection", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=11, spaceBefore=3, spaceAfter=3))
    styles.add(ParagraphStyle(name="PDFRight", parent=styles["Normal"], fontName="Helvetica", fontSize=8, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="PDFRightBold", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=8.5, leading=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name="PDFOtherTotal", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=15))

    story = []

    empresa = [
        Paragraph("<b>BRFER COMÉRCIO DE FERRAMENTAS LTDA</b>", styles["PDFBody"]),
        Paragraph("40.954.410/0001-96", styles["PDFBody"]),
        Paragraph("www.brfer.com.br", styles["PDFBody"]),
        Paragraph("(11) 4362-5151", styles["PDFBody"]),
        Paragraph("Rua Coronel Francisco Rodrigues Seckler, 53, galpão", styles["PDFBody"]),
        Paragraph("Paulicéia, São Bernardo do Campo - SP", styles["PDFBody"]),
        Paragraph("09.693-050", styles["PDFBody"]),
    ]
    titulo = [
        Paragraph(f"<b>Proposta Comercial Nº {texto(numero_proposta)}</b>", styles["PDFTitle"]),
        Paragraph(f"Data: {texto(data_proposta)}", styles["PDFBody"]),
    ]
    header = Table([[empresa, titulo]], colWidths=[120*mm, 58*mm])
    header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(1,0),(1,0),"RIGHT")]))
    story += [header, Spacer(1,3*mm)]

    cliente_linhas = [f"<b>{texto(nome_cliente)}</b>"]
    if documento: cliente_linhas.append(f"CPF/CNPJ: {texto(documento)}")
    if aos_cuidados: cliente_linhas.append(f"Aos cuidados de: {texto(aos_cuidados)}")
    if linha_endereco: cliente_linhas.append(texto(linha_endereco))
    if cidade_uf: cliente_linhas.append(texto(cidade_uf))
    if contatos: cliente_linhas.append(texto(" | ".join(contatos)))

    story.append(Paragraph("Para", styles["PDFSection"]))
    cliente_box = Table([[Paragraph("<br/>".join(cliente_linhas), styles["PDFBody"])]], colWidths=[178*mm])
    cliente_box.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.5,colors.black),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [cliente_box, Spacer(1,3*mm)]

    intro_html = texto(introducao_proposta).replace("\n", "<br/>")
    story += [Paragraph(intro_html, styles["PDFBody"]), Spacer(1,3*mm)]

    story.append(Paragraph("Itens de produto ou serviço", styles["PDFSection"]))
    rows = [[Paragraph("<b>Nº</b>",styles["PDFSmall"]),Paragraph("<b>Item / SKU</b>",styles["PDFSmall"]),Paragraph("<b>Qtd</b>",styles["PDFSmall"]),Paragraph("<b>Un</b>",styles["PDFSmall"]),Paragraph("<b>Preço un.</b>",styles["PDFSmall"]),Paragraph("<b>Total</b>",styles["PDFSmall"])]]
    total_produtos = 0.0
    total_quantidades = 0.0
    for idx,item in enumerate(carrinho,1):
        nome = item.get("nome") or item.get("descricao") or "Produto"
        sku = item.get("sku") or ""
        qtd = float(item.get("quantidade",1) or 1)
        preco = float(item.get("preco_unitario",0) or 0)
        total_item = qtd * preco
        total_produtos += total_item
        total_quantidades += qtd
        item_html = f"<b>{texto(nome)}</b>" + (f"<br/><font size='7'>SKU: {texto(sku)}</font>" if sku else "")
        preco_html = f"<b>{dinheiro_pdf(preco)}</b><br/><font size='7'>Frete: a combinar</font>"
        rows.append([Paragraph(str(idx),styles["PDFSmall"]),Paragraph(item_html,styles["PDFSmall"]),Paragraph(f"{qtd:.2f}".replace(".",","),styles["PDFSmall"]),Paragraph(texto(item.get("unidade") or "UN"),styles["PDFSmall"]),Paragraph(preco_html,styles["PDFRight"]),Paragraph(f"<b>{dinheiro_pdf(total_item)}</b>",styles["PDFRight"])])
    rows.append([Paragraph("",styles["PDFSmall"]),Paragraph("<b>Totais</b>",styles["PDFSmall"]),Paragraph(f"<b>{total_quantidades:.2f}</b>".replace(".",","),styles["PDFSmall"]),Paragraph("",styles["PDFSmall"]),Paragraph("",styles["PDFSmall"]),Paragraph(f"<b>{dinheiro_pdf(total_produtos)}</b>",styles["PDFRightBold"])])
    tabela = Table(rows,colWidths=[10*mm,78*mm,15*mm,12*mm,31*mm,32*mm],repeatRows=1)
    tabela.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.black),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f3f3f3")),("ALIGN",(0,0),(0,-1),"CENTER"),("ALIGN",(2,1),(3,-1),"CENTER"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [tabela, Spacer(1,4*mm)]

    story.append(Paragraph("Outros itens ou serviços", styles["PDFSection"]))
    outros = [
        Paragraph(f"<b>{dinheiro_pdf(total_carrinho)}</b>",styles["PDFOtherTotal"]),
        Spacer(1,1.5*mm),
        Paragraph(f"• &nbsp;<b>{dinheiro_pdf(valor_avista)}</b> à vista (TED/PIX)",styles["PDFBody"]),
        Paragraph(f"• &nbsp;<b>3x de {dinheiro_pdf(valor_parcela_3x)}</b> SEM JUROS",styles["PDFBody"]),
        Paragraph(f"• &nbsp;<b>12x de {dinheiro_pdf(valor_parcela_12x)}</b> COM JUROS NO CARTÃO",styles["PDFBody"]),
    ]
    if outros_itens_servicos:
        for linha in str(outros_itens_servicos).splitlines():
            linha=linha.strip()
            if not linha: continue
            n=linha.casefold()
            if n.startswith(("condições de pagamento","total:","pagamento à vista","3x de","12x de")): continue
            outros.append(Paragraph(texto(linha),styles["PDFSmall"]))
    outros_box=Table([[outros]],colWidths=[178*mm])
    outros_box.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.6,colors.black),("LEFTPADDING",(0,0),(-1,-1),6),("RIGHTPADDING",(0,0),(-1,-1),6),("TOPPADDING",(0,0),(-1,-1),6),("BOTTOMPADDING",(0,0),(-1,-1),6),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story += [outros_box, Spacer(1,4*mm)]

    resumo=Table([[Paragraph("<b>Data</b>",styles["PDFSmall"]),Paragraph("<b>Total dos itens</b>",styles["PDFSmall"]),Paragraph("<b>Total da proposta</b>",styles["PDFSmall"])],[Paragraph(texto(data_proposta),styles["PDFSmall"]),Paragraph(dinheiro_pdf(total_produtos),styles["PDFRight"]),Paragraph(dinheiro_pdf(total_carrinho),styles["PDFRightBold"])]],colWidths=[55*mm,61*mm,62*mm])
    resumo.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.black),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#f3f3f3")),("ALIGN",(1,0),(-1,-1),"RIGHT"),("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story += [resumo, Spacer(1,4*mm)]

    story.append(Paragraph("Observações",styles["PDFSection"]))
    obs=Table([[Paragraph(texto(observacao_padrao).replace("\n","<br/>"),styles["PDFBody"])]],colWidths=[178*mm])
    obs.setStyle(TableStyle([("BOX",(0,0),(-1,-1),0.4,colors.black),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
    story += [obs, Spacer(1,5*mm), Paragraph("Atenciosamente,",styles["PDFBody"]), Paragraph("Departamento de vendas",styles["PDFBody"])]

    def rodape(canvas,document):
        canvas.saveState(); canvas.setFont("Helvetica",7); canvas.drawRightString(A4[0]-12*mm,7*mm,f"Página {document.page}"); canvas.restoreState()
    doc.build(story,onFirstPage=rodape,onLaterPages=rodape)
    return buffer.getvalue()
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


        contato = obter_ou_criar_contato(
            dados_front
        )


        contato_id = contato.get(
            "id"
        )


        if not contato_id:

            raise TinyAPIError(
                "Não foi possível obter o ID do contato.",
                502,
                contato
            )

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

        for indice, item in enumerate(
            carrinho,
            start=1
        ):

            sku = item.get(
                "sku"
            )

            if sku is not None:
                sku = str(sku).strip()

            if not sku:

                return jsonify({

                    "erro":
                        "Produto sem SKU.",

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
                        "Produto não encontrado no Tiny pelo SKU.",

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

        introducao_proposta = (
            dados_front.get("introducao")
            or
            "Prezado cliente, seguem abaixo proposta comercial com "
            "pagamento à vista com desconto e nossos dados bancários:\n\n"
            "Segue nossos dados bancários:\n"
            "BRFER Comércio de Ferramentas LTDA\n"
            "CNPJ 40.954.410/0001-96\n"
            "Banco: 341 – Itaú\n"
            "Agência: 8811\n"
            "Conta Corrente: 99874-2\n\n"
            "Se preferir, o pagamento pode ser realizado via PIX, a chave "
            "é o nosso CNPJ"
        )

        resumo_carrinho = dados_front.get(
            "resumo_carrinho",
            {}
        )

        def valor_float(nome):
            try:
                return float(resumo_carrinho.get(nome, 0) or 0)
            except (TypeError, ValueError):
                return 0.0

        total_carrinho = valor_float("total")
        valor_avista = valor_float("avista")
        valor_parcela_3x = valor_float("parcela_3x")
        valor_parcela_12x = valor_float("parcela_12x")

        def dinheiro(valor):
            return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
        data_proximo_contato = hoje + timedelta(days=3)

        data_proposta = hoje.isoformat()
        data_proximo_contato_str = data_proximo_contato.isoformat()

        outros_itens_servicos = (
            dados_front.get(
                "outros_itens_servicos"
            )
            or
            (
                "Condições de pagamento\n"
                f"Total: {dinheiro(total_carrinho)}\n"
                f"Pagamento à vista com desconto: {dinheiro(valor_avista)}\n"
                f"3x de {dinheiro(valor_parcela_3x)} sem juros\n"
                f"12x de {dinheiro(valor_parcela_12x)} com juros no cartão."
            )
        )

        hoje = datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).date()

        data_proposta = hoje.isoformat()

        data_proximo_contato = (
            hoje + timedelta(days=3)
        ).isoformat()

        observacao_padrao = (
            dados_front.get(
                "observacoes"
            )
            or
            "Somos um E-COMMERCE, não reservamos estoque "
            "antes da aprovação do pagamento."
        )

        observacao_pagamento = (
            f"{observacao_padrao}\n\n"
            "Condições de pagamento do carrinho\n"
            f"Total do carrinho: {dinheiro(total_carrinho)}\n"
            f"Pagamento à vista com desconto: {dinheiro(valor_avista)}\n"
            f"3x de {dinheiro(valor_parcela_3x)} sem juros\n"
            f"12x de {dinheiro(valor_parcela_12x)} com juros no cartão."
        )

        payload_tiny = {

            "contato": {

                "id":
                    contato_id
            },

            "itens":
                itens_tiny,

            "introducao":
                introducao_proposta,

            "data":
                data_proposta,

            "dataProximoContato":
                data_proximo_contato,

            "outrosItensServicos":
                outros_itens_servicos,

            "observacao":
                observacao_pagamento,
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

            pdf_bytes = gerar_pdf_proposta(
                dados_front=dados_front,
                dados_orcamento=dados_orcamento if isinstance(dados_orcamento, dict) else {},
                orcamento_id=orcamento_id,
                introducao_proposta=introducao_proposta,
                observacao_padrao=observacao_padrao,
                total_carrinho=total_carrinho,
                valor_avista=valor_avista,
                valor_parcela_3x=valor_parcela_3x,
                valor_parcela_12x=valor_parcela_12x,
                data_proposta=data_proposta,
                outros_itens_servicos=outros_itens_servicos,
            )

            pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")

            return jsonify({
                "sucesso": True,
                "id": orcamento_id,
                "contato": {
                    "id": contato_id,
                    "criado_agora": contato.get("criado_agora", False)
                },
                "criacao": dados_criacao,
                "orcamento": dados_orcamento,
                "pdf_base64": pdf_base64,
                "pdf_filename": f"proposta_comercial_{orcamento_id}.pdf"
            }), 200


        pdf_bytes = gerar_pdf_proposta(
            dados_front=dados_front,
            dados_orcamento=dados_orcamento if isinstance(dados_orcamento, dict) else {},
            orcamento_id=orcamento_id,
            introducao_proposta=introducao_proposta,
            observacao_padrao=observacao_padrao,
            total_carrinho=total_carrinho,
            valor_avista=valor_avista,
            valor_parcela_3x=valor_parcela_3x,
            valor_parcela_12x=valor_parcela_12x,
            data_proposta=data_proposta,
            outros_itens_servicos=outros_itens_servicos,
        )

        pdf_base64 = base64.b64encode(pdf_bytes).decode("ascii")

        return jsonify({
            "sucesso": True,
            "id": orcamento_id,
            "contato": {
                "id": contato_id,
                "criado_agora": contato.get("criado_agora", False)
            },
            "criacao": dados_criacao,
            "erro_get": True,
            "status_get_tiny": response_get.status_code,
            "resposta_get_tiny": dados_orcamento,
            "pdf_base64": pdf_base64,
            "pdf_filename": f"proposta_comercial_{orcamento_id}.pdf"
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