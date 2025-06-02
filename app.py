from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify
import pandas as pd
import json
import os
from io import BytesIO

app = Flask(__name__)

atributos = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/modelo')
def modelo():
    df = pd.DataFrame(columns=['ID', 'Descricao'])
    df.loc[0] = ['001', 'exemplo de descricao 110v']
    df.loc[1] = ['002', 'exemplo de descricao 220v']

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return send_file(output, download_name="modelo_descricoes.xlsx", as_attachment=True)

@app.route('/configurar', methods=['GET', 'POST'])
def configurar():
    nome = request.form.get('nome')
    variacoes = atributos.get(nome, {}).get('variacoes', [])
    return render_template('configurar.html', atributos=atributos, variacoes=variacoes, atributo_em_edicao=atributos.get(nome))

@app.route('/adicionar_variacao', methods=['POST'])
def adicionar_variacao():
    nome = request.form.get('nome')
    variacoes_raw = request.form.to_dict(flat=False)
    variacoes = []
    i = 0
    while f'variacoes[{i}][descricao]' in variacoes_raw:
        descricao = variacoes_raw.get(f'variacoes[{i}][descricao]', [''])[0]
        padroes = variacoes_raw.get(f'variacoes[{i}][padroes]', [''])[0].splitlines()
        variacoes.append({'descricao': descricao, 'padroes': [p.strip() for p in padroes if p.strip()]})
        i += 1
    atributos[nome] = {'nome': nome, 'variacoes': variacoes, 'tipo_retorno': 'texto'}
    return redirect(url_for('configurar'))

@app.route('/salvar_prioridade', methods=['POST'])
def salvar_prioridade():
    ordem = request.form.get('ordem_prioridade').split(',')
    nome = request.args.get('nome')
    if not nome or nome not in atributos:
        return redirect(url_for('configurar'))
    variacoes_antigas = atributos[nome]['variacoes']
    variacoes_reordenadas = []
    for desc in ordem:
        for v in variacoes_antigas:
            if v['descricao'] == desc:
                variacoes_reordenadas.append(v)
    atributos[nome]['variacoes'] = variacoes_reordenadas
    return redirect(url_for('configurar'))

@app.route('/editar/<nome>')
def editar_configuracao(nome):
    if nome in atributos:
        return render_template('configurar.html', atributos=atributos, variacoes=atributos[nome]['variacoes'], atributo_em_edicao=atributos[nome])
    return redirect(url_for('configurar'))

@app.route('/excluir/<nome>')
def excluir_configuracao(nome):
    if nome in atributos:
        del atributos[nome]
    return redirect(url_for('configurar'))

@app.route('/exportar_configuracoes')
def exportar_configuracoes():
    output = BytesIO()
    output.write(json.dumps(atributos, indent=4, ensure_ascii=False).encode('utf-8'))
    output.seek(0)
    return send_file(output, download_name="configuracoes.json", as_attachment=True)

@app.route('/importar_configuracoes', methods=['POST'])
def importar_configuracoes():
    file = request.files.get('arquivo')
    if file:
        dados = json.load(file)
        if isinstance(dados, dict):
            atributos.clear()
            atributos.update(dados)
    return redirect(url_for('configurar'))

@app.route('/processar')
def processar():
    return render_template('resultados.html')

if __name__ == '__main__':
    app.run(debug=True)
