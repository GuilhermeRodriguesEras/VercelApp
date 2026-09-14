from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

import requests
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import secrets
import time
from hashlib import sha256
from urllib.parse import urlencode

import base64
from io import BytesIO
from html import unescape
from html.parser import HTMLParser

from flask import send_file

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image

app = Flask(__name__)

BRFER_LOGO_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAJUAAABwCAIAAACYSaUpAAAACXBIWXMAAA7EAAAOxAGVKw4bAAABZGlDQ1BJQ0NCYXNlZChSR0IsR29vZ2xlL1NraWEvN0M1RkEyMTUxMzk3NDc0QTA0ODZCQkNDODM3MzNENTkpAAB4nH2QvUrDYBSGH2tBFMVBhw4OGRxc1P5of8ClrVhcW4VWpzRNi9ifkKboBejm4OomLt6A6GUoCA7i4CWIoLNvGiQFqefw5nt485Iv50Akhioah07Xc8ulglGtHRhT70yoh2VafYfxpdT3S5B9Xv0nN66mG3bf0vkhea4u1ycb4sVWwKc+1wO+8PnEczzxtc/uXrkovhOvtEa4PsKW4/r5N/FWpz2wwv9m1u7uV3RWpSVK9NQt2tisU+GYI0xRhiKb7JAnSUKUIEVO7sZQeeJ6ZklTUBfVWb3PSCm2lc75+wyu7N1A9gsmL0OvfgUP5xB7Db1lzTZ/BvePoRfu2DFdc2hFpUizCZ+3MFeDhSeYOfxd7JhZjT+zGuzSxWJNlNQ0CdI/hc1LvY60eocAACraSURBVHic7X0HXFTH9r8v7728kvfy0qOCSi/L0pcuXVEQQRAQUZAmilJEpQlRQQUUsTew946IMfaoSSxRY9SY2Cv2xK4oZe/9nd3ZnZ29bXcBTd7//85nP8vduWfOnJnvnDNzZuZe2lFtR1KplJFC07TAT3YiJwP7Llywy2Jzsr9/LxLWliSkJ/CTlRXgb9dKzVpG2tenDSVI5dTKct8CMZTUgB8tJ8T3RolRBPnzDZVONoGwPozr1ujDFqWrNLZiAhLa0Vq7L12JTxVh/jYsmpHCINzNST3bRCVOUQyBnAza6MDQ raw HTML string removed for brevity ... "

class HTMLParaTexto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes = []
        self.tags_bloco = {
            "p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li"
        }

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "br":
            self.partes.append("\n")
        elif tag == "li":
            self.partes.append("\n• ")
        elif tag in self.tags_bloco:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.tags_bloco and tag != "br":
            self.partes.append("\n")

    def handle_data(self, data):
        self.partes.append(data)


def html_para_texto(valor):
    if not valor:
        return ""

    parser = HTMLParaTexto()
    parser.feed(str(valor))
    parser.close()

    texto = "".join(parser.partes)
    texto = unescape(texto)

    linhas = []
    for linha in texto.splitlines():
        linha_limpa = " ".join(linha.split())
        if linha_limpa:
            linhas.append(linha_limpa)

    return "\n".join(linhas).strip()


