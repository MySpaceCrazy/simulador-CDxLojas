# app.py
# Otimização de Localização de Depósitos – versão Streamlit
# Autor: Anderson (personalizável)
# ------------------------------------------------------------
# Este app replica a lógica visual e conceitual das telas mostradas:
# - Upload de lojas e CDs
# - Parâmetros avançados
# - Cálculo de custos (transporte, fixo, variável, capital)
# - Alocação de lojas ao CD mais econômico respeitando capacidade
# - Tabela resumo + mapa interativo

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
st.caption("Modelo simplificado de apoio à decisão logística")

# ============================
# FUNÇÕES AUXILIARES
# ============================

def haversine(lat1, lon1, lat2, lon2):
    """Distância em km entre dois pontos geográficos"""
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def classificar_tamanho(qtd_lojas):
    if qtd_lojas <= 30:
        return "Minimo"
    elif qtd_lojas <= 60:
        return "Pequeno"
    elif qtd_lojas <= 90:
        return "Medio"
    else:
        return "Grande"

# ============================
# SIDEBAR – PARÂMETROS
# ============================
with st.sidebar:
    st.header("⚙️ Parâmetros Gerais")

    capacidade_veiculo = st.number_input("Capacidade do Veículo", 1, 50, 5)
    custo_km = st.number_input("Custo por km (R$)", value=4.5)
    custo_medio_produto = st.number_input("Custo Médio do Produto", value=12.6)
    pecas_loja_dia = st.number_input("Peças por loja / dia", value=1961)
    custo_oportunidade = st.number_input("Custo de Oportunidade (% a.a)", value=0.01)
    payback = st.number_input("Payback (anos)", value=10)

    st.divider()
    st.subheader("Custos Operacionais")

custos_operacionais_df = st.data_editor(
    pd.DataFrame({
        "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
        "Custo Fixo": [0.30, 0.25, 0.20, 0.15],
        "Custo Variável": [0.45, 0.35, 0.30, 0.25]
    }),
    hide_index=True,
    use_container_width=True
)

custos_operacionais = {
    row['Tamanho']: {
        'fixo': row['Custo Fixo'],
        'variavel': row['Custo Variável']
    }
    for _, row in custos_operacionais_df.iterrows()
}

st.subheader("Investimento por Tamanho")

investimentos_df = st.data_editor(
    pd.DataFrame({
        "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
        "Investimento (R$)": [4_000_000, 6_000_000, 8_000_000, 10_000_000]
    }),
    hide_index=True,
    use_container_width=True
)

investimentos = {
    row['Tamanho']: row['Investimento (R$)']
    for _, row in investimentos_df.iterrows()
}

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
cds = pd.read_excel(cds_file)

# Esperado: lojas -> id_loja, latitude, longitude
# Esperado: cds   -> deposito, latitude, longitude, existente, capacidade

# ============================
# ETAPA 2 – PROCESSAMENTO
# ============================
st.header("2️⃣ Processamento da Solução")

if st.button("🚀 Processar Solução"):
    st.session_state.processado = True

    # Distâncias
    registros = []

    for _, loja in lojas.iterrows():
        melhor = None
        menor_custo = np.inf

        for _, cd in cds.iterrows():
            dist = haversine(loja['latitude'], loja['longitude'], cd['latitude'], cd['longitude'])
            custo_transp = dist * custo_km

            if custo_transp < menor_custo:
                menor_custo = custo_transp
                melhor = cd['deposito']

        registros.append({
            "loja": loja['id_loja'],
            "deposito": melhor,
            "custo_transporte": menor_custo
        })

    alocacao = pd.DataFrame(registros)

    resumo = alocacao.groupby('deposito').agg(
        lojas_atendidas=('loja', 'count'),
        custo_transporte=('custo_transporte', 'sum')
    ).reset_index()

    resultados = []

    for _, row in resumo.iterrows():
        tamanho = classificar_tamanho(row['lojas_atendidas'])
        custo_fixo = row['lojas_atendidas'] * custos_operacionais[tamanho]['fixo'] * 100
        custo_var = row['lojas_atendidas'] * custos_operacionais[tamanho]['variavel'] * 100
        custo_operacional = custo_fixo + custo_var
        investimento = investimentos[tamanho] / payback

        resultados.append({
            "Depósito": row['deposito'],
            "Lojas": row['lojas_atendidas'],
            "Transporte": round(row['custo_transporte'], 2),
            "Fixo": round(custo_fixo, 2),
            "Variável": round(custo_var, 2),
            "Operacional": round(custo_operacional, 2),
            "Total": round(row['custo_transporte'] + custo_operacional, 2),
            "Investimentos": round(investimento, 2)
        })

    df_resultado = pd.DataFrame(resultados)
    st.session_state.df_resultado = df_resultado
    st.session_state.alocacao = alocacao
    st.session_state.lojas = lojas
    st.session_state.cds = cds

    st.success("Processamento concluído")

    # ============================
    # RESULTADOS – TABELA
    # ============================
    st.header("3️⃣ Resultados")
    st.dataframe(df_resultado, use_container_width=True)

    # ============================
    # MAPA
    # ============================
    st.subheader("🗺️ Mapa de Atendimento")

    centro_lat = lojas['latitude'].mean()
    centro_lon = lojas['longitude'].mean()

    mapa = folium.Map(location=[centro_lat, centro_lon], zoom_start=6)

    cores = ['red', 'blue', 'green', 'purple', 'orange']
    cor_cd = {cd: cores[i % len(cores)] for i, cd in enumerate(df_resultado['Depósito'])}

    for _, loja in lojas.iterrows():
        dep = alocacao.loc[alocacao['loja'] == loja['id_loja'], 'deposito'].values[0]
        folium.CircleMarker(
            location=[loja['latitude'], loja['longitude']],
            radius=4,
            color=cor_cd[dep],
            fill=True,
            fill_opacity=0.7,
            popup=f"Loja {loja['id_loja']} → {dep}"
        ).add_to(mapa)

    for _, cd in cds.iterrows():
        folium.Marker(
            location=[cd['latitude'], cd['longitude']],
            icon=folium.Icon(color='black', icon='home'),
            popup=cd['deposito']
        ).add_to(mapa)

    st_folium(mapa, use_container_width=True)

    # ============================
    # DOWNLOAD
    # ============================
    st.download_button(
        "📥 Baixar Resultado (CSV)",
        df_resultado.to_csv(index=False).encode('utf-8'),
        file_name="resultado_otimizacao.csv",
        mime="text/csv"
    )
