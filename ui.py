import streamlit as st
import json
import pandas as pd
import plotly.express as px
import os

# --- Configuração da página ---
st.set_page_config(layout="wide", page_title="Simulação Energética")

# --- Constantes e caminhos de imagem ---
IMAGE_PATHS = {
    "BM": "IMGs/biomassa.png",
    "PV": "IMGs/solar.png",
    "WT": "IMGs/eolico.png",
    "BAT": "IMGs/bateria.png"
}
TABS = ["🔵 Biomassa", "☀️ PV", "🌬️ WT", "🔋 Baterias", "⚡ Cargas", "💰 Custos"]

# --- Carrega JSON em cache ---
@st.cache_data
def load_data(path=r"C:\Users\shenr\Downloads\SIMULATE_CLP-main (1)\SIMULATE_CLP-main\dispatch_data.json"):
    with open(path, "r") as f:
        return json.load(f)
data = load_data()

# --- Helpers ---
def build_time_df(raw, prefix, n):
    df = pd.DataFrame(raw).T if raw else pd.DataFrame()
    if not df.empty:
        df.columns = [f"{prefix}{i+1}" for i in range(n)]
        df["Hora"] = list(range(len(df)))
    return df

def plot_full_and_instant(df_unit, asset_key, unit_name):
    """Slider + instantâneo + gráfico 24h com chave única."""
    max_h = int(df_unit["Hora"].max())
    slider_key = f"slider_{asset_key}_{unit_name}"
    chart_key = f"chart_inst_{asset_key}_{unit_name}"
    hora = st.slider(f"Hora – {unit_name}", 0, max_h, 0, key=slider_key)
    valor = float(df_unit.loc[df_unit["Hora"] == hora, unit_name])
    total = float(df_unit[unit_name].sum())
    st.markdown(f"**Hora {hora}:** {valor:.2f} MW")
    st.markdown(f"**Total dia:** {total:.2f} MW")
    fig = px.line(df_unit, x="Hora", y=unit_name, markers=True, title=f"{unit_name} – Produção 24h")
    fig.update_layout(xaxis=dict(range=[0, max_h]), yaxis_title="MW")
    st.plotly_chart(fig, use_container_width=True, key=chart_key)

def render_asset_tab(df, key, title):
    st.header(title)
    img = IMAGE_PATHS.get(key)
    if img and os.path.exists(img):
        st.image(img, width=300)
    if df.empty:
        st.info(f"Sem dados de {title}")
        return
    units = [c for c in df.columns if c!="Hora"]
    unit_tabs = st.tabs(units)
    for unit, utab in zip(units, unit_tabs):
        with utab:
            st.subheader(unit)
            sub = st.tabs(["Perfil 24h", "Inspeção por Hora"])
            # Perfil 24h
            with sub[0]:
                fig = px.line(df, x="Hora", y=unit, markers=True, title=f"{unit} – Produção 24h")
                fig.update_layout(yaxis_title="MW", xaxis=dict(range=[0, df["Hora"].max()]))
                st.plotly_chart(fig, use_container_width=True, key=f"profile_{key}_{unit}")
            # Inspeção por hora
            with sub[1]:
                plot_full_and_instant(df[["Hora", unit]].rename(columns={unit: unit}),
                                      asset_key=key, unit_name=unit)

# --- Séries temporais ---
df_bm  = build_time_df(data["p_bm"],  "BM",  data["Nbm"])
df_pv  = build_time_df(data.get("p_pv", []), "PV", data["Npv"])
df_wt  = build_time_df(data.get("p_wt", []), "WT", data["Nwt"])
df_bat = build_time_df(data.get("p_bat", []), "BAT", data["Nbat"])

# --- Cria abas principais ---
main_tabs = st.tabs(TABS)

# 1) Biomassa
with main_tabs[0]:
    render_asset_tab(df_bm, "BM", "Biomassa")

# 2) PV
with main_tabs[1]:
    render_asset_tab(df_pv, "PV", "PV")

# 3) WT
with main_tabs[2]:
    render_asset_tab(df_wt, "WT", "WT")

# 4) Baterias
with main_tabs[3]:
    render_asset_tab(df_bat, "BAT", "Baterias")

