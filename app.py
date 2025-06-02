import os
import re
import json
import datetime  # Importação necessária para o template
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from werkzeug.utils import secure_filename

# Configuração do Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')  # Use variável de ambiente em produção
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CONFIG_FOLDER'] = 'configs'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# Garante que as pastas existam
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CONFIG_FOLDER'], exist_ok=True)

class ExtratorAtributos:
    def __init__(self):
        self.atributos = {}
        self.dados_originais = None
        self.dados_processados = None

    def carregar_configuracao(self, config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.atributos = json.load(f)

    def salvar_configuracao(self, config_path):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.atributos, f, ensure_ascii=False, indent=4)

    def processar_dados(self):
        if self.dados_originais is None:
            raise ValueError("Nenhum dado carregado para processamento")

        if not self.atributos:
            raise ValueError("Nenhum atributo configurado")

        self.dados_processados = self.dados_originais.copy()

        for atributo_nome, config in self.atributos.items():
            tipo_retorno = config['tipo_retorno']
            variacoes = config['variacoes']

            # Prepara regex para cada variação
            regex_variacoes = []
            for variacao in variacoes:
                padroes_escaped = [re.escape(p) for p in variacao['padroes']]
                regex = r'\b(' + '|'.join(padroes_escaped) + r')\b'
                regex_variacoes.append((regex, variacao['descricao']))

            self.dados_processados[atributo_nome] = ""

            for idx, row in self.dados_processados.iterrows():
                descricao = str(row['Descrição']).lower()
                resultado = None

                # Verifica cada variação na ordem de prioridade
                for regex, desc_padrao in regex_variacoes:
                    match = re.search(regex, descricao, re.IGNORECASE)
                    if match:
                        resultado = self.formatar_resultado(
                            descricao,
                            tipo_retorno,
                            atributo_nome,
                            desc_padrao,
                            match.group()
                        )
                        break  # Usa a primeira correspondência (maior prioridade)

                self.dados_processados.at[idx, atributo_nome] = resultado if resultado else ""

        return self.dados_processados

    def formatar_resultado(self, descricao, tipo_retorno, nome_atributo, descricao_padrao, valor_encontrado):
        if tipo_retorno == "valor":
            numeros = re.findall(r'\d+', valor_encontrado)
            return numeros[0] if numeros else ""
        elif tipo_retorno == "texto":
            return descricao_padrao
        elif tipo_retorno == "completo":
            return f"{nome_atributo}: {descricao_padrao}"
        return valor_encontrado

extrator = ExtratorAtributos()

# Rotas
@app.route('/')
def index():
    return render_template('index.html', datetime=datetime)  # datetime passado para o template

@app.route('/upload', methods=['POST'])
def upload_arquivo():
    if 'arquivo' not in request.files:
        flash('Nenhum arquivo enviado', 'error')
        return redirect(url_for('index'))

    arquivo = request.files['arquivo']
    if arquivo.filename == '':
        flash('Nenhum arquivo selecionado', 'error')
        return redirect(url_for('index'))

    if arquivo and allowed_file(arquivo.filename):
        filename = secure_filename(arquivo.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        arquivo.save(filepath)

        try:
            extrator.dados_originais = pd.read_excel(filepath)
            if 'ID' not in extrator.dados_originais.columns or 'Descrição' not in extrator.dados_originais.columns:
                flash("A planilha deve conter as colunas 'ID' e 'Descrição'", 'error')
                return redirect(url_for('index'))

            flash('Planilha carregada com sucesso!', 'success')
            return redirect(url_for('configuracao'))

        except Exception as e:
            flash(f'Erro ao carregar planilha: {str(e)}', 'error')
            return redirect(url_for('index'))

    flash('Tipo de arquivo não permitido. Use apenas Excel (.xlsx, .xls)', 'error')
    return redirect(url_for('index'))

@app.route('/configuracao', methods=['GET', 'POST'])
def configuracao():
    if request.method == 'POST':
        try:
            data = request.get_json()
            nome = data.get('nome')
            tipo_retorno = data.get('tipo_retorno')
            variacoes = data.get('variacoes')

            if not nome or not tipo_retorno or not variacoes:
                return jsonify({'success': False, 'message': 'Dados incompletos'}), 400

            extrator.atributos[nome] = {
                'tipo_retorno': tipo_retorno,
                'variacoes': variacoes
            }

            return jsonify({'success': True, 'message': 'Atributo adicionado com sucesso!'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    # Lista arquivos de configuração disponíveis
    config_files = []
    for file in os.listdir(app.config['CONFIG_FOLDER']):
        if file.endswith('.json'):
            config_files.append(file)

    return render_template('configuracao.html', config_files=config_files, datetime=datetime)

# ... (outras rotas permanecem iguais, mas certifique-se de passar datetime para os templates) ...

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls'}

# Configuração para o Render
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))  # Usa a porta do Render ou 5000 localmente
    app.run(host='0.0.0.0', port=port, debug=False)  # debug=False em produção