def escape_html(valor):
    valor = unescape(str(valor or "").strip())
    return (
        valor
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def formatar_texto_para_pdf(valor):
    """
    Converte qualquer texto ou HTML em um formato seguro com <br/> 
    para o Paragraph do ReportLab preservar quebras de linha e estrutura.
    """
    if not valor:
        return ""
    
    val_str = str(valor)
    if "<" in val_str and ">" in val_str:
        val_str = html_para_texto(val_str)
    else:
        val_str = unescape(val_str)

    linhas = [escape_html(linha) for linha in val_str.splitlines() if linha.strip()]
    return "<br/>".join(linhas)


def gerar_pdf_proposta(dados_front, dados_orcamento, contato, orcamento_id):
    """Gera o PDF local com dimensões e espaçamentos próximos ao PDF do Tiny."""

    cliente = dados_front.get("cliente") or {}
    endereco = dados_front.get("endereco") or {}

    def primeiro_valor(*valores):
        for valor in valores:
            if valor not in (None, ""):
                return valor
        return ""

    def float_seguro(valor, padrao=0.0):
        try:
            return float(valor or 0)
        except (TypeError, ValueError):
            return padrao

    def numero_pt(valor):
        return f"{float_seguro(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    def texto(valor):
        return str(valor or "").strip()

    def endereco_formatado():
        partes = []
        logradouro = texto(endereco.get("logradouro"))
        numero = texto(endereco.get("numero"))
        complemento = texto(endereco.get("complemento"))
        bairro = texto(endereco.get("bairro"))
        cidade = texto(endereco.get("cidade"))
        uf = texto(endereco.get("uf"))
        cep = texto(endereco.get("cep"))

        if logradouro:
            linha = logradouro
            if numero:
                linha += f", Nº {numero}"
            if complemento:
                linha += f", {complemento}"
            if bairro:
                linha += f", {bairro}"
            partes.append(linha)

        cidade_linha = cidade
        if cep:
            cidade_linha += f" - {cep}" if cidade_linha else cep
        if uf:
            cidade_linha += f", {uf}" if cidade_linha else uf
        if cidade_linha:
            partes.append(cidade_linha)

        return partes

    styles = getSampleStyleSheet()

    normal = ParagraphStyle(
        "PropostaNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.8,
        leading=10.2,
        spaceBefore=0,
        spaceAfter=0,
        leftIndent=0,
        rightIndent=0,
        firstLineIndent=0,
        textColor=colors.black,
    )
    title_style = ParagraphStyle(
        "PropostaTitle",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=15.2,
        leading=18,
        alignment=TA_CENTER,
    )
    table_header = ParagraphStyle(
        "PropostaTableHeader",
        parent=normal,
        fontName="Helvetica-Bold",
        fontSize=8.2,
        leading=9.2,
        alignment=TA_CENTER,
    )
    table_left = ParagraphStyle(
        "PropostaTableLeft",
        parent=normal,
        fontSize=8.1,
        leading=9.8,
        leftIndent=0,
        rightIndent=0,
        firstLineIndent=0,
    )
    table_center = ParagraphStyle(
        "PropostaTableCenter",
        parent=table_left,
        alignment=TA_CENTER,
    )
    table_right = ParagraphStyle(
        "PropostaTableRight",
        parent=table_left,
        alignment=TA_RIGHT,
    )
    empresa_style = ParagraphStyle(
        "EmpresaHeader",
        parent=normal,
        fontSize=8.5,
        leading=9.5,
        alignment=TA_RIGHT,
    )

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=8 * mm,
        bottomMargin=18 * mm,
        title=f"Proposta Comercial {orcamento_id}",
        author="BRFER Comércio de Ferramentas LTDA",
    )

    story = []

    logo_stream = BytesIO(base64.b64decode(BRFER_LOGO_BASE64))
    logo = Image(logo_stream, width=38 * mm, height=28 * mm)

    empresa_html = (
        "<b>BRFER COMÉRCIO DE FERRAMENTAS LTDA</b><br/>"
        "40.954.410/0001-96<br/>"
        "www.brfer.com.br<br/>"
        "(11) 4362-5151<br/>"
        "Rua Coronel Francisco Rodrigues Seckler, 53, galpão<br/>"
        "Paulicéia, São Bernardo do Campo - SP<br/>"
        "09.693-050<br/>"
        "799387168111"
    )

    header = Table(
        [[logo, Paragraph(empresa_html, empresa_style)]],
        colWidths=[45 * mm, 145 * mm],
        rowHeights=[28 * mm],
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 6 * mm))

    numero_proposta = primeiro_valor(
        dados_orcamento.get("numeroProposta"),
        dados_orcamento.get("numero"),
        orcamento_id,
    )
    story.append(Paragraph(
        f"Proposta Comercial Nº {escape_html(numero_proposta)}",
        title_style,
    ))
    story.append(Spacer(1, 5 * mm))

    nome_cliente = texto(
        primeiro_valor(
            cliente.get("razao_social"),
            cliente.get("nome"),
            contato.get("nome") if isinstance(contato, dict) else "",
            "Cliente",
        )
    )
    documento = texto(primeiro_valor(
        cliente.get("cpf_cnpj"),
        contato.get("cpfCnpj") if isinstance(contato, dict) else "",
    ))
    endereco_linhas = endereco_formatado()

    telefone = texto(primeiro_valor(
        contato.get("telefone") if isinstance(contato, dict) else "",
        cliente.get("telefone"),
    ))
    celular = texto(primeiro_valor(
        contato.get("celular") if isinstance(contato, dict) else "",
        contato.get("telefoneCelular") if isinstance(contato, dict) else "",
        cliente.get("celular"),
    ))
    email = texto(primeiro_valor(
        contato.get("email") if isinstance(contato, dict) else "",
        cliente.get("email"),
    ))

    story.append(Paragraph("Para", normal))
    story.append(Paragraph(escape_html(nome_cliente), normal))
    story.append(Spacer(1, 3.5 * mm))

    dados_endereco = [
        [Paragraph("<b>Endereço do Cliente</b>", normal)],
        [Paragraph(escape_html(documento), normal)],
    ]
    for linha in endereco_linhas:
        dados_endereco.append([Paragraph(escape_html(linha), normal)])

    contato_linha = []
    if telefone:
        contato_linha.append(f"Fone: {escape_html(telefone)}")
    if celular and celular != telefone:
        contato_linha.append(f"Celular: {escape_html(celular)}")
    if email:
        contato_linha.append(f"E-mail: {escape_html(email)}")
    if contato_linha:
        dados_endereco.append([Paragraph(", ".join(contato_linha), normal)])

    endereco_box = Table(dados_endereco, colWidths=[190 * mm])
    endereco_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.4),
    ]))
    story.append(endereco_box)
    story.append(Spacer(1, 4.5 * mm))

    introducao = dados_front.get("introducao") or (
        "Prezado cliente, seguem abaixo proposta comercial com "
        "pagamento à vista com desconto e nossos dados bancários:\n\n"
        "Segue nossos dados bancários:\n"
        "BRFER Comércio de Ferramentas LTDA\n"
        "CNPJ 40.954.410/0001-96\n"
        "Banco: 341 – Itaú\n"
        "Agência: 8811\n"
        "Conta Corrente: 99874-2\n\n"
        "Se preferir, o pagamento pode ser realizado via PIX, a chave "
        "é o nosso CNPJ \n"
    )

    introducao_fmt = formatar_texto_para_pdf(introducao)
    if introducao_fmt:
        story.append(Paragraph(introducao_fmt, normal))
        story.append(Spacer(1, 2.5 * mm))

    story.append(Paragraph("<b>Itens de produto ou serviço</b>", normal))
    story.append(Spacer(1, 1 * mm))

    itens = dados_orcamento.get("itens")
    if not isinstance(itens, list) or not itens:
        itens = []
        for item in dados_front.get("carrinho") or []:
            itens.append({
                "produto": {
                    "descricao": item.get("descricao") or item.get("nome"),
                    "sku": item.get("sku"),
                },
                "quantidade": item.get("quantidade", 1),
                "valorUnitario": item.get("preco_unitario", 0),
                "descrComplementarOrc": item.get("descricao") or item.get("nome"),
            })

    corpo_itens = [[
        Paragraph("Nº", table_header),
        Paragraph("Item", table_header),
        Paragraph("SKU", table_header),
        Paragraph("Qtd", table_header),
        Paragraph("Un", table_header),
        Paragraph("Preço un", table_header),
        Paragraph("Total", table_header),
    ]]

    soma_quantidades = 0.0
    total_itens_calculado = 0.0

    for indice, item in enumerate(itens, start=1):
        produto = item.get("produto") or {}
        descricao = texto(primeiro_valor(
            produto.get("descricao"),
            item.get("descricao"),
            item.get("nome"),
            "Produto",
        ))
        sku = texto(primeiro_valor(produto.get("sku"), item.get("sku")))
        quantidade = float_seguro(item.get("quantidade"), 1.0)
        valor_unitario = float_seguro(
            item.get("valorUnitario"),
            float_seguro(item.get("preco_unitario")),
        )
        total_item = quantidade * valor_unitario
        soma_quantidades += quantidade
        total_itens_calculado += total_item

        complemento = texto(item.get("descrComplementarOrc"))
        
        # Formatação adequada da descrição e do complemento para o PDF
        descricao_fmt = formatar_texto_para_pdf(descricao)
        descricao_html = f"<b>{descricao_fmt}</b>"
        
        if complemento and unescape(complemento).strip() != unescape(descricao).strip():
            complemento_fmt = formatar_texto_para_pdf(complemento)
            if complemento_fmt:
                descricao_html += f"<br/><font color='#555555'>{complemento_fmt}</font>"

        corpo_itens.append([
            Paragraph(str(indice), table_center),
            Paragraph(descricao_html, table_left),
            Paragraph(escape_html(sku), table_left),
            Paragraph(numero_pt(quantidade), table_center),
            Paragraph("UN", table_center),
            Paragraph(numero_pt(valor_unitario), table_right),
            Paragraph(numero_pt(total_item), table_right),
        ])

    subtotal = float_seguro(primeiro_valor(
        dados_orcamento.get("valorSubtotal"),
        dados_orcamento.get("valorTotal"),
        total_itens_calculado,
    ))
    total_proposta = float_seguro(primeiro_valor(
        dados_orcamento.get("valorTotal"),
        subtotal,
    ))

    corpo_itens.append([
        Paragraph(
            f"<b>Número de itens: {len(itens)}</b><br/>"
            f"<b>Soma das quantidades:</b> {numero_pt(soma_quantidades)}",
            normal,
        ),
        "", "", "", "",
        Paragraph("<b>Total dos itens</b>", table_right),
        Paragraph(numero_pt(subtotal), table_right),
    ])

    tabela_itens = Table(
        corpo_itens,
        colWidths=[8 * mm, 86 * mm, 30 * mm, 13 * mm, 12 * mm, 20.5 * mm, 20.5 * mm],
        repeatRows=1,
        splitByRow=1,
    )
    tabela_itens.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("SPAN", (0, -1), (4, -1)),
        ("ALIGN", (5, -1), (6, -1), "RIGHT"),
    ]))
    story.append(tabela_itens)
    story.append(Spacer(1, 4.5 * mm))

    data_raw = primeiro_valor(
        dados_orcamento.get("data"),
        datetime.now(ZoneInfo("America/Sao_Paulo")).date().isoformat(),
    )
    try:
        data_fmt = datetime.fromisoformat(str(data_raw)[:10]).strftime("%d/%m/%Y")
    except Exception:
        data_fmt = str(data_raw)

    resumo_data = Table([
        [
            Paragraph("<b>Data</b>", normal),
            Paragraph("<b>Total dos itens</b>", table_right),
            Paragraph("<b>Total da proposta</b>", table_right),
        ],
        [
            Paragraph(escape_html(data_fmt), normal),
            Paragraph(numero_pt(subtotal), table_right),
            Paragraph(numero_pt(total_proposta), table_right),
        ],
    ], colWidths=[47 * mm, 71.5 * mm, 71.5 * mm])
    resumo_data.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDEDED")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(resumo_data)
    story.append(Spacer(1, 4 * mm))

    observacoes = dados_front.get("observacoes") or (
        "Somos um E-COMMERCE, não reservamos estoque antes da aprovação do pagamento."
    )
    resumo = dados_front.get("resumo_carrinho") or {}
    total_carrinho = float_seguro(primeiro_valor(resumo.get("total"), subtotal))
    valor_avista = float_seguro(resumo.get("avista"))
    valor_3x = float_seguro(resumo.get("parcela_3x"))
    valor_12x = float_seguro(resumo.get("parcela_12x"))

    if not valor_avista:
        valor_avista = total_carrinho * 0.98

    pagamentos_html = (
        "<b>Condições de pagamento:</b><br/>"
        f"Total: <b>R$ {numero_pt(total_carrinho)}</b><br/>"
        f"Pagamento à vista com desconto: <b>R$ {numero_pt(valor_avista)}</b><br/>"
        f"<b>3x de R$ {numero_pt(valor_3x)}</b> sem juros<br/>"
        f"<b>12x de R$ {numero_pt(valor_12x)}</b> com juros no cartão.<br/><br/>"
        "<i>*Frete a combinar. Entre em contato com nosso time de vendas para obter uma cotação.</i>"
    )
    
    observacoes_html = formatar_texto_para_pdf(observacoes)
    conteudo_obs = observacoes_html
    if conteudo_obs and pagamentos_html:
        conteudo_obs += "<br/><br/>" + pagamentos_html
    elif pagamentos_html:
        conteudo_obs = pagamentos_html

    observacoes_box = Table(
        [[Paragraph(conteudo_obs, normal)]],
        colWidths=[190 * mm],
    )
    observacoes_box.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.75, colors.black),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    story.append(Paragraph("<b>Observações</b>", normal))
    story.append(Spacer(1, 1.2 * mm))
    story.append(observacoes_box)
    story.append(Spacer(1, 4.5 * mm))

    story.append(Paragraph("Atenciosamente,", normal))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Departamento de Vendas.", normal))

    doc.build(story)
    buffer.seek(0)
    return buffer

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
    agora = int(time.time())
    expires_in = int(expires_in or 3600)
    expires_at = agora + expires_in - 60

    dados = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "updated_at": agora
    }

    print("[OAUTH DEBUG] Preparando salvamento dos tokens")
    print("[OAUTH DEBUG] expires_in recebido:", expires_in)
    print("[OAUTH DEBUG] expires_at:", expires_at)
    print("[OAUTH DEBUG] expires_at local:", formatar_timestamp(expires_at))
    print("[OAUTH DEBUG] access_token:", resumo_token(access_token))
    print("[OAUTH DEBUG] refresh_token:", resumo_token(refresh_token))

    redis_set(
        TINY_TOKEN_KEY,
        json.dumps(dados)
    )

    print("[OAUTH DEBUG] Tokens OAuth salvos no Upstash Redis.")

    tokens_salvos = carregar_tokens()
    if tokens_salvos:
        log_resumo_tokens(
            "CONFIRMAÇÃO APÓS SALVAR NO REDIS",
            tokens_salvos
        )
    else:
        print("[OAUTH DEBUG] ATENÇÃO: não foi possível reler os tokens após salvar.")

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
    

