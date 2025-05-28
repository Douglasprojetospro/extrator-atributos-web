import os
import re
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CONFIG_FOLDER'] = 'configs'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB

# Garante que as pastas existem
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CONFIG_FOLDER'], exist_ok=True)

class ExtratorAtributos:
    def __init__(self):
        self.atributos = {}
        self.dados_originais = None
        self.dados_processados = None

    def carregar_configuracao(self, config):
        """Carrega uma configuração de atributos"""
        self.atributos = config

    def exportar_configuracao(self):
        """Exporta a configuração atual de atributos"""
        return self.atributos

    def processar_dados(self):
        if self.dados_originais is None:
            raise ValueError("Nenhum dado carregado para processamento")

        if not self.atributos:
            raise ValueError("Nenhum atributo configurado")

        self.dados_processados = self.dados_originais.copy()

        for atributo_nome, config in self.atributos.items():
            tipo_retorno = config['tipo_retorno']
            variacoes = config['variacoes']  # Note a correção ortográfica aqui

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
                            desc_padrao,
                            match.group()
                        )
                        break  # Usa a primeira correspondência (maior prioridade)

                self.dados_processados.at[idx, atributo_nome] = resultado if resultado else ""

        return self.dados_processados

    def formatar_resultado(self, descricao_completa, tipo_retorno, nome_atributo, descricao_padrao, valor_encontrado):
        if tipo_retorno == "valor":
            # Extrai apenas números do valor encontrado
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
            variacoes = data.get('variacoes')  # Note a correção ortográfica aqui

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
        return jsonify(extrator.exportar_configuracao())
    elif request.method == 'DELETE':
        nome = request.args.get('nome')
        if nome in extrator.atributos:
            del extrator.atributos[nome]
            return jsonify({'success': True})
        return jsonify({'success': False}), 404

@app.route('/salvar-configuracao', methods=['POST'])
def salvar_configuracao():
    try:
        nome_config = request.form.get('nome_config')
        if not nome_config:
            flash('Nome da configuração é obrigatório', 'error')
            return redirect(url_for('configuracao'))

        filename = secure_filename(f"{nome_config}.json")
        filepath = os.path.join(app.config['CONFIG_FOLDER'], filename)
        
        with open(filepath, 'w') as f:
            json.dump(extrator.exportar_configuracao(), f)
        
        flash('Configuração salva com sucesso!', 'success')
        return redirect(url_for('configuracao'))
    except Exception as e:
        flash(f'Erro ao salvar configuração: {str(e)}', 'error')
        return redirect(url_for('configuracao'))

@app.route('/carregar-configuracao', methods=['POST'])
def carregar_configuracao():
    try:
        if 'config_file' not in request.files:
            flash('Nenhum arquivo enviado', 'error')
            return redirect(url_for('configuracao'))

        arquivo = request.files['config_file']
        if arquivo.filename == '':
            flash('Nenhum arquivo selecionado', 'error')
            return redirect(url_for('configuracao'))

        if arquivo and allowed_config_file(arquivo.filename):
            filename = secure_filename(arquivo.filename)
            filepath = os.path.join(app.config['CONFIG_FOLDER'], filename)
            arquivo.save(filepath)
            
            with open(filepath, 'r') as f:
                config = json.load(f)
            
            extrator.carregar_configuracao(config)
            flash('Configuração carregada com sucesso!', 'success')
            return redirect(url_for('configuracao'))
        else:
            flash('Tipo de arquivo não permitido. Use apenas JSON', 'error')
            return redirect(url_for('configuracao'))
    except Exception as e:
        flash(f'Erro ao carregar configuração: {str(e)}', 'error')
        return redirect(url_for('configuracao'))

@app.route('/listar-configuracoes', methods=['GET'])
def listar_configuracoes():
    try:
        configs = []
        for filename in os.listdir(app.config['CONFIG_FOLDER']):
            if filename.endswith('.json'):
                configs.append(filename[:-5])  # Remove a extensão .json
        return jsonify(configs)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

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
    modelo.loc[2] = ['003', 'lâmpada LED 9W branca']
    modelo.loc[3] = ['004', 'tomada 20A 250V']
    modelo.loc[4] = ['005', 'cabo flexível 2,5mm 750V']

    try:
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], 'modelo.xlsx')
        modelo.to_excel(output_path, index=False)
        return send_file(output_path, as_attachment=True)
    except Exception as e:
        flash(f'Erro ao gerar modelo: {str(e)}', 'error')
        return redirect(url_for('index'))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'xlsx', 'xls'}

def allowed_config_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'json'

if __name__ == '__main__':
    app.run(debug=True)
