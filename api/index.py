import os
import json
import traceback
from io import BytesIO
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional
from xml.sax.saxutils import escape

import requests

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from pydantic import BaseModel

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI()


app.add_middleware(
    CORSMiddleware,

    allow_origins=["*"],

    allow_credentials=False,

    allow_methods=["*"],

    allow_headers=["*"],
)


# ============================================================
# CONFIGURAÇÕES
# ============================================================

TINY_TOKEN = "f751b8c151b478f9472103ef94669425592b01d1"

TINY_PEDIDO_URL = (
    "https://api.tiny.com.br/api2/pedido.incluir.php"
)


# ============================================================
# DADOS DA EMPRESA
# ============================================================
#
# Os valores abaixo foram baseados no PDF que você enviou.
#
# Recomendo posteriormente colocar isso também em variáveis
# de ambiente.
# ============================================================

EMPRESA = {
    "nome":
        os.getenv(
            "EMPRESA_NOME",
            "BRFER COMÉRCIO DE FERRAMENTAS LTDA"
        ),

    "cnpj":
        os.getenv(
            "EMPRESA_CNPJ",
            "40.954.410/0001-96"
        ),

    "site":
        os.getenv(
            "EMPRESA_SITE",
            "www.brfer.com.br"
        ),

    "telefone":
        os.getenv(
            "EMPRESA_TELEFONE",
            "(11) 4362-5151"
        ),

    "endereco":
        os.getenv(
            "EMPRESA_ENDERECO",
            "Rua Coronel Francisco Rodrigues Seckler, 53, galpão"
        ),

    "cidade":
        os.getenv(
            "EMPRESA_CIDADE",
            "Paulicéia, São Bernardo do Campo - SP"
        ),

    "cep":
        os.getenv(
            "EMPRESA_CEP",
            "09.693-050"
        ),

    "banco":
        os.getenv(
            "EMPRESA_BANCO",
            "341 – Itaú"
        ),

    "agencia":
        os.getenv(
            "EMPRESA_AGENCIA",
            "8811"
        ),

    "conta":
        os.getenv(
            "EMPRESA_CONTA",
            "99874-2"
        ),

    "favorecido":
        os.getenv(
            "EMPRESA_FAVORECIDO",
            "BRFER Comércio de Ferramentas LTDA"
        ),

    "pix":
        os.getenv(
            "EMPRESA_PIX",
            "CNPJ"
        )
}


# ============================================================
# MODELOS
# ============================================================

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


class EnderecoProposta(BaseModel):

    cep: Optional[str] = ""

    logradouro: Optional[str] = ""

    numero: Optional[str] = ""

    bairro: Optional[str] = ""

    cidade: Optional[str] = ""

    uf: Optional[str] = ""


