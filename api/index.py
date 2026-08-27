from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "mensagem": "Backend Flask funcionando na Vercel"
    })


@app.route("/api/testar-tiny", methods=["GET"])
def testar_tiny():
    return jsonify({
        "status": "ok",
        "mensagem": "Rota /api/testar-tiny funcionando"
    })


@app.route("/api/gerar-proposta", methods=["POST"])
def gerar_proposta():
    return jsonify({
        "status": "ok",
        "mensagem": "Rota /api/gerar-proposta funcionando"
    })


@app.route("/api/obter-proposta/<int:id_proposta>", methods=["GET"])
def obter_proposta(id_proposta):
    return jsonify({
        "status": "ok",
        "id": id_proposta,
        "mensagem": "Rota /api/obter-proposta funcionando"
    })