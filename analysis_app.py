import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# =========================================================
# GRUNDEINSTELLUNGEN
# =========================================================
st.set_page_config(page_title="Analyse", layout="wide")

# =========================================================
# KONSTANTEN & ALLGEMEINE HILFSFUNKTIONEN
# =========================================================
NUM_TIME_POINTS = 301  # Auflösung für Zeitachsen bei Modellkurven


def role_human(role: str) -> str:
    """Übersetzt Rollen-Kürzel in Klartext."""
    if role == "B":
        return "Käufer"
    if role == "S":
        return "Verkäufer"
    if role == "P1":
        return "Käufer (Alt)"
    if role == "P2":
        return "Verkäufer (Alt)"
    return str(role)


def offer_hover_text(df_part: pd.DataFrame) -> list[str]:
    """Hovertext für OFFER-Punkte (Käufer/Verkäufer)."""
    out = []
    for _, row in df_part.iterrows():
        out.append(
            f"Spiel: {row.get('game_code', '–')}"
            f"<br>Event: {row.get('event_type', '–')}"
            f"<br>Rolle: {role_human(row.get('proposer_role', '–'))}"
            f"<br>Angebotsnr.: {row.get('offer_index', '–')}"
            f"<br>Zeit: {float(row.get('time_relative', np.nan)):.2f}s"
            f"<br>Preis: {float(row.get('price', np.nan)):.2f}€"
        )
    return out


def accept_hover_text(df_part: pd.DataFrame) -> list[str]:
    """Hovertext für ACCEPT-Punkte."""
    out = []
    for _, row in df_part.iterrows():
        out.append(
            f"Spiel: {row.get('game_code', '–')}"
            f"<br>Event: {row.get('event_type', 'ACCEPT')}"
            f"<br>Anbieter: {role_human(row.get('proposer_role', '–'))}"
            f"<br>Akzeptiert von: {role_human(row.get('accepter_role', '–'))}"
            f"<br>Zeit: {float(row.get('time_relative', np.nan)):.2f}s"
            f"<br>Preis: {float(row.get('price', np.nan)):.2f}€"
        )
    return out


@st.cache_data
def load_games_log(path: str = "games_log.csv") -> pd.DataFrame:
    """Lädt die Log-Datei und konvertiert sinnvolle Spalten in numerische Werte."""
    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
    except FileNotFoundError:
        st.error(f"Datei `{path}` wurde nicht gefunden. Lege sie ins gleiche Verzeichnis wie dieses Skript.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Fehler beim Laden von `{path}`: {e}")
        return pd.DataFrame()

    cols_to_convert = [
        "timestamp_abs",
        "time_relative",
        "price",
        "agreed_price",
        "B_Net",
        "S_Net",
        "B_Gross",
        "S_Gross",
        "B_rate",
        "S_rate",
        "buyer_value",
        "seller_cost",
    ]
    for col in cols_to_convert:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def refresh_data():
    """Löscht Cache und startet App neu."""
    load_games_log.clear()
    st.rerun()


# =========================================================
# DATEN LADEN
# =========================================================
df = load_games_log()

# =========================================================
# SIDEBAR: FILTER & STEUERUNG
# =========================================================
st.sidebar.button("Daten aktualisieren", on_click=refresh_data)

if df.empty:
    st.sidebar.warning("Keine Daten geladen. Prüfe `games_log.csv`.")
    st.stop()

if "treatment_key" not in df.columns:
    st.sidebar.error("Spalte `treatment_key` fehlt in den Daten.")
    st.stop()

# Session-State Defaults
if "show_all_games" not in st.session_state:
    st.session_state.show_all_games = False
if "show_global" not in st.session_state:
    st.session_state.show_global = False
if "selected_game_code" not in st.session_state:
    st.session_state.selected_game_code = None

# Treatment-Auswahl
all_treatments = sorted(df["treatment_key"].dropna().unique())
selected_treatment = st.sidebar.selectbox(
    "Treatment",
    options=all_treatments,
    index=0 if len(all_treatments) > 0 else None,
)

df_treat = df[df["treatment_key"] == selected_treatment]
if df_treat.empty:
    st.sidebar.warning(f"Keine Spiele für Treatment `{selected_treatment}` gefunden.")
    st.stop()

# Master Toggle: Global
st.sidebar.markdown("---")
st.sidebar.toggle(
    "Globale Ansicht",
    key="show_global",
    help="Wenn aktiv: NUR globale Übersichten (alle Treatments/alle Spiele). Alles andere wird ausgeblendet.",
)

# Toggle: Alle Spiele vs Einzelspiel (deaktiviert im Global-Modus)
st.sidebar.toggle(
    "Alle Spiele dieses Treatments",
    key="show_all_games",
    disabled=st.session_state.show_global,
    help="Schaltet zwischen Einzelspiel-Ansicht und aggregierter Treatment-Ansicht um.",
)

# Auswahl Game-Code nur wenn: nicht global und nicht all-games
selected_code = None
if st.session_state.show_global:
    # egal, wird später sowieso gestoppt, aber wir setzen df_game stabil
    df_game = df_treat.copy()
else:
    if st.session_state.show_all_games:
        selected_code = None
        df_game = df_treat.copy()
        # optional: Game selection reset
        st.session_state.selected_game_code = None
    else:
        all_codes = sorted(df_treat["game_code"].dropna().unique())
        selected_code = st.sidebar.selectbox(
            "Game-Code",
            options=all_codes,
            index=0 if len(all_codes) > 0 else None,
            key="selected_game_code",
        )
        df_game = df_treat[df_treat["game_code"] == selected_code].copy()

if df_game.empty:
    st.warning("Keine Einträge für die aktuelle Auswahl gefunden.")
    st.stop()

# Downloads
col_dl, col_main = st.columns([1, 4])
with col_dl.expander("Downloads"):
    try:
        with open("games_log.csv", "rb") as f:
            st.download_button("games_log.csv herunterladen", data=f, file_name="games_log.csv", mime="text/csv")
    except FileNotFoundError:
        st.warning("games_log.csv nicht gefunden.")
    try:
        with open("fragebogen.csv", "rb") as f:
            st.download_button("fragebogen.csv herunterladen", data=f, file_name="fragebogen.csv", mime="text/csv")
    except FileNotFoundError:
        st.warning("fragebogen.csv nicht gefunden.")

single_game_view = (not st.session_state.show_all_games) and (not st.session_state.show_global)