# 5) Cargas
with main_tabs[4]:
    st.header("⚡ Cargas")
    sub = st.tabs(["Não Controlável", "Despachável", "Estado de Corte"])
    # Não controlável
    with sub[0]:
        df_pl = build_time_df(data["p_l"], "L", data["Nl"])
        if df_pl.empty:
            st.info("Sem dados de carga não controlável")
        else:
            for unit in [c for c in df_pl.columns if c!="Hora"]:
                st.subheader(unit)
                plot_full_and_instant(df_pl[["Hora", unit]].rename(columns={unit: unit}),
                                      asset_key="L", unit_name=unit)
    # Despachável + limites
    with sub[1]:
        dfs = {
            "DL":   (data.get("p_dl", []),    data["Ndl"]),
            "REF":  (data.get("p_dl_ref", []),data["Ndl"]),
            "MIN":  (data.get("p_dl_min", []),data["Ndl"]),
            "MAX":  (data.get("p_dl_max", []),data["Ndl"])
        }
        for prefix, (raw, n) in dfs.items():
            df_tmp = build_time_df(raw, prefix, n)
            st.subheader(prefix)
            if df_tmp.empty:
                st.info(f"Sem dados de {prefix.lower()}")
            else:
                for unit in [c for c in df_tmp.columns if c!="Hora"]:
                    st.subheader(unit)
                    plot_full_and_instant(df_tmp[["Hora", unit]].rename(columns={unit: unit}),
                                          asset_key=prefix, unit_name=unit)
    # Estado de corte
    with sub[2]:
        df_udl = build_time_df(data.get("u_dl", []), "UDL", data["Ndl"])
        if df_udl.empty:
            st.info("Sem dados de estado de corte")
        else:
            st.dataframe(df_udl, use_container_width=True)

# 6) Custos & Tarifas
with main_tabs[5]:
    st.header("💰 Custos e Tarifas")
    sub = st.tabs(["Biomassa", "PV & WT", "Bateria", "Tarifas"])
    # Biomassa
    with sub[0]:
        p_df = df_bm.set_index("Hora")
        u_df = build_time_df(data["u_bm"], "UBM", data["Nbm"]).set_index("Hora")
        k_bm, k_start = data["kappa_bm"], data["kappa_bm_start"]
        df_cbm = pd.DataFrame({
            f"BM{i+1}": p_df[f"BM{i+1}"]*k_bm[i] + u_df[f"UBM{i+1}"]*k_start[i]
            for i in range(data["Nbm"])
        }).reset_index()
        for unit in [c for c in df_cbm.columns if c!="Hora"]:
            st.subheader(unit)
            plot_full_and_instant(df_cbm[["Hora", unit]], asset_key="CBM", unit_name=unit)
    # PV & WT
    with sub[1]:
        for prefix, raw, kappa, n in [
            ("PV", data.get("p_pv", []), data["kappa_pv"], data["Npv"]),
            ("WT", data.get("p_wt", []), data["kappa_wt"], data["Nwt"])
        ]:
            df_ts = build_time_df(raw, prefix, n)
            if df_ts.empty:
                st.info(f"Sem dados de {prefix.lower()}")
                continue
            df_cost = df_ts.set_index("Hora")
            for i in range(n):
                df_cost[f"{prefix}{i+1}"] *= kappa[i]
            df_cost = df_cost.reset_index()
            for unit in [c for c in df_cost.columns if c!="Hora"]:
                st.subheader(unit)
                plot_full_and_instant(df_cost[["Hora", unit]], asset_key="C"+prefix, unit_name=unit)
    # Bateria
    with sub[2]:
        df_chg = build_time_df(data.get("p_chg", []), "BAT_CHG", data["Nbat"]).set_index("Hora")
        df_dch = build_time_df(data.get("p_dch", []), "BAT_DCH", data["Nbat"]).set_index("Hora")
        k_bat = data["kappa_bat"]
        df_cb = pd.DataFrame({
            f"BAT{i+1}": (df_chg[f"BAT_CHG{i+1}"] + df_dch[f"BAT_DCH{i+1}"]) * k_bat[i]
            for i in range(data["Nbat"])
        }).reset_index()
        for unit in [c for c in df_cb.columns if c!="Hora"]:
            st.subheader(unit)
            plot_full_and_instant(df_cb[["Hora", unit]], asset_key="CBAT", unit_name=unit)
    # Tarifas
    with sub[3]:
        df_tar = pd.DataFrame({
            "Hora": range(len(data["tau_pld"])),
            "PLD": data["tau_pld"],
            "Dist": data["tau_dist"],
            "DL": data["tau_dl"]
        })
        for unit in ["PLD", "Dist", "DL"]:
            st.subheader(unit)
            plot_full_and_instant(df_tar[["Hora", unit]], asset_key="TAR", unit_name=unit)
