import streamlit as st
import pdfplumber
import pandas as pd
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(
    page_title="Service Checklist",
    page_icon="✅",
    layout="centered", # 'Centered' fica melhor em mobile que 'Wide'
    initial_sidebar_state="collapsed"
)

# --- CSS Personalizado para Tema Dark Moderno ---
st.markdown("""
<style>
    /* Ajuste de fundo e cores de texto */
    .stApp {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    
    /* Estilo dos Cards (Expanders) */
    .streamlit-expanderHeader {
        background-color: #262730;
        border-radius: 10px;
        color: #ffffff;
        font-weight: 500;
        border: 1px solid #41444C;
    }
    
    /* Destaque para itens concluídos */
    .concluido-card {
        border-left: 5px solid #00FF7F !important;
    }
    
    /* Botões */
    .stButton>button {
        width: 100%;
        border-radius: 20px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- Funções ---
def extrair_chamados_do_pdf(uploaded_file):
    chamados_lista = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    # Filtra linhas vazias e muito curtas
                    linhas = [line.strip() for line in text.split('\n') if len(line.strip()) > 3]
                    chamados_lista.extend(linhas)
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
    return chamados_lista

# --- Inicialização de Estado ---
if 'dados_checklist' not in st.session_state:
    st.session_state.dados_checklist = []

# --- Interface Principal ---
def main():
    st.title("🚀 Field Service")
    st.caption("Gerenciador de Chamados Mobile")

    # Área de Upload (Só aparece se a lista estiver vazia para economizar espaço)
    if not st.session_state.dados_checklist:
        uploaded_file = st.file_uploader("📂 Carregar PDF da Rota", type="pdf")
        
        if uploaded_file is not None:
            with st.spinner('Processando rota...'):
                lista_bruta = extrair_chamados_do_pdf(uploaded_file)
                
                # Inicializa a estrutura
                st.session_state.dados_checklist = []
                for item in lista_bruta:
                    st.session_state.dados_checklist.append({
                        "descricao": item,
                        "concluido": False,
                        "chegada": None,
                        "saida": None,
                        "status": "Aberto",
                        "obs": ""
                    })
            st.rerun()

    # Botão de Reset (caso precise carregar outro arquivo)
    else:
        if st.sidebar.button("🔄 Nova Lista / Limpar"):
            st.session_state.dados_checklist = []
            st.rerun()

    # --- Renderização da Lista (Estilo Mobile) ---
    if st.session_state.dados_checklist:
        
        # Barra de progresso
        total = len(st.session_state.dados_checklist)
        concluidos = sum(1 for c in st.session_state.dados_checklist if c['concluido'])
        progresso = concluidos / total if total > 0 else 0
        st.progress(progresso)
        st.caption(f"Progresso: {concluidos}/{total} chamados")

        st.markdown("---")

        for i, chamado in enumerate(st.session_state.dados_checklist):
            # Define ícone e cor baseados no status
            icon = "✅" if chamado['concluido'] else "📍"
            titulo = f"{icon} {chamado['descricao'][:30]}..." # Corta texto longo no título
            
            # O Expander funciona como um "Card" que abre e fecha
            with st.expander(titulo, expanded=not chamado['concluido']):
                st.markdown(f"**Detalhe:** {chamado['descricao']}")
                
                c1, c2 = st.columns(2)
                
                # Inputs de Hora
                novo_chegada = c1.time_input("Chegada", value=chamado['chegada'], key=f"in_{i}")
                novo_saida = c2.time_input("Saída", value=chamado['saida'], key=f"out_{i}")
                
                # Status
                opcoes_status = ["Aberto", "Pendente", "Concluído"]
                idx_status = opcoes_status.index(chamado['status']) if chamado['status'] in opcoes_status else 0
                novo_status = st.selectbox("Status", options=opcoes_status, index=idx_status, key=f"st_{i}")
                
                # Checkbox de conclusão final
                novo_concluido = st.checkbox("Finalizar Chamado", value=chamado['concluido'], key=f"chk_{i}")

                # Atualização do Estado
                st.session_state.dados_checklist[i]['chegada'] = novo_chegada
                st.session_state.dados_checklist[i]['saida'] = novo_saida
                st.session_state.dados_checklist[i]['status'] = novo_status
                st.session_state.dados_checklist[i]['concluido'] = novo_concluido

                # Lógica automática: Se marcar finalizado, muda status para Concluído
                if novo_concluido and chamado['status'] != "Concluído":
                    st.session_state.dados_checklist[i]['status'] = "Concluído"
                    st.rerun()

        st.markdown("---")
        
        # Exportação
        if st.button("📥 Baixar Relatório Final"):
            df = pd.DataFrame(st.session_state.dados_checklist)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Clique para Download",
                data=csv,
                file_name=f"relatorio_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

if __name__ == "__main__":
    main()