# =========================================================
# HILFSFUNKTIONEN FÜR BERECHNUNGEN
# =========================================================
def extract_single_game_parameters(df_game_: pd.DataFrame) -> dict:
    row0 = df_game_.iloc[0]

    buyer_val = float(row0.get("buyer_value", 130.0))
    seller_cost = float(row0.get("seller_cost", 30.0))

    try:
        r_buyer = float(row0.get("B_rate", 0.0))
        r_seller = float(row0.get("S_rate", 0.0))
    except Exception:
        st.error("B_rate oder S_rate fehlt in den Daten!")
        st.stop()

    if df_game_["time_relative"].notna().any():
        t_min = float(df_game_["time_relative"].min())
        t_max = float(df_game_["time_relative"].max())
    else:
        t_min, t_max = 0.0, 120.0

    df_accept_single = df_game_[df_game_["event_type"] == "ACCEPT"].sort_values("time_relative")
    last_accept = df_accept_single.iloc[-1] if not df_accept_single.empty else None

    if last_accept is not None:
        deal_price_data = last_accept.get("agreed_price", np.nan)
        if np.isnan(deal_price_data):
            deal_price_data = last_accept.get("price", np.nan)
    else:
        deal_price_data = np.nan

    mid_price = (buyer_val + seller_cost) / 2.0
    analysis_price = float(deal_price_data) if not np.isnan(deal_price_data) else mid_price

    disc_buyer_end = float(np.exp(-r_buyer * t_max))
    disc_seller_end = float(np.exp(-r_seller * t_max))

    return {
        "row0": row0,
        "buyer_val": buyer_val,
        "seller_cost": seller_cost,
        "r_buyer": r_buyer,
        "r_seller": r_seller,
        "t_min": t_min,
        "t_max": t_max,
        "last_accept": last_accept,
        "deal_price_data": deal_price_data,
        "analysis_price": analysis_price,
        "disc_buyer_end": disc_buyer_end,
        "disc_seller_end": disc_seller_end,
    }


def compute_single_game_metrics(params: dict) -> dict:
    last_accept = params["last_accept"]
    buyer_val = params["buyer_val"]
    seller_cost = params["seller_cost"]
    r_buyer = params["r_buyer"]
    r_seller = params["r_seller"]

    deal_t = deal_price = np.nan
    eff = np.nan
    b_brut = s_brut = np.nan
    b_net = s_net = np.nan
    proposer_role_raw = accepter_role_raw = "?"

    if last_accept is not None:
        deal_t = float(last_accept.get("time_relative", np.nan))

        deal_price = params["deal_price_data"]
        if np.isnan(deal_price):
            deal_price = float(last_accept.get("price", np.nan))

        proposer_role_raw = last_accept.get("proposer_role", "?")
        accepter_role_raw = last_accept.get("accepter_role", "?")

        b_brut = max(0, buyer_val - deal_price)
        s_brut = max(0, deal_price - seller_cost)

        b_net = last_accept.get("B_Net", np.nan)
        s_net = last_accept.get("S_Net", np.nan)

        br_total = b_brut + s_brut

        if not np.isnan(b_net) and not np.isnan(s_net):
            net_total_real = float(b_net) + float(s_net)
        else:
            net_b_real = b_brut * np.exp(-r_buyer * deal_t)
            net_s_real = s_brut * np.exp(-r_seller * deal_t)
            net_total_real = net_b_real + net_s_real

        eff = net_total_real / br_total if br_total > 0 else np.nan

    return {
        "deal_t": deal_t,
        "deal_price": deal_price,
        "eff": eff,
        "b_brut": b_brut,
        "s_brut": s_brut,
        "b_net": b_net,
        "s_net": s_net,
        "proposer_role_raw": proposer_role_raw,
        "accepter_role_raw": accepter_role_raw,
    }


