from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import pandas as pd
import os
import json
import re
from werkzeug.utils import secure_filename
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'segredo-super-seguro'
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Banco de dados em memória
atributos = {}
dados_processados = pd.DataFrame()
dados_originais = pd.DataFrame()
atributo_em_edicao = None
prioridade_variacoes = []

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        arquivo = request.files['arquivo']
        if not arquivo.filename.endswith('.xlsx'):
            flash("Formato inválido. Envie um arquivo .xlsx", 'error')
            return redirect(url_for('index'))

        df = pd.read_excel(arquivo)
        if 'ID' not in df.columns or 'Descrição' not in df.columns:
            flash("A planilha precisa conter as colunas 'ID' e 'Descrição'", 'error')
            return redirect(url_for('index'))

        global dados_originais
        dados_originais = df
        flash("Planilha carregada com sucesso!", 'success')
        return redirect(url_for('configurar'))

    return render_template('index.html')

@app.route('/baixar-modelo')
def baixar_modelo():
    modelo = pd.DataFrame(columns=['ID', 'Descrição'])
    modelo.loc[0] = ['001', 'exemplo produto 110v']
    modelo.loc[1] = ['002', 'outro produto 220v']

    output = BytesIO()
    modelo.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="modelo_atributos.xlsx", as_attachment=True)

@app.route('/configurar', methods=['GET'])
def configurar():
    return render_template(
        'configurar.html',
        atributo_em_edicao=atributo_em_edicao,
        atributos=atributos,
        variacoes=atributo_em_edicao['variacoes'] if atributo_em_edicao else []
    )

@app.route('/adicionar-variacao', methods=['POST'])
def adicionar_variacao():
    nome = request.form['nome']
    variacoes_form = request.form.to_dict(flat=False)

    variacoes = []
    index = 0
    while f'variacoes[{index}][descricao]' in variacoes_form:
        descricao = variacoes_form[f'variacoes[{index}][descricao]'][0]
        padroes = variacoes_form.get(f'variacoes[{index}][padroes]', [''])[0].splitlines()
        padroes = [p.strip() for p in padroes if p.strip()]
        variacoes.append({'descricao': descricao, 'padroes': padroes})
        index += 1

    global atributo_em_edicao
    atributo_em_edicao = {
        'nome': nome,
        'variacoes': variacoes
    }

    flash("Variações salvas. Agora defina a prioridade.", 'success')
    return redirect(url_for('configurar'))

@app.route('/salvar-prioridade', methods=['POST'])
def salvar_prioridade():
    ordem = request.form.get('ordem_prioridade', '').split(',')
    if not atributo_em_edicao:
        flash("Nenhum atributo em edição", 'error')
        return redirect(url_for('configurar'))

    # Ordenar as variações pela ordem recebida
    novas_variacoes = []
    for desc in ordem:
        for var in atributo_em_edicao['variacoes']:
            if var['descricao'] == desc:
                novas_variacoes.append(var)
                break

    global atributos
    atributos[atributo_em_edicao['nome']] = {
        'variacoes': novas_variacoes
    }

    global atributo_em_edicao
    atributo_em_edicao = None
    flash("Atributo configurado com sucesso!", 'success')
    return redirect(url_for('configurar'))

@app.route('/editar/<nome>')
def editar_configuracao(nome):
    global atributo_em_edicao
    atributo_em_edicao = {'nome': nome, 'variacoes': atributos[nome]['variacoes']}
    return redirect(url_for('configurar'))

@app.route('/excluir/<nome>')
def excluir_configuracao(nome):
    if nome in atributos:
        del atributos[nome]
        flash("Atributo excluído com sucesso!", 'success')
    return redirect(url_for('configurar'))

@app.route('/exportar')
def exportar_configuracoes():
    output = BytesIO()
    json.dump(atributos, output, indent=4, ensure_ascii=False)
    output.seek(0)
    return send_file(output, download_name="configuracoes.json", as_attachment=True)

@app.route('/importar', methods=['POST'])
def importar_configuracoes():
    arquivo = request.files['arquivo']
    if not arquivo.filename.endswith('.json'):
        flash("Formato inválido. Envie um JSON.", 'error')
        return redirect(url_for('configurar'))

    global atributos
    atributos = json.load(arquivo)
    flash("Configurações importadas com sucesso!", 'success')
    return redirect(url_for('configurar'))

@app.route('/processar')
def processar():
    global dados_processados
    if dados_originais.empty or not atributos:
        flash("Planilha e atributos são necessários para processar.", 'error')
        return redirect(url_for('index'))

    df = dados_originais.copy()

    for nome_attr, config in atributos.items():
        df[nome_attr] = ""

        for idx, row in df.iterrows():
            descricao = str(row['Descrição']).lower()
            encontrado = ""

            for variacao in config['variacoes']:
                for padrao in variacao['padroes']:
                    if re.search(re.escape(padrao), descricao):
                        encontrado = variacao['descricao']
                        break
                if encontrado:
                    break

            df.at[idx, nome_attr] = encontrado

    dados_processados = df
    return render_template('resultados.html', dados=df)

@app.route('/baixar-resultados')
def baixar_resultados():
    if dados_processados.empty:
        flash("Nenhum dado processado ainda", 'error')
        return redirect(url_for('processar'))

    output = BytesIO()
    dados_processados.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="resultados_extraidos.xlsx", as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