class PropostaTinyPayload(BaseModel):

    natureza_operacao: Optional[str] = (
        "Venda de Mercadorias para Consumidor Final"
    )

    cliente: ClienteProposta

    vendedor: Optional[str] = (
        "Departamento de vendas"
    )

    introducao: Optional[str] = ""

    carrinho: List[ItemProposta]

    frete: Optional[float] = 0.00

    desconto: Optional[float] = 0.00

    forma_envio: Optional[str] = "Transportadora"

    validade_dias: Optional[int] = 3

    descricao_prazo_entrega: Optional[str] = (
        "IMEDIATO APÓS CONFIRMAÇÃO DO PAGAMENTO"
    )

    email: Optional[str] = ""

    telefone: Optional[str] = ""

    endereco: Optional[EnderecoProposta] = (
        EnderecoProposta()
    )

    condicoes_comerciais: Optional[str] = ""

    condicoes_pagamento: Optional[str] = ""

    observacoes: Optional[str] = ""

    assinatura: Optional[str] = (
        "Atenciosamente,\nDepartamento de vendas"
    )


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def moeda(valor):
    """
    Converte número para formato brasileiro:
    1234.56 -> R$ 1.234,56
    """

    valor = Decimal(
        str(valor)
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    texto = f"{valor:,.2f}"

    texto = (
        texto
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    return f"R$ {texto}"


def numero_br(valor):
    """
    1234.56 -> 1.234,56
    """

    valor = Decimal(
        str(valor)
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    texto = f"{valor:,.2f}"

    return (
        texto
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


def texto_pdf(texto):
    """
    Escapa caracteres especiais para Paragraph do ReportLab.
    """

    if texto is None:
        return ""

    return escape(
        str(texto)
    ).replace(
        "\n",
        "<br/>"
    )


def tipo_pessoa(cpf_cnpj):
    """
    Tenta determinar F/J pelo tamanho do documento.
    """

    if not cpf_cnpj:
        return ""

    somente_numeros = "".join(
        c for c in cpf_cnpj
        if c.isdigit()
    )

    if len(somente_numeros) == 14:
        return "J"

    if len(somente_numeros) == 11:
        return "F"

    return ""


# ============================================================
# GERAR PDF
# ============================================================

def gerar_pdf_proposta(
    payload: PropostaTinyPayload,
    numero_pedido: str
):

    buffer = BytesIO()

    # --------------------------------------------------------
    # DOCUMENTO
    # --------------------------------------------------------

    doc = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=15 * mm,
        leftMargin=15 * mm,

        topMargin=15 * mm,
        bottomMargin=18 * mm,

        title=(
            f"Proposta Comercial Nº {numero_pedido}"
        ),

        author=EMPRESA["nome"]
    )

    # --------------------------------------------------------
    # ESTILOS
    # --------------------------------------------------------

    styles = getSampleStyleSheet()

    estilo_normal = ParagraphStyle(
        "NormalCustom",

        parent=styles["Normal"],

        fontName="Helvetica",

        fontSize=8.5,

        leading=11,

        spaceAfter=3
    )

    estilo_pequeno = ParagraphStyle(
        "Pequeno",

        parent=estilo_normal,

        fontSize=7.5,

        leading=9
    )

    estilo_titulo = ParagraphStyle(
        "Titulo",

        parent=styles["Heading1"],

        fontName="Helvetica-Bold",

        fontSize=15,

        leading=18,

        alignment=TA_LEFT,

        spaceAfter=5
    )

    estilo_subtitulo = ParagraphStyle(
        "Subtitulo",

        parent=styles["Heading2"],

        fontName="Helvetica-Bold",

        fontSize=10,

        leading=12,

        spaceBefore=7,

        spaceAfter=5
    )

    estilo_destaque = ParagraphStyle(
        "Destaque",

        parent=estilo_normal,

        fontName="Helvetica-Bold",

        fontSize=9
    )

    estilo_direita = ParagraphStyle(
        "Direita",

        parent=estilo_normal,

        alignment=TA_RIGHT
    )

    estilo_centro = ParagraphStyle(
        "Centro",

        parent=estilo_normal,

        alignment=TA_CENTER
    )

    estilo_total = ParagraphStyle(
        "Total",

        parent=estilo_normal,

        fontName="Helvetica-Bold",

        fontSize=10,

        alignment=TA_RIGHT
    )

    # --------------------------------------------------------
    # STORY
    # --------------------------------------------------------

    story = []

    # ========================================================
    # CABEÇALHO
    # ========================================================

    cabecalho_esquerda = [

        Paragraph(
            texto_pdf(EMPRESA["nome"]),
            ParagraphStyle(
                "Empresa",
                parent=estilo_normal,
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=13
            )
        ),

        Paragraph(
            f"CNPJ: {texto_pdf(EMPRESA['cnpj'])}",
            estilo_pequeno
        ),

        Paragraph(
            texto_pdf(EMPRESA["site"]),
            estilo_pequeno
        ),

        Paragraph(
            texto_pdf(EMPRESA["telefone"]),
            estilo_pequeno
        ),

        Paragraph(
            texto_pdf(EMPRESA["endereco"]),
            estilo_pequeno
        ),

        Paragraph(
            texto_pdf(EMPRESA["cidade"]),
            estilo_pequeno
        ),

        Paragraph(
            texto_pdf(EMPRESA["cep"]),
            estilo_pequeno
        )
    ]

    cabecalho_direita = [

        Paragraph(
            "PROPOSTA COMERCIAL",
            ParagraphStyle(
                "TituloCabecalho",
                parent=estilo_titulo,
                alignment=TA_RIGHT,
                fontSize=13
            )
        ),

        Paragraph(
            f"Nº {texto_pdf(numero_pedido)}",
            ParagraphStyle(
                "Numero",
                parent=estilo_destaque,
                alignment=TA_RIGHT,
                fontSize=10
            )
        ),

        Spacer(1, 5),

        Paragraph(
            datetime.now().strftime("%d/%m/%Y"),
            estilo_direita
        )
    ]

    tabela_cabecalho = Table(
        [
            [
                cabecalho_esquerda,
                cabecalho_direita
            ]
        ],
        colWidths=[
            110 * mm,
            65 * mm
        ]
    )

    tabela_cabecalho.setStyle(
        TableStyle([
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LINEBELOW",
                (0, 0),
                (-1, 0),
                1,
                colors.black
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                0
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                0
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                0
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            )
        ])
    )

    story.append(
        tabela_cabecalho
    )

    story.append(
        Spacer(1, 8)
    )

    # ========================================================
    # CLIENTE
    # ========================================================

    endereco = payload.endereco

    endereco_cliente = (
        f"{endereco.logradouro}, Nº {endereco.numero}"
    )

    if endereco.bairro:
        endereco_cliente += (
            f", {endereco.bairro}"
        )

    cidade_uf = endereco.cidade

    if endereco.uf:
        cidade_uf += f" - {endereco.uf}"

    if endereco.cep:
        cidade_uf += f" - {endereco.cep}"

    cliente_dados = [

        [
            Paragraph(
                "<b>Para</b>",
                estilo_normal
            ),

            Paragraph(
                f"<b>{texto_pdf(payload.cliente.nome)}</b>",
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Aos cuidados de</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.cliente.aos_cuidados
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>CPF/CNPJ</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.cliente.cpf_cnpj
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Endereço</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    endereco_cliente
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Cidade</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    cidade_uf
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Fone</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.telefone
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>E-mail</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.email
                ),
                estilo_normal
            )
        ]
    ]

    tabela_cliente = Table(
        cliente_dados,
        colWidths=[
            32 * mm,
            143 * mm
        ]
    )

    tabela_cliente.setStyle(
        TableStyle([
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                2
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                2
            )
        ])
    )

    story.append(
        tabela_cliente
    )

    story.append(
        Spacer(1, 8)
    )

    # ========================================================
    # INTRODUÇÃO
    # ========================================================

    introducao = payload.introducao.strip()

    if not introducao:

        introducao = (
            "Prezado cliente, seguem abaixo "
            "nossa proposta comercial."
        )

    story.append(
        Paragraph(
            texto_pdf(introducao),
            estilo_normal
        )
    )

    story.append(
        Spacer(1, 4)
    )

    # ========================================================
    # DADOS BANCÁRIOS
    # ========================================================

    story.append(
        Paragraph(
            "Dados para pagamento",
            estilo_subtitulo
        )
    )

    dados_bancarios = [

        [
            Paragraph(
                "<b>Favorecido</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    EMPRESA["favorecido"]
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>CNPJ</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    EMPRESA["cnpj"]
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Banco</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    EMPRESA["banco"]
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Agência</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    EMPRESA["agencia"]
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Conta Corrente</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    EMPRESA["conta"]
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>PIX</b>",
                estilo_normal
            ),

            Paragraph(
                f"Chave: {texto_pdf(EMPRESA['pix'])}",
                estilo_normal
            )
        ]
    ]

    tabela_banco = Table(
        dados_bancarios,
        colWidths=[
            35 * mm,
            140 * mm
        ]
    )

    tabela_banco.setStyle(
        TableStyle([
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                colors.lightgrey
            ),

            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.lightgrey
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                3
            )
        ])
    )

    story.append(
        tabela_banco
    )

    # ========================================================
    # ITENS
    # ========================================================

    story.append(
        Paragraph(
            "Itens de produto ou serviço",
            estilo_subtitulo
        )
    )

    tabela_itens = []

    tabela_itens.append([
        Paragraph("<b>Nº</b>", estilo_centro),
        Paragraph("<b>SKU</b>", estilo_centro),
        Paragraph("<b>Produto</b>", estilo_centro),
        Paragraph("<b>Qtd</b>", estilo_centro),
        Paragraph("<b>Un</b>", estilo_centro),
        Paragraph("<b>Preço un.</b>", estilo_centro),
        Paragraph("<b>Total</b>", estilo_centro)
    ])

    total_itens = Decimal("0.00")
    quantidade_total = Decimal("0.00")

    for indice, item in enumerate(
        payload.carrinho,
        start=1
    ):

        quantidade = Decimal(
            str(item.quantidade)
        )

        preco = Decimal(
            str(item.preco_unitario)
        )

        total_item = (
            quantidade * preco
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        total_itens += total_item
        quantidade_total += quantidade

        tabela_itens.append([

            Paragraph(
                str(indice),
                estilo_centro
            ),

            Paragraph(
                texto_pdf(item.codigo),
                estilo_centro
            ),

            Paragraph(
                texto_pdf(item.descricao),
                estilo_normal
            ),

            Paragraph(
                numero_br(quantidade),
                estilo_centro
            ),

            Paragraph(
                texto_pdf(item.unidade),
                estilo_centro
            ),

            Paragraph(
                moeda(preco),
                estilo_direita
            ),

            Paragraph(
                moeda(total_item),
                estilo_direita
            )
        ])

    tabela_produtos = Table(
        tabela_itens,

        colWidths=[
            9 * mm,
            22 * mm,
            70 * mm,
            15 * mm,
            12 * mm,
            23 * mm,
            24 * mm
        ],

        repeatRows=1
    )

    tabela_produtos.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#eeeeee")
            ),

            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),

            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.lightgrey
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            )
        ])
    )

    story.append(
        tabela_produtos
    )

    # ========================================================
    # RESUMO
    # ========================================================

    story.append(
        Spacer(1, 5)
    )

    desconto = Decimal(
        str(payload.desconto or 0)
    )

    frete = Decimal(
        str(payload.frete or 0)
    )

    total_proposta = (
        total_itens
        - desconto
        + frete
    )

    resumo = [

        [
            Paragraph(
                "<b>Número de itens</b>",
                estilo_normal
            ),

            Paragraph(
                str(len(payload.carrinho)),
                estilo_direita
            )
        ],

        [
            Paragraph(
                "<b>Soma das quantidades</b>",
                estilo_normal
            ),

            Paragraph(
                numero_br(quantidade_total),
                estilo_direita
            )
        ],

        [
            Paragraph(
                "<b>Total dos itens</b>",
                estilo_normal
            ),

            Paragraph(
                moeda(total_itens),
                estilo_direita
            )
        ],

        [
            Paragraph(
                "<b>Desconto</b>",
                estilo_normal
            ),

            Paragraph(
                moeda(desconto),
                estilo_direita
            )
        ],

        [
            Paragraph(
                "<b>Frete</b>",
                estilo_normal
            ),

            Paragraph(
                moeda(frete),
                estilo_direita
            )
        ],

        [
            Paragraph(
                "<b>TOTAL DA PROPOSTA</b>",
                estilo_destaque
            ),

            Paragraph(
                moeda(total_proposta),
                estilo_total
            )
        ]
    ]

    tabela_resumo = Table(
        resumo,
        colWidths=[
            125 * mm,
            50 * mm
        ]
    )

    tabela_resumo.setStyle(
        TableStyle([
            (
                "LINEABOVE",
                (0, -1),
                (-1, -1),
                1,
                colors.black
            ),

            (
                "BACKGROUND",
                (0, -1),
                (-1, -1),
                colors.HexColor("#eeeeee")
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                3
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                3
            )
        ])
    )

    story.append(
        tabela_resumo
    )

    # ========================================================
    # CONDIÇÕES COMERCIAIS
    # ========================================================

    story.append(
        Paragraph(
            "Condições comerciais",
            estilo_subtitulo
        )
    )

    if payload.condicoes_comerciais:

        story.append(
            Paragraph(
                texto_pdf(
                    payload.condicoes_comerciais
                ),
                estilo_normal
            )
        )

    if payload.condicoes_pagamento:

        story.append(
            Paragraph(
                "<b>Condições de Pagamento:</b>",
                estilo_normal
            )
        )

        story.append(
            Paragraph(
                texto_pdf(
                    payload.condicoes_pagamento
                ),
                estilo_normal
            )
        )

    # ========================================================
    # CONDIÇÕES GERAIS
    # ========================================================

    story.append(
        Paragraph(
            "Condições gerais",
            estilo_subtitulo
        )
    )

    condicoes_gerais = [

        [
            Paragraph(
                "<b>Descrição do prazo de entrega</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.descricao_prazo_entrega
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Forma de envio</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.forma_envio
                ),
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Validade da proposta</b>",
                estilo_normal
            ),

            Paragraph(
                f"{payload.validade_dias} dias",
                estilo_normal
            )
        ],

        [
            Paragraph(
                "<b>Vendedor</b>",
                estilo_normal
            ),

            Paragraph(
                texto_pdf(
                    payload.vendedor
                ),
                estilo_normal
            )
        ]
    ]

    tabela_condicoes = Table(
        condicoes_gerais,
        colWidths=[
            55 * mm,
            120 * mm
        ]
    )

    tabela_condicoes.setStyle(
        TableStyle([
            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.5,
                colors.lightgrey
            ),

            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.25,
                colors.lightgrey
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            )
        ])
    )

    story.append(
        tabela_condicoes
    )

    # ========================================================
    # OBSERVAÇÕES
    # ========================================================

    if payload.observacoes:

        story.append(
            Paragraph(
                "Observações",
                estilo_subtitulo
            )
        )

        story.append(
            Paragraph(
                texto_pdf(
                    payload.observacoes
                ),
                estilo_normal
            )
        )

    # ========================================================
    # FINAL
    # ========================================================

    story.append(
        Spacer(1, 10)
    )

    story.append(
        Paragraph(
            "Agradecemos a compreensão e aguardamos por sua compra!",
            estilo_normal
        )
    )

    story.append(
        Spacer(1, 8)
    )

    story.append(
        Paragraph(
            texto_pdf(
                payload.assinatura
            ),
            estilo_normal
        )
    )

    # ========================================================
    # RODAPÉ
    # ========================================================

    def footer(canvas, document):

        canvas.saveState()

        canvas.setFont(
            "Helvetica",
            7
        )

        canvas.drawString(
            15 * mm,
            8 * mm,
            EMPRESA["nome"]
        )

        canvas.drawRightString(
            A4[0] - 15 * mm,
            8 * mm,
            f"Página {document.page}"
        )

        canvas.restoreState()

    # ========================================================
    # GERAR
    # ========================================================

    doc.build(
        story,
        onFirstPage=footer,
        onLaterPages=footer
    )

    return buffer.getvalue()


