import streamlit as st
import pandas as pd
import re
import json
import requests
from io import BytesIO
import base64
import streamlit_sortables
from streamlit_sortables import SortableList

st.set_page_config(
    page_title="Sistema de Extração de Atributos Avançado",
    page_icon="📊",
    layout="wide",
)

class ExtratorAtributos:
    def __init__(self):
        self.atributos = st.session_state.get("atributos", {})
        self.dados_processados = st.session_state.get("dados_processados", pd.DataFrame())
        self.etapa_configuracao = st.session_state.get("etapa_configuracao", 0)
        self.atributo_atual = st.session_state.get("atributo_atual", {})
        self.setup_ui()

    def setup_ui(self):
        st.title("Sistema de Extração de Atributos Avançado")

        tabs = st.tabs(["Modelo e Upload", "Configuração", "Resultados"])

        with tabs[0]:
            self.setup_aba_modelo()
        with tabs[1]:
            self.setup_aba_configuracao()
        with tabs[2]:
            self.setup_aba_resultados()

    def setup_aba_modelo(self):
        st.header("Modelo e Upload")

        # Gerar modelo
        st.subheader("Modelo de Planilha")
        if st.button("Gerar Modelo Excel"):
            modelo = pd.DataFrame(columns=["ID", "Descrição"])
            modelo.loc[0] = ["001", "ventilador de paredes 110V"]
            modelo.loc[1] = ["002", "luminária de teto 220V branca"]

            buffer = BytesIO()
            modelo.to_excel(buffer, index=False)
            buffer.seek(0)

            b64 = base64.b64encode(buffer.read()).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="modelo_descricoes.xlsx">Download Modelo Excel</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.session_state["status"] = "Modelo gerado com sucesso!"

        # Upload de planilha
        st.subheader("Upload de Planilha")
        github_url = st.text_input("URL do arquivo no GitHub (raw)", placeholder="https://raw.githubusercontent.com/usuario/repo/main/planilha.xlsx")

        uploaded_file = st.file_uploader("Ou selecione uma planilha local", type=["xlsx", "xls"])

        if github_url and st.button("Carregar do GitHub"):
            try:
                response = requests.get(github_url)
                response.raise_for_status()
                self.dados_originais = pd.read_excel(BytesIO(response.content))

                if "ID" not in self.dados_originais.columns or "Descrição" not in self.dados_originais.columns:
                    raise ValueError("A planilha deve conter as colunas 'ID' e 'Descrição'")

                st.session_state["dados_originais"] = self.dados_originais
                st.dataframe(self.dados_originais.head())
                st.session_state["status"] = f"Planilha carregada do GitHub - {len(self.dados_originais)} registros"
                st.success("Planilha carregada com sucesso!")
            except Exception as e:
                st.session_state["status"] = f"Erro ao carregar planilha: {str(e)}"
                st.error(f"Falha ao carregar planilha:\n{str(e)}")

        if uploaded_file and st.button("Carregar do Upload"):
            try:
                self.dados_originais = pd.read_excel(uploaded_file)

                if "ID" not in self.dados_originais.columns or "Descrição" not in self.dados_originais.columns:
                    raise ValueError("A planilha deve conter as colunas 'ID' e 'Descrição'")

                st.session_state["dados_originais"] = self.dados_originais
                st.dataframe(self.dados_originais.head())
                st.session_state["status"] = f"Planilha carregada localmente - {len(self.dados_originais)} registros"
                st.success("Planilha carregada com sucesso!")
            except Exception as e:
                st.session_state["status"] = f"Erro ao carregar planilha: {str(e)}"
                st.error(f"Falha ao carregar planilha:\n{str(e)}")

        # Barra de status
        st.markdown("---")
        st.write(f"**Status**: {st.session_state.get('status', 'Pronto')}")

    def setup_aba_configuracao(self):
        st.header("Configuração de Atributos")

        # Instruções
        instrucoes = {
            0: "1. Digite o nome do atributo que deseja configurar (ex: 'Voltagem')\nO nome será usado como cabeçalho na planilha de resultados.",
            1: "2. Adicione as variações de descrição para este atributo (ex: '110V', '220V', 'Bivolt')\nCada variação será uma possível saída do sistema.",
            2: "3. Para cada variação, adicione os padrões de reconhecimento (um por linha)\nEstes são os textos que o sistema buscará na descrição do produto.",
            3: "4. Defina a ordem de prioridade das variações\nQuando vários padrões forem encontrados, o sistema usará a variação com maior prioridade.",
            4: "5. Selecione o formato de retorno para este atributo\nO sistema pode retornar apenas o valor, o texto padrão ou uma descrição completa."
        }

        st.subheader("Instruções")
        st.write(instrucoes[self.etapa_configuracao])

        # Configuração do passo atual
        st.subheader("Configuração do Atributo")
        with st.form(key="config_form"):
            if self.etapa_configuracao == 0:
                nome_atributo = st.text_input("Nome do Atributo", value=self.atributo_atual.get("nome", ""))
                st.session_state["nome_atributo"] = nome_atributo

            elif self.etapa_configuracao == 1:
                variacoes_text = "\n".join([v["descricao"] for v in self.atributo_atual.get("variacoes", [])])
                variacoes = st.text_area("Variações (uma por linha)", value=variacoes_text, height=150)
                st.session_state["variacoes"] = variacoes

            elif self.etapa_configuracao == 2:
                if "variacoes" not in self.atributo_atual:
                    variacoes = [v.strip() for v in st.session_state.get("variacoes", "").split("\n") if v.strip()]
                    self.atributo_atual["variacoes"] = [{"descricao": v, "padroes": []} for v in variacoes]

                tabs = st.tabs([v["descricao"] for v in self.atributo_atual["variacoes"]])
                for idx, tab in enumerate(tabs):
                    with tab:
                        padroes_text = "\n".join(self.atributo_atual["variacoes"][idx].get("padroes", []))
                        padroes = st.text_area(f"Padrões para '{self.atributo_atual['variacoes'][idx]['descricao']}'", value=padroes_text, height=100)
                        st.session_state[f"padroes_{idx}"] = padroes

            elif self.etapa_configuracao == 3:
                if "variacoes" in self.atributo_atual:
                    variacoes = [v["descricao"] for v in self.atributo_atual["variacoes"]]
                    st.write("Arraste para ordenar (a primeira tem maior prioridade):")
                    ordenadas = SortableList(variacoes, key="sortable_variacoes")
                    st.session_state["ordem_prioridade"] = ordenadas

            elif self.etapa_configuracao == 4:
                tipo_retorno = st.radio(
                    "Formato de Retorno",
                    ["Valor (ex: '110')", "Texto Padrão (ex: '110V')", "Descrição Completa (ex: 'Voltagem: 110V')"],
                    index=["valor", "texto", "completo"].index(self.atributo_atual.get("tipo_retorno", "texto"))
                )
                st.session_state["tipo_retorno"] = {"Valor (ex: '110')": "valor", "Texto Padrão (ex: '110V')": "texto", "Descrição Completa (ex: 'Voltagem: 110V')": "completo"}[tipo_retorno]

            # Botões de navegação
            col1, col2, col3 = st.columns([1, 1, 1])
            with col1:
                if st.form_submit_button("← Voltar", disabled=self.etapa_configuracao == 0):
                    self.voltar_passo()
            with col2:
                if st.form_submit_button("Avançar →" if self.etapa_configuracao < 4 else "Concluir"):
                    self.avancar_passo()
            with col3:
                if st.form_submit_button("Cancelar"):
                    self.cancelar_configuracao()

        # Importar/Exportar configurações
        st.subheader("Gerenciar Configurações")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Exportar Configurações"):
                self.exportar_configuracoes()
        with col2:
            config_file = st.file_uploader("Importar Configurações", type=["json"])
            if config_file and st.button("Carregar Configuração"):
                self.importar_configuracoes(config_file)

        # Lista de atributos configurados
        st.subheader("Atributos Configurados")
        if self.atributos:
            data = []
            for nome, config in self.atributos.items():
                variacoes = ", ".join([v["descricao"] for v in config["variacoes"]])
                prioridade = config["variacoes"][0]["descricao"]
                formato = {"valor": "Valor", "texto": "Texto", "completo": "Completo"}[config["tipo_retorno"]]
                data.append([nome, variacoes, prioridade, formato])

            df_atributos = pd.DataFrame(data, columns=["Atributo", "Variações", "Prioridade", "Formato"])
            st.dataframe(df_atributos, use_container_width=True)

            # Gerenciamento de atributos
            col1, col2, col3 = st.columns(3)
            with col1:
                atributo_selecionado = st.selectbox("Selecionar Atributo para Editar", [""] + list(self.atributos.keys()))
                if st.button("Editar Selecionado") and atributo_selecionado:
                    self.editar_atributo(atributo_selecionado)
            with col2:
                if st.button("Remover Selecionado") and atributo_selecionado:
                    self.remover_atributo(atributo_selecionado)
            with col3:
                if st.button("Limpar Todos"):
                    self.limpar_atributos()

    def setup_aba_resultados(self):
        st.header("Resultados")

        if st.button("Extrair Atributos"):
            self.processar_dados()

        progress = st.progress(0)
        if "progress" in st.session_state:
            progress.progress(st.session_state["progress"])

        if not self.dados_processados.empty:
            st.dataframe(self.dados_processados, use_container_width=True)

            buffer = BytesIO()
            self.dados_processados.to_excel(buffer, index=False)
            buffer.seek(0)
            b64 = base64.b64encode(buffer.read()).decode()
            href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="resultados_extracao.xlsx">Download Resultados</a>'
            st.markdown(href, unsafe_allow_html=True)

    def avancar_passo(self):
        try:
            if self.etapa_configuracao == 0:
                nome = st.session_state.get("nome_atributo", "").strip()
                if not nome:
                    raise ValueError("Por favor, informe um nome para o atributo")
                self.atributo_atual = {"nome": nome}
                self.etapa_configuracao += 1

            elif self.etapa_configuracao == 1:
                var_text = st.session_state.get("variacoes", "").strip()
                if not var_text:
                    raise ValueError("Por favor, informe pelo menos uma variação")
                variacoes = [v.strip() for v in var_text.split("\n") if v.strip()]
                if not variacoes:
                    raise ValueError("Por favor, informe pelo menos uma variação válida")
                self.atributo_atual["variacoes"] = [{"descricao": v, "padroes": []} for v in variacoes]
                self.etapa_configuracao += 1

            elif self.etapa_configuracao == 2:
                for idx, variacao in enumerate(self.atributo_atual["variacoes"]):
                    padroes = st.session_state.get(f"padroes_{idx}", "").strip().split("\n")
                    padroes = [p.strip() for p in padroes if p.strip()]
                    if not padroes:
                        raise ValueError(f"Por favor, informe pelo menos um padrão para '{variacao['descricao']}'")
                    variacao["padroes"] = padroes
                self.etapa_configuracao += 1

            elif self.etapa_configuracao == 3:
                ordem_prioridade = st.session_state.get("ordem_prioridade", [v["descricao"] for v in self.atributo_atual["variacoes"]])
                variacoes_ordenadas = []
                for descricao in ordem_prioridade:
                    for variacao in self.atributo_atual["variacoes"]:
                        if variacao["descricao"] == descricao:
                            variacoes_ordenadas.append(variacao)
                            break
                self.atributo_atual["variacoes"] = variacoes_ordenadas
                self.etapa_configuracao += 1

            elif self.etapa_configuracao == 4:
                self.atributo_atual["tipo_retorno"] = st.session_state.get("tipo_retorno", "texto")
                self.atributos[self.atributo_atual["nome"]] = self.atributo_atual
                st.session_state["atributos"] = self.atributos
                self.etapa_configuracao = 0
                self.atributo_atual = {}
                st.session_state["etapa_configuracao"] = 0
                st.session_state["atributo_atual"] = {}
                st.success("Atributo configurado com sucesso!")

            st.session_state["etapa_configuracao"] = self.etapa_configuracao
            st.session_state["atributo_atual"] = self.atributo_atual
            st.experimental_rerun()

        except Exception as e:
            st.error(str(e))

    def voltar_passo(self):
        if self.etapa_configuracao > 0:
            self.etapa_configuracao -= 1
            st.session_state["etapa_configuracao"] = self.etapa_configuracao
            st.experimental_rerun()

    def cancelar_configuracao(self):
        self.etapa_configuracao = 0
        self.atributo_atual = {}
        st.session_state["etapa_configuracao"] = 0
        st.session_state["atributo_atual"] = {}
        st.info("Configuração cancelada")
        st.experimental_rerun()

    def editar_atributo(self, nome_atributo):
        self.atributo_atual = self.atributos[nome_atributo].copy()
        self.etapa_configuracao = 0
        st.session_state["atributo_atual"] = self.atributo_atual
        st.session_state["etapa_configuracao"] = 0
        st.experimental_rerun()

    def remover_atributo(self, nome_atributo):
        del self.atributos[nome_atributo]
        st.session_state["atributos"] = self.atributos
        st.experimental_rerun()

    def limpar_atributos(self):
        self.atributos = {}
        st.session_state["atributos"] = self.atributos
        st.experimental_rerun()

    def exportar_configuracoes(self):
        if not self.atributos:
            st.warning("Nenhuma configuração para exportar")
            return

        dados_export = {}
        for nome, config in self.atributos.items():
            dados_export[nome] = {
                "tipo_retorno": config["tipo_retorno"],
                "variacoes": [{"descricao": v["descricao"], "padroes": v["padroes"]} for v in config["variacoes"]]
            }

        buffer = BytesIO()
        buffer.write(json.dumps(dados_export, indent=4, ensure_ascii=False).encode("utf-8"))
        buffer.seek(0)

        b64 = base64.b64encode(buffer.read()).decode()
        href = f'<a href="data:application/json;base64,{b64}" download="config_atributos.json">Download Configurações</a>'
        st.markdown(href, unsafe_allow_html=True)
        st.session_state["status"] = "Configurações exportadas com sucesso!"
        st.success("Configurações exportadas com sucesso!")

    def importar_configuracoes(self, config_file):
        try:
            dados_import = json.load(config_file)
            if not isinstance(dados_import, dict):
                raise ValueError("Formato de arquivo inválido")

            self.atributos = {}
            for nome, config in dados_import.items():
                if not isinstance(config, dict) or "tipo_retorno" not in config or "variacoes" not in config:
                    continue

                self.atributos[nome] = {
                    "nome": nome,
                    "tipo_retorno": config["tipo_retorno"],
                    "variacoes": [{"descricao": v["descricao"], "padroes": v["padroes"]} for v in config["variacoes"]]
                }

            st.session_state["atributos"] = self.atributos
            st.session_state["status"] = "Configurações importadas com sucesso!"
            st.success("Configurações importadas com sucesso!")
            st.experimental_rerun()

        except json.JSONDecodeError as e:
            st.error(f"Arquivo JSON inválido:\n{str(e)}")
        except Exception as e:
            st.error(f"Falha ao importar configurações:\n{str(e)}")

    def processar_dados(self):
        if "dados_originais" not in st.session_state:
            st.warning("Por favor, carregue uma planilha primeiro")
            return

        if not self.atributos:
            st.warning("Por favor, configure pelo menos um atributo")
            return

        try:
            self.dados_processados = st.session_state["dados_originais"].copy()
            total_linhas = len(self.dados_processados)

            for idx, (atributo_nome, config) in enumerate(self.atributos.items()):
                tipo_retorno = config["tipo_retorno"]
                variacoes = config["variacoes"]

                regex_variacoes = []
                for variacao in variacoes:
                    padroes_escaped = [re.escape(p) for p in variacao["padroes"]]
                    regex = r'\b(' + '|'.join(padroes_escaped) + r')\b'
                    regex_variacoes.append((regex, variacao["descricao"]))

                self.dados_processados[atributo_nome] = ""

                for i, row in self.dados_processados.iterrows():
                    descricao = str(row["Descrição"]).lower()
                    resultado = None

                    for regex, desc_padrao in regex_variacoes:
                        match = re.search(regex, descricao, re.IGNORECASE)
                        if match:
                            resultado = self.formatar_resultado(
                                match.group(1),
                                tipo_retorno,
                                atributo_nome,
                                desc_padrao
                            )
                            break

                    self.dados_processados.at[i, atributo_nome] = resultado if resultado else ""
                    st.session_state["progress"] = (i + 1) / total_linhas
                    st.experimental_rerun()

            st.session_state["dados_processados"] = self.dados_processados
            st.session_state["status"] = "Processamento concluído com sucesso!"
            st.success("Atributos extraídos com sucesso!")
            st.experimental_rerun()

        except Exception as e:
            st.session_state["status"] = f"Erro durante o processamento: {str(e)}"
            st.error(f"Falha ao processar dados:\n{str(e)}")

    def formatar_resultado(self, valor_encontrado, tipo_retorno, nome_atributo, descricao_padrao):
        if tipo_retorno == "valor":
            numeros = re.findall(r'\d+', valor_encontrado)
            return numeros[0] if numeros else ""
        elif tipo_retorno == "texto":
            return descricao_padrao
        elif tipo_retorno == "completo":
            return f"{nome_atributo}: {descricao_padrao}"
        return valor_encontrado

if __name__ == "__main__":
    app = ExtratorAtributos()