def fingerprint_token(token):
    """Identificador seguro do token para os logs, sem expor o valor completo."""
    if not token:
        return None
    return sha256(str(token).encode("utf-8")).hexdigest()[:12]


def resumo_token(token):
    """Resumo seguro de um token para diagnóstico."""
    if not token:
        return {
            "presente": False,
            "tamanho": 0,
            "inicio": None,
            "fingerprint": None,
        }

    token = str(token)
    return {
        "presente": True,
        "tamanho": len(token),
        "inicio": token[:8] + "...",
        "fingerprint": fingerprint_token(token),
    }


def formatar_timestamp(timestamp):
    if not timestamp:
        return None
    try:
        return datetime.fromtimestamp(
            int(timestamp),
            tz=ZoneInfo("America/Sao_Paulo")
        ).strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return str(timestamp)


def log_resumo_tokens(rotulo, tokens):
    tokens = tokens or {}
    agora = int(time.time())
    expires_at = int(tokens.get("expires_at") or 0)

    print("")
    print("=" * 80)
    print(f"[OAUTH DEBUG] {rotulo}")
    print("=" * 80)
    print("Horário atual:", formatar_timestamp(agora))
    print("Access token:", resumo_token(tokens.get("access_token")))
    print("Refresh token:", resumo_token(tokens.get("refresh_token")))
    print("Atualizado em:", formatar_timestamp(tokens.get("updated_at")))
    print("Expira em:", formatar_timestamp(expires_at))
    print(
        "Segundos restantes:",
        expires_at - agora if expires_at else None
    )
    print("Chaves armazenadas:", list(tokens.keys()))
    print("=" * 80)
    print("")


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

