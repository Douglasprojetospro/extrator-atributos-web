import os
import json
import re
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'chave-secreta'
UPLOAD_FOLDER = 'uploads'
RESULT_FOLDER = 'resultados'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/modelo')
def modelo():
    modelo_df = pd.DataFrame(columns=['ID', 'Descrição'])
    modelo_df.loc[0] = ['001', 'ventilador de paredes 110V']
    modelo_df.loc[1] = ['002', 'luminária de teto 220V branca']
    path = os.path.join(RESULT_FOLDER, 'modelo_descricoes.xlsx')
    modelo_df.to_excel(path, index=False)
    return send_file(path, as_attachment=True)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['arquivo']
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        session['planilha_path'] = path
        df = pd.read_excel(path)
        session['colunas'] = list(df.columns)
        session['atributos'] = {}
        return redirect(url_for('configurar'))
    flash('Nenhum arquivo selecionado.', 'error')
    return redirect(url_for('index'))

@app.route('/configurar', methods=['GET', 'POST'])
def configurar():
    if request.method == 'POST':
        nome = request.form['nome']
        tipo_retorno = request.form['tipo_retorno']
        variacoes = request.form.getlist('variacoes')
        padroes = request.form.getlist('padroes')
        prioridade = request.form.getlist('prioridade')

        atributo = {
            'nome': nome,
            'tipo_retorno': tipo_retorno,
            'variacoes': []
        }

        for idx, desc in enumerate(variacoes):
            atributo['variacoes'].append({
                'descricao': desc,
                'padroes': [p.strip() for p in padroes[idx].split(',') if p.strip()]
            })

        atributo['variacoes'] = [
            next(v for v in atributo['variacoes'] if v['descricao'] == nome) if nome in prioridade else v
            for nome in prioridade
            for v in atributo['variacoes']
            if v['descricao'] == nome
        ]

        atributos = session.get('atributos', {})
        atributos[nome] = atributo
        session['atributos'] = atributos

        flash(f'Atributo "{nome}" configurado.', 'success')
        return redirect(url_for('configurar'))

    atributos = session.get('atributos', {})
    return render_template('configurar.html', atributos=atributos)

@app.route('/processar')
def processar():
    planilha_path = session.get('planilha_path')
    atributos = session.get('atributos', {})

    if not planilha_path or not atributos:
        flash('Envie uma planilha e configure os atributos antes.', 'error')
        return redirect(url_for('index'))

    df = pd.read_excel(planilha_path)
    for nome, config in atributos.items():
        tipo = config['tipo_retorno']
        variacoes = config['variacoes']
        resultados = []

        for _, row in df.iterrows():
            desc = str(row.get('Descrição', '')).lower()
            encontrado = ''
            for var in variacoes:
                for padrao in var['padroes']:
                    if re.search(re.escape(padrao.lower()), desc):
                        if tipo == 'valor':
                            numeros = re.findall(r'\d+', padrao)
                            encontrado = numeros[0] if numeros else ''
                        elif tipo == 'texto':
                            encontrado = var['descricao']
                        elif tipo == 'completo':
                            encontrado = f"{nome}: {var['descricao']}"
                        break
                if encontrado:
                    break
            resultados.append(encontrado)

        df[nome] = resultados

    output_path = os.path.join(RESULT_FOLDER, 'resultado.xlsx')
    df.to_excel(output_path, index=False)
    session['resultado_path'] = output_path
    return redirect(url_for('resultado'))

@app.route('/resultado')
def resultado():
    atributos = session.get('atributos', {})
    resultado_path = session.get('resultado_path')
    if not resultado_path:
        return redirect(url_for('index'))
    df = pd.read_excel(resultado_path)
    return render_template('resultados.html', df=df.head(20).to_dict(orient='records'), atributos=list(atributos.keys()))

@app.route('/download')
def download():
    path = session.get('resultado_path')
    if not path:
        return redirect(url_for('index'))
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
