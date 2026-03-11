import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# ==========================================
# KONFIGURATION & SETUP
# ==========================================
st.set_page_config(page_title="Verhandlungs-Analyse", layout="wide")

st.title("Diskontrates und Simulation")
st.markdown("""
Bachelor Projekt - Gruppe 2
            """)

# ==========================================
# SIDEBAR (LINKS): PARAMETER
# ==========================================
st.sidebar.header("PARAMETER")

st.sidebar.subheader("Transaktionswerte")
buyer_val = st.sidebar.number_input("Budget Käufer $V$", value=130.0, step=10.0)
seller_cost = st.sidebar.number_input("Kosten Verkäufer $C$", value=30.0, step=10.0)

st.sidebar.subheader("Diskontierungsrate $r$")
r_buyer_pct = st.sidebar.slider(
    "Käufer $r_B$ (% pro s)", 
    min_value=0.0, max_value=5.0, value=0.5, step=0.1
)
r_seller_pct = st.sidebar.slider(
    "Verkäufer $r_S$ (% pro s)",
    min_value=0.0, max_value=5.0, value=1.0, step=0.1
)

# Umrechnung
r_buyer = r_buyer_pct / 100.0
r_seller = r_seller_pct / 100.0

sim_duration = st.sidebar.slider("Verhandlungszeit $t$", 30, 300, 120)
fixed_price = st.sidebar.slider(
    "Vereinbarter Preis $P$", 
    min_value=float(seller_cost), 
    max_value=float(buyer_val), 
    value=(buyer_val+seller_cost)/2
)

st.sidebar.divider()

# --- MONTE CARLO PARAMETER ---
st.sidebar.subheader("Monte Carlo")
mc_simulations = st.sidebar.slider(
    "Anzahl Simulationen", 
    min_value=100, max_value=5000, value=1000, step=100,
    help="Wie viele zufällige Deals sollen simuliert werden?"
)
mc_seed = st.sidebar.number_input(
    "Seed", 
    value=42, step=1,
    help="Ändere diese Zahl, um eine neue zufällige Verteilung zu würfeln."
)

# --- NEU: ZUSATZPARAMETER FÜR NORMALVERTEILUNG ---
st.sidebar.subheader("Verteilung (Preis)")
mc_std_dev = st.sidebar.slider(
    "Standardabweichung $\sigma$ (Preis)", 
    min_value=1.0, max_value=50.0, value=15.0, step=1.0,
    help="Steuert, wie stark die Preise um die Mitte (Fair Share) streuen."
)

# ==========================================
# BERECHNUNG (Statisch)
# ==========================================
t = np.linspace(0, sim_duration, num=sim_duration+1)

# Faktoren
factor_buyer = np.exp(-r_buyer * t)
factor_seller = np.exp(-r_seller * t)

# Brutto (Surplus)
surplus_buyer_gross = buyer_val - fixed_price
surplus_seller_gross = fixed_price - seller_cost
total_gross = surplus_buyer_gross + surplus_seller_gross
mid_price = (buyer_val + seller_cost) / 2 # Mitte des Verhandlungsspielraums

# Netto (Auszahlung)
net_buyer = surplus_buyer_gross * factor_buyer
net_seller = surplus_seller_gross * factor_seller
total_net = net_buyer + net_seller

# ==========================================
# VISUALISIERUNG 1 & 2
# ==========================================

# --- ABSCHNITT 1: DISKONTFAKTOREN ---
st.markdown("### Verlauf der Diskontfaktoren")
col_chart1, col_form1 = st.columns([3, 1]) 

with col_chart1:
    fig_factors = go.Figure()
    fig_factors.add_trace(go.Scatter(x=t, y=factor_buyer, mode='lines', name=f'Käufer', line=dict(color='blue', width=3)))
    fig_factors.add_trace(go.Scatter(x=t, y=factor_seller, mode='lines', name=f'Verkäufer', line=dict(color='red', width=3)))
    
    fig_factors.update_layout(
        xaxis_title="Zeit t", yaxis_title="Faktor", 
        yaxis_range=[0, 1.05], height=550, margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_factors, use_container_width=True)

with col_form1:
    st.markdown(f":blue[**Käufer:**]")
    st.latex(r"\delta_B(t) = e^{-r_B \cdot t}")
    st.caption(f"Rate $r_B = {r_buyer_pct}\%$")
    st.divider()
    st.markdown(f":red[**Verkäufer:**]")
    st.latex(r"\delta_S(t) = e^{-r_S \cdot t}")
    st.caption(f"Rate $r_S = {r_seller_pct}\%$")


st.divider()

# --- ABSCHNITT 2: NETTO-AUSZAHLUNGEN ---
st.markdown(f"### Netto-Auszahlung (bei $P$ = {fixed_price} EUR)")
col_chart2, col_form2 = st.columns([3, 1])

