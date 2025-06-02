from flask import Flask, render_template, request, redirect, url_for, send_file, flash
import pandas as pd
import os
import json
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'segredo-temporario'

atributos_config = {}
df_processado = None
nome_arquivo = None
total_linhas = 0
atributo_em_edicao = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    global df_processado, nome_arquivo, total_linhas

    arquivo = request.files['arquivo']
    if not arquivo:
        flash('Nenhum arquivo enviado', 'error')
        return redirect(url_for('index'))

    try:
        df = pd.read_excel(arquivo)
        if 'ID' not in df.columns or 'Descrição' not in df.columns:
            flash("A planilha deve conter as colunas 'ID' e 'Descrição'", 'error')
            return redirect(url_for('index'))

        df_processado = df
        nome_arquivo = arquivo.filename
        total_linhas = len(df)
        return redirect(url_for('configurar'))
    except Exception as e:
        flash(f'Erro ao processar arquivo: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/baixar-modelo')
def baixar_modelo():
    modelo = pd.DataFrame(columns=['ID', 'Descrição'])
    modelo.loc[0] = ['001', 'ventilador de parede 110V']
    modelo.loc[1] = ['002', 'luminária 220V']

    buffer = BytesIO()
    modelo.to_excel(buffer, index=False)
    buffer.seek(0)

    return send_file(buffer, as_attachment=True, download_name='modelo_descricoes.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/configurar', methods=['GET'])
def configurar():
    return render_template('configurar.html', atributos=atributos_config, atributo_em_edicao=atributo_em_edicao, variacoes=atributo_em_edicao['variacoes'] if atributo_em_edicao else [])

@app.route('/adicionar-variacao', methods=['POST'])
def adicionar_variacao():
    global atributo_em_edicao
    nome = request.form.get('nome')
    variacoes_form = request.form.to_dict(flat=False)

    variacoes = []
    for i in range(len([k for k in variacoes_form if k.startswith('variacoes[')] ) // 2):
        descricao = variacoes_form.get(f'variacoes[{i}][descricao]', [''])[0].strip()
        padroes_texto = variacoes_form.get(f'variacoes[{i}][padroes]', [''])[0]
        padroes = [p.strip() for p in padroes_texto.strip().split('\n') if p.strip()]
        variacoes.append({'descricao': descricao, 'padroes': padroes})

    atributo_em_edicao = {
        'nome': nome,
        'tipo_retorno': 'texto',
        'variacoes': variacoes
    }
    return redirect(url_for('configurar'))

@app.route('/salvar-prioridade', methods=['POST'])
def salvar_prioridade():
    global atributo_em_edicao
    ordem = request.form.get('ordem_prioridade', '').split(',')
    if not atributo_em_edicao:
        flash("Nenhum atributo em edição", 'error')
        return redirect(url_for('configurar'))

    novas_variacoes = []
    for desc in ordem:
        for v in atributo_em_edicao['variacoes']:
            if v['descricao'] == desc:
                novas_variacoes.append(v)
                break

    atributo_em_edicao['variacoes'] = novas_variacoes
    atributos_config[atributo_em_edicao['nome']] = atributo_em_edicao
    atributo_em_edicao = None
    flash("Configuração salva com sucesso!", 'success')
    return redirect(url_for('configurar'))

@app.route('/editar/<nome>')
def editar_configuracao(nome):
    global atributo_em_edicao
    atributo_em_edicao = atributos_config.get(nome)
    return redirect(url_for('configurar'))

@app.route('/excluir/<nome>')
def excluir_configuracao(nome):
    atributos_config.pop(nome, None)
    flash(f"Atributo '{nome}' excluído.", 'info')
    return redirect(url_for('configurar'))

@app.route('/exportar-configuracoes')
def exportar_configuracoes():
    json_data = json.dumps(atributos_config, indent=2, ensure_ascii=False)
    buffer = BytesIO()
    buffer.write(json_data.encode('utf-8'))
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='config_atributos.json', mimetype='application/json')

@app.route('/importar-configuracoes', methods=['POST'])
def importar_configuracoes():
    global atributos_config
    arquivo = request.files['arquivo']
    if not arquivo:
        flash('Nenhum arquivo enviado', 'error')
        return redirect(url_for('configurar'))

    try:
        dados = json.load(arquivo)
        if isinstance(dados, dict):
            atributos_config = dados
            flash("Configurações importadas com sucesso!", 'success')
        else:
            flash("Formato de arquivo inválido", 'error')
    except Exception as e:
        flash(f"Erro ao importar: {str(e)}", 'error')
    return redirect(url_for('configurar'))

@app.route('/processar')
def processar():
    global df_processado
    if df_processado is None or not atributos_config:
        flash("Dados ou atributos ausentes", 'error')
        return redirect(url_for('index'))

    df_resultado = df_processado.copy()
    for nome_attr, config in atributos_config.items():
        col_resultado = []
        for desc in df_resultado['Descrição']:
            desc_lower = str(desc).lower()
            valor_final = ""
            for variacao in config['variacoes']:
                for padrao in variacao['padroes']:
                    if padrao.lower() in desc_lower:
                        valor_final = variacao['descricao']
                        break
                if valor_final:
                    break
            col_resultado.append(valor_final)
        df_resultado[nome_attr] = col_resultado

    # salvar para download
    df_resultado.to_excel('resultado_processado.xlsx', index=False)
    return render_template('resultados.html', dados=df_resultado, nome_arquivo=nome_arquivo, total_linhas=total_linhas)

@app.route('/baixar-resultado')
def baixar_resultado():
    return send_file('resultado_processado.xlsx', as_attachment=True)

if __name__ == '__main__':
    app.run(debug=False, port=10000, host='0.0.0.0')
