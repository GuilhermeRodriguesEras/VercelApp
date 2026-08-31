from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

import requests
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
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
TINY_REFRESH_LOCK_KEY = "tiny:oauth:refresh-lock"
TINY_REFRESH_LOCK_TTL = 60
TINY_REFRESH_WAIT_SECONDS = 12


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
    """
    Renova o access token com proteção contra concorrência.

    A aplicação roda na Vercel e pode receber duas requisições
    simultâneas quando o access token expira. Se ambas tentarem usar
    o mesmo refresh token ao mesmo tempo, o provedor OAuth pode
    invalidar o refresh token usado pela segunda requisição.

    Por isso:
    1. adquirimos um lock distribuído no Upstash;
    2. depois de adquirir o lock, recarregamos os tokens do Redis;
    3. se outra execução já renovou os tokens, reutilizamos os novos;
    4. somente uma execução chama o endpoint OAuth de refresh;
    5. se o Tiny devolver invalid_grant/Token is not active,
       informamos que é necessária uma nova autorização.
    """

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

    # ========================================================
    # LOCK DISTRIBUÍDO NO UPSTASH
    # ========================================================
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

            # Outra execução está renovando. Esperamos um pouco e
            # verificamos se ela já atualizou os tokens.
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

        # Se não conseguimos o lock, fazemos uma última leitura antes
        # de desistir. Isso evita erro quando a outra execução acabou
        # de concluir a renovação.
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

        # ========================================================
        # RECARREGAR TOKENS DEPOIS DO LOCK
        # ========================================================
        # O objeto recebido pelo chamador pode estar desatualizado.
        # Por isso sempre consultamos o Redis novamente depois de
        # adquirir o lock.
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

        # Se outra execução já renovou os tokens antes de adquirirmos
        # o lock, não consumimos novamente o refresh token.
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

        # ========================================================
        # REFRESH NO TINY
        # ========================================================
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
                # O refresh token não pode mais ser utilizado. Removê-lo
                # evita que todas as próximas requisições repitam o mesmo
                # refresh inválido. A aplicação deverá ser autorizada
                # novamente pelo endpoint /api/oauth/autorizar.
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

        # Se o Tiny rotacionar o refresh token, o novo valor substitui
        # imediatamente o anterior. Se não enviar um novo refresh token,
        # mantemos o atual.
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

        # ========================================================
        # SALVAR NOVOS TOKENS
        # ========================================================
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
        # O TTL evita que o lock fique preso em caso de falha. Aqui
        # removemos o lock ao finalizar normalmente.
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
    cpf_cnpj,
    nome=None,
    busca_exaustiva=False
):
    """
    Localiza um contato pelo CPF/CNPJ.

    Estratégia:
    1. Usa o filtro oficial cpfCnpj da API V3.
    2. Tenta novamente considerando as situações B/A/I/E.
    3. Se ainda não encontrar e busca_exaustiva=True, percorre a
       paginação de /contatos e compara o CPF/CNPJ localmente.

    A busca exaustiva é importante para o cenário em que o Tiny
    informa "Contato com CNPJ/CPF já existe", mas o filtro direto
    não devolve o registro esperado.
    """

    documento = limpar_documento(cpf_cnpj)

    if not documento:
        raise TinyAPIError(
            "CPF/CNPJ do cliente não informado."
        )

    # --------------------------------------------------------
    # 1) FILTRO DIRETO POR CPF/CNPJ
    # --------------------------------------------------------

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
            # Se uma situação específica não for aceita pela conta,
            # tentamos as demais. Para a consulta sem situação,
            # entretanto, o erro é relevante e deve ser informado.
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

    # --------------------------------------------------------
    # 2) FALLBACK POR NOME
    # --------------------------------------------------------
    # O filtro por nome é oficialmente suportado pela API V3.
    # Ainda assim, o contato só é aceito se o CPF/CNPJ também
    # conferir exatamente.

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

    # --------------------------------------------------------
    # 3) BUSCA EXAUSTIVA PAGINADA
    # --------------------------------------------------------
    # Esta é a parte importante para o erro atual.
    #
    # O Tiny documenta cpfCnpj como filtro, porém, se o filtro não
    # retornar um cadastro que sabemos que existe, percorremos a
    # listagem e fazemos a comparação localmente.
    #
    # Isso só é executado quando explicitamente solicitado para
    # evitar uma varredura completa de contatos em toda requisição.

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

            # Se não há itens, não há mais o que procurar.
            if not contatos:
                break

            offset += len(contatos)

            # Se o Tiny informou o total, paramos exatamente quando
            # ultrapassarmos a quantidade existente.
            if total is not None and offset >= total:
                break

            # Proteção contra API que devolva repetidamente a mesma
            # página sem atualizar a paginação.
            if len(contatos) < limit and total is None:
                break

    return None