class HTMLParaTexto(HTMLParser):
    def __init__(self):
        super().__init__()
        self.partes = []
        self.tags_bloco = {
            "p",
            "div",
            "br",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "li",
        }

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "br":
            self.partes.append("\n")
        elif tag in self.tags_bloco:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag in self.tags_bloco and tag != "br":
            self.partes.append("\n")

    def handle_data(self, data):
        self.partes.append(data)


def html_para_texto(valor):
    if not valor:
        return ""

    parser = HTMLParaTexto()
    parser.feed(str(valor))
    parser.close()

    texto = "".join(parser.partes)

    texto = unescape(texto)

    linhas = []
    for linha in texto.splitlines():
        linha = " ".join(linha.split())
        if linha:
            linhas.append(linha)

    return "\n".join(linhas).strip()

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
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        print("[OAUTH DEBUG] refresh_token não encontrado.")
        raise TinyAPIError(
            "Refresh token não encontrado. Autorize novamente a aplicação no Tiny.",
            401,
            {"autorizacao": "/api/oauth/autorizar"}
        )

    log_resumo_tokens("ANTES DA RENOVAÇÃO AUTOMÁTICA", tokens)

    lock_token = secrets.token_urlsafe(32)
    lock_adquirido = False

    try:
        for tentativa in range(int(TINY_REFRESH_WAIT_SECONDS * 2)):
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
                print("[OAUTH DEBUG] Lock de renovação adquirido. Tentativa:", tentativa + 1)
                break

            time.sleep(0.5)
            tokens_atualizados = carregar_tokens()
            if not tokens_atualizados:
                continue

            novo_access = tokens_atualizados.get("access_token")
            novo_expires_at = int(tokens_atualizados.get("expires_at", 0))

            if (
                novo_access
                and novo_access != tokens.get("access_token")
                and int(time.time()) < novo_expires_at
            ):
                print("[OAUTH DEBUG] Outra execução já renovou o OAuth.")
                log_resumo_tokens("TOKENS RENOVADOS POR OUTRA EXECUÇÃO", tokens_atualizados)
                return {
                    "access_token": novo_access,
                    "refresh_token": tokens_atualizados.get("refresh_token"),
                    "expires_in": max(1, novo_expires_at - int(time.time()))
                }

        if not lock_adquirido:
            tokens_atualizados = carregar_tokens()
            if tokens_atualizados:
                novo_access = tokens_atualizados.get("access_token")
                novo_expires_at = int(tokens_atualizados.get("expires_at", 0))
                if (
                    novo_access
                    and novo_access != tokens.get("access_token")
                    and int(time.time()) < novo_expires_at
                ):
                    return {
                        "access_token": novo_access,
                        "refresh_token": tokens_atualizados.get("refresh_token"),
                        "expires_in": max(1, novo_expires_at - int(time.time()))
                    }

            raise TinyAPIError(
                "Outra requisição está renovando o acesso ao Tiny. Tente novamente em alguns segundos.",
                503,
                {"motivo": "lock_de_renovacao_oauth"}
            )

        tokens_atuais = carregar_tokens() or {}
        access_atual = tokens_atuais.get("access_token")
        expires_at_atual = int(tokens_atuais.get("expires_at", 0))
        refresh_atual = tokens_atuais.get("refresh_token")

        if (
            access_atual
            and int(time.time()) < expires_at_atual
            and access_atual != tokens.get("access_token")
        ):
            print("[OAUTH DEBUG] Tokens já foram renovados por outra execução.")
            return {
                "access_token": access_atual,
                "refresh_token": refresh_atual,
                "expires_in": max(1, expires_at_atual - int(time.time()))
            }

        refresh_token = refresh_atual or refresh_token

        print("[OAUTH DEBUG] Enviando refresh_token ao Tiny:", resumo_token(refresh_token))
        print("[OAUTH DEBUG] client_id configurado:", bool(TINY_CLIENT_ID))
        print("[OAUTH DEBUG] client_secret configurado:", bool(TINY_CLIENT_SECRET))
        print("[OAUTH DEBUG] URL OAuth:", TINY_TOKEN_URL)

        response = requests.post(
            TINY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": TINY_CLIENT_ID,
                "client_secret": TINY_CLIENT_SECRET,
                "refresh_token": refresh_token
            },
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            timeout=30
        )

        dados = resposta_json(response)

        print("[OAUTH DEBUG] Renovação OAuth Tiny HTTP:", response.status_code)
        print("[OAUTH DEBUG] Content-Type:", response.headers.get("Content-Type"))

        dados_log = dict(dados) if isinstance(dados, dict) else {"resposta": dados}
        if isinstance(dados_log, dict):
            if "access_token" in dados_log:
                dados_log["access_token"] = resumo_token(dados_log["access_token"])
            if "refresh_token" in dados_log:
                dados_log["refresh_token"] = resumo_token(dados_log["refresh_token"])
        print("[OAUTH DEBUG] Resposta resumida do Tiny:", dados_log)

        if not response.ok:
            texto_erro = json.dumps(dados, ensure_ascii=False).lower()
            invalid_grant = (
                "invalid_grant" in texto_erro
                or "token is not active" in texto_erro
                or "invalid_token" in texto_erro
            )

            if invalid_grant:
                print("[OAUTH DEBUG] O refresh_token foi rejeitado pelo Tiny.")
                print("[OAUTH DEBUG] Tokens NÃO serão apagados durante o diagnóstico.")
                raise TinyAPIError(
                    "O refresh token do Tiny não está mais ativo. É necessário autorizar novamente a aplicação no Tiny.",
                    401,
                    {
                        "resposta_tiny": dados,
                        "autorizacao": "/api/oauth/autorizar"
                    }
                )

            raise TinyAPIError(
                "Não foi possível renovar o access token.",
                response.status_code,
                dados
            )

        novo_access_token = dados.get("access_token")
        novo_refresh_token = dados.get("refresh_token") or refresh_token
        expires_in = dados.get("expires_in", 3600)

        print("[OAUTH DEBUG] Novo access_token:", resumo_token(novo_access_token))
        print("[OAUTH DEBUG] Novo refresh_token retornado:", resumo_token(dados.get("refresh_token")))
        print("[OAUTH DEBUG] Refresh token efetivamente salvo:", resumo_token(novo_refresh_token))
        print(
            "[OAUTH DEBUG] O refresh_token mudou:",
            fingerprint_token(novo_refresh_token) != fingerprint_token(refresh_token)
        )
        print("[OAUTH DEBUG] expires_in recebido:", expires_in)

        if not novo_access_token:
            raise TinyAPIError("Tiny não retornou novo access_token.", 502, dados)

        salvar_tokens(
            novo_access_token,
            novo_refresh_token,
            expires_in
        )

        print("[OAUTH DEBUG] Renovação concluída com sucesso.")
        return {
            "access_token": novo_access_token,
            "refresh_token": novo_refresh_token,
            "expires_in": expires_in
        }

    except requests.RequestException as e:
        print("[OAUTH DEBUG] Erro de comunicação durante o refresh:", repr(e))
        raise TinyAPIError(
            "Erro de comunicação durante a renovação do token.",
            None,
            str(e)
        )

    finally:
        if lock_adquirido:
            try:
                redis_delete(TINY_REFRESH_LOCK_KEY)
                print("[OAUTH DEBUG] Lock de renovação OAuth liberado.")
            except Exception as e:
                print("[OAUTH DEBUG] Não foi possível liberar o lock:", str(e))

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

            texto_erro = json.dumps(
                dados,
                ensure_ascii=False
            ).lower()

            contato_nao_encontrado = (
                "cpf/cnpj not found" in texto_erro
                or
                "cpf/cnpj não encontrado" in texto_erro
                or
                "cpf/cnpj nao encontrado" in texto_erro
                or
                "cpf ou cnpj não encontrado" in texto_erro
                or
                "cpf ou cnpj nao encontrado" in texto_erro
                or
                (
                    response.status_code == 404
                    and (
                        "not found" in texto_erro
                        or
                        "não encontrado" in texto_erro
                        or
                        "nao encontrado" in texto_erro
                    )
                )
            )

            if contato_nao_encontrado:
                print(
                    "CPF/CNPJ não encontrado no Tiny. "
                    "O contato será criado automaticamente."
                )

                return None

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

    if len(documento) not in (11, 14):
        raise TinyAPIError(
            "CPF/CNPJ inválido. O documento deve conter 11 dígitos (CPF) "
            "ou 14 dígitos (CNPJ)."
        )

    if not nome:
        raise TinyAPIError(
            "Nome do cliente não informado."
        )

    codigo = f"{documento}"


    tipo_pessoa = "J" if len(documento) == 14 else "F"

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
        "tipoPessoa": tipo_pessoa,
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
                busca_exaustiva=False
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
        "tipoPessoa": tipo_pessoa,
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
        busca_exaustiva=False
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

