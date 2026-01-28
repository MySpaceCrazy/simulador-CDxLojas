# app.py
# Otimização de Localização de Depósitos – versão Streamlit (completa)
# ------------------------------------------------------------
# App com todos os parâmetros editáveis pelo usuário final
# Sidebar: Parâmetros avançados
# Área principal: Upload, capacidade, processamento, resultados e mapa

import streamlit as st
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
import folium
from streamlit_folium import st_folium

# ============================
# CONFIGURAÇÃO GERAL
# ============================
st.set_page_config(
    page_title="Otimização de Depósitos",
    page_icon="📦",
    layout="wide"
)

st.markdown(
    """
    <style>
        .block-container {padding-top: 2rem;}
        .stButton>button {border-radius: 10px; height: 3em;}
        .stDownloadButton>button {border-radius: 10px;}
        div[data-baseweb="input"] > div {border-radius: 8px;}
    </style>
    """,
    unsafe_allow_html=True
)

st.title("📦 Otimização de Localização de Depósitos")
st.caption("Simulador de apoio à decisão logística")

# ============================
# FUNÇÕES AUXILIARES
# ============================

def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def classificar_tamanho(qtd_lojas, faixas):
    for _, row in faixas.iterrows():
        if qtd_lojas <= row['Max Lojas']:
            return row['Tamanho']
    return faixas.iloc[-1]['Tamanho']

# ============================
# SIDEBAR – PARÂMETROS AVANÇADOS
# ============================
with st.sidebar:
    st.header("⚙️ Parâmetros Avançados")

    st.subheader("Parâmetros Básicos")
    nome_cenario = st.text_input("Nome do Cenário", "Minha Análise 01/2026")
    capacidade_veiculo = st.number_input("Capacidade do Veículo", min_value=1, value=5)
    custo_km = st.number_input("Custo por Km (R$)", value=4.5)
    custo_medio_produto = st.number_input("Custo Médio do Produto (R$)", value=12.6)
    pecas_loja_dia = st.number_input("Peças por Loja / Dia", value=1961)
    custo_oportunidade = st.number_input("Custo de Oportunidade (% a.a)", value=0.01)
    payback = st.number_input("Payback (anos)", value=10)

    st.divider()
    st.subheader("Custo Operacional")

    custos_operacionais_df = st.data_editor(
        pd.DataFrame({
            "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
            "Max Lojas": [30, 60, 90, 9999],
            "% Fixo": [0.30, 0.25, 0.20, 0.15],
            "Custo Variável": [0.45, 0.35, 0.30, 0.25]
        }),
        hide_index=True,
        use_container_width=True
    )

    st.divider()
    st.subheader("Custo de Capital")

    custo_capital_df = st.data_editor(
        pd.DataFrame({
            "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
            "Max Lojas": [30, 60, 90, 9999],
            "Dias Cobertura": [25, 20, 15, 10]
        }),
        hide_index=True,
        use_container_width=True
    )

    st.divider()
    st.subheader("Investimento por Tamanho")

    investimentos_df = st.data_editor(
        pd.DataFrame({
            "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
            "Max Lojas": [30, 60, 90, 9999],
            "Investimento (R$)": [4_000_000, 6_000_000, 8_000_000, 10_000_000]
        }),
        hide_index=True,
        use_container_width=True
    )

# ============================
# ETAPA 1 – UPLOAD
# ============================
st.header("1️⃣ Carregar Arquivos")
col1, col2 = st.columns(2)

with col1:
    lojas_file = st.file_uploader("Arquivo de Lojas (xlsx)", type=["xlsx"])
with col2:
    cds_file = st.file_uploader("Arquivo de CDs (xlsx)", type=["xlsx"])

if not lojas_file or not cds_file:
    st.info("Faça upload dos dois arquivos para continuar")
    st.stop()

lojas = pd.read_excel(lojas_file)
cds_base = pd.read_excel(cds_file)

# ============================
# ETAPA 2 – CAPACIDADE DOS DEPÓSITOS
# ============================
st.header("2️⃣ Configurar Capacidades")

cds_editor = st.data_editor(
    cds_base[["deposito", "existente", "capacidade"]],
    hide_index=True,
    use_container_width=True,
    column_config={
        "deposito": st.column_config.TextColumn("Depósito", disabled=True),
        "existente": st.column_config.CheckboxColumn("Existente?"),
        "capacidade": st.column_config.NumberColumn("Capacidade (Lojas)", min_value=0)
    }
)

cds = cds_base.merge(cds_editor, on="deposito", suffixes=("", "_edit"))
cds["existente"] = cds["existente_edit"]
cds["capacidade"] = cds["capacidade_edit"]
cds = cds.drop(columns=["existente_edit", "capacidade_edit"])

