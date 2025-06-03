import pandas as pd
import re
import json
import streamlit as st
from io import BytesIO
import base64

class ExtratorAtributos:
    def __init__(self):
        st.set_page_config(page_title="Sistema de Extração de Atributos", layout="wide")
        self.inicializar_sessao()
        self.setup_ui()
    
    def inicializar_sessao(self):
        if 'dados_originais' not in st.session_state:
            st.session_state.dados_originais = None
        if 'dados_processados' not in st.session_state:
            st.session_state.dados_processados = None
        if 'atributos' not in st.session_state:
            st.session_state.atributos = {}
        if 'etapa_configuracao' not in st.session_state:
            st.session_state.etapa_configuracao = 0
        if 'atributo_atual' not in st.session_state:
            st.session_state.atributo_atual = {
                'nome': '',
                'variacoes': [],
                'tipo_retorno': 'texto'
            }
    
    def setup_ui(self):
        st.title("📋 Sistema de Extração de Atributos")
        
        tab1, tab2, tab3 = st.tabs(["📤 Upload", "⚙️ Configuração", "📊 Resultados"])
        
        with tab1:
            self.setup_aba_upload()
        with tab2:
            self.setup_aba_configuracao()
        with tab3:
            self.setup_aba_resultados()
    
    def setup_aba_configuracao(self):
        st.header("⚙️ Configuração de Atributos")
        
        # Instruções
        with st.expander("ℹ️ Instruções", expanded=True):
            st.markdown(self.get_instrucao_atual())
        
        # Configuração do atributo
        st.subheader("🔧 Configuração do Atributo")
        self.render_passo_atual()
        
        # Navegação
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("← Voltar", disabled=st.session_state.etapa_configuracao == 0):
                self.voltar_passo()
        with col2:
            btn_text = "Avançar →" if st.session_state.etapa_configuracao < 4 else "✅ Concluir"
            if st.button(btn_text):
                self.avancar_passo()
        with col3:
            if st.button("❌ Cancelar"):
                self.cancelar_configuracao()
        
        # Gerenciamento de configurações
        st.subheader("🔄 Gerenciamento de Configurações")
        col_exp, col_imp = st.columns(2)
        with col_exp:
            if st.button("📤 Exportar Configurações"):
                self.exportar_configuracoes()
        with col_imp:
            arquivo_config = st.file_uploader("📥 Importar Configurações", type=["json"])
            if arquivo_config:
                self.importar_configuracoes(arquivo_config)
        
        # Lista de atributos configurados
        st.subheader("📋 Atributos Configurados")
        if st.session_state.atributos:
            self.mostrar_atributos_configurados()
        else:
            st.info("ℹ️ Nenhum atributo configurado ainda.")
    
    def get_instrucao_atual(self):
        instrucoes = [
            "1️⃣ **Nome do Atributo**: Digite o nome que será usado como cabeçalho na planilha de resultados (ex: 'Voltagem')",
            "2️⃣ **Variações**: Adicione as diferentes versões deste atributo (uma por linha). Exemplo para Voltagem:\n- 110V\n- 220V\n- Bivolt",
            "3️⃣ **Padrões de Reconhecimento**: Para cada variação, defina os textos que o sistema deve buscar na descrição do produto",
            "4️⃣ **Ordem de Prioridade**: Defina qual variação deve ser considerada primeiro quando houver múltiplas correspondências",
            "5️⃣ **Formato de Saída**: Escolha como o resultado será exibido:\n- **Valor**: Apenas o valor (ex: '110')\n- **Texto**: O texto padrão (ex: '110V')\n- **Completo**: Atributo + valor (ex: 'Voltagem: 110V')"
        ]
        return instrucoes[st.session_state.etapa_configuracao]
    
    def render_passo_atual(self):
        if st.session_state.etapa_configuracao == 0:
            self.render_passo_nome()
        elif st.session_state.etapa_configuracao == 1:
            self.render_passo_variacoes()
        elif st.session_state.etapa_configuracao == 2:
            self.render_passo_padroes()
        elif st.session_state.etapa_configuracao == 3:
            self.render_passo_prioridade()
        else:
            self.render_passo_formato()
    
    def render_passo_nome(self):
        st.session_state.atributo_atual['nome'] = st.text_input(
            "Nome do Atributo:", 
            value=st.session_state.atributo_atual['nome'],
            placeholder="Ex: Voltagem, Cor, Material",
            key="nome_atributo"
        )
    
    def render_passo_variacoes(self):
        # Se não tem variações ainda, inicializa
        if not st.session_state.atributo_atual['variacoes']:
            st.session_state.atributo_atual['variacoes'] = []
        
        # Mostra textarea para edição
        variacoes_texto = "\n".join([v['descricao'] for v in st.session_state.atributo_atual['variacoes']])
        novas_variações = st.text_area(
            "Variações (uma por linha):",
            value=variacoes_texto,
            height=150,
            placeholder="Exemplo para Voltagem:\n110V\n220V\nBivolt",
            key="variações_input"
        )
        
        # Atualiza as variações
        if novas_variações:
            st.session_state.atributo_atual['variacoes'] = [
                {'descricao': v.strip(), 'padroes': []} 
                for v in novas_variações.split('\n') if v.strip()
            ]
    
    def render_passo_padroes(self):
        if not st.session_state.atributo_atual['variacoes']:
            st.warning("Defina as variações primeiro")
            return
        
        tabs = st.tabs([v['descricao'] for v in st.session_state.atributo_atual['variacoes']])
        
        for i, variacao in enumerate(st.session_state.atributo_atual['variacoes']):
            with tabs[i]:
                padroes_texto = "\n".join(variacao.get('padroes', []))
                novos_padroes = st.text_area(
                    f"Padrões para '{variacao['descricao']}':",
                    value=padroes_texto,
                    height=100,
                    placeholder=f"Exemplo para {variacao['descricao']}:\n110v\n110 volts\n110",
                    key=f"padroes_{i}"
                )
                
                if novos_padroes:
                    variacao['padroes'] = [p.strip() for p in novos_padroes.split('\n') if p.strip()]
    
    def render_passo_prioridade(self):
        if not st.session_state.atributo_atual['variacoes']:
            st.warning("Defina as variações primeiro")
            return
        
        st.info("Arraste para ordenar (o primeiro tem maior prioridade)")
        
        # Implementação simplificada de ordenação
        variacoes = st.session_state.atributo_atual['variacoes']
        
        # Mostra cada variação em um selectbox para simular ordenação
        ordem = []
        for i in range(len(variacoes)):
            opcoes = [f"{j+1}. {v['descricao']}" for j, v in enumerate(variacoes) if j not in ordem]
            selecionado = st.selectbox(f"Posição {i+1}", opcoes, key=f"prioridade_{i}")
            idx_selecionado = [f"{j+1}. {v['descricao']}" for j, v in enumerate(variacoes)].index(selecionado)
            ordem.append(idx_selecionado)
        
        # Aplica nova ordem
        st.session_state.atributo_atual['variacoes'] = [variacoes[i] for i in ordem]
    
    def render_passo_formato(self):
        st.session_state.atributo_atual['tipo_retorno'] = st.radio(
            "Formato de retorno:",
            options=["valor", "texto", "completo"],
            index=["valor", "texto", "completo"].index(st.session_state.atributo_atual.get('tipo_retorno', 'texto')),
            format_func=lambda x: {
                'valor': 'Valor (ex: "110")',
                'texto': 'Texto Padrão (ex: "110V")',
                'completo': 'Descrição Completa (ex: "Voltagem: 110V")'
            }[x],
            key="formato_retorno"
        )
    
    def avancar_passo(self):
        try:
            # Validação antes de avançar
            if st.session_state.etapa_configuracao == 0:
                if not st.session_state.atributo_atual['nome'].strip():
                    raise ValueError("Informe um nome para o atributo")
            elif st.session_state.etapa_configuracao == 1:
                if not st.session_state.atributo_atual['variacoes']:
                    raise ValueError("Informe pelo menos uma variação")
            elif st.session_state.etapa_configuracao == 2:
                for v in st.session_state.atributo_atual['variacoes']:
                    if not v['padroes']:
                        raise ValueError(f"Informe padrões para '{v['descricao']}'")
            
            # Avança ou finaliza
            if st.session_state.etapa_configuracao < 4:
                st.session_state.etapa_configuracao += 1
            else:
                self.finalizar_configuracao()
            
            st.rerun()
        
        except Exception as e:
            st.error(f"Erro: {str(e)}")
    
    def finalizar_configuracao(self):
        # Salva o atributo
        nome = st.session_state.atributo_atual['nome']
        st.session_state.atributos[nome] = {
            'tipo_retorno': st.session_state.atributo_atual['tipo_retorno'],
            'variacoes': st.session_state.atributo_atual['variacoes']
        }
        
        # Reseta para novo atributo
        st.session_state.etapa_configuracao = 0
        st.session_state.atributo_atual = {
            'nome': '',
            'variacoes': [],
            'tipo_retorno': 'texto'
        }
        
        st.success(f"Atributo '{nome}' configurado com sucesso!")
        st.rerun()
    
    def voltar_passo(self):
        if st.session_state.etapa_configuracao > 0:
            st.session_state.etapa_configuracao -= 1
            st.rerun()
    
    def cancelar_configuracao(self):
        st.session_state.etapa_configuracao = 0
        st.session_state.atributo_atual = {
            'nome': '',
            'variacoes': [],
            'tipo_retorno': 'texto'
        }
        st.info("Configuração cancelada")
        st.rerun()
    
    def mostrar_atributos_configurados(self):
        df = pd.DataFrame([
            {
                'Atributo': nome,
                'Variações': len(config['variacoes']),
                'Padrões': sum(len(v['padroes']) for v in config['variacoes']),
                'Formato': config['tipo_retorno']
            }
            for nome, config in st.session_state.atributos.items()
        ])
        
        st.dataframe(df, use_container_width=True)
        
        # Controles de edição/remoção
        col1, col2 = st.columns(2)
        with col1:
            atributo_editar = st.selectbox(
                "Selecionar para editar",
                list(st.session_state.atributos.keys()),
                key="seletor_edicao"
            )
            if st.button("✏️ Editar"):
                self.editar_atributo(atributo_editar)
        with col2:
            atributo_remover = st.selectbox(
                "Selecionar para remover",
                list(st.session_state.atributos.keys()),
                key="seletor_remocao"
            )
            if st.button("🗑️ Remover"):
                self.remover_atributo(atributo_remover)
    
    def editar_atributo(self, nome):
        if nome in st.session_state.atributos:
            st.session_state.atributo_atual = {
                'nome': nome,
                'tipo_retorno': st.session_state.atributos[nome]['tipo_retorno'],
                'variacoes': st.session_state.atributos[nome]['variacoes']
            }
            st.session_state.etapa_configuracao = 0
            st.rerun()
    
    def remover_atributo(self, nome):
        if nome in st.session_state.atributos:
            del st.session_state.atributos[nome]
            st.success(f"Atributo '{nome}' removido!")
            st.rerun()

    # ... (outros métodos permanecem iguais) ...

if __name__ == "__main__":
    extrator = ExtratorAtributos()
