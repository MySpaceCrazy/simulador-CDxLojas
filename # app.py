# app.py
# Otimização de Localização de Depósitos – versão estável com capacidade por CD

import streamlit as st
import pandas as pd
import numpy as np
from math import radians, cos, sin, asin, sqrt
import folium
from streamlit_folium import st_folium

# ============================
# CONFIGURAÇÃO
# ============================
st.set_page_config(
    page_title="Otimização de Depósitos",
    page_icon="📦",
    layout="wide"
)

# ============================
# FUNÇÕES
# ============================
def haversine(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1)*cos(lat2)*sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return 6371 * c


def classificar_tamanho(qtd, df):
    for _, row in df.iterrows():
        if qtd <= row["Max Lojas"]:
            return row["Tamanho"]
    return df.iloc[-1]["Tamanho"]

# ============================
# SIDEBAR
# ============================
with st.sidebar:
    st.header("⚙️ Parâmetros Avançados")

    nome_cenario = st.text_input("Nome do Cenário", "Minha Análise 01/2026")
    custo_km = st.number_input("Custo por Km (R$)", value=4.5)
    pecas_loja_dia = st.number_input("Peças por Loja / Dia", value=1961)
    custo_medio_produto = st.number_input("Custo Médio Produto (R$)", value=12.6)
    custo_oportunidade = st.number_input("Custo Oportunidade (% a.a)", value=0.01)
    payback = st.number_input("Payback (anos)", value=10)

    st.subheader("Custos Operacionais")
    custos_operacionais_df = st.data_editor(
        pd.DataFrame({
            "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
            "Max Lojas": [30, 60, 90, 9999],
            "% Fixo": [0.30, 0.25, 0.20, 0.15],
            "Variável": [0.45, 0.35, 0.30, 0.25]
        }),
        hide_index=True
    )

    st.subheader("Custo de Capital")
    custo_capital_df = st.data_editor(
        pd.DataFrame({
            "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
            "Max Lojas": [30, 60, 90, 9999],
            "Dias Cobertura": [25, 20, 15, 10]
        }),
        hide_index=True
    )

    st.subheader("Investimentos")
    investimentos_df = st.data_editor(
        pd.DataFrame({
            "Tamanho": ["Minimo", "Pequeno", "Medio", "Grande"],
            "Max Lojas": [30, 60, 90, 9999],
            "Investimento (R$)": [4e6, 6e6, 8e6, 1e7]
        }),
        hide_index=True
    )
# ============================
# UPLOAD
# ============================
st.header("1️⃣ Carregar Arquivos")

lojas_file = st.file_uploader("Lojas (xlsx)", type="xlsx")
cds_file = st.file_uploader("CDs (xlsx)", type="xlsx")

if not lojas_file or not cds_file:
    st.stop()

lojas = pd.read_excel(lojas_file)
cds_base = pd.read_excel(cds_file)
# ============================
# CAPACIDADE CDs
# ============================
st.header("2️⃣ Capacidade dos CDs")

cds = st.data_editor(
    cds_base[["deposito", "existente", "capacidade", "latitude", "longitude"]],
    hide_index=True
)

cds_validos = cds[cds["existente"]].copy()
# ============================
# BOTÕES
# ============================
st.header("3️⃣ Processamento")

col1, col2, col3 = st.columns(3)
btn_matriz = col1.button("📊 Gerar Matriz")
btn_processar = col2.button("🚀 Processar Solução")
btn_limpar = col3.button("🧹 Limpar Cache")

if btn_limpar:
    st.session_state.clear()
    st.rerun()
# ============================
# MATRIZ
# ============================
if btn_matriz:
    matriz = []
    for _, loja in lojas.iterrows():
        for _, cd in cds_validos.iterrows():
            matriz.append({
                "Loja": loja["id_loja"],
                "Depósito": cd["deposito"],
                "Custo": haversine(loja["latitude"], loja["longitude"], cd["latitude"], cd["longitude"]) * custo_km
            })
    st.session_state.matriz = pd.DataFrame(matriz)
    st.subheader("Prévia da Matriz de Custos")
    st.dataframe(st.session_state.matriz.head(20))
