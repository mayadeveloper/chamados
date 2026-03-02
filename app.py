import streamlit as st
import pdfplumber
import pandas as pd
from datetime import datetime
import re
import sqlite3
import hashlib

# --- Configuração da Página ---
st.set_page_config(
    page_title="Service Checklist",
    page_icon="✅",
    layout="centered", # 'Centered' fica melhor em mobile que 'Wide'
    initial_sidebar_state="collapsed"
)

# --- CSS Personalizado para Tema Dark Moderno ---
st.markdown(""" """)
# --- Função de Estilo (Tema) ---
def aplicar_estilo():
    tema = st.session_state.get('theme', 'dark')
    
    if tema == 'dark':
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
    else:
        st.markdown("""
        <style>
            /* Forçar Tema Claro (Light Mode) */
            .stApp {
                background-color: #FFFFFF !important;
                color: #31333F !important;
            }
            
            /* Estilo dos Cards (Expanders) */
            .streamlit-expanderHeader {
                background-color: #F0F2F6 !important;
                border-radius: 10px;
                color: #31333F !important;
                font-weight: 500;
                border: 1px solid #E6E9EF !important;
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
                background-color: #FFFFFF;
                color: #31333F;
                border: 1px solid #d3d3d3;
            }
        </style>
        """, unsafe_allow_html=True)

# --- Funções ---