def compute_efficiency_rows(df_any: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if df_any.empty or "game_code" not in df_any.columns:
        return pd.DataFrame()

    for game_code, df_g in df_any.groupby("game_code"):
        df_accept_g = df_g[df_g["event_type"] == "ACCEPT"].sort_values("time_relative")
        if df_accept_g.empty:
            continue

        last = df_accept_g.iloc[-1]
        row0 = df_g.iloc[0]

        buyer_val_g = float(row0.get("buyer_value", 130.0))
        seller_cost_g = float(row0.get("seller_cost", 30.0))

        try:
            r_buyer_g = float(row0.get("B_rate", 0.0))
            r_seller_g = float(row0.get("S_rate", 0.0))
        except Exception:
            st.error("B_rate oder S_rate fehlt in den Daten!")
            st.stop()

        deal_t_g = float(last.get("time_relative", np.nan))
        deal_price_g = float(last.get("agreed_price", np.nan))
        if np.isnan(deal_price_g):
            deal_price_g = float(last.get("price", np.nan))

        if np.isnan(deal_t_g) or np.isnan(deal_price_g):
            continue

        p1_brut_g = max(0, buyer_val_g - deal_price_g)
        p2_brut_g = max(0, deal_price_g - seller_cost_g)
        br_total_g = p1_brut_g + p2_brut_g

        p1_net_g = last.get("B_Net", np.nan)
        p2_net_g = last.get("S_Net", np.nan)

        if not np.isnan(p1_net_g) and not np.isnan(p2_net_g):
            net_buyer_g = float(p1_net_g)
            net_seller_g = float(p2_net_g)
            net_total_g = net_buyer_g + net_seller_g
        else:
            net_buyer_g = p1_brut_g * np.exp(-r_buyer_g * deal_t_g)
            net_seller_g = p2_brut_g * np.exp(-r_seller_g * deal_t_g)
            net_total_g = net_buyer_g + net_seller_g

        # Effizienz relativ zu 100 (Surplus 100)
        eff_g = net_total_g / 100

        num_offers_g = len(df_g[df_g["event_type"] == "OFFER"])

        rows.append(
            {
                "Spiel": game_code,
                "Deal-Zeit": deal_t_g,
                "Preis": deal_price_g,
                "Effizienz": eff_g,
                "MinKosten": seller_cost_g,
                "Budget": buyer_val_g,
                "Anzahl Angebote": num_offers_g,
                "Netto Käufer": net_buyer_g,
                "Netto Verkäufer": net_seller_g,
            }
        )

    return pd.DataFrame(rows) if rows else pd.DataFrame()


# Precompute efficiency tables
df_eff = compute_efficiency_rows(df_treat)
df_eff_all = compute_efficiency_rows(df)

# =========================================================
# GLOBAL MODE: Wenn aktiv, NUR globale Charts anzeigen
# =========================================================
if st.session_state.show_global:
    st.title("GLOBAL – Übersicht")

    # Mapping: game_code -> treatment_key
    treat_map = df[["game_code", "treatment_key"]].dropna().drop_duplicates(subset=["game_code"])

    # letzte Einigung pro Spiel (nur ACCEPT)
    df_accept_all = (
        df[df["event_type"] == "ACCEPT"]
        .sort_values("time_relative")
        .groupby("game_code", as_index=False)
        .tail(1)
        .drop(columns=["treatment_key"], errors="ignore")
        .merge(treat_map, on="game_code", how="left")
    )

    if df_accept_all.empty or "treatment_key" not in df_accept_all.columns:
        st.info("Keine globalen ACCEPT-Daten vorhanden.")
        st.stop()

    # Brutto-Auszahlungen
    df_accept_all["Brutto Käufer"] = (df_accept_all["buyer_value"] - df_accept_all["price"]).clip(lower=0)
    df_accept_all["Brutto Verkäufer"] = (df_accept_all["price"] - df_accept_all["seller_cost"]).clip(lower=0)

    # Brutto-Anteile je Spiel
    df_accept_all = df_accept_all.copy()
    df_accept_all["Brutto Gesamt"] = df_accept_all["Brutto Käufer"] + df_accept_all["Brutto Verkäufer"]

    df_accept_all["Bruttoanteil Käufer"] = np.where(
        df_accept_all["Brutto Gesamt"] > 0,
        df_accept_all["Brutto Käufer"] / df_accept_all["Brutto Gesamt"],
        np.nan,
    )
    df_accept_all["Bruttoanteil Verkäufer"] = np.where(
        df_accept_all["Brutto Gesamt"] > 0,
        df_accept_all["Brutto Verkäufer"] / df_accept_all["Brutto Gesamt"],
        np.nan,
    )

    # =========================================================
    # Helper: "Mittelwert (Median)" als eine Zelle
    # =========================================================
    def mean_median_str(s: pd.Series, fmt: str) -> str:
        s = pd.to_numeric(s, errors="coerce").dropna()
        if s.empty:
            return "–"
        return f"{s.mean():{fmt}} ({s.median():{fmt}})"

    # =========================================================
    # Effizienz & Deal-Zeit aus df_eff_all holen und Treatment mergen
    # =========================================================
    df_eff_all_m = df_eff_all.copy()
    if not df_eff_all_m.empty:
        df_eff_all_m = df_eff_all_m.rename(columns={"Spiel": "game_code"})
        df_eff_all_m = df_eff_all_m.merge(treat_map, on="game_code", how="left")

    # =========================================================
    # SUMMARY pro Treatment
    # =========================================================
    g = df_accept_all.groupby("treatment_key")

    summary = pd.DataFrame(index=sorted(df_accept_all["treatment_key"].dropna().unique()))
    summary.index.name = "Treatment"

    # Spiele/Spieler
    summary["Spiele"] = g["game_code"].nunique()
    summary["Spieler"] = summary["Spiele"] * 2

    # Einigungspreis: mean (median)
    summary["Einigungspreis €"] = g["price"].apply(lambda s: mean_median_str(s, ".2f"))

    # Bruttoanteile: mean (median) in %
    summary["Bruttoanteil Käufer %"] = g["Bruttoanteil Käufer"].apply(lambda s: mean_median_str(s * 100, ".1f"))
    summary["Bruttoanteil Verkäufer %"] = g["Bruttoanteil Verkäufer"].apply(lambda s: mean_median_str(s * 100, ".1f"))

    # Effizienz/Dauer: mean (median)
    if df_eff_all_m.empty or "treatment_key" not in df_eff_all_m.columns:
        summary["Effizienz %"] = "–"
        summary["Verhandlungsdauer s"] = "–"
    else:
        g2 = df_eff_all_m.groupby("treatment_key")
        summary["Effizienz %"] = g2["Effizienz"].apply(lambda s: mean_median_str(s * 100, ".1f"))
        summary["Verhandlungsdauer s"] = g2["Deal-Zeit"].apply(lambda s: mean_median_str(s, ".2f"))

    # Sortierung
    summary = summary.sort_values("Spiele", ascending=False)

    st.dataframe(summary.reset_index(), use_container_width=True, hide_index=True)

    st.subheader("Deal-Zeit vs. Effizienz")
    if df_eff_all.empty:
        st.info("Keine Spiele mit ACCEPT-Event in den Daten.")
    else:
        df_plot = df_eff_all.merge(
            df[["game_code", "treatment_key"]].drop_duplicates(),
            left_on="Spiel",
            right_on="game_code",
            how="left",
        )

        treatments = sorted(df_plot["treatment_key"].dropna().unique())
        COLOR_SEQ = [
            "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
            "#bcbd22", "#17becf",
        ]
        color_map = {t: COLOR_SEQ[i % len(COLOR_SEQ)] for i, t in enumerate(treatments)}

        fig_eff_time = go.Figure()
        for t_key, df_t in df_plot.groupby("treatment_key"):
            fig_eff_time.add_trace(
                go.Scatter(
                    x=df_t["Deal-Zeit"],
                    y=df_t["Effizienz"],
                    mode="markers",
                    name=str(t_key),
                    marker=dict(size=9, color=color_map.get(t_key, "#333333"), opacity=0.85),
                    text=[
                        f"Spiel: {row.Spiel}"
                        f"<br>Treatment: {t_key}"
                        f"<br>Deal-Zeit: {row['Deal-Zeit']:.2f}s"
                        f"<br>Effizienz: {row['Effizienz']:.1%}"
                        for _, row in df_t.iterrows()
                    ],
                    hoverinfo="text",
                )
            )

        fig_eff_time.update_layout(
            xaxis_title="Verhandlungsdauer (s)",
            yaxis_title="Effizienz",
            yaxis_tickformat=".0%",
            height=520,
            margin=dict(l=0, r=0, t=40, b=0),
            legend_title_text="Treatment",
        )
        st.plotly_chart(fig_eff_time, use_container_width=True)

    st.divider()
    st.subheader("Brutto-Auszahlungen nach Treatment")

    treat_map = df[["game_code", "treatment_key"]].dropna().drop_duplicates(subset=["game_code"])
    df_accept_all = (
        df[df["event_type"] == "ACCEPT"]
        .sort_values("time_relative")
        .groupby("game_code", as_index=False)
        .tail(1)
        .drop(columns=["treatment_key"], errors="ignore")
        .merge(treat_map, on="game_code", how="left")
    )

    if df_accept_all.empty or "treatment_key" not in df_accept_all.columns:
        st.info("Keine globalen ACCEPT-Daten vorhanden.")
        st.stop()

    df_accept_all["Brutto Käufer"] = (df_accept_all["buyer_value"] - df_accept_all["price"]).clip(lower=0)
    df_accept_all["Brutto Verkäufer"] = (df_accept_all["price"] - df_accept_all["seller_cost"]).clip(lower=0)

    TREATMENTS = sorted(df_accept_all["treatment_key"].dropna().unique())
    COLOR_SEQ = [
        "#1f77b4", "#d62728", "#2ca02c", "#ff7f0e",
        "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        "#bcbd22", "#17becf",
    ]
    COLOR_MAP = {t: COLOR_SEQ[i % len(COLOR_SEQ)] for i, t in enumerate(TREATMENTS)}

    col_hb, col_hs = st.columns([1, 1])
    BIN_SIZE = 5

    with col_hb:
        fig_brutto_buyer = go.Figure()
        for t_key, df_t in df_accept_all.groupby("treatment_key"):
            fig_brutto_buyer.add_trace(
                go.Histogram(
                    x=df_t["Brutto Käufer"].dropna(),
                    name=str(t_key),
                    opacity=0.6,
                    marker=dict(color=COLOR_MAP.get(t_key)),
                    autobinx=False,
                    xbins=dict(start=0, end=100, size=BIN_SIZE),
                )
            )
        fig_brutto_buyer.update_layout(
            title="Brutto-Auszahlung Käufer",
            xaxis_title="Brutto Käufer (€)",
            yaxis_title="Häufigkeit",
            barmode="overlay",
            height=350,
            margin=dict(l=0, r=0, t=60, b=0),
            legend_title_text="Treatment",
            xaxis=dict(range=[0, 100]),
        )
        st.plotly_chart(fig_brutto_buyer, use_container_width=True)

    with col_hs:
        fig_brutto_seller = go.Figure()
        for t_key, df_t in df_accept_all.groupby("treatment_key"):
            fig_brutto_seller.add_trace(
                go.Histogram(
                    x=df_t["Brutto Verkäufer"].dropna(),
                    name=str(t_key),
                    opacity=0.6,
                    marker=dict(color=COLOR_MAP.get(t_key)),
                    autobinx=False,
                    xbins=dict(start=0, end=100, size=BIN_SIZE),
                )
            )
        fig_brutto_seller.update_layout(
            title="Brutto-Auszahlung Verkäufer",
            xaxis_title="Brutto Verkäufer (€)",
            yaxis_title="Häufigkeit",
            barmode="overlay",
            height=350,
            margin=dict(l=0, r=0, t=60, b=0),
            legend_title_text="Treatment",
            xaxis=dict(range=[0, 100]),
        )
        st.plotly_chart(fig_brutto_seller, use_container_width=True)



    # =========================================================
    # GLOBAL: Korrelationsmatrix (Spiel-Level)
    # - Test: Verhandlungsdauer + Einigungspreis
    # - Deal: Verhandlungsdauer + Einigungspreis
    # - Merge über game_code (nur gleiche Spiele)
    # =========================================================

    @st.cache_data
    def load_testrounds_log(path: str = "testrounds_log.csv") -> pd.DataFrame:
        return pd.read_csv(path, sep=";", encoding="utf-8")


    df_test = load_testrounds_log()

    required_cols_test = {"game_code", "time_relative", "event_type", "price"}
    if not required_cols_test.issubset(df_test.columns):
        st.warning(
            "testrounds_log.csv hat nicht die benötigten Spalten. "
            f"Erwartet: {sorted(required_cols_test)}"
        )
        st.stop()

    # --- Test: letzte Einigung pro Spiel (Zeit + Preis) ---
    df_test_deals = (
        df_test[df_test["event_type"] == "ACCEPT"]
        .sort_values("time_relative")
        .groupby("game_code", as_index=False)
        .tail(1)
        .rename(
            columns={
                "time_relative": "Test_Verhandlungsdauer",
                "price": "Test_Einigungspreis",
            }
        )
        [["game_code", "Test_Verhandlungsdauer", "Test_Einigungspreis"]]
    )

    # --- Deal (echtes Spiel): letzte Einigung pro Spiel (Zeit + Preis) ---
    df_game_deals = (
        df[df["event_type"] == "ACCEPT"]
        .sort_values("time_relative")
        .groupby("game_code", as_index=False)
        .tail(1)
        .rename(
            columns={
                "time_relative": "Deal_Verhandlungsdauer",
                "price": "Deal_Einigungspreis",
            }
        )
        [["game_code", "Deal_Verhandlungsdauer", "Deal_Einigungspreis"]]
    )

    # --- Merge: nur Spiele, die in beiden Logs vorkommen ---
    df_corr_base = df_test_deals.merge(df_game_deals, on="game_code", how="inner")

    corr_cols = [
        "Test_Verhandlungsdauer",
        "Deal_Verhandlungsdauer",
        "Test_Einigungspreis",
        "Deal_Einigungspreis",
    ]

    corr_matrix = df_corr_base[corr_cols].corr(method="pearson")

    import plotly.graph_objects as go

    # ---- Heatmap der Korrelationsmatrix ----
    z = corr_matrix.values
    x = list(corr_matrix.columns)
    y = list(corr_matrix.index)

    fig_corr = go.Figure(
        data=go.Heatmap(
            z=z,
            x=x,
            y=y,
            zmin=-1,
            zmax=1,
            colorscale="Portland",
            reversescale=True,   # +1 eher blau, -1 eher rot (optional)
            colorbar=dict(title="r"),
            hovertemplate="X: %{x}<br>Y: %{y}<br>r: %{z:.3f}<extra></extra>",
        )
    )

    # Werte als Text in die Zellen schreiben (optional, sieht gut aus)
    fig_corr.add_trace(
        go.Scatter(
            x=[xx for xx in x for _ in y],
            y=[yy for _ in x for yy in y],
            mode="text",
            text=[f"{v:.2f}" for v in z.T.flatten()],  # transponiert für gleiche Achsenlogik
            textfont=dict(
            size=18,          # ← Größe (16–20 ist ideal)
            color="black",    # dunkle Farbe = wirkt fett
            family="Arial Black",  # optional, falls verfügbar
            ),
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig_corr.update_yaxes(autorange="reversed")

    fig_corr.update_layout(
        title="Korrelations-Heatmap (Pearson)",
        height=420,
        margin=dict(l=0, r=0, t=50, b=0),
    )


    st.divider()
    st.subheader("Korrelationsmatrix Game-Level")

    st.caption(
        "Korrelationen zwischen Test- und Deal-Verhandlungsdauer sowie "
        "Test- und Deal-Einigungspreisen (nur Spiele mit Einigung in beiden Logs). "
        f"n = {len(df_corr_base)}"
    )
    st.plotly_chart(fig_corr, use_container_width=True)

    # ✅ WICHTIG: Global Mode beendet hier die App-Ausgabe
    st.stop()

# =========================================================
# AB HIER: NICHT-GLOBAL (Single Game oder All Games im Treatment)
# =========================================================

# =========================================================
# EINZELSPIEL: BASISDATEN & MODELL
# =========================================================
if single_game_view:
    params = extract_single_game_parameters(df_game)
    metrics = compute_single_game_metrics(params)

    row0 = params["row0"]
    buyer_val = params["buyer_val"]
    seller_cost = params["seller_cost"]
    r_buyer = params["r_buyer"]
    r_seller = params["r_seller"]
    t_max = params["t_max"]
    last_accept = params["last_accept"]
    analysis_price = params["analysis_price"]
    disc_buyer_end = params["disc_buyer_end"]
    disc_seller_end = params["disc_seller_end"]

    deal_t = metrics["deal_t"]
    deal_price = metrics["deal_price"]
    eff = metrics["eff"]
    b_brut = metrics["b_brut"]
    s_brut = metrics["s_brut"]
    b_net = metrics["b_net"]
    s_net = metrics["s_net"]
    proposer_role_raw = metrics["proposer_role_raw"]
    accepter_role_raw = metrics["accepter_role_raw"]

    df_offers_game = df_game[df_game["event_type"] == "OFFER"]
    num_offers_total = len(df_offers_game)
    num_offers_buyer = len(df_offers_game[df_offers_game["proposer_role"] == "B"])
    num_offers_seller = len(df_offers_game[df_offers_game["proposer_role"] == "S"])

    st.sidebar.markdown("---")
    if last_accept is not None:
        st.sidebar.metric("Einigungspreis", f"{deal_price:.2f} €")
        if not np.isnan(eff):
            st.sidebar.metric("Effizienz", f"{eff:.1%}")
        if not np.isnan(deal_t):
            st.sidebar.metric("Verhandlungsdauer", f"{deal_t:.2f} s")
    else:
        st.sidebar.info("Kein Deal in diesem Spiel.")

    st.subheader(f"SPIEL: {selected_code}")

    col_info1, col_right = st.columns([1, 2])
    with col_info1:
        st.write(f"**Treatment-Key:** `{row0.get('treatment_key', '–')}`")
        st.write(f"**Anzahl Events:** {len(df_game)}")
        st.write(f"**Anzahl Angebote gesamt:** {num_offers_total}")
        if last_accept is None:
            st.warning("In diesem Spiel gab es keine Einigung (kein ACCEPT-Event).")
        else:
            st.write(f"**Letztes Angebot:** {role_human(proposer_role_raw)}")
            st.write(f"**Akzeptiert von:** {role_human(accepter_role_raw)}")

    if last_accept is not None:
        brutto_buyer_str = f"{b_brut:.2f} €"
        brutto_seller_str = f"{s_brut:.2f} €"
        netto_buyer_str = f"{float(b_net):.2f} €" if not np.isnan(b_net) else "–"
        netto_seller_str = f"{float(s_net):.2f} €" if not np.isnan(s_net) else "–"
    else:
        brutto_buyer_str = brutto_seller_str = "–"
        netto_buyer_str = netto_seller_str = "–"

    stats_df = pd.DataFrame(
        {
            "": ["Diskontrate", "Diskontfaktor", "Anzahl Angebote", "Brutto-Auszahlung", "Netto-Auszahlung"],
            "Käufer": [f"{r_buyer:.4f}", f"{disc_buyer_end:.4f}", num_offers_buyer, brutto_buyer_str, netto_buyer_str],
            "Verkäufer": [f"{r_seller:.4f}", f"{disc_seller_end:.4f}", num_offers_seller, brutto_seller_str, netto_seller_str],
        }
    )

    with col_right:
        col_tbl, col_bar = st.columns([2, 1])
        with col_tbl:
            st.table(stats_df.set_index(""))
        with col_bar:
            if last_accept is None:
                st.info("Keine Einigung – keine Auszahlungen darstellbar.")
            else:
                brutto_k = float(b_brut) if not np.isnan(b_brut) else 0.0
                brutto_v = float(s_brut) if not np.isnan(s_brut) else 0.0
                netto_k = float(b_net) if not (b_net is None or np.isnan(b_net)) else 0.0
                netto_v = float(s_net) if not (s_net is None or np.isnan(s_net)) else 0.0

                x_labels = ["Käufer", "Verkäufer"]
                fig_pay = go.Figure()
                fig_pay.add_bar(x=x_labels, y=[netto_k, netto_v], name="Netto", marker=dict(color=["#90CAF9", "#FFCDD2"]))
                fig_pay.add_bar(x=x_labels, y=[brutto_k, brutto_v], name="Brutto", marker=dict(color=["#42A5F5", "#EF9A9A"]))
                fig_pay.update_layout(
                    barmode="group",
                    height=220,
                    margin=dict(l=0, r=0, t=10, b=0),
                    xaxis_title="",
                    yaxis_title="",
                    showlegend=False,
                )
                st.plotly_chart(fig_pay, use_container_width=True)

    st.divider()

    # Modellkurven
    t = np.linspace(0, max(t_max, 1.0), num=NUM_TIME_POINTS)
    factor_buyer = np.exp(-r_buyer * t)
    factor_seller = np.exp(-r_seller * t)

    surplus_buyer_gross = buyer_val - analysis_price
    surplus_seller_gross = analysis_price - seller_cost
    total_gross = surplus_buyer_gross + surplus_seller_gross

    net_buyer = surplus_buyer_gross * factor_buyer
    net_seller = surplus_seller_gross * factor_seller
    total_net = net_buyer + net_seller

    # 3D-Scatter (Single)
    if not df_offers_game.empty:
        t_offer = df_offers_game["time_relative"].astype(float)
        price_offer = df_offers_game["price"].astype(float)

        b_gross_offer = (buyer_val - price_offer).clip(lower=0)
        s_gross_offer = (price_offer - seller_cost).clip(lower=0)

        net_buyer_offer = b_gross_offer * np.exp(-r_buyer * t_offer)
        net_seller_offer = s_gross_offer * np.exp(-r_seller * t_offer)

        fig3d_single = go.Figure(
            data=[
                go.Scatter3d(
                    x=net_buyer_offer,
                    y=net_seller_offer,
                    z=t_offer,
                    mode="markers",
                    marker=dict(size=5, color=t_offer, colorscale="Viridis", opacity=0.8, colorbar=dict(title="Zeit (s)")),
                    text=[
                        f"Zeit: {tt:.2f}s"
                        f"<br>Preis: {p:.2f}€"
                        f"<br>Netto Käufer: {nb:.2f}€"
                        f"<br>Netto Verkäufer: {ns:.2f}€"
                        f"<br>Rolle: {role_human(role)}"
                        for tt, p, nb, ns, role in zip(
                            t_offer, price_offer, net_buyer_offer, net_seller_offer, df_offers_game["proposer_role"]
                        )
                    ],
                    hoverinfo="text",
                )
            ]
        )
        fig3d_single.update_layout(
            scene=dict(xaxis_title="Netto Käufer (€)", yaxis_title="Netto Verkäufer (€)", zaxis_title="Zeit (s)"),
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
            scene_camera=dict(eye=dict(x=1.6, y=1.6, z=1.2)),
        )
        st.subheader("Netto-Auszahlungen pro Angebot")
        st.plotly_chart(fig3d_single, use_container_width=True)

    st.divider()

    # ----------------------------
    # 2.1 Verlauf der Diskontfaktoren
    # ----------------------------
    st.markdown("### Verlauf der Diskontfaktoren")

    col_chart1, col_form1 = st.columns([3, 1])

    with col_chart1:
        fig_factors = go.Figure()
        fig_factors.add_trace(
            go.Scatter(
                x=t,
                y=factor_buyer,
                mode="lines",
                name="Käufer",
                line=dict(width=3, color="blue"),
                hovertemplate="Zeit: %{x:.2f}s<br>Diskontfaktor Käufer: %{y:.3f}<extra></extra>",
            )
        )
        fig_factors.add_trace(
            go.Scatter(
                x=t,
                y=factor_seller,
                mode="lines",
                name="Verkäufer",
                line=dict(width=3, color="red"),
                hovertemplate="Zeit: %{x:.2f}s<br>Diskontfaktor Verkäufer: %{y:.3f}<extra></extra>",
            )
        )

        fig_factors.update_layout(
            xaxis_title="Zeit t (s)",
            yaxis_title="Diskontfaktor",
            yaxis_range=[0, 1.05],
            height=450,
            margin=dict(l=0, r=100, t=20, b=0),
            legend=dict(orientation="v", xanchor="left", x=1.02, yanchor="top", y=1),
        )
        st.plotly_chart(fig_factors, use_container_width=True)

    with col_form1:
        st.markdown("**Käufer:**")
        st.latex(r"\delta_K(t) = e^{-r_K \cdot t}")
        st.caption(f"Diskontrate Käufer: $r_K = {r_buyer}$ pro Sekunde")
        st.caption(
            f"Diskontfaktor am Spielende (t = {t_max:.2f} s): "
            f"$\\delta_K(t) = {disc_buyer_end:.3f}$"
        )
        st.divider()
        st.markdown("**Verkäufer:**")
        st.latex(r"\delta_V(t) = e^{-r_V \cdot t}")
        st.caption(f"Diskontrate Verkäufer: $r_V = {r_seller}$ pro Sekunde")
        st.caption(
            f"Diskontfaktor am Spielende (t = {t_max:.2f} s): "
            f"$\\delta_V(t) = {disc_seller_end:.3f}$"
        )

    st.divider()


    # ----------------------------
    # 2.2 Netto-Auszahlungen (Modell)
    # ----------------------------
    st.markdown(f"### Netto-Auszahlungen")

    col_chart2, col_form2 = st.columns([3, 1])

    with col_chart2:
        fig_money = go.Figure()
        fig_money.add_trace(
            go.Scatter(
                x=t,
                y=net_buyer,
                mode="lines",
                name="Auszahlung Käufer",
                line=dict(color="blue"),
                hovertemplate="Zeit: %{x:.2f}s<br>Netto Käufer: %{y:.2f}€<extra></extra>",
            )
        )
        fig_money.add_trace(
            go.Scatter(
                x=t,
                y=net_seller,
                mode="lines",
                name="Auszahlung Verkäufer",
                line=dict(color="red"),
                hovertemplate="Zeit: %{x:.2f}s<br>Netto Verkäufer: %{y:.2f}€<extra></extra>",
            )
        )
        fig_money.add_trace(
            go.Scatter(
                x=t,
                y=total_net,
                mode="lines",
                name="Gesamt-Auszahlung",
                line=dict(dash="dot", color="green"),
                hovertemplate="Zeit: %{x:.2f}s<br>Gesamt-Auszahlung: %{y:.2f}€<extra></extra>",
            )
        )

        fig_money.add_hline(
            y=total_gross,
            line_dash="dash",
            annotation_text="Brutto-Auszahlung",
            annotation_position="top right",
        )

        fig_money.update_layout(
            xaxis_title="Zeit t (s)",
            yaxis_title="Netto-Auszahlung",
            height=450,
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="v", xanchor="left", x=1.02, yanchor="top", y=1),
        )
        st.plotly_chart(fig_money, use_container_width=True)

    with col_form2:
        st.markdown("**Käufer-Auszahlung:**")
        st.latex(r"u_K(t) = (V - P) \cdot e^{-r_K t}")
        st.divider()
        st.markdown("**Verkäufer-Auszahlung:**")
        st.latex(r"u_V(t) = (P - C) \cdot e^{-r_V t}")
        st.divider()
        st.markdown("**Gesamt-Auszahlung:**")
        st.latex(r"\Pi(t) = u_K(t) + u_V(t)")

    st.divider()


else:
    # =====================================================
    # AGGREGIERTE BASISINFOS – ALLE SPIELE IM TREATMENT
    # =====================================================
    df_offers_treat = df_treat[df_treat["event_type"] == "OFFER"].copy()
    total_offers_treat = len(df_offers_treat)
    offers_buyer_treat = len(df_offers_treat[df_offers_treat["proposer_role"] == "B"])
    offers_seller_treat = len(df_offers_treat[df_offers_treat["proposer_role"] == "S"])

    st.subheader(f"BASISDATEN {selected_treatment}")
    st.write(f"**Anzahl Spiele:** {df_treat['game_code'].nunique()}")
    st.write(f"**Anzahl Events:** {len(df_game)}")
    st.write(f"**Anzahl Angebote gesamt:** {total_offers_treat}")
    st.write(f"**Anzahl Angebote Käufer:** {offers_buyer_treat}")
    st.write(f"**Anzahl Angebote Verkäufer:** {offers_seller_treat}")
    st.divider()

    # Histogramme (nur all games im treatment)
    st.subheader("Verteilungen im Treatment")
    col_h1, col_h2 = st.columns([1, 1])

    with col_h1:
        if df_eff.empty or "Preis" not in df_eff.columns:
            st.info("Keine Deals (ACCEPT) → keine Einigungspreise.")
        else:
            fig_hist_deals = go.Figure()
            fig_hist_deals.add_trace(go.Histogram(x=df_eff["Preis"].dropna(), nbinsx=20, name="Einigungspreis", marker=dict(color="grey")))
            fig_hist_deals.update_layout(
                xaxis_title="Preis (€)",
                yaxis_title="Häufigkeit",
                height=300,
                margin=dict(l=0, r=0, t=50, b=0),
                xaxis=dict(range=[30, 130]),
            )
            st.plotly_chart(fig_hist_deals, use_container_width=True)

    with col_h2:
        df_offers_treat = df_treat[df_treat["event_type"] == "OFFER"].copy()
        if df_offers_treat.empty or "price" not in df_offers_treat.columns:
            st.info("Keine OFFER-Events im Treatment.")
        else:
            df_b = df_offers_treat[df_offers_treat["proposer_role"] == "B"]
            df_s = df_offers_treat[df_offers_treat["proposer_role"] == "S"]

            fig_hist_offers = go.Figure()
            if not df_b.empty:
                fig_hist_offers.add_trace(go.Histogram(x=df_b["price"].dropna(), nbinsx=20, name="Käufer-Angebote", opacity=0.65, marker=dict(color="blue")))
            if not df_s.empty:
                fig_hist_offers.add_trace(go.Histogram(x=df_s["price"].dropna(), nbinsx=20, name="Verkäufer-Angebote", opacity=0.65, marker=dict(color="red")))

            fig_hist_offers.update_layout(
                xaxis_title="Preis (€)",
                yaxis_title="Häufigkeit",
                barmode="overlay",
                height=300,
                margin=dict(l=0, r=0, t=50, b=0),
                xaxis=dict(range=[30, 130]),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            fig_hist_offers.update_traces(xbins=dict(size=5))
            st.plotly_chart(fig_hist_offers, use_container_width=True)

    st.divider()

    # 3D Charts (treatment)
    if not df_eff.empty:
        st.subheader("Einigungspreis vs. Verhandlungsdauer vs. Anzahl Angebote")
        fig3d = go.Figure(
            data=[
                go.Scatter3d(
                    x=df_eff["Deal-Zeit"],
                    y=df_eff["Anzahl Angebote"],
                    z=df_eff["Preis"],
                    mode="markers",
                    marker=dict(size=6, color=df_eff["Preis"], colorscale="Viridis", opacity=0.8, colorbar=dict(title="Preis (€)")),
                    text=[
                        f"Spiel: {row.Spiel}"
                        f"<br>Dauer: {row['Deal-Zeit']:.2f}s"
                        f"<br>Anzahl Angebote: {row['Anzahl Angebote']}"
                        f"<br>Preis: {row['Preis']:.2f}€"
                        for _, row in df_eff.iterrows()
                    ],
                    hoverinfo="text",
                )
            ]
        )
        fig3d.update_layout(
            scene=dict(
                xaxis_title="Verhandlungsdauer (s)",
                yaxis_title="Anzahl Angebote",
                zaxis_title="Einigungspreis (€)",
                camera=dict(eye=dict(x=0.1, y=2.3, z=0.8)),
            ),
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
        )

        st.subheader("Netto Käufer vs. Netto Verkäufer vs. Verhandlungsdauer")
        fig3d_net = go.Figure(
            data=[
                go.Scatter3d(
                    x=df_eff["Netto Käufer"],
                    y=df_eff["Netto Verkäufer"],
                    z=df_eff["Deal-Zeit"],
                    mode="markers",
                    marker=dict(size=6, color=df_eff["Deal-Zeit"], colorscale="Plasma", opacity=0.8, colorbar=dict(title="Dauer (s)")),
                    text=[
                        f"Spiel: {row.Spiel}"
                        f"<br>Netto Käufer: {row['Netto Käufer']:.2f}€"
                        f"<br>Netto Verkäufer: {row['Netto Verkäufer']:.2f}€"
                        f"<br>Dauer: {row['Deal-Zeit']:.2f}s"
                        for _, row in df_eff.iterrows()
                    ],
                    hoverinfo="text",
                )
            ]
        )
        fig3d_net.update_layout(
            scene=dict(
                xaxis_title="Netto Käufer (€)",
                yaxis_title="Netto Verkäufer (€)",
                zaxis_title="Verhandlungsdauer (s)",
                camera=dict(eye=dict(x=0.1, y=2.3, z=0.8)),
            ),
            height=600,
            margin=dict(l=0, r=0, t=0, b=0),
        )

        col_small1, col_small2 = st.columns([1, 1])
        with col_small1:
            st.plotly_chart(fig3d, use_container_width=True)
        with col_small2:
            st.plotly_chart(fig3d_net, use_container_width=True)

        st.divider()

    # Sidebar: aggregierte Kennzahlen (nur all games)
    if df_eff.empty:
        st.sidebar.info("Keine Spiele mit ACCEPT-Event in diesem Treatment.")
    else:
        avg_eff = df_eff["Effizienz"].mean(skipna=True)
        med_eff = df_eff["Effizienz"].median(skipna=True)
        avg_treat_t = df_eff["Deal-Zeit"].mean(skipna=True)
        med_treat_t = df_eff["Deal-Zeit"].median(skipna=True)

        st.sidebar.metric("Effizienz (arithm. Mittel)", f"{avg_eff:.1%}")
        st.sidebar.metric("Effizienz (Median)", f"{med_eff:.1%}")
        st.sidebar.metric("Verhandlungsdauer (arithm. Mittel)", f"{avg_treat_t:.2f} s")
        st.sidebar.metric("Verhandlungsdauer (Median)", f"{med_treat_t:.2f} s")

    # Streudiagramm Deals nach Effizienz (nur all games)
    st.divider()
    if df_eff.empty:
        st.info("Keine Spiele mit ACCEPT-Event in diesem Treatment.")
    else:
        st.markdown("### Streudiagramm der Deals nach Effizienz")
        fig_scatter = go.Figure()
        fig_scatter.add_trace(
            go.Scatter(
                x=df_eff["Deal-Zeit"],
                y=df_eff["Preis"],
                mode="markers",
                marker=dict(size=12, color=df_eff["Effizienz"], colorscale="RdYlGn", showscale=True, colorbar=dict(title="Effizienz")),
                text=[
                    f"Spiel: {row.Spiel}"
                    f"<br>Zeit: {row['Deal-Zeit']:.2f}s"
                    f"<br>Preis: {row['Preis']:.2f}€"
                    f"<br>Effizienz: {row['Effizienz']:.1%}"
                    for _, row in df_eff.iterrows()
                ],
                hoverinfo="text",
                name="Reale Deals",
            )
        )
        fig_scatter.add_hline(y=df_eff["MinKosten"].iloc[0], line_dash="dash", line_color="red", annotation_text="Min. Kosten Verkäufer")
        fig_scatter.add_hline(y=df_eff["Budget"].iloc[0], line_dash="dash", line_color="blue", annotation_text="Max. Budget Käufer")
        fig_scatter.update_layout(xaxis_title="Zeitpunkt der Einigung (s)", yaxis_title="Vereinbarter Preis (€)", height=600)
        st.plotly_chart(fig_scatter, use_container_width=True)

# =========================================================
# VISUALISIERUNG 3: ANGEBOTE & DEALS (REAL, ÜBER ZEIT)
# (läuft für Single und All-Games-Treatment, aber NICHT global)
# =========================================================
st.subheader("Zeitlicher Verlauf der Angebote")

df_offers = df_game[df_game["event_type"] == "OFFER"].copy()
df_accept = df_game[df_game["event_type"] == "ACCEPT"].copy()

if df_offers.empty:
    st.info("Keine OFFER-Events für diese Auswahl vorhanden.")
else:
    fig_real = go.Figure()
    df_offers = df_game[df_game["event_type"] == "OFFER"].copy()
    df_offers = df_offers.sort_values(["game_code", "time_relative"])
    df_offers["offer_index"] = df_offers.groupby(["game_code", "proposer_role"]).cumcount() + 1


    df_k = df_offers[df_offers["proposer_role"] == "B"]
    if not df_k.empty:
        fig_real.add_trace(
            go.Scatter(
                x=df_k["time_relative"],
                y=df_k["price"],
                mode="markers",
                name="Angebote Käufer",
                marker=dict(size=10, color="blue", symbol="circle"),
                text=offer_hover_text(df_k),
                hoverinfo="text",
            )
        )

    df_v = df_offers[df_offers["proposer_role"] == "S"]
    if not df_v.empty:
        fig_real.add_trace(
            go.Scatter(
                x=df_v["time_relative"],
                y=df_v["price"],
                mode="markers",
                name="Angebote Verkäufer",
                marker=dict(size=10, color="red", symbol="circle"),
                text=offer_hover_text(df_v),
                hoverinfo="text",
            )
        )

    if not df_accept.empty:
        fig_real.add_trace(
            go.Scatter(
                x=df_accept["time_relative"],
                y=df_accept["price"],
                mode="markers",
                name="Einigung (ACCEPT)",
                marker=dict(size=16, symbol="x", color="#FFF59D", line=dict(width=2, color="#FBC02D")),
                text=accept_hover_text(df_accept),
                hoverinfo="text",
            )
        )


    if single_game_view:
        # nur in single mode sind seller_cost/buyer_val definiert -> sicherer guard
        fig_real.add_hline(y=seller_cost, line_dash="dash", annotation_text="Kosten Verkäufer", annotation_position="bottom right")
        fig_real.add_hline(y=buyer_val, line_dash="dash", annotation_text="Budget Käufer", annotation_position="top right")

    fig_real.update_layout(
        xaxis_title="Zeit (s)",
        yaxis_title="Preis (€)",
        height=500,
        margin=dict(l=0, r=100, t=40, b=0),
        legend=dict(orientation="v", xanchor="left", x=1.02, yanchor="top", y=1),
    )
    st.plotly_chart(fig_real, use_container_width=True)

    # =========================================================
# VISUALISIERUNG 4: PREISVERLAUF NACH ANGEBOTSNUMMER
# =========================================================

st.divider()
st.subheader("Preisverlauf nach Angebotsnummer")

if df_offers.empty:
    st.info("Keine OFFER-Events für diese Auswahl vorhanden.")
else:
    fig_seq = go.Figure()

    if single_game_view:
        # Innerhalb eines Spiels: Reihenfolge nach Zeit
        df_offers_sorted = df_offers.sort_values("time_relative").copy()

        # Käufer
        df_k_seq = df_offers_sorted[df_offers_sorted["proposer_role"] == "B"].copy()
        df_k_seq["offer_index"] = range(1, len(df_k_seq) + 1)

        # Verkäufer
        df_v_seq = df_offers_sorted[df_offers_sorted["proposer_role"] == "S"].copy()
        df_v_seq["offer_index"] = range(1, len(df_v_seq) + 1)

        if not df_k_seq.empty:
            fig_seq.add_trace(
                go.Scatter(
                    x=df_k_seq["offer_index"],
                    y=df_k_seq["price"],
                    mode="lines+markers",
                    name="Käufer",
                    line=dict(color="blue"),
                    marker=dict(symbol="circle", size=8, color="blue"),
                    text=offer_hover_text(df_k_seq),
                    hoverinfo="text"

                )
            )

        if not df_v_seq.empty:

            fig_seq.add_trace(
                go.Scatter(
                    x=df_v_seq["offer_index"],
                    y=df_v_seq["price"],
                    mode="lines+markers",
                    name="Verkäufer",
                    line=dict(color="red"),
                    text=offer_hover_text(df_k_seq),
                    hoverinfo="text"
                )
            )

        # Einigung als X-Punkt am Ende
        if last_accept is not None:
            deal_price_seq = float(last_accept.get("agreed_price", np.nan))
            if np.isnan(deal_price_seq):
                deal_price_seq = float(last_accept.get("price", np.nan))

            max_index = max(
                len(df_k_seq) if not df_k_seq.empty else 0,
                len(df_v_seq) if not df_v_seq.empty else 0,
            )
            x_agree = max_index + 1 if max_index > 0 else 1

            fig_seq.add_trace(
                go.Scatter(
                    x=[x_agree],
                    y=[deal_price_seq],
                    mode="markers",
                    name="Einigung",
                    marker=dict(symbol="x", size=14, color="yellow"),
                    text=[f"Einigung<br>Preis: {deal_price_seq:.2f}€"],
                    hoverinfo="text",
                )
            )


    else:
        # Alle Spiele: pro Spiel eigene Sequenz, aber gemeinsame Legende
        df_offers_sorted = df_offers.sort_values(["game_code", "time_relative"]).copy()

        first_buyer = True
        first_seller = True

        for game_code, df_game_offers in df_offers_sorted.groupby("game_code"):
            # Käufer
            df_k = df_game_offers[df_game_offers["proposer_role"] == "B"].copy()
            if not df_k.empty:
                df_k["offer_index"] = range(1, len(df_k) + 1)
                k_text = [
                    f"Spiel: {game_code}"
                    f"<br>Rolle: Käufer"
                    f"<br>Angebotsnr.: {row['offer_index']}"
                    f"<br>Zeit: {row['time_relative']:.2f}s"
                    f"<br>Preis: {row['price']:.2f}€"
                    for _, row in df_k.iterrows()
                ]
                fig_seq.add_trace(
                    go.Scatter(
                        x=df_k["offer_index"],
                        y=df_k["price"],
                        mode="lines+markers",
                        name="Käufer",
                        legendgroup="Käufer",
                        showlegend=first_buyer,
                        line=dict(color="blue"),
                        marker=dict(symbol="circle", size=6, color="blue"),
                        text=k_text,
                        hoverinfo="text",
                    )
                )
                first_buyer = False

            # Verkäufer
            df_v = df_game_offers[df_game_offers["proposer_role"] == "S"].copy()
            if not df_v.empty:
                df_v["offer_index"] = range(1, len(df_v) + 1)
                v_text = [
                    f"Spiel: {game_code}"
                    f"<br>Rolle: Verkäufer"
                    f"<br>Angebotsnr.: {row['offer_index']}"
                    f"<br>Zeit: {row['time_relative']:.2f}s"
                    f"<br>Preis: {row['price']:.2f}€"
                    for _, row in df_v.iterrows()
                ]
                fig_seq.add_trace(
                    go.Scatter(
                        x=df_v["offer_index"],
                        y=df_v["price"],
                        mode="lines+markers",
                        name="Verkäufer",
                        legendgroup="Verkäufer",
                        showlegend=first_seller,
                        line=dict(color="red"),
                        marker=dict(symbol="circle", size=6, color="red"),
                        text=v_text,
                        hoverinfo="text",
                    )
                )
                first_seller = False


    fig_seq.update_layout(
        xaxis_title="Angebotsnummer (innerhalb eines Spiels)",
        yaxis_title="Preis (€)",
        height=450,
        margin=dict(l=0, r=100, t=40, b=0),
        legend=dict(orientation="v", xanchor="left", x=1.02, yanchor="top", y=1),
    )

    st.plotly_chart(fig_seq, use_container_width=True)


# =========================================================
# TABELLEN (nicht global)
# =========================================================
st.divider()
st.subheader("Kompakte Übersicht")

base_cols = ["time_relative", "event_type", "proposer_role", "B_Gross", "B_Net", "S_Gross", "S_Net"]
cols_present = [c for c in base_cols if c in df_game.columns]

if cols_present:
    tbl = df_game[cols_present].copy()
    if "proposer_role" in tbl.columns:
        tbl["proposer_role"] = tbl["proposer_role"].apply(role_human)

    rename_map = {
        "B_Gross": "Brutto Käufer",
        "B_Net": "Netto Käufer",
        "S_Gross": "Brutto Verkäufer",
        "S_Net": "Netto Verkäufer",
        "time_relative": "Zeit (s)",
    }
    tbl = tbl.rename(columns={k: v for k, v in rename_map.items() if k in tbl.columns})

    if "Zeit (s)" in tbl.columns:
        tbl = tbl.sort_values("Zeit (s)")
    st.dataframe(tbl, use_container_width=True, hide_index=True)
else:
    st.info("Keine passenden Spalten für die Übersichtstabelle gefunden.")

st.divider()
st.subheader("Rohdaten")
if "event_id" in df_game.columns:
    df_show = df_game.sort_values(["time_relative", "event_id"])
else:
    df_show = df_game.sort_values(["time_relative"])
st.dataframe(df_show, use_container_width=True, hide_index=True)