# ============================
# PROCESSAMENTO
# ============================
if btn_processar:
    capacidade_restante = cds_validos.set_index("deposito")["capacidade"].to_dict()
    alocacao = []

    for _, loja in lojas.iterrows():
        custos = []
        for _, cd in cds_validos.iterrows():
            custos.append({
                "deposito": cd["deposito"],
                "custo": haversine(loja["latitude"], loja["longitude"], cd["latitude"], cd["longitude"]) * custo_km
            })

        custos = sorted(custos, key=lambda x: x["custo"])

        alocado = False
        for c in custos:
            if capacidade_restante[c["deposito"]] > 0:
                capacidade_restante[c["deposito"]] -= 1
                alocacao.append({
                    "loja": loja["id_loja"],
                    "deposito": c["deposito"],
                    "custo": c["custo"]
                })
                alocado = True
                break

        if not alocado:
            alocacao.append({
                "loja": loja["id_loja"],
                "deposito": "SEM_CAPACIDADE",
                "custo": None
            })

    st.session_state.alocacao = pd.DataFrame(alocacao)
    st.session_state.mostrar_mapa = True
# ============================
# RESULTADOS
# ============================
if "alocacao" in st.session_state:
    st.header("4️⃣ Resultados")

    resumo_base = st.session_state.alocacao.groupby("deposito").agg(
        Lojas=("loja", "count"),
        Transporte=("custo", "sum")
    ).reset_index()

    resultados = []

    for _, row in resumo_base.iterrows():
        deposito = row["deposito"]
        lojas_qtd = row["Lojas"]
        transporte = row["Transporte"] if not np.isnan(row["Transporte"]) else 0

        # Classificação de tamanho
        tamanho = classificar_tamanho(lojas_qtd, custos_operacionais_df)

        # Parâmetros operacionais
        p_fixo = custos_operacionais_df.loc[
            custos_operacionais_df["Tamanho"] == tamanho, "% Fixo"
        ].values[0]

        p_var = custos_operacionais_df.loc[
            custos_operacionais_df["Tamanho"] == tamanho, "Variável"
        ].values[0]

        # Base operacional
        base_operacional = lojas_qtd * pecas_loja_dia * custo_medio_produto

        custo_fixo = base_operacional * p_fixo
        custo_variavel = base_operacional * p_var
        operacional = custo_fixo + custo_variavel

        # Capital
        dias = custo_capital_df.loc[
            custo_capital_df["Tamanho"] == tamanho, "Dias Cobertura"
        ].values[0]

        capital = (
            lojas_qtd
            * pecas_loja_dia
            * dias
            * custo_medio_produto
            * custo_oportunidade
        )

        # Investimento anualizado
        investimento_total = investimentos_df.loc[
            investimentos_df["Tamanho"] == tamanho, "Investimento (R$)"
        ].values[0]

        investimento = investimento_total / payback

        total = transporte + operacional + capital + investimento

        resultados.append({
            "Depósito": deposito,
            "Lojas": lojas_qtd,
            "Tamanho": tamanho,
            "Transporte (R$)": round(transporte, 2),
            "Fixo (R$)": round(custo_fixo, 2),
            "Variável (R$)": round(custo_variavel, 2),
            "Operacional (R$)": round(operacional, 2),
            "Capital (R$)": round(capital, 2),
            "Investimento (R$)": round(investimento, 2),
            "Total (R$)": round(total, 2)
        })

    df_resultado = pd.DataFrame(resultados)
    st.dataframe(df_resultado, use_container_width=True)
# ============================
# MAPA
# ============================
if st.session_state.get("mostrar_mapa"):
    st.subheader("🗺️ Mapa de Distribuição")

    mapa = folium.Map(
        location=[lojas["latitude"].mean(), lojas["longitude"].mean()],
        zoom_start=6
    )

    cores = ["red", "blue", "green", "purple", "orange"]
    cor_cd = {cd: cores[i % len(cores)] for i, cd in enumerate(resumo["deposito"])}

    for _, row in st.session_state.alocacao.iterrows():
        if row["deposito"] == "SEM_CAPACIDADE":
            continue
        loja = lojas[lojas["id_loja"] == row["loja"]].iloc[0]
        folium.CircleMarker(
            [loja["latitude"], loja["longitude"]],
            radius=4,
            color=cor_cd[row["deposito"]],
            fill=True
        ).add_to(mapa)

    for _, cd in cds_validos.iterrows():
        folium.Marker(
            [cd["latitude"], cd["longitude"]],
            popup=cd["deposito"],
            icon=folium.Icon(icon="home", color="black")
        ).add_to(mapa)

    st_folium(mapa, use_container_width=True)