# ============================================================
# CRIAR CONTATO
# ============================================================

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

    # O código é usado para identificar o contato no Tiny.
    # Como o CPF/CNPJ é único, ele evita criar códigos
    # aleatórios e facilita futuras consultas.
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

    # A API V3 permite criar o contato com os dados do formulário.
    # Não criamos usuário na Tray; este é somente um contato no Tiny.
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

        # O Tiny pode retornar HTTP 400 informando que o CPF/CNPJ
        # já existe. Isso significa que a consulta anterior não
        # conseguiu localizar o registro, mas o cadastro existe.
        # Nesse caso, fazemos uma nova busca antes de desistir.
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


# ============================================================
# OBTER OU CRIAR CONTATO
# ============================================================

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


# ============================================================
# LOCALIZAR PRODUTO POR SKU
# ============================================================

def localizar_produto_por_sku(
    sku
):

    if not sku:
        return None

    # SKU é um código e pode conter letras, números, hífens etc.
    # Portanto, não fazemos a normalização numérica usada no GTIN.
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

    # Não usamos o primeiro resultado como fallback.
    # O código/SKU precisa corresponder exatamente ao SKU recebido
    # para evitar associar um produto incorreto ao orçamento.
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

        # ============================================================
        # INTRODUÇÃO, OBSERVAÇÃO E DATAS DA PROPOSTA
        # ============================================================
        # A introdução aparece no início da Proposta Comercial.
        #
        # Os valores abaixo são calculados no frontend usando exatamente
        # a mesma lógica exibida no carrinho e enviados para cá para que
        # o backend seja a única camada responsável pela montagem do
        # payload do Tiny.
        # ============================================================

        introducao_proposta = (
            dados_front.get("introducao")
            or
            "Prezado cliente, seguem abaixo proposta comercial com "
            "pagamento à vista com desconto e nossos dados bancários:\n\n"
            "Favorecido: Segue nossos dados bancários:\n"
            "Favorecido: *BRFER Comércio de Ferramentas LTDA*\n"
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

        # A API do Olist documenta explicitamente os campos "data" e
        # "dataProximoContato" no POST de orçamentos. Usamos o fuso de
        # São Paulo para que a virada do dia não dependa do UTC da Vercel.
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
                "Condições de pagamento do carrinho\n"
                f"Total do carrinho: {dinheiro(total_carrinho)}\n"
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

            # Mantido como já estava: informações adicionais em
            # "Outros itens ou serviços".
            "outrosItensServicos":
                outros_itens_servicos,

            # A observação continua recebendo a observação padrão
            # e agora também os custos/valores das parcelas.
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

            return jsonify({

                "sucesso":
                    True,

                "id":
                    orcamento_id,

                "contato": {
                    "id": contato_id,
                    "criado_agora": contato.get("criado_agora", False)
                },

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

            "contato": {
                "id": contato_id,
                "criado_agora": contato.get("criado_agora", False)
            },

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