# ============================
# ETAPA 3 – PROCESSAMENTO
# ============================
st.header("3️⃣ Processamento")

col_a, col_b, col_c, col_d = st.columns(4)
btn_matriz = col_a.button("📊 Gerar Matriz")
btn_limpar = col_b.button("🧹 Limpar Cache")
btn_processar = col_c.button("🚀 Processar Solução")
btn_mapa = col_d.button("🗺️ Abrir Mapa")

if btn_limpar:
    st.session_state.clear()
    st.experimental_rerun()

if btn_processar:
    # Matriz de custo
    matriz = []
    for _, loja in lojas.iterrows():
        for _, cd in cds.iterrows():
            dist = haversine(loja['latitude'], loja['longitude'], cd['latitude'], cd['longitude'])
            matriz.append({
                "loja": loja['id_loja'],
                "deposito": cd['deposito'],
                "custo_transporte": dist * custo_km
            })

    matriz_df = pd.DataFrame(matriz)

    # Alocação respeitando capacidade
    alocacao = []
    capacidade_restante = cds.set_index('deposito')['capacidade'].to_dict()

    for loja in lojas['id_loja']:
        candidatos = matriz_df[matriz_df['loja'] == loja].sort_values('custo_transporte')
        for _, c in candidatos.iterrows():
            if capacidade_restante[c['deposito']] > 0:
                capacidade_restante[c['deposito']] -= 1
                alocacao.append(c)
                break

    alocacao_df = pd.DataFrame(alocacao)

    resumo = alocacao_df.groupby('deposito').agg(
        lojas=('loja', 'count'),
        transporte=('custo_transporte', 'sum')
    ).reset_index()

    resultados = []

    for _, row in resumo.iterrows():
        tamanho = classificar_tamanho(row['lojas'], custos_operacionais_df)

        fixo = row['lojas'] * custos_operacionais_df.loc[custos_operacionais_df['Tamanho'] == tamanho, '% Fixo'].values[0] * 100
        variavel = row['lojas'] * custos_operacionais_df.loc[custos_operacionais_df['Tamanho'] == tamanho, 'Custo Variável'].values[0] * 100
        operacional = fixo + variavel

        dias = custo_capital_df.loc[custo_capital_df['Tamanho'] == tamanho, 'Dias Cobertura'].values[0]
        capital = row['lojas'] * pecas_loja_dia * dias * custo_medio_produto * custo_oportunidade

        investimento = investimentos_df.loc[investimentos_df['Tamanho'] == tamanho, 'Investimento (R$)'].values[0] / payback

        resultados.append({
            "Depósito": row['deposito'],
            "Lojas": row['lojas'],
            "Transporte": round(row['transporte'], 2),
            "Fixo": round(fixo, 2),
            "Variável": round(variavel, 2),
            "Operacional": round(operacional, 2),
            "Capital": round(capital, 2),
            "Investimentos": round(investimento, 2),
            "Total": round(row['transporte'] + operacional + capital + investimento, 2)
        })

    st.session_state.df_resultado = pd.DataFrame(resultados)
    st.session_state.alocacao = alocacao_df
    st.session_state.processado = True

# ============================
# ETAPA 4 – RESULTADOS
# ============================
if st.session_state.get('processado'):
    st.header("4️⃣ Resultados")
    st.dataframe(st.session_state.df_resultado, use_container_width=True)

    if btn_mapa:
        st.subheader("🗺️ Mapa de Distribuição")
        centro_lat = lojas['latitude'].mean()
        centro_lon = lojas['longitude'].mean()
        mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=6)

        cores = ['red', 'blue', 'green', 'purple', 'orange', 'darkred']
        cor_cd = {cd: cores[i % len(cores)] for i, cd in enumerate(st.session_state.df_resultado['Depósito'])}

        for _, loja in lojas.iterrows():
            dep = st.session_state.alocacao.loc[
                st.session_state.alocacao['loja'] == loja['id_loja'], 'deposito'
            ].values[0]

            folium.CircleMarker(
                [loja['latitude'], loja['longitude']],
                radius=4,
                color=cor_cd[dep],
                fill=True,
                fill_opacity=0.7,
                popup=f"Loja {loja['id_loja']} → {dep}"
            ).add_to(mapa)

        for _, cd in cds.iterrows():
            folium.Marker(
                [cd['latitude'], cd['longitude']],
                icon=folium.Icon(color='black', icon='home'),
                popup=cd['deposito']
            ).add_to(mapa)

        st_folium(mapa, use_container_width=True)

    st.download_button(
        "📥 Baixar Resultado (CSV)",
        st.session_state.df_resultado.to_csv(index=False).encode('utf-8'),
        file_name=f"resultado_{nome_cenario}.csv",
        mime="text/csv"
    )