with col_chart2:
    fig_money = go.Figure()
    fig_money.add_trace(go.Scatter(x=t, y=net_buyer, mode='lines', name='Auszahlung Käufer', line=dict(color='blue', width=2)))
    fig_money.add_trace(go.Scatter(x=t, y=net_seller, mode='lines', name='Auszahlung Verkäufer', line=dict(color='red', width=2)))
    fig_money.add_trace(go.Scatter(x=t, y=total_net, mode='lines', name='Gesamt-Surplus', line=dict(color='green', dash='dot', width=2)))
    fig_money.add_hline(y=total_gross, line_dash="dash", line_color="grey")

    fig_money.update_layout(
        xaxis_title="Zeit t", yaxis_title="EUR", 
        height=550, margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_money, use_container_width=True)

with col_form2:
    st.markdown(f":blue[**Käufer Payoff:**]")
    st.latex(r"u_B(t) = (V - P) \cdot e^{-r_B t}")
    st.divider()
    st.markdown(f":red[**Verkäufer Payoff:**]")
    st.latex(r"u_S(t) = (P - C) \cdot e^{-r_S t}")
    st.divider()
    st.markdown(f":green[**Gesamt-Surplus:**]")
    st.latex(r"\Pi(t) = u_B(t) + u_S(t)")

# ==========================================
# MONTE CARLO SIMULATION 1: UNIFORM
# ==========================================
st.divider()
st.subheader("Monte Carlo / Zero-Intelligence-Agents (Uniform Distribution)")
st.markdown(f"""
Hier werden **{mc_simulations} Verhandlungen** simuliert. Jeder Punkt ist eine Einigung zu einem zufälligen Zeitpunkt $t$ und Preis $P$.
""")
st.markdown(f"""
**Annahmen:**
* **Totale Irrationalität:** Der Ausgang hängt vom Zufall und nicht von individuellen Strategien ab.
* **Unabhängigkeit von Zeit und Preis:** Der vereinbarte Preis ist unabhängig von der Verhandlungsdauer.
* **Gleichverteilung aller Preise:** Jeder Preis zwischen {int(seller_cost)} und {int(buyer_val)} ist gleich wahrscheinlich (was in echten Verhandlungen extrem unwahrscheinlich ist).
""")

col_mc1, col_mc2 = st.columns([3, 1])

# Zufall initialisieren (mit Seed aus der Sidebar)
np.random.seed(mc_seed)

# 1. Zufällige Zeiten (Gleichverteilt zwischen 0 und sim_duration)
sim_times = np.random.uniform(0, sim_duration, mc_simulations)

# 2. Zufällige Preise (Gleichverteilt zwischen Kosten und Budget)
sim_prices = np.random.uniform(seller_cost, buyer_val, mc_simulations)

# 3. Payoffs berechnen
mc_payoff_buyer = (buyer_val - sim_prices) * np.exp(-r_buyer * sim_times)
mc_payoff_seller = (sim_prices - seller_cost) * np.exp(-r_seller * sim_times)

# 4. Effizienz berechnen (Wieviel % vom Brutto-Surplus sind noch da?)
mc_total_net = mc_payoff_buyer + mc_payoff_seller
mc_efficiency = mc_total_net / total_gross # 0.0 bis 1.0

with col_mc1:
    fig_mc = go.Figure()

    fig_mc.add_trace(go.Scatter(
        x=sim_times,
        y=sim_prices,
        mode='markers',
        marker=dict(
            size=6,
            color=mc_efficiency, # Farbe nach Effizienz
            colorscale='RdYlGn', # Rot (schlecht) bis Grün (gut)
            showscale=True,
            colorbar=dict(title="Effizienz")
        ),
        text=[f"Zeit: {t:.1f}s<br>Preis: {p:.2f}€<br>Effizienz: {e:.1%}" for t, p, e in zip(sim_times, sim_prices, mc_efficiency)],
        hoverinfo='text',
        name='Simulierte Deals'
    ))

    # Referenzlinien
    fig_mc.add_hline(y=seller_cost, line_dash="dash", line_color="red", annotation_text="Min. Kosten")
    fig_mc.add_hline(y=buyer_val, line_dash="dash", line_color="blue", annotation_text="Max. Budget")

    fig_mc.update_layout(
        xaxis_title="Zeitpunkt der Einigung (t)",
        yaxis_title="Vereinbarter Preis (P)",
        height=600,
        title=f"Gleichverteilung (Uniform)"
    )
    st.plotly_chart(fig_mc, use_container_width=True)

