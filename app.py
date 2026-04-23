from flask import Flask, render_template, request, jsonify
import base64
import os
import uuid
import re

# Importa as suas funções e módulos
import database
from OCRespecifico import ler_especifico
from OCRnormal import ler_normal

app = Flask(__name__)

# Cria a pasta para salvar as fotos das placas, caso não exista
os.makedirs('fotos', exist_ok=True)

# Inicializa as tabelas no PostgreSQL ao rodar o projeto
database.criar_banco_e_tabelas()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/processar_imagem', methods=['POST'])
def processar_imagem():
    try:
        # 1. Recebe os dados da imagem (Base64) do Front-end
        dados = request.get_json()
        if not dados or 'imagem' not in dados:
            return jsonify({"status": "Erro: Imagem não recebida"}), 400

        imagem_base64 = dados['imagem'].split(',')[1]
        nome_arquivo = f"fotos/captura_{uuid.uuid4().hex}.jpg"

        # 2. Salva o arquivo localmente para os leitores OCR processarem
        with open(nome_arquivo, "wb") as fh:
            fh.write(base64.b64decode(imagem_base64))

        # 3. Chama os leitores (agora eles retornam strings sem porcentagem)
        resultado_esp = ler_especifico(nome_arquivo)
        resultado_norm = ler_normal(nome_arquivo)

        # Valores padrão
        status_exibicao = "Aguardando..."
        proprietario = "Desconhecido"
        placa_limpa = ""

        # 4. Lógica de Verificação de Placa e Acesso
        if "✅" in resultado_esp:
            # Extrai apenas o texto da placa da string "✅ ABC1234"
            busca = re.search(r'[A-Z]{3}[0-9][A-Z0-9][0-9]{2}', resultado_esp)

            if busca:
                placa_limpa = busca.group()

                # Consulta status e proprietário no Banco de Dados
                status_db, prop_db = database.buscar_dados_veiculo(placa_limpa)
                proprietario = prop_db

                # Regra: Se estiver no banco como "Liberada", mantém.
                # Se for "Não Cadastrada", vira "Acesso Negado".
                if status_db == "Liberada":
                    status_exibicao = "Liberada"
                elif status_db == "Não Cadastrada":
                    status_exibicao = "Acesso Negado"
                else  :
                    status_exibicao = status_db  # Bloqueada ou Pendências

                # 5. Registra no histórico (com trava de 10 segundos para não duplicar)
                database.registrar_historico(placa_limpa, status_exibicao, "EasyOCR Específico", proprietario)

        elif "❌" in resultado_esp:
            status_exibicao = "Placa ilegível"

        # 6. Envia a resposta completa para o index.html
        return jsonify({
            "especifico": resultado_esp,
            "normal": resultado_norm,
            "status": status_exibicao,
            "placa_lida": placa_limpa,
            "proprietario": proprietario
        })

    except Exception as e:
        print(f"Erro no servidor: {e}")
        return jsonify({"status": "Erro interno no servidor"}), 500


if __name__ == '__main__':
    # Roda o servidor Flask
    app.run(debug=True, port=5000)