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
Templates HTML necessários:
index.html (página inicial para upload do arquivo)

html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Extrator de Atributos</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <div class="container mt-5">
        <h1 class="mb-4">Extrator de Atributos</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="card">
            <div class="card-header">
                Upload da Planilha
            </div>
            <div class="card-body">
                <form action="/upload" method="POST" enctype="multipart/form-data">
                    <div class="mb-3">
                        <label for="arquivo" class="form-label">Selecione o arquivo Excel (.xlsx, .xls)</label>
                        <input class="form-control" type="file" id="arquivo" name="arquivo" accept=".xlsx,.xls" required>
                    </div>
                    <button type="submit" class="btn btn-primary">Enviar</button>
                </form>
            </div>
        </div>

        <div class="mt-3">
            <a href="/gerar-modelo" class="btn btn-secondary">Baixar Modelo</a>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
configuracao.html (página de configuração de atributos)

html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Configuração de Atributos</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .variation-item { border: 1px solid #ddd; padding: 10px; margin-bottom: 10px; border-radius: 5px; }
        .patterns-list { margin-top: 5px; }
        .pattern-tag { display: inline-block; background: #e9ecef; padding: 2px 5px; margin: 2px; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container mt-5">
        <h1 class="mb-4">Configuração de Atributos</h1>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        <div class="row">
            <div class="col-md-6">
                <div class="card mb-4">
                    <div class="card-header">
                        Adicionar Novo Atributo
                    </div>
                    <div class="card-body">
                        <form id="form-atributo">
                            <div class="mb-3">
                                <label for="nome-atributo" class="form-label">Nome do Atributo</label>
                                <input type="text" class="form-control" id="nome-atributo" required>
                            </div>
                            
                            <div class="mb-3">
                                <label for="tipo-retorno" class="form-label">Tipo de Retorno</label>
                                <select class="form-select" id="tipo-retorno" required>
                                    <option value="valor">Valor (ex: '110')</option>
                                    <option value="texto">Texto Padrão (ex: '110V')</option>
                                    <option value="completo">Descrição Completa (ex: 'Voltagem: 110V')</option>
                                </select>
                            </div>
                            
                            <div class="mb-3">
                                <label class="form-label">Variações</label>
                                <div id="variacoes-container">
                                    <!-- Variações serão adicionadas aqui -->
                                </div>
                                <button type="button" class="btn btn-sm btn-outline-primary mt-2" id="btn-add-variacao">
                                    Adicionar Variação
                                </button>
                            </div>
                            
                            <button type="submit" class="btn btn-primary">Registrar Atributo</button>
                        </form>
                    </div>
                </div>
                
                <div class="card mb-4">
                    <div class="card-header">
                        Gerenciar Configurações
                    </div>
                    <div class="card-body">
                        <form action="/salvar-configuracao" method="POST" class="mb-3">
                            <div class="mb-3">
                                <label for="nome-config" class="form-label">Salvar Configuração Atual</label>
                                <input type="text" class="form-control" id="nome-config" name="nome_config" required>
                            </div>
                            <button type="submit" class="btn btn-success">Salvar Configuração</button>
                        </form>
                        
                        <form action="/carregar-configuracao" method="POST" enctype="multipart/form-data">
                            <div class="mb-3">
                                <label for="config-file" class="form-label">Carregar Configuração</label>
                                <input class="form-control" type="file" id="config-file" name="config_file" accept=".json" required>
                            </div>
                            <button type="submit" class="btn btn-info">Carregar Configuração</button>
                        </form>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <span>Atributos Configurados</span>
                        <button class="btn btn-sm btn-primary" id="btn-processar">Processar Dados</button>
                    </div>
                    <div class="card-body">
                        <div id="atributos-lista">
                            <!-- Atributos serão carregados aqui -->
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal para adicionar variação -->
    <div class="modal fade" id="variacaoModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Adicionar Variação</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body">
                    <div class="mb-3">
                        <label for="descricao-variacao" class="form-label">Descrição da Variação</label>
                        <input type="text" class="form-control" id="descricao-variacao">
                    </div>
                    <div class="mb-3">
                        <label for="padroes-variacao" class="form-label">Padrões (separados por vírgula)</label>
                        <input type="text" class="form-control" id="padroes-variacao" placeholder="ex: 110v, 110V, 127">
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                    <button type="button" class="btn btn-primary" id="btn-confirm-variacao">Adicionar</button>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
        $(document).ready(function() {
            let variacoes = [];
            const variacaoModal = new bootstrap.Modal(document.getElementById('variacaoModal'));
            
            // Carregar atributos existentes
            carregarAtributos();
            
            // Abrir modal para adicionar variação
            $('#btn-add-variacao').click(function() {
                $('#descricao-variacao, #padroes-variacao').val('');
                variacaoModal.show();
            });
            
            // Confirmar adição de variação
            $('#btn-confirm-variacao').click(function() {
                const descricao = $('#descricao-variacao').val().trim();
                const padroes = $('#padroes-variacao').val().split(',').map(p => p.trim()).filter(p => p);
                
                if (!descricao || padroes.length === 0) {
                    alert('Preencha a descrição e pelo menos um padrão');
                    return;
                }
                
                variacoes.push({
                    descricao: descricao,
                    padroes: padroes
                });
                
                renderVariacoes();
                variacaoModal.hide();
            });
            
            // Renderizar variações
            function renderVariacoes() {
                const container = $('#variacoes-container');
                container.empty();
                
                if (variacoes.length === 0) {
                    container.append('<p class="text-muted">Nenhuma variação adicionada</p>');
                    return;
                }
                
                variacoes.forEach((variacao, index) => {
                    const variationItem = $(`
                        <div class="variation-item" data-index="${index}">
                            <div class="d-flex justify-content-between">
                                <strong>${variacao.descricao}</strong>
                                <button type="button" class="btn-close btn-remove-variation" data-index="${index}"></button>
                            </div>
                            <div class="patterns-list">
                                ${variacao.padroes.map(p => `<span class="pattern-tag">${p}</span>`).join('')}
                            </div>
                        </div>
                    `);
                    
                    container.append(variationItem);
                });
                
                // Adicionar evento para remover variação
                $('.btn-remove-variation').click(function() {
                    const index = $(this).data('index');
                    variacoes.splice(index, 1);
                    renderVariacoes();
                });
            }
            
            // Enviar atributo para o servidor
            $('#form-atributo').submit(function(e) {
                e.preventDefault();
                
                const nome = $('#nome-atributo').val().trim();
                const tipoRetorno = $('#tipo-retorno').val();
                
                if (variacoes.length === 0) {
                    alert('Adicione pelo menos uma variação');
                    return;
                }
                
                $.ajax({
                    url: '/configuracao',
                    method: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify({
                        nome: nome,
                        tipo_retorno: tipoRetorno,
                        variacoes: variacoes
                    }),
                    success: function(response) {
                        if (response.success) {
                            alert('Atributo adicionado com sucesso!');
                            $('#nome-atributo').val('');
                            variacoes = [];
                            renderVariacoes();
                            carregarAtributos();
                        } else {
                            alert('Erro: ' + response.message);
                        }
                    },
                    error: function(xhr) {
                        alert('Erro ao adicionar atributo: ' + xhr.responseJSON?.message || 'Erro desconhecido');
                    }
                });
            });
            
            // Carregar atributos do servidor
            function carregarAtributos() {
                $.get('/api/atributos', function(data) {
                    const container = $('#atributos-lista');
                    container.empty();
                    
                    if (Object.keys(data).length === 0) {
                        container.append('<p class="text-muted">Nenhum atributo configurado</p>');
                        return;
                    }
                    
                    for (const [nome, config] of Object.entries(data)) {
                        const atributoItem = $(`
                            <div class="card mb-2">
                                <div class="card-body">
                                    <div class="d-flex justify-content-between">
                                        <div>
                                            <h5 class="card-title">${nome}</h5>
                                            <p class="card-text">
                                                <small>Tipo de retorno: ${config.tipo_retorno}</small><br>
                                                <small>Variações: ${config.variacoes.length}</small>
                                            </p>
                                        </div>
                                        <button class="btn btn-sm btn-danger btn-remove-atributo" data-nome="${nome}">Remover</button>
                                    </div>
                                </div>
                            </div>
                        `);
                        
                        container.append(atributoItem);
                    }
                    
                    // Adicionar evento para remover atributo
                    $('.btn-remove-atributo').click(function() {
                        const nome = $(this).data('nome');
                        if (confirm(`Tem certeza que deseja remover o atributo "${nome}"?`)) {
                            $.ajax({
                                url: '/api/atributos?nome=' + encodeURIComponent(nome),
                                method: 'DELETE',
                                success: function(response) {
                                    if (response.success) {
                                        carregarAtributos();
                                    } else {
                                        alert('Erro ao remover atributo');
                                    }
                                }
                            });
                        }
                    });
                });
            }
            
            // Processar dados
            $('#btn-processar').click(function() {
                $.post('/processar', function(response) {
                    if (response.success) {
                        window.location.href = '/resultados';
                    } else {
                        alert('Erro ao processar: ' + response.error);
                    }
                }).fail(function(xhr) {
                    alert('Erro ao processar: ' + xhr.responseJSON?.error || 'Erro desconhecido');
                });
            });
            
            // Carregar lista de configurações salvas
            $.get('/listar-configuracoes', function(configs) {
                // Implementar se necessário
            });
        });
    </script>
</body>
</html>
