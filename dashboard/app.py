import streamlit as st
import snowflake.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import warnings

# Esconder o aviso do Pandas no terminal
warnings.filterwarnings('ignore', message='.*pandas only supports SQLAlchemy.*')

# 1. SETUP DE PÁGINA
st.set_page_config(page_title="Aegis Centro de Controle", page_icon="🏥", layout="wide")

# CSS CUSTOMIZADO (Dark Mode, Glow, Cards e Substituição de Overrides do Streamlit)
st.markdown("""
<style>
    /* Configurações Globais de Fundo e Container */
    .stApp { background-color: #0b0e14; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    
    /* Layout dos Cards de KPI */
    .dark-card {
        background-color: #151923;
        border-radius: 12px;
        padding: 22px;
        box-shadow: 0 4px 25px rgba(0,0,0,0.4);
        margin-bottom: 15px;
        display: flex;
        flex-direction: column;
    }
    .card-cyan { border-left: 6px solid #00f2fe; }
    .card-purple { border-left: 6px solid #b122e5; }
    .card-pink { border-left: 6px solid #ff0844; }
    .card-orange { border-left: 6px solid #ffb199; }
    
    .kpi-title { font-size: 13px; color: #8b949e; text-transform: uppercase; font-weight: 600; letter-spacing: 0.5px; margin-bottom: 6px; }
    .kpi-value { font-size: 30px; font-weight: 700; color: #ffffff; line-height: 1.2; margin-bottom: 0px; }
    
    /* Tipografia Corrigida */
    h1, h2, h3, h4, h5, h6 { color: #ffffff !important; font-family: 'sans serif'; }
    
    /* Estilização Customizada das Abas (Tabs) para Casar com o Tema */
    .stTabs [data-baseweb="tab-list"] { background-color: transparent; border-bottom: 1px solid #151923; gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        color: #8b949e; 
        font-weight: 600; 
        background-color: transparent; 
        padding: 10px 20px;
        border-radius: 4px 4px 0 0;
    }
    .stTabs [aria-selected="true"] { 
        color: #00f2fe !important; 
        border-bottom: 2px solid #00f2fe !important;
        background-color: rgba(0, 242, 254, 0.04) !important;
    }

    /* Estilização Customizada para Substituir o Alerta Amarelo NATIVO */
    .custom-warning {
        background-color: #151923; 
        padding: 22px; 
        border-left: 6px solid #00f2fe; 
        border-radius: 12px;
        margin: 20px 0;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
    }
</style>
""", unsafe_allow_html=True)

# Header Principal UI/UX Centrado no Tema do Hospital
st.title("Centro de controle")
st.markdown("<p style='color:#e5e7eb; margin-top:-15px; margin-bottom:30px;'>Monitoramento Operacional e Clínico em Tempo Real</p>", unsafe_allow_html=True)

# 2. CONEXÃO E INGESTÃO DE DADOS
@st.cache_resource(show_spinner="🔌 Conectando ao Data Warehouse...")
def init_connection():
    return snowflake.connector.connect(**st.secrets["snowflake"])

conn = init_connection()

@st.cache_data(show_spinner="⏳ Puxando dados do Snowflake...")
def load_data():
    query = """
    SELECT 
        f.ADMISSION_DATE,
        f.DISCHARGE_DATE,
        f.LENGTH_OF_STAY_DAYS,
        f.BILLING_AMOUNT_WITH_TAX,
        f.IS_CRITICAL_LONG_STAY,
        f.MEDICAL_CONDITION,
        f.MEDICAL_DEPARTMENT,
        f.ADMISSION_TYPE,
        p.AGE_GROUP,
        p.PATIENT_GENDER,
        p.BLOOD_TYPE,
        i.INSURANCE_PROVIDER_NAME,
        m.MEDICATION_NAME,
        t.TEST_RESULT_STATUS
    FROM FCT_ADMISSIONS f
    LEFT JOIN DIM_PATIENTS p ON f.PATIENT_ID = p.PATIENT_ID
    LEFT JOIN DIM_INSURANCE_PROVIDERS i ON f.INSURANCE_PROVIDER_ID = i.INSURANCE_PROVIDER_ID
    LEFT JOIN DIM_MEDICATIONS m ON f.MEDICATION_ID = m.MEDICATION_ID
    LEFT JOIN DIM_TEST_RESULTS t ON f.TEST_RESULT_ID = t.TEST_RESULT_ID
    """
    
    cursor = conn.cursor()
    cursor.execute(query)
    colunas = [col[0] for col in cursor.description]
    df = pd.DataFrame(cursor.fetchall(), columns=colunas)
    
    df['ADMISSION_DATE'] = pd.to_datetime(df['ADMISSION_DATE'])
    df['DISCHARGE_DATE'] = pd.to_datetime(df['DISCHARGE_DATE'])
    df['PATIENT_GENDER'] = df['PATIENT_GENDER'].replace({'MALE': 'MASCULINO', 'FEMALE': 'FEMININO'})
    
    return df

