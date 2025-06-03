import pandas as pd
import re
import os
import json
import streamlit as st
from io import BytesIO
from datetime import datetime

class ExtratorAtributosStreamlit:
    def __init__(self):
        self.atributos = {}
        self.dados_processados = pd.DataFrame()
        self.etapa_configuracao = 0  # 0=nome, 1=variações, 2=padrões, 3=prioridade, 4=formato
        self.atributo_atual = {}
        self.dados_originais = None
        
        # Configuração da página
        st.set_page_config(page_title="Sistema de Extração de Atributos", layout="wide")
        
    def run(self):
        st.title("📋 Sistema de Extração de Atributos Avançado")
        
        # Criando abas
        tab1, tab2, tab3 = st.tabs(["Modelo e Upload", "Configuração", "Resultados"])
        
        with tab1:
            self.aba_modelo()
        
        with tab2:
            self.aba_configuracao()
        
        with tab3:
            self.aba_resultados()
    
    def aba_modelo(self):
        st.header("Modelo e Upload de Planilha")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Gerar Modelo")
            if st.button("Gerar Modelo Excel"):
                self.gerar_modelo()
        
        with col2:
            st.subheader("Carregar Planilha")
            uploaded_file = st.file_uploader("Selecione a planilha", type=["xlsx", "xls"])
            
            if uploaded_file is not None:
                try:
                    self.dados_originais = pd.read_excel(uploaded_file)
                    
                    if 'ID' not in self.dados_originais.columns or 'Descrição' not in self.dados_originais.columns:
                        st.error("A planilha deve conter as colunas 'ID' e 'Descrição'")
                    else:
                        st.success("Planilha carregada com sucesso!")
                        st.dataframe(self.dados_originais.head())
                except Exception as e:
                    st.error(f"Erro ao carregar planilha: {str(e)}")
    
    def aba_configuracao(self):
        st.header("Configuração de Atributos")
        
        # Seção de instruções
        st.subheader("Configurar Novo Atributo")
        
        if self.etapa_configuracao == 0:
            self.passo_nome_atributo()
        elif self.etapa_configuracao == 1:
            self.passo_variacoes()
        elif self.etapa_configuracao == 2:
            self.passo_padroes()
        elif self.etapa_configuracao == 3:
            self.passo_prioridade()
        elif self.etapa_configuracao == 4:
            self.passo_formato()
        
        # Seção de atributos configurados
        st.subheader("Atributos Configurados")
        
        if not self.atributos:
            st.info("Nenhum atributo configurado ainda")
        else:
            # Mostra tabela de atributos
            dados_tabela = []
            for nome, config in self.atributos.items():
                variacoes = ", ".join([v['descricao'] for v in config['variacoes']])
                prioridade = config['variacoes'][0]['descricao']
                formato = "Valor" if config['tipo_retorno'] == "valor" else "Texto" if config['tipo_retorno'] == "texto" else "Completo"
                dados_tabela.append([nome, variacoes, prioridade, formato])
            
            df_atributos = pd.DataFrame(dados_tabela, columns=["Atributo", "Variações", "Prioridade", "Formato"])
            st.dataframe(df_atributos, use_container_width=True)
            
            # Botões de ação
            col1, col2, col3 = st.columns(3)
            
            with col1:
                atributo_editar = st.selectbox("Selecione para editar", [""] + list(self.atributos.keys()))
                if atributo_editar and st.button("Editar Atributo"):
                    self.atributo_atual = self.atributos[atributo_editar].copy()
                    self.etapa_configuracao = 0
                    st.experimental_rerun()
            
            with col2:
                atributo_remover = st.selectbox("Selecione para remover", [""] + list(self.atributos.keys()))
                if atributo_remover and st.button("Remover Atributo"):
                    del self.atributos[atributo_remover]
                    st.success(f"Atributo '{atributo_remover}' removido!")
                    st.experimental_rerun()
            
            with col3:
                if st.button("Limpar Todos"):
                    self.atributos = {}
                    st.success("Todos os atributos foram removidos!")
                    st.experimental_rerun()
        
        # Importar/Exportar configurações
        st.subheader("Importar/Exportar Configurações")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="Exportar Configurações",
                data=self.exportar_configuracoes(),
                file_name="config_atributos.json",
                mime="application/json",
                disabled=not self.atributos
            )
        
        with col2:
            uploaded_config = st.file_uploader("Importar Configurações", type=["json"])
            if uploaded_config is not None:
                try:
                    dados_import = json.load(uploaded_config)
                    self.importar_configuracoes(dados_import)
                    st.success("Configurações importadas com sucesso!")
                    st.experimental_rerun()
                except Exception as e:
                    st.error(f"Erro ao importar configurações: {str(e)}")
    
    def passo_nome_atributo(self):
        st.write("**1. Nome do Atributo**")
        st.write("Digite o nome do atributo que deseja configurar (ex: 'Voltagem'). O nome será usado como cabeçalho na planilha de resultados.")
        
        nome = st.text_input("Nome do Atributo:", value=self.atributo_atual.get('nome', ''))
        
        if st.button("Próximo"):
            if not nome.strip():
                st.error("Por favor, informe um nome para o atributo")
            else:
                self.atributo_atual = {'nome': nome.strip()}
                self.etapa_configuracao = 1
                st.experimental_rerun()
    
    def passo_variacoes(self):
        st.write("**2. Variações do Atributo**")
        st.write("Adicione as variações de descrição para este atributo (ex: '110V', '220V', 'Bivolt'). Cada variação será uma possível saída do sistema.")
        
        variacoes_texto = st.text_area(
            "Variações (uma por linha):", 
            value="\n".join([v['descricao'] for v in self.atributo_atual.get('variacoes', [])]),
            height=150
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Voltar"):
                self.etapa_configuracao = 0
                st.experimental_rerun()
        
        with col2:
            if st.button("Próximo"):
                variacoes = [v.strip() for v in variacoes_texto.split('\n') if v.strip()]
                if not variacoes:
                    st.error("Por favor, informe pelo menos uma variação válida")
                else:
                    self.atributo_atual['variacoes'] = [{'descricao': v, 'padroes': []} for v in variacoes]
                    self.etapa_configuracao = 2
                    st.experimental_rerun()
    
    def passo_padroes(self):
        st.write("**3. Padrões de Reconhecimento**")
        st.write("Para cada variação, adicione os padrões de reconhecimento (um por linha). Estes são os textos que o sistema buscará na descrição do produto.")
        
        tabs = st.tabs([v['descricao'] for v in self.atributo_atual['variacoes']])
        
        for i, tab in enumerate(tabs):
            with tab:
                variacao = self.atributo_atual['variacoes'][i]
                padroes = st.text_area(
                    f"Padrões para '{variacao['descricao']}':",
                    value="\n".join(variacao.get('padroes', [])),
                    height=100,
                    key=f"padroes_{i}"
                )
                self.atributo_atual['variacoes'][i]['padroes'] = [p.strip() for p in padroes.split('\n') if p.strip()]
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Voltar"):
                self.etapa_configuracao = 1
                st.experimental_rerun()
        
        with col2:
            if st.button("Próximo"):
                # Valida se todos os padrões foram preenchidos
                erro = False
                for variacao in self.atributo_atual['variacoes']:
                    if not variacao['padroes']:
                        st.error(f"Por favor, informe pelo menos um padrão para '{variacao['descricao']}'")
                        erro = True
                        break
                
                if not erro:
                    self.etapa_configuracao = 3
                    st.experimental_rerun()
    
    def passo_prioridade(self):
        st.write("**4. Ordem de Prioridade**")
        st.write("Defina a ordem de prioridade das variações. Quando vários padrões forem encontrados, o sistema usará a variação com maior prioridade.")
        
        # Cria lista ordenável
        variacoes = [v['descricao'] for v in self.atributo_atual['variacoes']]
        
        st.write("**Ordem atual (a primeira tem maior prioridade):**")
        for i, var in enumerate(variacoes, 1):
            st.write(f"{i}. {var}")
        
        # Widget para reordenar
        nova_ordem = st.multiselect(
            "Reordenar (selecione na nova ordem):",
            options=variacoes,
            default=variacoes
        )
        
        if set(nova_ordem) != set(variacoes):
            st.warning("Você deve incluir todas as variações na nova ordem")
            nova_ordem = variacoes
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Voltar"):
                self.etapa_configuracao = 2
                st.experimental_rerun()
        
        with col2:
            if st.button("Próximo"):
                # Reordena as variações conforme a prioridade
                variacoes_ordenadas = []
                for descricao in nova_ordem:
                    for variacao in self.atributo_atual['variacoes']:
                        if variacao['descricao'] == descricao:
                            variacoes_ordenadas.append(variacao)
                            break
                
                self.atributo_atual['variacoes'] = variacoes_ordenadas
                self.etapa_configuracao = 4
                st.experimental_rerun()
    
    def passo_formato(self):
        st.write("**5. Formato de Retorno**")
        st.write("Selecione o formato de retorno para este atributo. O sistema pode retornar apenas o valor, o texto padrão ou uma descrição completa.")
        
        formato = st.radio(
            "Formato de retorno:",
            options=["valor", "texto", "completo"],
            index=["valor", "texto", "completo"].index(self.atributo_atual.get('tipo_retorno', 'texto')),
            format_func=lambda x: {
                "valor": "Valor (ex: '110')", 
                "texto": "Texto Padrão (ex: '110V')", 
                "completo": "Descrição Completa (ex: 'Voltagem: 110V')"
            }[x]
        )
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Voltar"):
                self.etapa_configuracao = 3
                st.experimental_rerun()
        
        with col2:
            if st.button("Concluir"):
                self.atributo_atual['tipo_retorno'] = formato
                
                # Adiciona ao dicionário de atributos
                self.atributos[self.atributo_atual['nome']] = self.atributo_atual
                
                # Reseta para nova configuração
                self.etapa_configuracao = 0
                self.atributo_atual = {}
                st.success("Atributo configurado com sucesso!")
                st.experimental_rerun()
    
    def aba_resultados(self):
        st.header("Processamento e Resultados")
        
        if st.button("Extrair Atributos", disabled=self.dados_originais is None or not self.atributos):
            if self.dados_originais is None:
                st.error("Por favor, carregue uma planilha primeiro")
            elif not self.atributos:
                st.error("Por favor, configure pelo menos um atributo")
            else:
                with st.spinner("Processando dados..."):
                    self.processar_dados()
                st.success("Processamento concluído!")
        
        if hasattr(self, 'dados_processados') and not self.dados_processados.empty:
            st.subheader("Resultados")
            st.dataframe(self.dados_processados, use_container_width=True)
            
            # Botão para exportar
            st.download_button(
                label="Exportar Resultados",
                data=self.exportar_resultados(),
                file_name=f"resultados_extracao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    def gerar_modelo(self):
        modelo = pd.DataFrame(columns=['ID', 'Descrição'])
        modelo.loc[0] = ['001', 'ventilador de paredes 110V']
        modelo.loc[1] = ['002', 'luminária de teto 220V branca']
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            modelo.to_excel(writer, index=False)
        
        st.download_button(
            label="Baixar Modelo Excel",
            data=output.getvalue(),
            file_name="modelo_descricoes.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    def exportar_configuracoes(self):
        dados_export = {}
        for nome, config in self.atributos.items():
            dados_export[nome] = {
                'tipo_retorno': config['tipo_retorno'],
                'variacoes': []
            }
            
            for variacao in config['variacoes']:
                dados_export[nome]['variacoes'].append({
                    'descricao': variacao['descricao'],
                    'padroes': variacao['padroes']
                })
        
        return json.dumps(dados_export, indent=4, ensure_ascii=False)
    
    def importar_configuracoes(self, dados_import):
        self.atributos = {}
        
        for nome, config in dados_import.items():
            if not isinstance(config, dict):
                continue
            
            if 'tipo_retorno' not in config or 'variacoes' not in config:
                continue
            
            self.atributos[nome] = {
                'nome': nome,
                'tipo_retorno': config['tipo_retorno'],
                'variacoes': []
            }
            
            for variacao in config['variacoes']:
                if not isinstance(variacao, dict):
                    continue
                
                if 'descricao' not in variacao or 'padroes' not in variacao:
                    continue
                
                self.atributos[nome]['variacoes'].append({
                    'descricao': variacao['descricao'],
                    'padroes': variacao['padroes']
                })
    
    def processar_dados(self):
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
                            match.group(1),
                            tipo_retorno,
                            atributo_nome,
                            desc_padrao
                        )
                        break  # Usa a primeira correspondência (maior prioridade)
                
                self.dados_processados.at[idx, atributo_nome] = resultado if resultado else ""
    
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
    
    def exportar_resultados(self):
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            self.dados_processados.to_excel(writer, index=False)
        return output.getvalue()

# Executa a aplicação
if __name__ == "__main__":
    app = ExtratorAtributosStreamlit()
    app.run()