# ============================================================
# OPTIONS / CORS
# ============================================================

@app.options("/{full_path:path}")
def options_proposta(full_path: str):

    return JSONResponse(
        status_code=200,
        content={
            "status": "ok"
        }
    )

@app.get("/teste")
def teste():

    return {
        "status": "ok",
        "tiny_token_configurado": bool(
            TINY_TOKEN
        )
    }

@app.post("/{full_path:path}")
def criar_proposta(
    payload: PropostaTinyPayload,
    full_path: str
):

    try:

        if not TINY_TOKEN:

            return JSONResponse(
                status_code=500,

                content={
                    "status": "erro",

                    "detalhe":
                        "TINY_TOKEN não está configurado "
                        "nas variáveis de ambiente."
                }
            )

        itens_tiny = []

        for item in payload.carrinho:

            item_tiny = {

                "codigo":
                    item.codigo,

                "descricao":
                    item.descricao,

                "unidade":
                    item.unidade,

                "quantidade":
                    item.quantidade,

                "valor_unitario":
                    item.preco_unitario
            }

            itens_tiny.append({
                "item": item_tiny
            })

        endereco = payload.endereco

        pedido = {

            "data_pedido":
                datetime.now().strftime("%d/%m/%Y"),

            "cliente": {

                "nome":
                    payload.cliente.nome,

                "tipo_pessoa":
                    tipo_pessoa(
                        payload.cliente.cpf_cnpj
                    ),

                "cpf_cnpj":
                    payload.cliente.cpf_cnpj,

                "endereco":
                    endereco.logradouro,

                "numero":
                    endereco.numero,

                "bairro":
                    endereco.bairro,

                "cep":
                    endereco.cep,

                "cidade":
                    endereco.cidade,

                "uf":
                    endereco.uf,

                "fone":
                    payload.telefone,

                "email":
                    payload.email,

                "atualizar_cliente":
                    "S"
            },

            "itens":
                itens_tiny,

            "valor_frete":
                payload.frete,

            "valor_desconto":
                payload.desconto,

            "forma_envio":
                payload.forma_envio,

            "nome_vendedor":
                payload.vendedor,

            "obs":
                (
                    "SOLICITAÇÃO DE COTAÇÃO VIA SITE\n"
                    f"Email: {payload.email}\n"
                    f"Telefone: {payload.telefone}\n"
                    f"Aos cuidados de: "
                    f"{payload.cliente.aos_cuidados}\n"
                    f"Validade da proposta: "
                    f"{payload.validade_dias} dias\n"
                    f"Prazo de entrega: "
                    f"{payload.descricao_prazo_entrega}"
                )[:100],

            "obs_internas":
                (
                    "Origem: Site / Tray\n"
                    "Tipo: Solicitação de orçamento"
                )[:100],

            "numero_pedido_ecommerce":
                datetime.now().strftime(
                    "%Y%m%d%H%M%S%f"
                )[:50],

            "ecommerce":
                "Site - Solicitação de Cotação",

            "marcadores": [
                {
                    "marcador": {
                        "descricao":
                            "Solicitação de orçamento via site"
                    }
                }
            ],

            "nome_natureza_operacao":
                payload.natureza_operacao
        }

        situacao_tiny = os.getenv(
            "TINY_SITUACAO",
            "Aberto"
        )

        if situacao_tiny:

            pedido["situacao"] = situacao_tiny

        dados_tiny = {
            "pedido": pedido
        }

        print()
        print("=" * 70)
        print("PEDIDO ENVIADO AO TINY")
        print("=" * 70)

        print(
            json.dumps(
                dados_tiny,
                indent=4,
                ensure_ascii=False
            )
        )

        response_tiny = requests.post(

            TINY_PEDIDO_URL,

            data={

                "token":
                    TINY_TOKEN,

                "formato":
                    "JSON",

                "pedido":
                    json.dumps(
                        dados_tiny,
                        ensure_ascii=False
                    )
            },

            timeout=30
        )

        print()
        print("=" * 70)
        print(
            "HTTP TINY:",
            response_tiny.status_code
        )
        print("=" * 70)

        print(
            response_tiny.text
        )


        try:

            resposta_tiny = (
                response_tiny.json()
            )

        except Exception:

            return JSONResponse(

                status_code=502,

                content={

                    "status":
                        "erro",

                    "detalhe":
                        (
                            "Tiny retornou uma resposta "
                            "que não é JSON."
                        ),

                    "tiny_http":
                        response_tiny.status_code,

                    "tiny_resposta":
                        response_tiny.text[:1000]
                }
            )


        retorno = (
            resposta_tiny
            .get("retorno", {})
        )

        status_tiny = retorno.get(
            "status"
        )

        if status_tiny != "OK":

            erros = retorno.get(
                "erros",
                []
            )

            registros = retorno.get(
                "registros",
                []
            )

            print(
                "ERRO NO TINY:",
                json.dumps(
                    resposta_tiny,
                    indent=4,
                    ensure_ascii=False
                )
            )

            return JSONResponse(

                status_code=400,

                content={

                    "status":
                        "erro",

                    "detalhe":
                        "Tiny recusou a inclusão do pedido.",

                    "erros":
                        erros,

                    "registros":
                        registros,

                    "tiny":
                        resposta_tiny
                }
            )

        registros = retorno.get(
            "registros",
            {}
        )

        registro = {}

        if isinstance(
            registros,
            dict
        ):

            registro = registros.get(
                "registro",
                {}
            )

        elif isinstance(
            registros,
            list
        ) and registros:

            registro = registros[0].get(
                "registro",
                {}
            )

        pedido_id = registro.get(
            "id"
        )

        pedido_numero = registro.get(
            "numero"
        )

        if not pedido_id:

            return JSONResponse(

                status_code=502,

                content={

                    "status":
                        "erro",

                    "detalhe":
                        (
                            "O Tiny informou sucesso, "
                            "mas não retornou o ID do pedido."
                        ),

                    "tiny":
                        resposta_tiny
                }
            )

        if not pedido_numero:

            pedido_numero = pedido_id

        print()
        print("=" * 70)
        print("PEDIDO CRIADO NO TINY")
        print("=" * 70)

        print(
            "ID:",
            pedido_id
        )

        print(
            "NÚMERO:",
            pedido_numero
        )

        try:

            pdf_bytes = gerar_pdf_proposta(

                payload,

                str(pedido_numero)
            )

        except Exception as pdf_error:

            print(
                "ERRO AO GERAR PDF:"
            )

            print(
                traceback.format_exc()
            )

            return JSONResponse(

                status_code=500,

                content={

                    "status":
                        "erro",

                    "detalhe":
                        (
                            "O pedido foi criado no Tiny, "
                            "mas ocorreu um erro ao gerar o PDF."
                        ),

                    "pedido_id":
                        pedido_id,

                    "pedido_numero":
                        pedido_numero,

                    "erro_pdf":
                        str(pdf_error)
                }
            )
        
        nome_arquivo = (
            f"Proposta_Comercial_{pedido_numero}.pdf"
        )

        return Response(

            content=pdf_bytes,

            media_type="application/pdf",

            headers={

                "Content-Disposition":
                    f'inline; filename="{nome_arquivo}"',

                "X-Tiny-Pedido-ID":
                    str(pedido_id),

                "X-Tiny-Pedido-Numero":
                    str(pedido_numero)
            }
        )

    except Exception as e:

        print(
            "EXCEÇÃO NÃO TRATADA:"
        )

        print(
            traceback.format_exc()
        )

        return JSONResponse(

            status_code=500,

            content={

                "status":
                    "erro",

                "detalhe":
                    str(e)
            }
        )