def obter_produto_por_id(produto_id):
    if not produto_id:
        return None

    response = tiny_request(
        "GET",
        f"/produtos/{produto_id}"
    )

    dados = resposta_json(response)

    print(
        "Consulta produto por ID",
        produto_id,
        "HTTP",
        response.status_code
    )

    if not response.ok:
        raise TinyAPIError(
            "Erro ao obter produto pelo ID.",
            response.status_code,
            dados
        )

    return dados

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

            produto_detalhado = obter_produto_por_id(
                produto_id
            )

            descricao_complementar = (
                produto_detalhado.get("descricaoComplementar")
                if isinstance(produto_detalhado, dict)
                else None
            )

            if descricao_complementar:
                item_tiny["descrComplementarOrc"] = html_para_texto(descricao_complementar)


            itens_tiny.append(
                item_tiny
            )

        introducao_proposta = (
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
            "Condições de pagamento:\n"
            f"Total: {dinheiro(total_carrinho)}\n"
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
                data_proximo_contato_str,

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

            # O PDF é produzido localmente pelo backend, usando os dados
            # efetivamente persistidos no Tiny e os dados do formulário.
            pdf_buffer = gerar_pdf_proposta(
                dados_front,
                dados_orcamento,
                contato,
                orcamento_id
            )

            resposta = send_file(
                pdf_buffer,
                mimetype="application/pdf",
                as_attachment=False,
                download_name=f"proposta_comercial{orcamento_id}.pdf"
            )

            # Força abertura inline no navegador em vez de download automático.
            resposta.headers["Content-Disposition"] = (
                f'inline; filename="proposta_comercial{orcamento_id}.pdf"'
            )
            resposta.headers["X-Proposta-Id"] = str(orcamento_id)

            return resposta

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
    "/api/oauth/testar-refresh",
    methods=["GET"]
)
def testar_refresh_oauth():
    """Força uma renovação OAuth. Rota temporária para diagnóstico."""
    inicio = int(time.time())
    print("#" * 80)
    print("[OAUTH TESTE] INÍCIO DO TESTE DE REFRESH")
    print("[OAUTH TESTE] Horário:", formatar_timestamp(inicio))
    print("#" * 80)

    try:
        tokens = carregar_tokens()
        if not tokens:
            return jsonify({
                "sucesso": False,
                "mensagem": "Nenhum token encontrado. Faça a autorização manual primeiro.",
                "autorizacao": "/api/oauth/autorizar"
            }), 401

        log_resumo_tokens("TOKENS ANTES DO TESTE", tokens)
        print("[OAUTH TESTE] Forçando refresh mesmo com access_token válido.")

        novos_tokens = renovar_access_token(tokens)
        tokens_depois = carregar_tokens()
        log_resumo_tokens("TOKENS DEPOIS DO TESTE", tokens_depois)

        fim = int(time.time())
        print("[OAUTH TESTE] SUCESSO. Duração:", fim - inicio, "segundos")

        return jsonify({
            "sucesso": True,
            "mensagem": "Refresh automático executado com sucesso. Consulte os logs da Vercel.",
            "access_token_recebido": bool(novos_tokens.get("access_token")),
            "refresh_token_recebido": bool(novos_tokens.get("refresh_token")),
            "expires_in": novos_tokens.get("expires_in"),
            "duracao_segundos": fim - inicio
        }), 200

    except TinyAPIError as e:
        print("[OAUTH TESTE] FALHA:", e.mensagem)
        return jsonify({
            "sucesso": False,
            "mensagem": e.mensagem,
            "detalhes": e.resposta,
            "autorizacao": "/api/oauth/autorizar"
        }), e.status or 500

    except Exception as e:
        print("[OAUTH TESTE] ERRO INESPERADO:", repr(e))
        return jsonify({
            "sucesso": False,
            "mensagem": "Erro inesperado durante o teste.",
            "detalhes": str(e)
        }), 500

