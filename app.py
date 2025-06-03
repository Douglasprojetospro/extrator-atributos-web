import pandas as pd
import re
import os
import json
import streamlit as st
from io import BytesIO
import requests
import base64
from github import Github

class ExtratorAtributos:
    def __init__(self):
        self.atributos = {}
        self.dados_processados = pd.DataFrame()
        self.etapa_configuracao = 0  # 0=nome, 1=variações, 2=padrões, 3=prioridade, 4=formato
        self.atributo_atual = {}
        
        # Configuração inicial do Streamlit
        st.set_page_config(page_title="Sistema de Extração de Atributos Avançado", layout="wide")
        
        # Inicializa o estado da sessão
        self.inicializar_sessao()
        self.setup_ui()
    
    def inicializar_sessao(self):
        """Inicializa todas as variáveis de sessão necessárias"""
        session_defaults = {
            'dados_originais': None,
            'dados_processados': None,
            'atributos': {},
            'atributo_atual': {},
            'etapa_configuracao': 0,
            'variacoes_ordenadas': []
        }
        
        for key, default in session_defaults.items():
            if key not in st.session_state:
                st.session_state[key] = default
    
    def setup_ui(self):
        """Configura a interface principal do usuário"""
        st.title("📋 Sistema de Extração de Atributos Avançado")
        
        # Abas principais
        tab1, tab2, tab3 = st.tabs(["📤 Modelo e Upload", "⚙️ Configuração", "📊 Resultados"])
        
        with tab1:
            self.setup_aba_modelo()
        with tab2:
            self.setup_aba_configuracao()
        with tab3:
            self.setup_aba_resultados()
    
    def setup_aba_modelo(self):
        """Configura a aba de modelo e upload de dados"""
        st.header("📁 Modelo e Upload de Dados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📝 Modelo de Planilha")
            st.markdown("""
            O modelo deve conter pelo menos:
            - Coluna **'ID'**: Identificador único
            - Coluna **'Descrição'**: Texto com os atributos a extrair
            """)
            if st.button("⬇️ Gerar Modelo Excel"):
                self.gerar_modelo()
        
        with col2:
            st.subheader("📤 Carregar Dados")
            opcao_carregar = st.radio("Fonte dos dados:", ("Upload Local", "GitHub"), horizontal=True)
            
            if opcao_carregar == "Upload Local":
                arquivo = st.file_uploader("Selecione a planilha", type=["xlsx", "xls", "csv"])
                if arquivo is not None:
                    self.carregar_planilha(arquivo)
            
            elif opcao_carregar == "GitHub":
                with st.form("github_form"):
                    repo_url = st.text_input("URL do repositório (ex: usuario/repo)")
                    caminho_arquivo = st.text_input("Caminho do arquivo (ex: dados/planilha.xlsx)")
                    token = st.text_input("Token de acesso (opcional)", type="password")
                    
                    if st.form_submit_button("Carregar do GitHub"):
                        if repo_url and caminho_arquivo:
                            self.carregar_github(repo_url, caminho_arquivo, token)
                        else:
                            st.warning("Preencha todos os campos obrigatórios")
        
        # Visualização dos dados carregados
        if st.session_state.dados_originais is not None:
            st.subheader("👀 Pré-visualização dos Dados")
            st.dataframe(st.session_state.dados_originais.head(), use_container_width=True)
    
    def setup_aba_configuracao(self):
        """Configura a aba de definição de atributos"""
        st.header("⚙️ Configuração de Atributos")
        
        # Frame de instruções
        with st.expander("ℹ️ Instruções", expanded=True):
            instrucao = self.get_instrucao_atual()
            st.markdown(instrucao)
        
        # Frame do passo atual
        st.subheader("🔧 Configuração do Atributo")
        self.render_passo_atual()
        
        # Navegação
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("← Voltar", disabled=st.session_state.etapa_configuracao == 0):
                self.voltar_passo()
        
        with col2:
            texto_botao = "Avançar →" if st.session_state.etapa_configuracao < 4 else "✅ Concluir"
            if st.button(texto_botao):
                self.avancar_passo()
        
        with col3:
            if st.button("❌ Cancelar"):
                self.cancelar_configuracao()
        
        # Importar/Exportar configurações
        st.subheader("🔄 Gerenciamento de Configurações")
        col_exp, col_imp = st.columns(2)
        
        with col_exp:
            if st.button("📤 Exportar Configurações"):
                self.exportar_configuracoes()
        
        with col_imp:
            arquivo_config = st.file_uploader("📥 Importar Configurações", type=["json"])
            if arquivo_config is not None:
                self.importar_configuracoes(arquivo_config)
        
        # Lista de atributos configurados
        st.subheader("📋 Atributos Configurados")
        if st.session_state.atributos:
            self.mostrar_atributos_configurados()
        else:
            st.info("ℹ️ Nenhum atributo configurado ainda.")
    
    def mostrar_atributos_configurados(self):
        """Exibe a tabela de atributos configurados e controles de edição"""
        df_atributos = pd.DataFrame([
            {
                'Atributo': nome,
                'Variações': ", ".join([v['descricao'] for v in config['variacoes']]),
                'Padrões': sum(len(v['padroes']) for v in config['variacoes']),
                'Prioridade': config['variacoes'][0]['descricao'],
                'Formato': "Valor" if config['tipo_retorno'] == "valor" else "Texto" if config['tipo_retorno'] == "texto" else "Completo"
            }
            for nome, config in st.session_state.atributos.items()
        ])
        
        st.dataframe(df_atributos, use_container_width=True, hide_index=True)
        
        # Botões de gerenciamento
        col_edit, col_rem, col_lim = st.columns(3)
        
        with col_edit:
            atributo_editar = st.selectbox(
                "Selecionar para editar",
                list(st.session_state.atributos.keys()),
                key="edit_select"
            )
            if st.button("✏️ Editar Selecionado"):
                self.editar_atributo(atributo_editar)
        
        with col_rem:
            atributo_remover = st.selectbox(
                "Selecionar para remover",
                list(st.session_state.atributos.keys()),
                key="remove_select"
            )
            if st.button("🗑️ Remover Selecionado"):
                self.remover_atributo(atributo_remover)
        
        with col_lim:
            if st.button("🧹 Limpar Todos"):
                self.limpar_atributos()
    
    def setup_aba_resultados(self):
        """Configura a aba de processamento e resultados"""
        st.header("📊 Processamento e Resultados")
        
        if st.button("🔍 Extrair Atributos", type="primary"):
            self.validar_e_processar()
        
        # Exibição dos resultados
        if st.session_state.dados_processados is not None:
            self.mostrar_resultados()
    
    def validar_e_processar(self):
        """Valida os dados antes do processamento"""
        if st.session_state.dados_originais is None:
            st.warning("⚠️ Por favor, carregue uma planilha primeiro")
        elif not st.session_state.atributos:
            st.warning("⚠️ Por favor, configure pelo menos um atributo")
        else:
            with st.spinner("⏳ Processando dados..."):
                self.processar_dados()
                st.success("✅ Processamento concluído com sucesso!")
    
    def mostrar_resultados(self):
        """Exibe e permite exportar os resultados"""
        st.subheader("📈 Resultados da Extração")
        
        # Mostra os dados com paginação
        st.dataframe(
            st.session_state.dados_processados,
            use_container_width=True,
            hide_index=True
        )
        
        # Exportação dos resultados
        st.subheader("💾 Exportar Resultados")
        nome_arquivo = st.text_input(
            "Nome do arquivo",
            "resultados_extracao",
            key="export_name"
        )
        
        col_csv, col_excel = st.columns(2)
        
        with col_csv:
            csv = st.session_state.dados_processados.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="💾 Exportar como CSV",
                data=csv,
                file_name=f"{nome_arquivo}.csv",
                mime='text/csv',
                key="csv_export"
            )
        
        with col_excel:
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                st.session_state.dados_processados.to_excel(writer, index=False)
            excel_bytes = excel_buffer.getvalue()
            
            st.download_button(
                label="💾 Exportar como Excel",
                data=excel_bytes,
                file_name=f"{nome_arquivo}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                key="excel_export"
            )
    
    def get_instrucao_atual(self):
        """Retorna as instruções para a etapa atual"""
        instrucoes = [
            "1️⃣ **Nome do Atributo**: Digite o nome que será usado como cabeçalho na planilha de resultados (ex: 'Voltagem')",
            "2️⃣ **Variações**: Adicione as diferentes versões deste atributo (uma por linha). Exemplo para Voltagem:\n- 110V\n- 220V\n- Bivolt",
            "3️⃣ **Padrões de Reconhecimento**: Para cada variação, defina os textos que o sistema deve buscar na descrição do produto",
            "4️⃣ **Ordem de Prioridade**: Defina qual variação deve ser considerada primeiro quando houver múltiplas correspondências",
            "5️⃣ **Formato de Saída**: Escolha como o resultado será exibido:\n- **Valor**: Apenas o valor (ex: '110')\n- **Texto**: O texto padrão (ex: '110V')\n- **Completo**: Atributo + valor (ex: 'Voltagem: 110V')"
        ]
        return instrucoes[st.session_state.etapa_configuracao]
    
    def render_passo_atual(self):
        """Renderiza o conteúdo da etapa atual de configuração"""
        etapas = [
            self.render_passo_nome,
            self.render_passo_variacoes,
            self.render_passo_padroes,
            self.render_passo_prioridade,
            self.render_passo_formato
        ]
        etapas[st.session_state.etapa_configuracao]()
    
    def render_passo_nome(self):
        """Renderiza a etapa de definição do nome do atributo"""
        st.session_state.atributo_atual['nome'] = st.text_input(
            "Nome do Atributo:", 
            value=st.session_state.atributo_atual.get('nome', ''),
            placeholder="Ex: Voltagem, Cor, Material",
            key="attr_name_input"
        )
    
    def render_passo_variacoes(self):
        """Renderiza a etapa de definição das variações"""
        default_var = "\n".join([v['descricao'] for v in st.session_state.atributo_atual.get('variacoes', [])])
        var_text = st.text_area(
            "Variações (uma por linha):", 
            value=default_var, 
            height=150,
            placeholder="Exemplo para Voltagem:\n110V\n220V\nBivolt",
            key="variations_area"
        )
        
        if var_text.strip():
            variacoes = [v.strip() for v in var_text.split('\n') if v.strip()]
            st.session_state.atributo_atual['variacoes'] = [{'descricao': v, 'padroes': []} for v in variacoes]
    
    def render_passo_padroes(self):
        """Renderiza a etapa de definição dos padrões de reconhecimento"""
        if 'variacoes' not in st.session_state.atributo_atual or not st.session_state.atributo_atual['variacoes']:
            st.warning("⚠️ Por favor, volte e defina as variações primeiro")
            return
        
        tabs = st.tabs([v['descricao'] for v in st.session_state.atributo_atual['variacoes']])
        
        for i, variacao in enumerate(st.session_state.atributo_atual['variacoes']):
            with tabs[i]:
                default_padroes = "\n".join(variacao.get('padroes', []))
                padroes = st.text_area(
                    f"Padrões para '{variacao['descricao']}':",
                    value=default_padroes, 
                    height=100,
                    placeholder=f"Exemplo para {variacao['descricao']}:\n110v\n110 volts\n110",
                    key=f"patterns_{i}"
                )
                
                if padroes.strip():
                    variacao['padroes'] = [p.strip() for p in padroes.split('\n') if p.strip()]
    
    def render_passo_prioridade(self):
        """Renderiza a etapa de definição de prioridades"""
        if 'variacoes' not in st.session_state.atributo_atual or not st.session_state.atributo_atual['variacoes']:
            st.warning("⚠️ Por favor, complete os passos anteriores primeiro")
            return
        
        st.info("🔀 Arraste os itens para ordenar (o primeiro tem maior prioridade)")
        
        # Implementação alternativa sem streamlit_sortables
        variacoes = st.session_state.atributo_atual['variacoes']
        ordem = list(range(len(variacoes)))
        
        # Se ainda não tem ordem definida, cria uma
        if 'ordem_prioridade' not in st.session_state:
            st.session_state.ordem_prioridade = ordem.copy()
        
        # Interface para reordenar
        for i in range(len(variacoes)):
            # Mostra um selectbox para cada posição
            opcoes = [f"{idx+1}. {variacoes[idx]['descricao']}" for idx in ordem]
            selecao = st.selectbox(
                f"Posição {i+1}",
                opcoes,
                index=i,
                key=f"priority_{i}"
            )
            
            # Atualiza a ordem
            idx_selecionado = opcoes.index(selecao)
            if idx_selecionado != i:
                ordem[i], ordem[idx_selecionado] = ordem[idx_selecionado], ordem[i]
        
        # Aplica a nova ordem
        novas_variacoes = [variacoes[idx] for idx in ordem]
        st.session_state.atributo_atual['variacoes'] = novas_variacoes
    
    def render_passo_formato(self):
        """Renderiza a etapa de seleção do formato de saída"""
        tipo_retorno = st.radio(
            "Formato de retorno:",
            options=["valor", "texto", "completo"],
            index=["valor", "texto", "completo"].index(
                st.session_state.atributo_atual.get('tipo_retorno', 'texto')),
            format_func=lambda x: {
                'valor': 'Valor (ex: "110")',
                'texto': 'Texto Padrão (ex: "110V")',
                'completo': 'Descrição Completa (ex: "Voltagem: 110V")'
            }[x],
            key="output_format_radio"
        )
        st.session_state.atributo_atual['tipo_retorno'] = tipo_retorno
    
    def avancar_passo(self):
        """Valida e avança para a próxima etapa"""
        try:
            validacoes = [
                self.validar_passo_nome,
                self.validar_passo_variacoes,
                self.validar_passo_padroes,
                lambda: True,  # Prioridade não precisa de validação
                self.validar_passo_formato
            ]
            
            if validacoes[st.session_state.etapa_configuracao]():
                if st.session_state.etapa_configuracao == 4:
                    self.finalizar_configuracao()
                else:
                    st.session_state.etapa_configuracao += 1
                    st.rerun()
        
        except Exception as e:
            st.error(f"❌ {str(e)}")
    
    def validar_passo_nome(self):
        """Validação do passo de nome do atributo"""
        if not st.session_state.atributo_atual.get('nome', '').strip():
            raise ValueError("Por favor, informe um nome para o atributo")
        return True
    
    def validar_passo_variacoes(self):
        """Validação do passo de variações"""
        if 'variacoes' not in st.session_state.atributo_atual or not st.session_state.atributo_atual['variacoes']:
            raise ValueError("Por favor, informe pelo menos uma variação")
        return True
    
    def validar_passo_padroes(self):
        """Validação do passo de padrões"""
        for variacao in st.session_state.atributo_atual['variacoes']:
            if not variacao.get('padroes', []):
                raise ValueError(f"Por favor, informe pelo menos um padrão para '{variacao['descricao']}'")
        return True
    
    def validar_passo_formato(self):
        """Validação do passo de formato"""
        if 'tipo_retorno' not in st.session_state.atributo_atual:
            raise ValueError("Tipo de retorno não definido")
        return True
    
    def finalizar_configuracao(self):
        """Finaliza a configuração do atributo"""
        # Validação final antes de salvar
        if 'nome' not in st.session_state.atributo_atual:
            raise ValueError("Nome do atributo não definido")
        
        if 'variacoes' not in st.session_state.atributo_atual or not st.session_state.atributo_atual['variacoes']:
            raise ValueError("Nenhuma variação definida")
        
        if 'tipo_retorno' not in st.session_state.atributo_atual:
            raise ValueError("Tipo de retorno não definido")
        
        # Salva o atributo
        st.session_state.atributos[st.session_state.atributo_atual['nome']] = st.session_state.atributo_atual.copy()
        
        # Reseta para nova configuração
        st.session_state.etapa_configuracao = 0
        st.session_state.atributo_atual = {}
        st.session_state.ordem_prioridade = None
        
        st.success("🎉 Atributo configurado com sucesso!")
        st.rerun()
    
    def voltar_passo(self):
        """Volta para a etapa anterior"""
        if st.session_state.etapa_configuracao > 0:
            st.session_state.etapa_configuracao -= 1
            st.rerun()
    
    def cancelar_configuracao(self):
        """Cancela a configuração atual"""
        st.session_state.etapa_configuracao = 0
        st.session_state.atributo_atual = {}
        st.session_state.ordem_prioridade = None
        st.info("🔙 Configuração cancelada")
        st.rerun()
    
    def editar_atributo(self, nome_atributo):
        """Inicia a edição de um atributo existente"""
        if nome_atributo in st.session_state.atributos:
            st.session_state.atributo_atual = st.session_state.atributos[nome_atributo].copy()
            st.session_state.etapa_configuracao = 0
            st.rerun()
    
    def remover_atributo(self, nome_atributo):
        """Remove um atributo configurado"""
        if nome_atributo in st.session_state.atributos:
            del st.session_state.atributos[nome_atributo]
            st.success(f"🗑️ Atributo '{nome_atributo}' removido com sucesso!")
            st.rerun()
    
    def limpar_atributos(self):
        """Remove todos os atributos configurados"""
        st.session_state.atributos = {}
        st.success("🧹 Todos os atributos foram removidos!")
        st.rerun()
    
    def exportar_configuracoes(self):
        """Exporta as configurações para um arquivo JSON"""
        if not st.session_state.atributos:
            st.warning("⚠️ Nenhuma configuração para exportar")
            return
        
        # Prepara os dados para exportação
        dados_export = {
            nome: {
                'tipo_retorno': config['tipo_retorno'],
                'variacoes': [
                    {
                        'descricao': variacao['descricao'],
                        'padroes': variacao['padroes']
                    }
                    for variacao in config['variacoes']
                ]
            }
            for nome, config in st.session_state.atributos.items()
        }
        
        # Cria um arquivo JSON para download
        json_str = json.dumps(dados_export, indent=4, ensure_ascii=False)
        b64 = base64.b64encode(json_str.encode('utf-8')).decode()
        
        href = f'<a href="data:application/json;base64,{b64}" download="config_atributos.json">⬇️ Baixar Configurações</a>'
        st.markdown(href, unsafe_allow_html=True)
    
    def importar_configuracoes(self, arquivo):
        """Importa configurações de um arquivo JSON"""
        try:
            dados_import = json.load(arquivo)
            
            # Valida a estrutura do arquivo
            if not isinstance(dados_import, dict):
                raise ValueError("Formato de arquivo inválido")
            
            # Limpa os atributos atuais
            st.session_state.atributos = {}
            
            # Importa cada atributo com validação
            for nome, config in dados_import.items():
                if not isinstance(config, dict):
                    continue
                
                # Verifica se tem os campos obrigatórios
                if 'tipo_retorno' not in config or 'variacoes' not in config:
                    continue
                
                # Cria o atributo
                novo_atributo = {
                    'nome': nome,
                    'tipo_retorno': config['tipo_retorno'],
                    'variacoes': []
                }
                
                # Adiciona as variações com validação
                for variacao in config['variacoes']:
                    if not isinstance(variacao, dict):
                        continue
                    
                    if 'descricao' not in variacao or 'padroes' not in variacao:
                        continue
                    
                    novo_atributo['variacoes'].append({
                        'descricao': variacao['descricao'],
                        'padroes': variacao['padroes']
                    })
                
                # Só adiciona se tiver pelo menos uma variação válida
                if novo_atributo['variacoes']:
                    st.session_state.atributos[nome] = novo_atributo
            
            st.success("✅ Configurações importadas com sucesso!")
            st.rerun()
        
        except json.JSONDecodeError as e:
            st.error(f"❌ Arquivo JSON inválido: {str(e)}")
        except Exception as e:
            st.error(f"❌ Falha ao importar configurações: {str(e)}")
    
    def gerar_modelo(self):
        """Gera um modelo de planilha para download"""
        modelo = pd.DataFrame(columns=['ID', 'Descrição'])
        modelo.loc[0] = ['001', 'ventilador de paredes 110V']
        modelo.loc[1] = ['002', 'luminária de teto 220V branca']
        modelo.loc[2] = ['003', 'filtro de água bivolt']
        modelo.loc[3] = ['004', 'ar condicionado 220V 9000 BTUs']
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            modelo.to_excel(writer, index=False)
        excel_bytes = excel_buffer.getvalue()
        
        st.download_button(
            label="⬇️ Baixar Modelo Excel",
            data=excel_bytes,
            file_name="modelo_descricoes.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    def carregar_planilha(self, arquivo):
        """Carrega uma planilha de dados"""
        try:
            if arquivo.name.endswith('.csv'):
                st.session_state.dados_originais = pd.read_csv(arquivo)
            else:
                st.session_state.dados_originais = pd.read_excel(arquivo)
            
            # Verifica colunas obrigatórias
            colunas_obrigatorias = {'ID', 'Descrição'}
            colunas_faltantes = colunas_obrigatorias - set(st.session_state.dados_originais.columns)
            
            if colunas_faltantes:
                raise ValueError(f"A planilha deve conter as colunas: {', '.join(colunas_obrigatorias)}. Faltando: {', '.join(colunas_faltantes)}")
            
            st.success("✅ Planilha carregada com sucesso!")
            st.session_state.dados_processados = None
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Falha ao carregar planilha: {str(e)}")
    
    def carregar_github(self, repo_url, caminho_arquivo, token=None):
        """Carrega uma planilha do GitHub"""
        try:
            # Conecta ao GitHub
            g = Github(token) if token else Github()
            
            # Obtém o repositório
            repo = g.get_repo(repo_url)
            
            # Obtém o conteúdo do arquivo
            file_content = repo.get_contents(caminho_arquivo)
            
            # Decodifica o conteúdo
            file_data = base64.b64decode(file_content.content)
            
            # Carrega no pandas
            if caminho_arquivo.endswith('.csv'):
                st.session_state.dados_originais = pd.read_csv(BytesIO(file_data))
            else:
                st.session_state.dados_originais = pd.read_excel(BytesIO(file_data))
            
            # Verifica colunas obrigatórias
            colunas_obrigatorias = {'ID', 'Descrição'}
            colunas_faltantes = colunas_obrigatorias - set(st.session_state.dados_originais.columns)
            
            if colunas_faltantes:
                raise ValueError(f"A planilha deve conter as colunas: {', '.join(colunas_obrigatorias)}. Faltando: {', '.join(colunas_faltantes)}")
            
            st.success("✅ Dados carregados do GitHub com sucesso!")
            st.session_state.dados_processados = None
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Falha ao carregar do GitHub: {str(e)}")
    
    def processar_dados(self):
        """Processa os dados conforme as configurações"""
        try:
            # Cria uma cópia dos dados originais
            st.session_state.dados_processados = st.session_state.dados_originais.copy()
            
            # Processa cada atributo configurado
            for atributo_nome, config in st.session_state.atributos.items():
                tipo_retorno = config['tipo_retorno']
                variacoes = config['variacoes']
                
                # Prepara regex para cada variação
                regex_variacoes = []
                for variacao in variacoes:
                    padroes_escaped = [re.escape(p) for p in variacao['padroes']]
                    regex = r'(?i)\b(' + '|'.join(padroes_escaped) + r')\b'
                    regex_variacoes.append((regex, variacao['descricao']))
                
                # Aplica a extração para cada linha
                resultados = []
                for descricao in st.session_state.dados_processados['Descrição'].astype(str):
                    resultado = None
                    
                    # Verifica cada variação na ordem de prioridade
                    for regex, desc_padrao in regex_variacoes:
                        match = re.search(regex, descricao)
                        if match:
                            resultado = self.formatar_resultado(
                                match.group(1),
                                tipo_retorno,
                                atributo_nome,
                                desc_padrao
                            )
                            break  # Usa a primeira correspondência (maior prioridade)
                    
                    resultados.append(resultado if resultado else "")
                
                # Adiciona a coluna de resultados
                st.session_state.dados_processados[atributo_nome] = resultados
            
            st.rerun()
        
        except Exception as e:
            st.error(f"❌ Falha ao processar dados: {str(e)}")
            st.session_state.dados_processados = None
    
    def formatar_resultado(self, valor_encontrado, tipo_retorno, nome_atributo, descricao_padrao):
        """Formata o resultado conforme o tipo de retorno configurado"""
        if tipo_retorno == "valor":
            # Extrai apenas números
            numeros = re.findall(r'\d+', valor_encontrado)
            return numeros[0] if numeros else ""
        elif tipo_retorno == "texto":
            return descricao_padrao
        elif tipo_retorno == "completo":
            return f"{nome_atributo}: {descricao_padrao}"
        return valor_encontrado

# Executa a aplicação
if __name__ == "__main__":
    extrator = ExtratorAtributos()