with col_mc2:
    st.markdown("#### Legende")
    st.success("**Hohe Effizienz (Grün):**\nFrühe Einigung. Der Überschuss wurde fast vollständig verteilt.")
    st.error("**Niedrige Effizienz (Rot):**\nSpäte Einigung. Der Zeitwertverlust hat den Großteil des Überschusses vernichtet.")
    
    avg_eff = np.mean(mc_efficiency)
    st.metric(label="Ø Effizienz (Uniform)", value=f"{avg_eff:.1%}")
    
    st.markdown("---")
    st.caption(f"Parameter: N={mc_simulations}, Seed={mc_seed}")


# ==========================================
# NEU: MONTE CARLO SIMULATION 2: NORMAL
# ==========================================
st.divider()
st.subheader("Monte Carlo / Zero-Intelligence-Agents (Normal Distribution))")
st.markdown(f"""
**Annahmen:**
* **Zeit ($t$):** Weiterhin gleichverteilt (Uniform), da Einigungszeitpunkte schwer vorhersagbar sind.
* **Preis ($P$):** Normalverteilt um den Mittelwert **{mid_price:.0f} EUR** mit Standardabweichung $\sigma$. 
* Preise in der Mitte (fair share) sind wahrscheinlicher sind als Preise am Rand.
""")

col_mc3, col_mc4 = st.columns([3, 1])

# Zufall neu initialisieren
np.random.seed(mc_seed + 1) # +1 damit das Muster anders ist als oben

# 1. Zufällige Zeiten (Gleichverteilt)
sim_times_norm = np.random.uniform(0, sim_duration, mc_simulations)

# 2. Zufällige Preise (Normalverteilt)
# Wir clippen die Preise, damit sie nicht unter Kosten oder über Budget gehen
raw_prices_norm = np.random.normal(mid_price, mc_std_dev, mc_simulations)
sim_prices_norm = np.clip(raw_prices_norm, seller_cost, buyer_val)

# 3. Payoffs berechnen
mc_payoff_buyer_norm = (buyer_val - sim_prices_norm) * np.exp(-r_buyer * sim_times_norm)
mc_payoff_seller_norm = (sim_prices_norm - seller_cost) * np.exp(-r_seller * sim_times_norm)

# 4. Effizienz berechnen
mc_total_net_norm = mc_payoff_buyer_norm + mc_payoff_seller_norm
mc_efficiency_norm = mc_total_net_norm / total_gross

with col_mc3:
    fig_mc_norm = go.Figure()

    fig_mc_norm.add_trace(go.Scatter(
        x=sim_times_norm,
        y=sim_prices_norm,
        mode='markers',
        marker=dict(
            size=6,
            color=mc_efficiency_norm, 
            colorscale='RdYlGn', 
            showscale=True,
            colorbar=dict(title="Effizienz")
        ),
        text=[f"Zeit: {t:.1f}s<br>Preis: {p:.2f}€<br>Effizienz: {e:.1%}" for t, p, e in zip(sim_times_norm, sim_prices_norm, mc_efficiency_norm)],
        hoverinfo='text',
        name='Simulierte Deals'
    ))

    # Referenzlinien
    fig_mc_norm.add_hline(y=mid_price, line_dash="dash", line_color="gray", annotation_text="Mittelwert")
    fig_mc_norm.add_hline(y=seller_cost, line_dash="dash", line_color="red")
    fig_mc_norm.add_hline(y=buyer_val, line_dash="dash", line_color="blue")

    fig_mc_norm.update_layout(
        xaxis_title="Zeitpunkt der Einigung (t)",
        yaxis_title="Vereinbarter Preis (P)",
        height=600,
        title=f"Normalverteilung (mit $\sigma={mc_std_dev}$)"
    )
    st.plotly_chart(fig_mc_norm, use_container_width=True)

with col_mc4:
    st.markdown("#### Legende")    
    avg_eff_norm = np.mean(mc_efficiency_norm)
    st.metric(label="Ø Effizienz (Normal)", value=f"{avg_eff_norm:.1%}")
    
    st.markdown("---")
    st.caption(f"Parameter: $\sigma={mc_std_dev}$")


# ==========================================
# DATEN TABELLE
# ==========================================
st.divider()
st.subheader("Tabelle")

check_times = [0, 10, 20, 30, 60, 90, 120]
check_times = [x for x in check_times if x <= sim_duration]

data = []
for ct in check_times:
    nb = surplus_buyer_gross * np.exp(-r_buyer * ct)
    ns = surplus_seller_gross * np.exp(-r_seller * ct)
    tn = nb + ns
    data.append({
        "Zeit t": ct,
        "Käufer (€)": f"{nb:.2f}",
        "Verkäufer (€)": f"{ns:.2f}",
        "Gesamt (€)": f"{tn:.2f}",
        "Verlust (€)": f"{(total_gross - tn):.2f}"
    })

st.dataframe(pd.DataFrame(data), use_container_width=True)