# --- Funções de Banco de Dados (SQLite) ---
def init_db():
    """Cria a tabela se não existir."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    
    # Tabela de Usuários
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            theme TEXT DEFAULT 'dark'
        )
    ''')

    # Tabela de Configurações (Logo)
    c.execute('''
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value BLOB
        )
    ''')

    # Tabela de Chamados (com tecnico_id)
    c.execute('''
        CREATE TABLE IF NOT EXISTS chamados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tecnico_id INTEGER,
            os TEXT,
            cliente TEXT,
            endereco TEXT,
            numero TEXT,
            motivo TEXT,
            bairro TEXT,
            cidade TEXT,
            equipamento TEXT,
            modelo TEXT,
            marca TEXT,
            serial TEXT,
            chegada TEXT,
            saida TEXT,
            status TEXT,
            obs TEXT,
            concluido INTEGER,
            data_registro TEXT
        )
    ''')

    # Tabela de Diário de Bordo (Jornada e Veículo)
    c.execute('''
        CREATE TABLE IF NOT EXISTS diario_bordo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tecnico_id INTEGER,
            data TEXT,
            hora_inicio TEXT,
            hora_fim TEXT,
            km_inicial TEXT,
            km_final TEXT,
            placa TEXT,
            UNIQUE(tecnico_id, data)
        )
    ''')
    
    # Migração: Adiciona colunas que podem faltar em bancos de dados antigos.
    # Isso garante que o app não quebre para quem já tinha uma versão anterior.
    colunas_para_migrar = [
        ("tecnico_id", "INTEGER"),
        ("numero", "TEXT"),
        ("bairro", "TEXT"),
        ("cidade", "TEXT"),
        ("equipamento", "TEXT"),
        ("modelo", "TEXT"),
        ("marca", "TEXT"),
        ("serial", "TEXT"),
    ]

    for coluna, tipo in colunas_para_migrar:
        try:
            # Usando f-string aqui é seguro pois os nomes das colunas e tipos
            # são definidos internamente e não vêm de input do usuário.
            c.execute(f"ALTER TABLE chamados ADD COLUMN {coluna} {tipo}")
        except sqlite3.OperationalError:
            pass # Coluna já existe

    # Migração para tabela users (tema)
    try:
        c.execute("ALTER TABLE users ADD COLUMN theme TEXT DEFAULT 'dark'")
    except sqlite3.OperationalError:
        pass

    # Cria usuário Admin padrão se não existir
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                  ('admin', senha_hash, 'admin'))

    conn.commit()
    conn.close()

def db_criar_usuario(username, password, role):
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    senha_hash = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, senha_hash, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def db_verificar_login(username, password):
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    senha_hash = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT id, username, role, theme FROM users WHERE username = ? AND password = ?", (username, senha_hash))
    user = c.fetchone()
    conn.close()
    return user

def db_listar_usuarios():
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute("SELECT username, role FROM users")
    users = c.fetchall()
    conn.close()
    return users

def db_atualizar_tema(user_id, novo_tema):
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute("UPDATE users SET theme = ? WHERE id = ?", (novo_tema, user_id))
    conn.commit()
    conn.close()

def db_salvar_chamados(lista_chamados, user_id):
    """Salva uma nova lista de chamados no banco."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    for item in lista_chamados:
        c.execute('''
            INSERT INTO chamados (
                tecnico_id, os, cliente, endereco, numero, motivo, 
                bairro, cidade, equipamento, modelo, marca, serial, 
                chegada, saida, status, obs, concluido, data_registro
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            item['os'], item['cliente'], item['endereco'], item.get('numero'),
            item['motivo'],
            item.get('bairro'), item.get('cidade'), item.get('equipamento'),
            item.get('modelo'), item.get('marca'), item.get('serial'),
            None, None, "Aberto", "", 0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
    conn.commit()
    conn.close()

def db_atualizar_campo(id_chamado, campo, valor):
    """Atualiza um campo específico de um chamado."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    
    # Conversão de tipos para salvar no SQLite
    if isinstance(valor, bool):
        valor = 1 if valor else 0
    elif hasattr(valor, 'strftime'): # Se for objeto de tempo
        valor = valor.strftime("%H:%M")
    
    query = f"UPDATE chamados SET {campo} = ? WHERE id = ?"
    c.execute(query, (valor, id_chamado))
    conn.commit()
    conn.close()

def db_carregar_chamados(user_id=None, admin_view=False):
    """
    Carrega chamados. 
    Se admin_view=True, carrega de todos. 
    Se não, carrega apenas do user_id.
    """
    conn = sqlite3.connect('chamados.db')
    conn.row_factory = sqlite3.Row # Permite acessar colunas pelo nome
    c = conn.cursor()
    
    if admin_view:
        # Admin vê tudo e traz o nome do técnico junto (join simples ou apenas o ID por enquanto)
        c.execute("SELECT c.*, u.username as tecnico_nome FROM chamados c LEFT JOIN users u ON c.tecnico_id = u.id")
    else:
        c.execute("SELECT * FROM chamados WHERE tecnico_id = ?", (user_id,))
        
    rows = c.fetchall()
    conn.close()
    
    lista = []
    for row in rows:
        d = dict(row)
        # Converter tipos de volta (SQLite devolve tudo como texto/int)
        d['concluido'] = bool(d['concluido'])
        if d['chegada']:
            try: d['chegada'] = datetime.strptime(d['chegada'], "%H:%M").time()
            except: d['chegada'] = None
        if d['saida']:
            try: d['saida'] = datetime.strptime(d['saida'], "%H:%M").time()
            except: d['saida'] = None
        lista.append(d)
    return lista

def db_excluir_chamado(id_chamado):
    """Exclui um chamado específico pelo ID."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute("DELETE FROM chamados WHERE id = ?", (id_chamado,))
    conn.commit()
    conn.close()

def db_limpar_rota_usuario(user_id):
    """Limpa o banco de dados para começar nova lista."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute("DELETE FROM chamados WHERE tecnico_id = ?", (user_id,))
    conn.commit()
    conn.close()

def db_criar_chamado_manual(tecnico_id, dados_os):
    """Cria um chamado manual no banco."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO chamados (
            tecnico_id, os, cliente, endereco, numero, motivo, 
            bairro, cidade, equipamento, modelo, marca, serial, 
            chegada, saida, status, obs, concluido, data_registro
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        tecnico_id,
        dados_os.get('os'), dados_os.get('cliente'), dados_os.get('endereco'), dados_os.get('numero'),
        dados_os.get('motivo'), dados_os.get('bairro'), dados_os.get('cidade'),
        dados_os.get('equipamento'), dados_os.get('modelo'), dados_os.get('marca'), dados_os.get('serial'),
        None, None, "Aberto", "", 0,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

def db_salvar_diario(tecnico_id, data, campo, valor):
    """Salva dados do diário de bordo."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    # Garante que o registro do dia existe
    c.execute("INSERT OR IGNORE INTO diario_bordo (tecnico_id, data) VALUES (?, ?)", (tecnico_id, data))
    # Atualiza o campo específico
    query = f"UPDATE diario_bordo SET {campo} = ? WHERE tecnico_id = ? AND data = ?"
    c.execute(query, (valor, tecnico_id, data))
    conn.commit()
    conn.close()

def db_carregar_diario(tecnico_id, data):
    """Carrega dados do diário de bordo."""
    conn = sqlite3.connect('chamados.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM diario_bordo WHERE tecnico_id = ? AND data = ?", (tecnico_id, data))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else {}

def db_salvar_logo(image_bytes):
    """Salva a logo no banco de dados."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ('logo', image_bytes))
    conn.commit()
    conn.close()

def db_carregar_logo():
    """Carrega a logo do banco de dados."""
    conn = sqlite3.connect('chamados.db')
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key = 'logo'")
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def exibir_cabecalho():
    """Exibe a logo no topo da página se existir."""
    logo = db_carregar_logo()
    if logo:
        c1, c2, c3 = st.columns([1, 1, 1])
        with c2:
            st.image(logo, use_container_width=True)

def extrair_chamados_do_pdf(uploaded_file):
    chamados_lista = []
    try:
        with pdfplumber.open(uploaded_file) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
            
            # Processamento linha a linha para capturar campos específicos
            lines = full_text.split('\n')
            dados_temp = {}
            
            for line in lines:
                line = line.strip()
                
                # 1. Procura o Cód. O.S. (Gatilho para iniciar um novo item)
                match_os = re.search(r"Cód\. O\.S\.\s*(\d+)", line, re.IGNORECASE)
                if match_os:
                    # Se já existia uma OS sendo montada, salva ela antes de começar a nova
                    if dados_temp.get("os"):
                        chamados_lista.append({
                            "os": dados_temp.get("os"),
                            "cliente": dados_temp.get("para", "Não identificado"),
                            "endereco": dados_temp.get("endereco", "Não identificado"),
                            "numero": dados_temp.get("numero", "Não identificado"),
                            "motivo": dados_temp.get("motivo", "Não identificado"),
                            "bairro": dados_temp.get("bairro", "Não identificado"),
                            "cidade": dados_temp.get("cidade", "Não identificado"),
                            "equipamento": dados_temp.get("equipamento", "Não identificado"),
                            "modelo": dados_temp.get("modelo", "Não identificado"),
                            "marca": dados_temp.get("marca", "Não identificado"),
                            "serial": dados_temp.get("serial", "Não identificado"),
                        })
                        dados_temp = {} # Limpa para a próxima
                    
                    dados_temp["os"] = match_os.group(1)
                
                # 2. Captura os outros campos se já tivermos uma OS aberta
                if dados_temp.get("os"):
                    if "Para" in line:
                        dados_temp["para"] = re.sub(r"^Para\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Endereço" in line:
                        dados_temp["endereco"] = re.sub(r"^Endereço\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Número" in line:
                        dados_temp["numero"] = re.sub(r"^Número\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Motivo" in line:
                        dados_temp["motivo"] = re.sub(r"^Motivo\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Bairro" in line:
                        dados_temp["bairro"] = re.sub(r"^Bairro\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Cidade" in line:
                        dados_temp["cidade"] = re.sub(r"^Cidade\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Equipamento" in line:
                        dados_temp["equipamento"] = re.sub(r"^Equipamento\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Modelo" in line:
                        dados_temp["modelo"] = re.sub(r"^Modelo\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Marca" in line:
                        dados_temp["marca"] = re.sub(r"^Marca\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
                    elif "Serial" in line:
                        dados_temp["serial"] = re.sub(r"^Serial\s*[:.]?\s*", "", line, flags=re.IGNORECASE).strip()
            
            # Adiciona o último item processado (pois o loop acaba)
            if dados_temp.get("os"):
                chamados_lista.append({
                    "os": dados_temp.get("os"),
                    "cliente": dados_temp.get("para", "Não identificado"),
                    "endereco": dados_temp.get("endereco", "Não identificado"),
                    "numero": dados_temp.get("numero", "Não identificado"),
                    "motivo": dados_temp.get("motivo", "Não identificado"),
                    "bairro": dados_temp.get("bairro", "Não identificado"),
                    "cidade": dados_temp.get("cidade", "Não identificado"),
                    "equipamento": dados_temp.get("equipamento", "Não identificado"),
                    "modelo": dados_temp.get("modelo", "Não identificado"),
                    "marca": dados_temp.get("marca", "Não identificado"),
                    "serial": dados_temp.get("serial", "Não identificado"),
                })
                
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
    return chamados_lista

# --- Inicialização de Estado ---
# Inicializa o banco de dados
init_db()

# --- Telas do Sistema ---

def tela_login():
    exibir_cabecalho()
    st.markdown("<h1 style='text-align: center;'>🔐 Acesso ao Sistema</h1>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        
        if st.button("Entrar"):
            user = db_verificar_login(username, password)
            if user:
                st.session_state['logged_in'] = True
                st.session_state['user_id'] = user[0]
                st.session_state['username'] = user[1]
                st.session_state['role'] = user[2]
                st.session_state['theme'] = user[3] if user[3] else 'dark'
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos")

def tela_admin():
    exibir_cabecalho()
    st.title(f"Painel Gerencial - Olá, {st.session_state['username']}")
    
    # Seletor de Tema na Sidebar
    with st.sidebar:
        st.divider()
        st.write("🎨 **Aparência**")
        tema_atual = st.session_state.get('theme', 'dark')
        novo_tema = st.selectbox("Tema", ["dark", "light"], index=0 if tema_atual == 'dark' else 1, key="theme_admin")
        
        if novo_tema != tema_atual:
            db_atualizar_tema(st.session_state['user_id'], novo_tema)
            st.session_state['theme'] = novo_tema
            st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["📊 Visão Geral das OS", "👥 Gerenciar Técnicos", "⚙️ Configurações"])
    
    with tab1:
        st.subheader("Todas as Ordens de Serviço")
        
        # --- Sugestão 1: Filtro de Busca ---
        filtro = st.text_input("🔍 Buscar por OS, Cliente ou Técnico", placeholder="Digite para filtrar...")
        
        todos_chamados = db_carregar_chamados(admin_view=True)
        
        # Aplica o filtro se algo foi digitado
        if filtro and todos_chamados:
            filtro = filtro.lower()
            todos_chamados = [c for c in todos_chamados if filtro in str(c['os']).lower() or filtro in str(c['cliente']).lower() or filtro in str(c['tecnico_nome']).lower()]

        if todos_chamados:
            df = pd.DataFrame(todos_chamados)
            
            # Métricas
            total = len(df)
            concluidos = len(df[df['concluido'] == True])
            pendentes = total - concluidos
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total de OS", total)
            c2.metric("Concluídas", concluidos)
            c3.metric("Pendentes", pendentes)
            
            with st.expander("🗑️ Gerenciar / Excluir Chamados"):
                st.warning("Atenção: A exclusão é permanente.")
                for item in todos_chamados:
                    c_os, c_cli, c_tec, c_btn = st.columns([1.5, 3, 1.5, 1])
                    c_os.text(f"OS: {item['os']}")
                    c_cli.text(f"{item['cliente'][:30]}")
                    c_tec.text(f"Téc: {item['tecnico_nome']}")
                    if c_btn.button("Excluir", key=f"del_{item['id']}"):
                        db_excluir_chamado(item['id'])
                        st.rerun()

            st.dataframe(
                df[['tecnico_nome', 'os', 'cliente', 'status', 'chegada', 'saida', 'concluido']],
                use_container_width=True
            )
            
            if st.button("Atualizar Dados"):
                st.rerun()
        else:
            st.info("Nenhuma OS registrada no sistema.")

    with tab2:
        st.subheader("Cadastrar Novo Técnico")
        with st.form("novo_user"):
            new_user = st.text_input("Nome de Usuário")
            new_pass = st.text_input("Senha", type="password")
            new_role = st.selectbox("Função", ["tecnico", "admin"])
            if st.form_submit_button("Cadastrar"):
                if db_criar_usuario(new_user, new_pass, new_role):
                    st.success(f"Usuário {new_user} criado com sucesso!")
                else:
                    st.error("Erro: Usuário já existe.")
        
        st.divider()
        st.subheader("Usuários Existentes")
        users = db_listar_usuarios()
        for u in users:
            st.text(f"👤 {u[0]} - {u[1].upper()}")

    with tab3:
        st.subheader("Personalização do Sistema")
        st.write("Faça upload da logo da sua empresa para aparecer no topo de todas as telas.")
        uploaded_logo = st.file_uploader("Escolher Logo", type=['png', 'jpg', 'jpeg'])
        if uploaded_logo:
            if st.button("Salvar Logo"):
                db_salvar_logo(uploaded_logo.getvalue())
                st.success("Logo atualizada com sucesso!")
                st.rerun()
        
        # --- Sugestão 2: Botão de Backup ---
        st.divider()
        st.subheader("📦 Backup do Sistema")
        st.write("Baixe uma cópia de segurança do banco de dados regularmente.")
        try:
            with open("chamados.db", "rb") as f:
                st.download_button("📥 Baixar Backup (chamados.db)", f, file_name=f"backup_chamados_{datetime.now().strftime('%Y%m%d')}.db")
        except FileNotFoundError:
            st.warning("Banco de dados ainda não criado.")

def tela_tecnico():
    # Carrega dados específicos do usuário logado
    if 'dados_checklist' not in st.session_state or not st.session_state.dados_checklist:
        st.session_state.dados_checklist = db_carregar_chamados(user_id=st.session_state['user_id'])

    exibir_cabecalho()
    st.title(f"Bem-vindo {st.session_state['username']}")
    
    # --- Controle de Jornada e Veículo ---
    st.markdown("### 🚗 Controle de Jornada")
    data_hoje = datetime.now().strftime("%Y-%m-%d")
    diario = db_carregar_diario(st.session_state['user_id'], data_hoje)
    
    c1, c2, c3 = st.columns(3)
    placa = c1.text_input("Placa do Veículo", value=diario.get('placa', ''), key="placa")
    km_ini = c2.text_input("KM Inicial", value=diario.get('km_inicial', ''), key="km_ini")
    km_fim = c3.text_input("KM Final", value=diario.get('km_final', ''), key="km_fim")
    
    c4, c5 = st.columns(2)
    
    # Hora Início
    val_h_ini = diario.get('hora_inicio')
    t_ini = datetime.strptime(val_h_ini, "%H:%M").time() if val_h_ini else None
    h_ini = c4.time_input("Hora Início", value=t_ini, key="h_ini")
    
    # Hora Fim
    val_h_fim = diario.get('hora_fim')
    t_fim = datetime.strptime(val_h_fim, "%H:%M").time() if val_h_fim else None
    h_fim = c5.time_input("Hora Fim (Chegada)", value=t_fim, key="h_fim")
    
    # Salvar alterações automaticamente
    if placa != diario.get('placa', ''): db_salvar_diario(st.session_state['user_id'], data_hoje, 'placa', placa)
    if km_ini != diario.get('km_inicial', ''): db_salvar_diario(st.session_state['user_id'], data_hoje, 'km_inicial', km_ini)
    if km_fim != diario.get('km_final', ''): db_salvar_diario(st.session_state['user_id'], data_hoje, 'km_final', km_fim)
    
    str_h_ini = h_ini.strftime("%H:%M") if h_ini else None
    if str_h_ini != val_h_ini: db_salvar_diario(st.session_state['user_id'], data_hoje, 'hora_inicio', str_h_ini)
    
    str_h_fim = h_fim.strftime("%H:%M") if h_fim else None
    if str_h_fim != val_h_fim: db_salvar_diario(st.session_state['user_id'], data_hoje, 'hora_fim', str_h_fim)
    
    st.markdown("---")
    with st.expander("➕ Adicionar OS Manual"):
        with st.form("form_manual_os", clear_on_submit=True):
            st.write("Preencha os dados do novo chamado:")
            
            # Use columns for better layout
            col1, col2 = st.columns(2)
            os_manual = col1.text_input("Nº da OS*")
            cliente_manual = col2.text_input("Cliente*")
            
            endereco_manual = st.text_input("Endereço")
            
            col3, col4, col5 = st.columns(3)
            numero_manual = col3.text_input("Número")
            bairro_manual = col4.text_input("Bairro")
            cidade_manual = col5.text_input("Cidade")
            
            motivo_manual = st.text_area("Motivo")
            
            st.write("Detalhes do Equipamento (Opcional)")
            col6, col7 = st.columns(2)
            equip_manual = col6.text_input("Equipamento")
            marca_manual = col7.text_input("Marca")
            
            col8, col9 = st.columns(2)
            modelo_manual = col8.text_input("Modelo")
            serial_manual = col9.text_input("Serial")
            
            submitted = st.form_submit_button("Salvar Chamado")
            
            if submitted:
                if not os_manual or not cliente_manual:
                    st.warning("Nº da OS e Cliente são obrigatórios.")
                else:
                    dados_novos = { "os": os_manual, "cliente": cliente_manual, "endereco": endereco_manual, "numero": numero_manual, "bairro": bairro_manual, "cidade": cidade_manual, "motivo": motivo_manual, "equipamento": equip_manual, "marca": marca_manual, "modelo": modelo_manual, "serial": serial_manual }
                    db_criar_chamado_manual(st.session_state['user_id'], dados_novos)
                    st.success(f"OS {os_manual} adicionada com sucesso!")
                    if 'dados_checklist' in st.session_state: del st.session_state['dados_checklist']
                    st.rerun()

    # Sidebar com Logout e Reset
    with st.sidebar:
        st.write(f"Logado como: **{st.session_state['username']}**")
        if st.button("Sair / Logout"):
            st.session_state.clear()
            st.rerun()
            
        st.write("🎨 **Aparência**")
        tema_atual = st.session_state.get('theme', 'dark')
        novo_tema = st.selectbox("Tema", ["dark", "light"], index=0 if tema_atual == 'dark' else 1, key="theme_tecnico")
        if novo_tema != tema_atual:
            db_atualizar_tema(st.session_state['user_id'], novo_tema)
            st.session_state['theme'] = novo_tema
            st.rerun()
        st.divider()
        
        # Botão de Reset (apenas para a rota deste usuário)
        if st.session_state.dados_checklist:
            if st.button("🔄 Nova Lista / Limpar"):
                db_limpar_rota_usuario(st.session_state['user_id'])
                st.session_state.dados_checklist = []
                st.rerun()

    # Área de Upload
    if not st.session_state.dados_checklist:
        uploaded_file = st.file_uploader("📂 Carregar PDF da Rota", type="pdf")
        
        if uploaded_file is not None:
            with st.spinner('Processando rota...'):
                lista_bruta = extrair_chamados_do_pdf(uploaded_file)
                # Salva no banco vinculado ao usuário
                db_salvar_chamados(lista_bruta, st.session_state['user_id'])
                # Recarrega
                st.session_state.dados_checklist = db_carregar_chamados(user_id=st.session_state['user_id'])
            st.rerun()

    # Renderização da Lista (Lógica existente)
    renderizar_checklist()

# --- Interface Principal ---
def renderizar_checklist():
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
            # Título focado na OS e Cliente
            titulo = f"{icon} OS: {chamado['os']} - {chamado['cliente']}"
            
            # O Expander funciona como um "Card" que abre e fecha
            # expanded=False garante que comece fechado
            with st.expander(titulo, expanded=False):
                
                endereco_completo = f"{chamado.get('endereco', 'N/A')}, {chamado.get('numero', 'S/N')}"
                st.markdown(f"""
                **Localização:**
                - 🏢 **Endereço:** {endereco_completo}
                - 📍 **Bairro:** {chamado.get('bairro', 'N/A')}
                - 🏙️ **Cidade:** {chamado.get('cidade', 'N/A')}
                """)
                st.markdown("---")
                st.markdown(f"""
                **Detalhes do Equipamento:**
                - 💻 **Equipamento:** {chamado.get('equipamento', 'N/A')}
                - 🏷️ **Marca:** {chamado.get('marca', 'N/A')}
                - 📄 **Modelo:** {chamado.get('modelo', 'N/A')}
                - 🔢 **Serial:** {chamado.get('serial', 'N/A')}
                """)
                st.info(f"🔧 **Motivo:** {chamado.get('motivo', 'N/A')}")

                c1, c2 = st.columns(2)
                
                # Inputs de Hora
                novo_chegada = c1.time_input("Chegada", value=chamado['chegada'], key=f"in_{i}")
                novo_saida = c2.time_input("Saída", value=chamado['saida'], key=f"out_{i}")
                
                # Status
                opcoes_status = ["Aberto", "Pendente", "Concluído"]
                idx_status = opcoes_status.index(chamado['status']) if chamado['status'] in opcoes_status else 0
                novo_status = st.selectbox("Status", options=opcoes_status, index=idx_status, key=f"st_{i}")
                
                # Campo de Observações
                nova_obs = st.text_area("Observações", value=chamado['obs'], key=f"obs_{i}", height=68)
                
                # Checkbox de conclusão final
                novo_concluido = st.checkbox("Finalizar Chamado", value=chamado['concluido'], key=f"chk_{i}")

                # --- Lógica de Atualização (Memória + Banco) ---
                # Verifica se houve mudança e salva no banco imediatamente
                if novo_chegada != chamado['chegada']:
                    db_atualizar_campo(chamado['id'], 'chegada', novo_chegada)
                    st.session_state.dados_checklist[i]['chegada'] = novo_chegada
                
                if novo_saida != chamado['saida']:
                    db_atualizar_campo(chamado['id'], 'saida', novo_saida)
                    st.session_state.dados_checklist[i]['saida'] = novo_saida

                if novo_status != chamado['status']:
                    db_atualizar_campo(chamado['id'], 'status', novo_status)
                    st.session_state.dados_checklist[i]['status'] = novo_status

                if nova_obs != chamado['obs']:
                    db_atualizar_campo(chamado['id'], 'obs', nova_obs)
                    st.session_state.dados_checklist[i]['obs'] = nova_obs

                if novo_concluido != chamado['concluido']:
                    db_atualizar_campo(chamado['id'], 'concluido', novo_concluido)
                    st.session_state.dados_checklist[i]['concluido'] = novo_concluido

                # Lógica automática: Se marcar finalizado, muda status para Concluído
                if novo_concluido and chamado['status'] != "Concluído":
                    db_atualizar_campo(chamado['id'], 'status', "Concluído")
                    st.session_state.dados_checklist[i]['status'] = "Concluído"
                    st.rerun()

        st.markdown("---")
        
        # Exportação
        if st.button("📥 Baixar Relatório Final"):
            # Baixa apenas os dados do usuário
            dados_finais = db_carregar_chamados(user_id=st.session_state['user_id'])
            df = pd.DataFrame(dados_finais)
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                "Clique para Download",
                data=csv,
                file_name=f"relatorio_{st.session_state['username']}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

def main():
    # Aplica o estilo baseado no estado atual (antes de renderizar qualquer coisa)
    aplicar_estilo()

    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False

    if not st.session_state['logged_in']:
        tela_login()
    else:
        if st.session_state['role'] == 'admin':
            tela_admin()
        else:
            tela_tecnico()

if __name__ == "__main__":
    main()
