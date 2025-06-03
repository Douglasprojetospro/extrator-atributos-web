python
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
        
        # Inicializa o estado da sessão se não existir
        if 'dados_originais' not in st.session_state:
            st.session_state.dados_originais = None
        if 'dados_processados' not in st.session_state:
            st.session_state.dados_processados = None
        if 'atributos' not in st.session_state:
            st.session_state.atributos = {}
        
        self.setup_ui()
    
    def setup_ui(self):
        st.title("Sistema de Extração de Atributos Avançado")
        
        # Abas principais
        tab1, tab2, tab3 = st.tabs(["Modelo e Upload", "Configuração", "Resultados"])
        
        with tab1:
            self.setup_aba_modelo()
        
        with tab2:
            self.setup_aba_configuracao()
        
        with tab3:
            self.setup_aba_resultados()
    
    def setup_aba_modelo(self):
        st.header("Modelo e Upload de Dados")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Modelo de Planilha")
            if st.button("Gerar Modelo Excel"):
                self.gerar_modelo()
        
        with col2:
            st.subheader("Carregar Dados")
            opcao_carregar = st.radio("Fonte dos dados:", ("Upload Local", "GitHub"))
            
            if opcao_carregar == "Upload Local":
                arquivo = st.file_uploader("Selecione a planilha", type=["xlsx", "xls"])
                if arquivo is not None:
                    self.carregar_planilha(arquivo)
            
            elif opcao_carregar == "GitHub":
                repo_url = st.text_input("URL do repositório GitHub (ex: usuario/repo)")
                caminho_arquivo = st.text_input("Caminho do arquivo no repositório (ex: dados/planilha.xlsx)")
                token = st.text_input("Token de acesso GitHub (opcional)", type="password")
                
                if st.button("Carregar do GitHub") and repo_url and caminho_arquivo:
                    self.carregar_github(repo_url, caminho_arquivo, token)
        
        # Visualização dos dados carregados
        if st.session_state.dados_originais is not None:
            st.subheader("Pré-visualização dos Dados")
            st.dataframe(st.session_state.dados_originais.head())
    
    def setup_aba_configuracao(self):
        st.header("Configuração de Atributos")
        
        # Frame de instruções
        st.subheader("Instruções")
        instrucao = self.get_instrucao_atual()
        st.markdown(instrucao)
        
        # Frame do passo atual
        st.subheader("Configuração do Atributo")
        self.render_passo_atual()
        
        # Navegação
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("← Voltar", disabled=self.etapa_configuracao == 0):
                self.voltar_passo()
        
        with col2:
            texto_botao = "Avançar →" if self.etapa_configuracao < 4 else "Concluir"
            if st.button(texto_botao):
                self.avancar_passo()
        
        with col3:
            if st.button("Cancelar"):
                self.cancelar_configuracao()
        
        # Importar/Exportar configurações
        st.subheader("Gerenciamento de Configurações")
        col_exp, col_imp = st.columns(2)
        
        with col_exp:
            if st.button("Exportar Configurações"):
                self.exportar_configuracoes()
        
        with col_imp:
            arquivo_config = st.file_uploader("Importar Configurações", type=["json"])
            if arquivo_config is not None:
                self.importar_configuracoes(arquivo_config)
        
        # Lista de atributos configurados
        st.subheader("Atributos Configurados")
        if st.session_state.atributos:
            df_atributos = pd.DataFrame([
                {
                    'Atributo': nome,
                    'Variações': ", ".join([v['descricao'] for v in config['variacoes']]),
                    'Prioridade': config['variacoes'][0]['descricao'],
                    'Formato': "Valor" if config['tipo_retorno'] == "valor" else "Texto" if config['tipo_retorno'] == "texto" else "Completo"
                }
                for nome, config in st.session_state.atributos.items()
            ])
            st.dataframe(df_atributos, use_container_width=True)
            
            # Botões de gerenciamento
            col_edit, col_rem, col_lim = st.columns(3)
            
            with col_edit:
                atributo_editar = st.selectbox("Selecionar atributo para editar", list(st.session_state.atributos.keys()))
                if st.button("Editar Selecionado"):
                    self.editar_atributo(atributo_editar)
            
            with col_rem:
                atributo_remover = st.selectbox("Selecionar atributo para remover", list(st.session_state.atributos.keys()))
                if st.button("Remover Selecionado"):
                    self.remover_atributo(atributo_remover)
            
            with col_lim:
                if st.button("Limpar Todos"):
                    self.limpar_atributos()
        else:
            st.info("Nenhum atributo configurado ainda.")
    
    def setup_aba_resultados(self):
        st.header("Processamento e Resultados")
        
        if st.button("Extrair Atributos"):
            if st.session_state.dados_originais is None:
                st.warning("Por favor, carregue uma planilha primeiro")
            elif not st.session_state.atributos:
                st.warning("Por favor, configure pelo menos um atributo")
            else:
                with st.spinner("Processando dados..."):
                    self.processar_dados()
                    st.success("Processamento concluído com sucesso!")
        
        # Exibição dos resultados
        if st.session_state.dados_processados is not None:
            st.subheader("Resultados da Extração")
            st.dataframe(st.session_state.dados_processados, use_container_width=True)
            
            # Exportação dos resultados
            st.subheader("Exportar Resultados")
            nome_arquivo = st.text_input("Nome do arquivo", "resultados_extracao")
            
            col_csv, col_excel = st.columns(2)
            
            with col_csv:
                csv = self.dados_processados.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="Exportar como CSV",
                    data=csv,
                    file_name=f"{nome_arquivo}.csv",
                    mime='text/csv'
                )
            
            with col_excel:
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    self.dados_processados.to_excel(writer, index=False)
                excel_bytes = excel_buffer.getvalue()
                
                st.download_button(
                    label="Exportar como Excel",
                    data=excel_bytes,
                    file_name=f"{nome_arquivo}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
    
    def get_instrucao_atual(self):
        instrucoes = [
            "1. Digite o nome do atributo que deseja configurar (ex: 'Voltagem')\n"
            "O nome será usado como cabeçalho na planilha de resultados.",
            
            "2. Adicione as variações de descrição para este atributo (ex: '110V', '220V', 'Bivolt')\n"
            "Cada variação será uma possível saída do sistema.",
            
            "3. Para cada variação, adicione os padrões de reconhecimento (um por linha)\n"
            "Estes são os textos que o sistema buscará na descrição do produto.",
            
            "4. Defina a ordem de prioridade das variações\n"
            "Quando vários padrões forem encontrados, o sistema usará a variação com maior prioridade.",
            
            "5. Selecione o formato de retorno para este atributo\n"
            "O sistema pode retornar apenas o valor, o texto padrão ou uma descrição completa."
        ]
        return instrucoes[self.etapa_configuracao]
    
    def render_passo_atual(self):
        if self.etapa_configuracao == 0:
            self.atributo_atual['nome'] = st.text_input("Nome do Atributo:", 
                                                      value=self.atributo_atual.get('nome', ''))
        
        elif self.etapa_configuracao == 1:
            default_var = "\n".join([v['descricao'] for v in self.atributo_atual.get('variacoes', [])])
            var_text = st.text_area("Variações (uma por linha):", 
                                  value=default_var, height=150)
            
            if 'variacoes' not in self.atributo_atual and var_text.strip():
                variacoes = [v.strip() for v in var_text.split('\n') if v.strip()]
                self.atributo_atual['variacoes'] = [{'descricao': v, 'padroes': []} for v in variacoes]
        
        elif self.etapa_configuracao == 2:
            if 'variacoes' not in self.atributo_atual:
                st.warning("Por favor, volte e defina as variações primeiro")
                return
            
            tabs = st.tabs([v['descricao'] for v in self.atributo_atual['variacoes']])
            
            for i, variacao in enumerate(self.atributo_atual['variacoes']):
                with tabs[i]:
                    default_padroes = "\n".join(variacao.get('padroes', []))
                    padroes = st.text_area(f"Padrões para '{variacao['descricao']}':",
                                         value=default_padroes, height=100,
                                         key=f"padroes_{i}")
                    
                    if padroes.strip():
                        variacao['padroes'] = [p.strip() for p in padroes.split('\n') if p.strip()]
        
        elif self.etapa_configuracao == 3:
            if 'variacoes' not in self.atributo_atual:
                st.warning("Por favor, complete os passos anteriores primeiro")
                return
            
            st.write("Arraste para ordenar (a primeira tem maior prioridade):")
            
            # Cria uma lista ordenável com st.columns
            variacoes_ordenadas = st.session_state.get('variacoes_ordenadas', 
                                                      [v['descricao'] for v in self.atributo_atual['variacoes']])
            
            for i, descricao in enumerate(variacoes_ordenadas):
                col1, col2 = st.columns([0.9, 0.1])
                
                with col1:
                    st.text_input(f"Posição {i+1}", value=descricao, 
                                 key=f"var_{i}", disabled=True)
                
                with col2:
                    if st.button("↑", key=f"up_{i}") and i > 0:
                        variacoes_ordenadas[i], variacoes_ordenadas[i-1] = variacoes_ordenadas[i-1], variacoes_ordenadas[i]
                        st.session_state.variacoes_ordenadas = variacoes_ordenadas
                        st.experimental_rerun()
                    
                    if st.button("↓", key=f"down_{i}") and i < len(variacoes_ordenadas)-1:
                        variacoes_ordenadas[i], variacoes_ordenadas[i+1] = variacoes_ordenadas[i+1], variacoes_ordenadas[i]
                        st.session_state.variacoes_ordenadas = variacoes_ordenadas
                        st.experimental_rerun()
            
            # Atualiza a ordem das variações
            novas_variacoes = []
            for descricao in variacoes_ordenadas:
                for variacao in self.atributo_atual['variacoes']:
                    if variacao['descricao'] == descricao:
                        novas_variacoes.append(variacao)
                        break
            
            self.atributo_atual['variacoes'] = novas_variacoes
        
        elif self.etapa_configuracao == 4:
            tipo_retorno = st.radio("Formato de retorno:",
                                  options=["valor", "texto", "completo"],
                                  index=["valor", "texto", "completo"].index(
                                      self.atributo_atual.get('tipo_retorno', 'texto')),
                                  format_func=lambda x: {
                                      'valor': 'Valor (ex: "110")',
                                      'texto': 'Texto Padrão (ex: "110V")',
                                      'completo': 'Descrição Completa (ex: "Voltagem: 110V")'
                                  }[x])
            
            self.atributo_atual['tipo_retorno'] = tipo_retorno
    
    def avancar_passo(self):
        try:
            if self.etapa_configuracao == 0:
                if not self.atributo_atual.get('nome', '').strip():
                    raise ValueError("Por favor, informe um nome para o atributo")
                
                self.etapa_configuracao += 1
            
            elif self.etapa_configuracao == 1:
                if 'variacoes' not in self.atributo_atual or not self.atributo_atual['variacoes']:
                    raise ValueError("Por favor, informe pelo menos uma variação")
                
                self.etapa_configuracao += 1
            
            elif self.etapa_configuracao == 2:
                for variacao in self.atributo_atual['variacoes']:
                    if not variacao.get('padroes', []):
                        raise ValueError(f"Por favor, informe pelo menos um padrão para '{variacao['descricao']}'")
                
                self.etapa_configuracao += 1
                st.session_state.variacoes_ordenadas = [v['descricao'] for v in self.atributo_atual['variacoes']]
            
            elif self.etapa_configuracao == 3:
                self.etapa_configuracao += 1
            
            elif self.etapa_configuracao == 4:
                st.session_state.atributos[self.atributo_atual['nome']] = self.atributo_atual.copy()
                self.etapa_configuracao = 0
                self.atributo_atual = {}
                if 'variacoes_ordenadas' in st.session_state:
                    del st.session_state.variacoes_ordenadas
                
                st.success("Atributo configurado com sucesso!")
            
        except Exception as e:
            st.error(str(e))
    
    def voltar_passo(self):
        if self.etapa_configuracao > 0:
            self.etapa_configuracao -= 1
            if self.etapa_configuracao < 3 and 'variacoes_ordenadas' in st.session_state:
                del st.session_state.variacoes_ordenadas
    
    def cancelar_configuracao(self):
        self.etapa_configuracao = 0
        self.atributo_atual = {}
        if 'variacoes_ordenadas' in st.session_state:
            del st.session_state.variacoes_ordenadas
        st.info("Configuração cancelada")
    
    def editar_atributo(self, nome_atributo):
        self.atributo_atual = st.session_state.atributos[nome_atributo].copy()
        self.etapa_configuracao = 0
        st.session_state.variacoes_ordenadas = [v['descricao'] for v in self.atributo_atual['variacoes']]
    
    def remover_atributo(self, nome_atributo):
        del st.session_state.atributos[nome_atributo]
        st.success(f"Atributo '{nome_atributo}' removido com sucesso!")
    
    def limpar_atributos(self):
        st.session_state.atributos = {}
        st.success("Todos os atributos foram removidos!")
    
    def exportar_configuracoes(self):
        if not st.session_state.atributos:
            st.warning("Nenhuma configuração para exportar")
            return
        
        # Prepara os dados para exportação
        dados_export = {}
        for nome, config in st.session_state.atributos.items():
            dados_export[nome] = {
                'tipo_retorno': config['tipo_retorno'],
                'variacoes': []
            }
            
            for variacao in config['variacoes']:
                dados_export[nome]['variacoes'].append({
                    'descricao': variacao['descricao'],
                    'padroes': variacao['padroes']
                })
        
        # Cria um arquivo JSON para download
        json_str = json.dumps(dados_export, indent=4, ensure_ascii=False)
        b64 = base64.b64encode(json_str.encode('utf-8')).decode()
        
        href = f'<a href="data:application/json;base64,{b64}" download="config_atributos.json">Download das Configurações</a>'
        st.markdown(href, unsafe_allow_html=True)
    
    def importar_configuracoes(self, arquivo):
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
                st.session_state.atributos[nome] = {
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
                    
                    st.session_state.atributos[nome]['variacoes'].append({
                        'descricao': variacao['descricao'],
                        'padroes': variacao['padroes']
                    })
            
            st.success("Configurações importadas com sucesso!")
        
        except json.JSONDecodeError as e:
            st.error(f"Arquivo JSON inválido: {str(e)}")
        except Exception as e:
            st.error(f"Falha ao importar configurações: {str(e)}")
    
    def gerar_modelo(self):
        modelo = pd.DataFrame(columns=['ID', 'Descrição'])
        modelo.loc[0] = ['001', 'ventilador de paredes 110V']
        modelo.loc[1] = ['002', 'luminária de teto 220V branca']
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            modelo.to_excel(writer, index=False)
        excel_bytes = excel_buffer.getvalue()
        
        st.download_button(
            label="Baixar Modelo Excel",
            data=excel_bytes,
            file_name="modelo_descricoes.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    
    def carregar_planilha(self, arquivo):
        try:
            st.session_state.dados_originais = pd.read_excel(arquivo)
            
            if 'ID' not in st.session_state.dados_originais.columns or 'Descrição' not in st.session_state.dados_originais.columns:
                raise ValueError("A planilha deve conter as colunas 'ID' e 'Descrição'")
            
            st.success("Planilha carregada com sucesso!")
            st.session_state.dados_processados = None
        
        except Exception as e:
            st.error(f"Falha ao carregar planilha: {str(e)}")
    
    def carregar_github(self, repo_url, caminho_arquivo, token=None):
        try:
            # Conecta ao GitHub
            g = Github(token) if token else Github()
            
            # Obtém o repositório
            repo = g.get_repo(repo_url)
            
            # Obtém o conteúdo do arquivo
            file_content = repo.get_contents(caminho_arquivo)
            
            # Decodifica o conteúdo (o GitHub API retorna em base64)
            file_data = base64.b64decode(file_content.content)
            
            # Carrega no pandas
            st.session_state.dados_originais = pd.read_excel(BytesIO(file_data))
            
            if 'ID' not in st.session_state.dados_originais.columns or 'Descrição' not in st.session_state.dados_originais.columns:
                raise ValueError("A planilha deve conter as colunas 'ID' e 'Descrição'")
            
            st.success("Dados carregados do GitHub com sucesso!")
            st.session_state.dados_processados = None
        
        except Exception as e:
            st.error(f"Falha ao carregar do GitHub: {str(e)}")
    
    def processar_dados(self):
        try:
            st.session_state.dados_processados = st.session_state.dados_originais.copy()
            
            for atributo_nome, config in st.session_state.atributos.items():
                tipo_retorno = config['tipo_retorno']
                variacoes = config['variacoes']
                
                # Prepara regex para cada variação
                regex_variacoes = []
                for variacao in variacoes:
                    padroes_escaped = [re.escape(p) for p in variacao['padroes']]
                    regex = r'\b(' + '|'.join(padroes_escaped) + r')\b'
                    regex_variacoes.append((regex, variacao['descricao']))
                
                st.session_state.dados_processados[atributo_nome] = ""
                
                for idx, row in st.session_state.dados_processados.iterrows():
                    descricao = str(row['Descrição']).lower()
                    resultado = None
                    
                    # Verifica cada variação na ordem de prioridade
                    for regex, desc_padrao in regex_variacoes:
                        match = re.search(regex, descricao, re.IGNORECASE)
                        if match:
                            resultado = self.formatar_resultado(
                                match.group(1),
                                tipo_retorno,
                                atributo_nome,
                                desc_padrao
                            )
                            break  # Usa a primeira correspondência (maior prioridade)
                    
                    st.session_state.dados_processados.at[idx, atributo_nome] = resultado if resultado else ""
            
            st.success("Processamento concluído com sucesso!")
        
        except Exception as e:
            st.error(f"Falha ao processar dados: {str(e)}")
    
    def formatar_resultado(self, valor_encontrado, tipo_retorno, nome_atributo, descricao_padrao):
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
    app = ExtratorAtributos()