@app.route("/api/oauth/renovar-agendado", methods=["GET"])
def renovar_oauth_agendado():

    inicio = int(time.time())

    print("")
    print("#" * 80)
    print("[OAUTH CRON] INÍCIO DA RENOVAÇÃO AGENDADA")
    print("[OAUTH CRON] Horário:", formatar_timestamp(inicio))
    print("#" * 80)

    cron_secret = os.getenv("CRON_SECRET")

    authorization = request.headers.get(
        "Authorization",
        ""
    )

    token_recebido = ""

    if authorization.startswith("Bearer "):
        token_recebido = authorization[7:]

    if not cron_secret:
        print(
            "[OAUTH CRON] ERRO: CRON_SECRET não configurado."
        )

        return jsonify({
            "sucesso": False,
            "mensagem": "CRON_SECRET não configurado no servidor."
        }), 500

    if token_recebido != cron_secret:
        print(
            "[OAUTH CRON] Acesso negado: segredo do cron inválido."
        )

        return jsonify({
            "sucesso": False,
            "mensagem": "Não autorizado."
        }), 401

    print(
        "[OAUTH CRON] Autenticação do cron validada."
    )

    try:
        tokens_antes = carregar_tokens()

        if not tokens_antes:
            print(
                "[OAUTH CRON] Nenhum token encontrado no Redis."
            )

            return jsonify({
                "sucesso": False,
                "mensagem": (
                    "Nenhum token OAuth armazenado. "
                    "É necessária uma autorização manual."
                ),
                "precisa_autorizar": True
            }), 401

        log_resumo_tokens(
            "TOKENS ANTES DA RENOVAÇÃO AGENDADA",
            tokens_antes
        )

        print(
            "[OAUTH CRON] Forçando renovação do access_token."
        )

        novos_tokens = renovar_access_token(
            tokens_antes
        )

        tokens_depois = carregar_tokens()

        if tokens_depois:
            log_resumo_tokens(
                "TOKENS DEPOIS DA RENOVAÇÃO AGENDADA",
                tokens_depois
            )

        fim = int(time.time())

        print("")
        print("#" * 80)
        print("[OAUTH CRON] RENOVAÇÃO CONCLUÍDA COM SUCESSO")
        print(
            "[OAUTH CRON] Duração:",
            fim - inicio,
            "segundos"
        )
        print("#" * 80)

        return jsonify({
            "sucesso": True,
            "mensagem": "Renovação OAuth agendada executada com sucesso.",
            "access_token_recebido": bool(
                novos_tokens.get("access_token")
            ),
            "refresh_token_recebido": bool(
                novos_tokens.get("refresh_token")
            ),
            "expires_in": novos_tokens.get("expires_in"),
            "duracao_segundos": fim - inicio
        }), 200

    except TinyAPIError as e:
        fim = int(time.time())

        print("")
        print("#" * 80)
        print("[OAUTH CRON] FALHA NA RENOVAÇÃO")
        print("[OAUTH CRON] Mensagem:", str(e))
        print(
            "[OAUTH CRON] Duração:",
            fim - inicio,
            "segundos"
        )
        print("#" * 80)

        return jsonify({
            "sucesso": False,
            "mensagem": str(e),
            "detalhes": getattr(e, "detalhes", None),
            "precisa_autorizar": True,
            "autorizacao": "/api/oauth/autorizar"
        }), getattr(e, "status_code", 500) or 500

    except Exception as e:
        print(
            "[OAUTH CRON] Erro inesperado:",
            repr(e)
        )

        return jsonify({
            "sucesso": False,
            "mensagem": "Erro inesperado durante a renovação agendada.",
            "detalhes": str(e)
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

            "testar_refresh":
                "/api/oauth/testar-refresh",

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

@app.route(
    "/api/imprimir-proposta/<int:id_proposta>",
    methods=["POST"]
)
def imprimir_proposta(id_proposta):
    try:
        response = tiny_request(
            "POST",
            f"/orcamentos/{id_proposta}/imprimir"
        )
        
        dados = resposta_json(response)
        
        print(f"POST /orcamentos/{id_proposta}/imprimir:", response.status_code)

        if not response.ok:
            return jsonify({
                "erro": "Falha ao gerar o PDF da proposta.",
                "status_tiny": response.status_code,
                "resposta_tiny": dados
            }), response.status_code

        return jsonify(dados), 200

    except TinyAPIError as e:
        return jsonify({
            "erro": e.mensagem,
            "status_tiny": e.status,
            "resposta_tiny": e.resposta
        }), e.status or 502

    except Exception as e:
        return jsonify({
            "erro": "Erro interno ao tentar imprimir.",
            "detalhes": str(e)
        }), 500