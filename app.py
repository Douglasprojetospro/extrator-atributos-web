import os
import re
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# Garante que a pasta de uploads existe
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

class ExtratorAtributos:
    def __init__(self):
        self.atributos = {}
        self.dados_originais = None
        self.dados_processados = None

    def processar_dados(self):
        if self.dados_originais is None:
            raise ValueError("Nenhum dado carregado para processamento")

        if not self.atributos:
            raise ValueError("Nenhum atributo configurado")

        self.dados_processados = self.dados_originais.copy()

        for atributo_nome, config in self.atributos.items():
            tipo_retorno = config['tipo_retorno']
            variacoes = config['variacoes']  # Corrigido para 'variacoes' (com 'e')

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
                            descricao,  # Passa a descrição completa para extração de valores
                            tipo_retorno,
                            atributo_nome,
                            desc_padrao
                        )
                        break  # Usa a primeira correspondência (maior prioridade)

                self.dados_processados.at[idx, atributo_nome] = resultado if resultado else ""

        return self.dados_processados

    def formatar_resultado(self, valor_encontrado, tipo_retorno, nome_atributo, descricao_padrao):
        if tipo_retorno == "valor":
            # Extrai apenas números da descrição completa
            numeros = re.findall(r'\d+', valor_encontrado)
            return numeros[0] if numeros else ""
        elif tipo_retorno == "texto":
            return descricao_padrao
        elif tipo_retorno == "completo":
            return f"{nome_atributo}: {descricao_padrao}"
        return valor_encontrado

extrator = ExtratorAtributos()

@app.route('/')
def index():
    return render_template('index.html')

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

            extrator.atributos[nome] = {
                'nome': nome,
                'tipo_retorno': tipo_retorno,
                'variacoes': variacoes
            }

            return jsonify({'success': True, 'message': 'Atributo adicionado com sucesso!'})
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 400

    return render_template('configuracao.html')

@app.route('/api/atributos', methods=['GET', 'DELETE'])
def gerenciar_atributos():
    if request.method == 'GET':
        return jsonify(extrator.atributos)
    elif request.method == 'DELETE':
        nome = request.args.get('nome')
        if nome in extrator.atributos:
            del extrator.atributos[nome]
            return jsonify({'success': True})
        return jsonify({'success': False}), 404

@app.route('/processar', methods=['POST'])
def processar():
    try:
        dados_processados = extrator.processar_dados()
        # Salva os dados processados temporariamente para download
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultados_processados.xlsx')
        dados_processados.to_excel(output_path, index=False)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/resultados')
def resultados():
    if extrator.dados_processados is None:
        flash('Nenhum resultado disponível. Processe os dados primeiro.', 'error')
        return redirect(url_for('configuracao'))

    # Converter para HTML mantendo apenas as primeiras 50 linhas para exibição
    dados_html = extrator.dados_processados.head(50).to_html(classes='table table-striped', index=False)
    return render_template('resultados.html', dados=dados_html)

@app.route('/exportar')
def exportar():
    if extrator.dados_processados is None:
        flash('Nenhum resultado para exportar', 'error')
        return redirect(url_for('resultados'))

    try:
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'resultados.xlsx')
        extrator.dados_processados.to_excel(output_path, index=False)
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        flash(f'Erro ao exportar resultados: {str(e)}', 'error')
        return redirect(url_for('resultados'))

@app.route('/gerar-modelo')
def gerar_modelo():
    modelo = pd.DataFrame(columns=['ID', 'Descrição'])
    modelo.loc[0] = ['001', 'ventilador de parede 110V']
    modelo.loc[1] = ['002', 'luminária de teto 220V branca']

    try:
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modelo.xlsx')
        modelo.to_excel(output_path, index=False)
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        flash(f'Erro ao gerar modelo: {str(e)}', 'error')
        return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls'}

if __name__ == '__main__':
    app.run(debug=True)