df = load_data()

# 3. FILTROS NA SIDEBAR
st.sidebar.markdown("<h2 style='color:#00f2fe;'>Filtros Globais</h2>", unsafe_allow_html=True)
dept_selecionado = st.sidebar.multiselect("Ala Médica", options=df['MEDICAL_DEPARTMENT'].dropna().unique(), default=df['MEDICAL_DEPARTMENT'].dropna().unique())
adm_selecionada = st.sidebar.multiselect("Tipo de Entrada", options=df['ADMISSION_TYPE'].dropna().unique(), default=df['ADMISSION_TYPE'].dropna().unique())

df_filtered = df[(df['MEDICAL_DEPARTMENT'].isin(dept_selecionado)) & (df['ADMISSION_TYPE'].isin(adm_selecionada))]

# Container Reservado para Tratamento Amigável de Erros (UX Sem Quebras Visuais)
alerta_container = st.container()

if df_filtered.empty:
    with alerta_container:
        st.markdown(
            """
            <div class="custom-warning">
                <strong style="color: #00f2fe; font-size: 16px;">Aviso da Torre de Controle</strong>
                <p style="color: #ffffff; margin: 8px 0 0 0; font-size: 14px;">
                    Não há dados para os filtros selecionados. Por favor, ajuste as opções na barra lateral.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
    st.stop()

# FUNÇÃO AUXILIAR DE UX: Formatação Inteligente de Grandes Valores
def formatar_grandeza(valor):
    if valor >= 1_000_000_000:
        return f"R$ {valor / 1_000_000_000:.2f} Bi"
    elif valor >= 1_000_000:
        return f"R$ {valor / 1_000_000:.1f} Mi"
    elif valor >= 1_000:
        return f"R$ {valor / 1_000:.1f} Mil"
    return f"R$ {valor:.2f}"

# 4. CARDS DE KPI
col1, col2, col3, col4 = st.columns(4)

vol_pacientes = len(df_filtered)
receita_total = df_filtered['BILLING_AMOUNT_WITH_TAX'].sum()
ticket_medio = df_filtered['BILLING_AMOUNT_WITH_TAX'].mean()
alos = df_filtered['LENGTH_OF_STAY_DAYS'].mean()

faturamento_formatado = formatar_grandeza(receita_total).replace('.', ',')

col1.markdown(f"""<div class="dark-card card-cyan"><div class="kpi-title">Faturamento Total</div><div class="kpi-value">{faturamento_formatado}</div></div>""", unsafe_allow_html=True)
col2.markdown(f"""<div class="dark-card card-purple"><div class="kpi-title">Total de Internações</div><div class="kpi-value">{vol_pacientes:,}</div></div>""".replace(',', '.'), unsafe_allow_html=True)
col3.markdown(f"""<div class="dark-card card-pink"><div class="kpi-title">Ticket Médio</div><div class="kpi-value">R$ {ticket_medio:,.0f}</div></div>""".replace(',', '.'), unsafe_allow_html=True)
col4.markdown(f"""<div class="dark-card card-orange"><div class="kpi-title">Média de Permanência</div><div class="kpi-value">{alos:.1f} Dias</div></div>""", unsafe_allow_html=True)

# Configuração de Layout Unificada para os Gráficos Plotly (Sem conflitos de chaves)
dark_layout = dict(
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#e5e7eb', size=12),
    margin=dict(l=15, r=15, t=45, b=25)
)

# 5. ABAS (TABS)
tab1, tab2, tab3 = st.tabs([" Visão Geral Operacional", " Desfechos Clínicos", " Demografia & Farmácia"])

with tab1:
    admissoes = df_filtered.groupby('ADMISSION_DATE').size().reset_index(name='Volume')
    admissoes['Tipo'] = 'Entradas (Admissões)'
    admissoes.rename(columns={'ADMISSION_DATE': 'Data'}, inplace=True)
    
    altas = df_filtered.groupby('DISCHARGE_DATE').size().reset_index(name='Volume')
    altas['Tipo'] = 'Saídas (Altas)'
    altas.rename(columns={'DISCHARGE_DATE': 'Data'}, inplace=True)
    
    fluxo = pd.merge(admissoes.drop(columns='Tipo'), altas.drop(columns='Tipo'), on='Data', how='outer').fillna(0).sort_values('Data')
    fluxo.rename(columns={'Volume_x': 'Entradas', 'Volume_y': 'Saídas'}, inplace=True)

    fig_fluxo = go.Figure()
    fig_fluxo.add_trace(go.Scatter(x=fluxo['Data'], y=fluxo['Entradas'], mode='lines', name='Admissões', line=dict(color='#00f2fe', width=3), fill='tozeroy', fillcolor='rgba(0, 242, 254, 0.08)'))
    fig_fluxo.add_trace(go.Scatter(x=fluxo['Data'], y=fluxo['Saídas'], mode='lines', name='Altas', line=dict(color='#b122e5', width=3), fill='tozeroy', fillcolor='rgba(177, 34, 229, 0.08)'))
    
    fig_fluxo.update_layout(**dark_layout, title='FLUXO DE LEITOS: ADMISSÕES VS. ALTAS', legend=dict(font=dict(color='#e5e7eb'), orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig_fluxo.update_xaxes(showgrid=False, linecolor='#2a2e39')
    fig_fluxo.update_yaxes(showgrid=True, gridcolor='#151923', linecolor='#2a2e39')
    st.plotly_chart(fig_fluxo, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        rev_ins = df_filtered.groupby('INSURANCE_PROVIDER_NAME')['BILLING_AMOUNT_WITH_TAX'].sum().reset_index().sort_values('BILLING_AMOUNT_WITH_TAX', ascending=True)
        fig_ins = px.bar(rev_ins, y='INSURANCE_PROVIDER_NAME', x='BILLING_AMOUNT_WITH_TAX', orientation='h', title='DEPENDÊNCIA FINANCEIRA POR CONVÊNIO')
        fig_ins.update_traces(marker_color='#ffb199')
        fig_ins.update_layout(**dark_layout)
        fig_ins.update_xaxes(showgrid=True, gridcolor='#151923', title="")
        fig_ins.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_ins, use_container_width=True)

    with col_b:
        tkt_dept = df_filtered.groupby('MEDICAL_DEPARTMENT')['BILLING_AMOUNT_WITH_TAX'].mean().reset_index().sort_values('BILLING_AMOUNT_WITH_TAX', ascending=True)
        fig_bar = px.bar(tkt_dept, y='MEDICAL_DEPARTMENT', x='BILLING_AMOUNT_WITH_TAX', orientation='h', title='TICKET MÉDIO POR ALA MÉDICA')
        fig_bar.update_traces(marker_color="#86489c")
        fig_bar.update_layout(**dark_layout)
        fig_bar.update_xaxes(showgrid=True, gridcolor='#151923', title="")
        fig_bar.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_bar, use_container_width=True)

    col_c, col_d = st.columns(2)
    with col_c:
        adm_vol = df_filtered['ADMISSION_TYPE'].value_counts().reset_index()
        adm_vol.columns = ['ADMISSION_TYPE', 'COUNT']
        fig_donut = px.pie(adm_vol, names='ADMISSION_TYPE', values='COUNT', hole=0.7, title='PERFIL DE ENTRADA (URGÊNCIA VS ELETIVA)')
        fig_donut.update_traces(textinfo='none', hoverinfo='label+percent', marker=dict(colors=['#00f2fe', '#b122e5', '#ff0844']))
        fig_donut.update_layout(**dark_layout, showlegend=True, legend=dict(font=dict(color='#e5e7eb'), orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5))
        st.plotly_chart(fig_donut, use_container_width=True)
        
    with col_d:
        doencas = df_filtered['MEDICAL_CONDITION'].value_counts().reset_index()
        doencas.columns = ['CONDITION', 'COUNT']
        fig_doencas = px.bar(doencas, x='CONDITION', y='COUNT', title='VOLUME DE INTERNAÇÕES POR PATOLOGIA')
        fig_doencas.update_traces(marker_color='#00f2fe')
        fig_doencas.update_layout(**dark_layout)
        fig_doencas.update_xaxes(showgrid=False, title="")
        fig_doencas.update_yaxes(showgrid=True, gridcolor='#151923', title="")
        st.plotly_chart(fig_doencas, use_container_width=True)

# ==========================================
# ABA 2: DESFECHOS CLÍNICOS
# ==========================================
with tab2:
    st.markdown("<h4 style='color:#8b949e;'>Análise de Gravidade e Ocupação Clínica</h4>", unsafe_allow_html=True)
    
    col_e, col_f = st.columns(2)
    with col_e:
        test_cond = df_filtered.groupby(['MEDICAL_CONDITION', 'TEST_RESULT_STATUS']).size().reset_index(name='COUNT')
        fig_test_cond = px.bar(test_cond, y='MEDICAL_CONDITION', x='COUNT', color='TEST_RESULT_STATUS',
                               orientation='h', barmode='stack', title='GRAVIDADE CLINICA: EXAMES POR DOENÇA',
                               color_discrete_map={'NORMAL': '#00f2fe', 'INCONCLUSIVE': '#ffb199', 'ABNORMAL': '#ff0844'})
        fig_test_cond.update_layout(**dark_layout, legend=dict(font=dict(color='#e5e7eb'), title="", orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5))
        fig_test_cond.update_xaxes(showgrid=True, gridcolor='#151923', title="")
        fig_test_cond.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_test_cond, use_container_width=True)

    with col_f:
        criticos = df_filtered[df_filtered['IS_CRITICAL_LONG_STAY'].astype(str).str.upper() == 'TRUE']
        criticos_dept = criticos.groupby('MEDICAL_DEPARTMENT').size().reset_index(name='COUNT').sort_values('COUNT', ascending=True)
        fig_crit = px.bar(criticos_dept, y='MEDICAL_DEPARTMENT', x='COUNT', orientation='h', title='ALERTA: CASOS CRÍTICOS (LONG STAY) POR ALA')
        fig_crit.update_traces(marker_color='#ff0844')
        fig_crit.update_layout(**dark_layout)
        fig_crit.update_xaxes(showgrid=True, gridcolor='#151923', title="")
        fig_crit.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_crit, use_container_width=True)

    col_g, col_h = st.columns(2)
    with col_g:
        alos_cond = df_filtered.groupby('MEDICAL_CONDITION')['LENGTH_OF_STAY_DAYS'].mean().reset_index().sort_values('LENGTH_OF_STAY_DAYS', ascending=True)
        fig_alos = px.bar(alos_cond, y='MEDICAL_CONDITION', x='LENGTH_OF_STAY_DAYS', orientation='h', title='MÉDIA DE DIAS DE INTERNAÇÃO POR DOENÇA')
        fig_alos.update_traces(marker_color='#b122e5')
        fig_alos.update_layout(**dark_layout)
        fig_alos.update_xaxes(showgrid=True, gridcolor='#151923', title="Dias")
        fig_alos.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_alos, use_container_width=True)

    with col_h:
        test_res = df_filtered['TEST_RESULT_STATUS'].value_counts().reset_index()
        test_res.columns = ['STATUS', 'COUNT']
        fig_test = px.pie(test_res, names='STATUS', values='COUNT', hole=0.5, title='VISÃO GERAL DOS RESULTADOS DE EXAMES')
        fig_test.update_traces(marker=dict(colors=['#00f2fe', '#ff0844', '#ffb199']))
        fig_test.update_layout(**dark_layout, legend=dict(font=dict(color='#e5e7eb'), orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5))
        st.plotly_chart(fig_test, use_container_width=True)

# ==========================================
# ABA 3: DEMOGRAFIA E FARMÁCIA (SUPRIMENTOS)
# ==========================================
with tab3:
    st.markdown("<h4 style='color:#8b949e;'>Gestão de Suprimentos e Perfil Populacional</h4>", unsafe_allow_html=True)
    
    col_i, col_j = st.columns(2)
    with col_i:
        sangue = df_filtered['BLOOD_TYPE'].value_counts().reset_index()
        sangue.columns = ['BLOOD_TYPE', 'COUNT']
        fig_blood = px.bar(sangue, x='BLOOD_TYPE', y='COUNT', title='BANCO DE SANGUE: DEMANDA POR TIPAGEM', text_auto=True)
        fig_blood.update_traces(marker_color='#ff0844', marker_line_width=0, textfont_size=14, textposition="outside")
        fig_blood.update_layout(**dark_layout)
        fig_blood.update_xaxes(showgrid=False, title="")
        fig_blood.update_yaxes(showgrid=True, gridcolor='#151923', title="")
        st.plotly_chart(fig_blood, use_container_width=True)

    with col_j:
        custo_med = df_filtered.groupby('MEDICATION_NAME')['BILLING_AMOUNT_WITH_TAX'].mean().reset_index().sort_values('BILLING_AMOUNT_WITH_TAX', ascending=True)
        fig_custo_med = px.bar(custo_med, y='MEDICATION_NAME', x='BILLING_AMOUNT_WITH_TAX', orientation='h', title='TICKET MÉDIO DA CONTA POR MEDICAMENTO')
        fig_custo_med.update_traces(marker_color='#00f2fe')
        fig_custo_med.update_layout(**dark_layout)
        fig_custo_med.update_xaxes(showgrid=True, gridcolor='#151923', title="")
        fig_custo_med.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_custo_med, use_container_width=True)

    col_k, col_l = st.columns(2)
    with col_k:
        idade_genero = df_filtered.groupby(['AGE_GROUP', 'PATIENT_GENDER']).size().reset_index(name='COUNT')
        fig_stack = px.bar(idade_genero, x='AGE_GROUP', y='COUNT', color='PATIENT_GENDER', barmode='group', title='DEMOGRAFIA DE PACIENTES (IDADE X GÊNERO)', color_discrete_map={'MASCULINO': '#00f2fe', 'FEMININO': '#b122e5'})
        fig_stack.update_layout(**dark_layout, legend=dict(font=dict(color='#e5e7eb'), title="", orientation="h", yanchor="top", y=-0.05, xanchor="center", x=0.5))
        fig_stack.update_xaxes(showgrid=False, title="")
        fig_stack.update_yaxes(showgrid=True, gridcolor='#151923', title="Quantidade")
        st.plotly_chart(fig_stack, use_container_width=True)

    with col_l:
        meds = df_filtered['MEDICATION_NAME'].value_counts().head(7).reset_index()
        meds.columns = ['MEDICATION_NAME', 'COUNT']
        fig_meds = px.bar(meds, y='MEDICATION_NAME', x='COUNT', orientation='h', title='VOLUME: TOP MEDICAMENTOS PRESCRITOS')
        fig_meds.update_traces(marker_color='#ffb199')
        fig_meds.update_layout(**dark_layout, yaxis={'categoryorder':'total ascending'})
        fig_meds.update_xaxes(showgrid=True, gridcolor='#151923', title="")
        fig_meds.update_yaxes(showgrid=False, title="")
        st.plotly_chart(fig_meds, use_container_width=True)