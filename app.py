from __future__ import annotations

import asyncio
import hashlib
import os
import random
import secrets
import string
import time
import math
import csv
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from fastapi import FastAPI, Form, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict

# =============================================================================
# FastAPI / Templates / Static
# =============================================================================

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/videos", StaticFiles(directory="videos"), name="videos")
templates = Jinja2Templates(directory="templates")

# =============================================================================
# Logging Konfiguration & History-Check
# =============================================================================

LOG_FILE = "games_log.csv"
TEST_LOG_FILE = "testrounds_log.csv"
LOG_FIELDNAMES = [
    "event_id", "game_code", "date", "time", "time_relative", "event_type",
    "treatment_key", "agreed_price", "proposer_role", "price",  # <--- GEÄNDERT (statt P1/P2)
    "accepter_role",
    "B_Gross", "B_Net", "S_Gross", "S_Net",          # <--- GEÄNDERT (statt P1/P2)
    "buyer_value", "seller_cost", "proposer_pid", "accepter_pid",
    "B_rate", "S_rate", "B_cooldown", "S_cooldown", "timestamp_abs"
]

# Dieses Set speichert ALLE jemals verwendeten Codes (aus CSV + laufende Session)
USED_GAME_CODES: Set[str] = set()

def load_existing_codes_from_csv():
    """Liest beim Start alle bereits verwendeten Game-Codes aus der CSV ein."""
    if not os.path.exists(LOG_FILE):
        return

    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            # Wir nutzen DictReader mit dem korrekten Trennzeichen
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                c = row.get("game_code")
                if c:
                    USED_GAME_CODES.add(c)
        print(f"[INFO] {len(USED_GAME_CODES)} vergangene Lobby-Codes aus CSV geladen.")
    except Exception as e:
        print(f"[WARN] Konnte CSV nicht lesen oder parsen: {e}")

def log_game_event(row_data: dict):
    """Fügt eine Zeile zum zentralen CSV-Log hinzu."""
    file_exists = os.path.exists(LOG_FILE)
    
    try:
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=LOG_FIELDNAMES, delimiter=';')
            
            if not file_exists:
                writer.writeheader()
                
            writer.writerow(row_data)
    except Exception as e:
        print(f"ERROR writing to log file: {e}")

def log_test_event(row_data: dict):
    """Fügt eine Zeile zum TEST-Log (Übungsrunde) hinzu."""
    file_exists = os.path.exists(TEST_LOG_FILE)
    try:
        with open(TEST_LOG_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=LOG_FIELDNAMES, delimiter=';')
            if not file_exists:
                writer.writeheader()
            writer.writerow(row_data)
    except Exception as e:
        print(f"ERROR writing to test log file: {e}")

# =============================================================================
# Treatments
# =============================================================================


# --- BASIS-INSTRUKTIONEN (Wird für alle Treatments wiederverwendet) ---
BASE_INSTRUCTIONS_HTML = """
          <h2 style='margin:0 0 10px;'>Instruktionen</h2>

          <div id="roleAlert" style="background:#e0f2fe; color:#0369a1; padding:15px; border-radius:8px; margin-bottom:15px; border:1px solid #bae6fd; font-size:1.1rem;">
             Ihre Rolle: <strong>{me}</strong>
          </div>

          <p>Sie sind {me} und verhandeln mit ihrem {opp_dat} über den Preis eines Gutes.</p>

          <p>
          Der Käufer hat ein Budget von {bv} EUR<br>
          Der Verkäufer hat Kosten von {sc} EUR<br>
          Die Preisverhandlung findet im Bereich von {sc} EUR und {bv} EUR statt
          </p>

          <p><strong>Angebote</strong></p>
          <ul>
            <li>Sie können zu jeder Zeit Angebote senden, wenn Sie sich außerhalb der Wartezeit befinden</li>
            <li>Sie und der {opp} haben eine Wartezeit von {cd} Sekunden und gibt Ihnen die Gelegenheit über die derzeitigen Angebote nachzudenken</li>
            <li>In dieser Wartezeit können Sie weder Angebote senden, noch Angebote des {opp_gen} annehmen</li>
            <li>Die Wartezeit beginnt, wenn Sie dem {opp} ein Angebot geschickt haben</li>
            <li>Die Verhandlung endet, wenn Sie das Angebot des {opp_gen} annehmen oder der {opp} Ihr Angebot annimmt</li>
          </ul>

          <p><strong>Ihr Bruttogewinn</strong></p>
          <ul>
            <li>Als Käufer: {bv} EUR minus vereinbarter Preis</li>
            <li>Als Verkäufer: Vereinbarter Preis minus {sc} EUR</li>
          </ul>

        <p><strong>Zeit kostet Sie Geld</strong></p>
        <ul>
        <li>Ihr Nettogewinn reduziert sich pro Sekunde prozentual um Ihren eigenen Kostenfaktor von <strong>{my_cost_factor}%</strong></li>
        <li>{opp_cost_factor_text}</li>
        <li>{profit_info_text}</li> 
        </ul>
        <p><strong>Testrunde</strong></p>
        <ul>
        <li>Bevor die richtige Verhandlung beginnt, werden Sie mit einem <strong>Computer</strong> als {opp} eine Testrunde durchführen, die nicht ausgewertet wird</li>
        </ul>
        <p><strong>Bitte beantworten Sie unseren Fragebogen nach der Verhandlung</strong></p>

        """.strip()


TREATMENTS: Dict[str, dict] = {

    "T1": {
        "label": "T1",
        "discount_rate_per_role": {"B": 0.001, "S": 0.001},  # <--- B / S
        "cooldown_per_role": {"B": 10.0, "S": 10.0},         # <--- B / S
        "buyer_value": 130.0,
        "seller_cost": 30.0,
        "instructions_html": BASE_INSTRUCTIONS_HTML
    },

    "T2": {
        "label": "T2",
        "discount_rate_per_role": {"B": 0.005, "S": 0.001},  # <--- B / S
        "cooldown_per_role": {"B": 10.0, "S": 10.0},         # <--- B / S
        "buyer_value": 130.0,
        "seller_cost": 30.0,
        "instructions_html": BASE_INSTRUCTIONS_HTML
    },

    "T3": {
        "label": "T3",
        "discount_rate_per_role": {"B": 0.005, "S": 0.001},  # <--- B / S
        "cooldown_per_role": {"B": 10.0, "S": 10.0},         # <--- B / S
        "buyer_value": 130.0,
        "seller_cost": 30.0,
        "instructions_html": BASE_INSTRUCTIONS_HTML,
        "hide_opponent_discount": True
    },
}


# =============================================================================
# Logging Konfiguration (FRAGEBOGEN)
# =============================================================================


QUESTIONNAIRE_FILE = "fragebogen.csv"

QUESTIONNAIRE_FIELDS = [
    # Zeitstempel

    # Metadaten
    "game_code", "date", "time", "role", "timestamp_abs",
    "pid", "treatment_key", 
    "buyer_value", "seller_cost", 
    "discount_rate", "cooldown", 
    "agreed_price", 
    "who_accepted_role",
    
    # Antworten
    "q_satisfaction", 
    "q_t2_cost_impact",
    "q_patience", 
    "q_t3_disclosure_impact",
    "q_t3_time_pressure",
    "q_t3_hidden_costs",
    "q_primary_factor",
    "q_offer_perception",
    "q_experience",
    
    # Demografie
    "q_education",
    "q_education_other",
    "q_gender", 
    "q_is_student",
    "q_study_field",
    "q_study_field_other"
    # q_courses ist hier entfernt
]
def log_questionnaire(row_data: dict):
    """Speichert eine Zeile in fragebogen.csv"""
    file_exists = os.path.exists(QUESTIONNAIRE_FILE)
    try:
        with open(QUESTIONNAIRE_FILE, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=QUESTIONNAIRE_FIELDS, delimiter=';')
            if not file_exists:
                writer.writeheader()
            writer.writerow(row_data)
    except Exception as e:
        print(f"ERROR writing questionnaire: {e}")


# --- DIESEN BLOCK IN APP.PY EINFÜGEN ---

@app.get("/questionnaire/{code}/{pid}", response_class=HTMLResponse)
async def get_questionnaire(request: Request, code: str, pid: str):
    lobby = lobbies.get(code)
    
    # Falls Lobby oder Spieler nicht existieren
    if not lobby:
        return HTMLResponse("<h1>Fehler 404</h1><p>Lobby nicht gefunden.</p>", status_code=404)
    if pid not in lobby.players:
        return HTMLResponse("<h1>Fehler 404</h1><p>Spieler nicht gefunden.</p>", status_code=404)
    
    # Zeige die HTML-Datei an
    return templates.TemplateResponse("questionnaire.html", {
        "request": request,
        "code": code,
        "pid": pid,
        "treatment": lobby.treatment_key
    })

# 2. Diese Route speichert die Daten (hatten wir schon, hier zur Sicherheit nochmal komplett)
@app.post("/submit_questionnaire")
async def submit_questionnaire(
    request: Request,
    code: str = Form(...),
    pid: str = Form(...),
    
    # Formularfelder
    q_satisfaction: str = Form(""),
    q_t2_cost_impact: str = Form(""),
    q_patience: str = Form(""),
    q_t3_disclosure_impact: str = Form(""),
    q_t3_time_pressure: str = Form(""),
    q_t3_hidden_costs: str = Form(""),
    q_primary_factor: str = Form(""),
    q_offer_perception: str = Form(""),
    q_experience: str = Form(""),
    
    # Demografie
    q_education: str = Form(""),
    q_education_other: str = Form(""), 
    q_gender: str = Form(""),
    q_is_student: str = Form(""),
    q_study_field: str = Form(""),
    q_study_field_other: str = Form("")
    # q_courses entfernt
):
    # 1. Zeitstempel generieren
    current_dt = datetime.now()
    date_str = current_dt.strftime("%Y-%m-%d")
    time_str = current_dt.strftime("%H:%M:%S")
    ts_val   = current_dt.timestamp()

    lobby = lobbies.get(code)
    
    role = "?"
    treatment = "?"
    b_val = 0.0
    s_cost = 0.0
    agreed = 0.0
    accepter_role = "?"
    my_rate = 0.0
    my_cooldown = 0.0
    
    if lobby:
        role = lobby.pid_label.get(pid, "?")
        treatment = lobby.treatment_key
        b_val = lobby.buyer_value
        s_cost = lobby.seller_cost
        agreed = lobby.agreed_price if lobby.agreed_price else 0.0
        
        winner_pid = lobby.winner
        if winner_pid and winner_pid in lobby.pid_label:
            accepter_role = lobby.pid_label[winner_pid]
        elif winner_pid:
            accepter_role = "Unknown"
            
        if role in lobby.discount_rate_per_role:
            my_rate = lobby.discount_rate_per_role[role]
        if role in lobby.cooldown_per_role:
            my_cooldown = lobby.cooldown_per_role[role]

    # Daten zusammenstellen
    data = {
        "date": date_str,
        "time": time_str,
        "timestamp_abs": ts_val,
        
        "game_code": code,
        "pid": pid,
        "role": role,
        "treatment_key": treatment,
        "buyer_value": b_val,
        "seller_cost": s_cost,
        "discount_rate": my_rate,
        "cooldown": my_cooldown,
        "agreed_price": agreed,
        "who_accepted_role": accepter_role, 
        
        # Antworten
        "q_satisfaction": q_satisfaction,
        "q_t2_cost_impact": q_t2_cost_impact,
        "q_patience": q_patience,
        "q_t3_disclosure_impact": q_t3_disclosure_impact,
        "q_t3_time_pressure": q_t3_time_pressure,
        "q_t3_hidden_costs": q_t3_hidden_costs,
        "q_primary_factor": q_primary_factor,
        "q_offer_perception": q_offer_perception,
        "q_experience": q_experience,
        
        "q_education": q_education,
        "q_education_other": q_education_other,
        "q_gender": q_gender,
        "q_is_student": q_is_student,
        "q_study_field": q_study_field,
        "q_study_field_other": q_study_field_other
    }
    
    log_questionnaire(data)
    
    return HTMLResponse("""
    <!doctype html>
    <html lang="de">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Vielen Dank</title>
        <link rel="stylesheet" href="/static/style.css">
      </head>
      <body>
        <div class="wrap" style="text-align:center; margin-top:60px; max-width:600px;">
          <div class="card" style="padding:40px;">
            <h1 style="color:var(--col-buyer); margin-bottom:16px;">Vielen Dank!</h1>
            <p style="font-size:1.1rem; color:var(--muted); margin-bottom:32px;">
                Ihre Antworten wurden erfolgreich gespeichert.<br>
                Das Experiment ist für Sie beendet.
            </p>
            <a href="/" class="btn" style="display:inline-block; text-decoration:none;">Zurück zur Startseite</a>
          </div>
        </div>
      </body>
    </html>
    """)
# =============================================================================
# Konfiguration
# =============================================================================

COUNTDOWN_SECONDS = 3 

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin")
_ADMIN_TOKEN = hashlib.sha256(("adm|" + ADMIN_PASSWORD).encode()).hexdigest()
ADMIN_COOKIE = "admin_auth"

def _is_admin(request: Request) -> bool:
    return request.cookies.get(ADMIN_COOKIE, "") == _ADMIN_TOKEN


# =============================================================================
# Modelle
# =============================================================================

class PlayerState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pid: str
    ws: Any = None

class Offer(BaseModel):
    proposer: str
    price: float
    share_for_proposer: float
    timestamp: float

# --- NEUES MODELL ---
class PracticeSession(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    pid: str
    role: str       
    bot_role: str   
    offers: List[Offer] = []
    
    finished: bool = False
    agreed_price: Optional[float] = None
    last_bot_price: Optional[float] = None

    last_action_ts: float = 0.0      
    last_bot_action_ts: float = 0.0  
    
    started_at: float = 0.0

    # --- NEU: Status für den individuellen Countdown ---
    # "countdown" = 3,2,1 läuft
    # "running"   = Man kann bieten
    state: str = "countdown" 
    countdown_end_at: float = 0.0

class Lobby(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    code: str
    created_at: float
    treatment_key: str = ""
    event_counter: int = 0

    players: Dict[str, PlayerState] = {}
    order: List[str] = []                  
    pid_label: Dict[str, str] = {}

    instr_ack: Dict[str, bool] = {}
    ready: Dict[str, bool] = {}
    
    # NEU: Speichert den Status der Bot-Übungsrunde pro Spieler
    practice_sessions: Dict[str, PracticeSession] = {} 
    
    practice_completed: bool = False

    stage: str = "instr"
    countdown_end_at: float = 0.0

    started: bool = False
    started_at: float = 0.0
    finished: bool = False
    finished_at: float = 0.0
    winner: Optional[str] = None           

    offers: List[Offer] = []               

    # Parameter
    cooldown_per_role: Dict[str, float] = {}          
    discount_rate_per_role: Dict[str, float] = {}     
    buyer_value: float = 130.0
    seller_cost: float = 30.0

    # Metadaten
    last_action_ts: Dict[str, float] = {}  
    last_activity: float = 0.0             

    last_offer_by_role: Dict[str, Optional[Offer]] = {}

    # Ergebnis
    agreed_price: Optional[float] = None
    agreed_offer_role: Optional[str] = None     
    agreed_offer_pid: Optional[str] = None      
    result_payoffs: Dict[str, float] = {}

async def bot_reaction(lobby: Lobby, session: PracticeSession):
    """
    Intelligenterer Bot (Integer-Version):
    - Reagiert auf Hartnäckigkeit des Spielers.
    - Akzeptiert gute Angebote sofort.
    - Akzeptiert mittlere Angebote zufällig.
    - Vermeidet unsinnige Gegenangebote.
    - ALLE ANGEBOTE SIND GANZZAHLEN (INTEGERS).
    """
    # 1. Denkpause
    delay = random.uniform(1.5, 5.0)
    await asyncio.sleep(delay)

    if session.finished:
        return

    # Letztes Angebot des Spielers holen
    human_offers = [o for o in session.offers if o.proposer == session.pid]
    if not human_offers:
        return 
    
    p_offer = human_offers[-1].price # Das Angebot des Spielers

    # --- A) HARTNÄCKIGKEIT ERKENNEN ---
    is_stubborn = False
    if len(human_offers) >= 2:
        prev_offer = human_offers[-2].price
        delta = abs(p_offer - prev_offer)
        if delta < 2.0:
            is_stubborn = True
    
    # Schrittweite festlegen (Concession) -> JETZT ALS GANZZAHL
    if is_stubborn:
        # Größere Schritte: 4, 5, 6, 7, 8 oder 9 Euro
        step = random.randint(4, 9)
    else:
        # Normale Schritte: 2, 3, 4, 5 oder 6 Euro
        step = random.randint(2, 6)

    # --- B) BOT STARTWERTE ---
    if session.last_bot_price is None:
        if session.bot_role == "B":
            session.last_bot_price = 40  # int
        else:
            session.last_bot_price = 120 # int

    # Berechne potenzielles nächstes Angebot (Rohwert)
    next_price_raw = session.last_bot_price
    if session.bot_role == "B": 
        next_price_raw += step
    else: 
        next_price_raw -= step

    # Sicherstellen, dass es eine Ganzzahl bleibt (falls durch float-Rechnung was schief ging)
    next_price_raw = int(next_price_raw)

    # --- C) ENTSCHEIDUNG: ANNEHMEN ODER GEGENANGEBOT? ---
    should_accept = False

    if session.bot_role == "S": 
        # === BOT IST VERKÄUFER ===
        
        # 1. Super Angebot (>= 100)
        if p_offer >= 100:
            should_accept = True
            
        # 2. Mittleres Angebot (80 - 100)
        elif 80 <= p_offer < 100:
            if next_price_raw <= p_offer:
                should_accept = True
            else:
                if random.random() < 0.5:
                    should_accept = True
                    
        # 3. Schlechtes Angebot (< 80)
        else:
            if next_price_raw <= p_offer:
                should_accept = True
            else:
                should_accept = False

    else:
        # === BOT IST KÄUFER ===
        
        # 1. Super Angebot (<= 60)
        if p_offer <= 60:
            should_accept = True
            
        # 2. Mittleres Angebot (60 - 80)
        elif 60 < p_offer <= 80:
            if next_price_raw >= p_offer:
                should_accept = True
            else:
                if random.random() < 0.5:
                    should_accept = True
                    
        # 3. Schlechtes Angebot (> 80)
        else:
            if next_price_raw >= p_offer:
                should_accept = True
            else:
                should_accept = False

    # --- D) DURCHFÜHRUNG ---
    
    if should_accept:
        # === ANNAHME ===
        session.finished = True
        session.agreed_price = p_offer
        
        _log_practice_end(lobby, session, p_offer, "ACCEPT", session.bot_role)

        ws = lobby.players[session.pid].ws
        if ws:
            t_rel = now() - lobby.started_at
            payoffs = calculate_payoffs(p_offer, t_rel, lobby)
            res_payoffs = {session.pid: payoffs[f"{session.role}_Net"]}

            await ws.send_json({
                "type": "practice_ended",
                "price": p_offer,
                "payoffs": res_payoffs
            })
            await ws.send_json({"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=session.pid)})
        
        await check_practice_finished(lobby)
        return

    else:
        # === GEGENANGEBOT SENDEN ===
        
        # Speichern als Integer
        session.last_bot_price = int(next_price_raw)
        
        offer = Offer(
            proposer="BOT",
            price=session.last_bot_price,
            share_for_proposer=0.0,
            timestamp=now()
        )
        session.offers.append(offer)
        
        session.last_bot_action_ts = now()
        
        _log_practice_offer(lobby, session, offer)

        ws = lobby.players[session.pid].ws
        if ws:
            await ws.send_json({"type": "offer", "offer": offer.model_dump()})
            await ws.send_json({"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=session.pid)})


def init_practice_for_player(lobby: Lobby, pid: str):
    """Initialisiert die Bot-Session im Countdown-Modus."""
    role = lobby.pid_label.get(pid, "B")
    bot_role = "S" if role == "B" else "B"
    
    # 3 Sekunden Countdown ab jetzt
    cd_end = now() + 3.0
    
    sess = PracticeSession(
        pid=pid,
        role=role,
        bot_role=bot_role,
        offers=[],
        started_at=0.0, # Wird erst gesetzt, wenn Countdown vorbei ist
        
        # NEU: Start im Countdown-Modus
        state="countdown",
        countdown_end_at=cd_end
    )
    lobby.practice_sessions[pid] = sess
    
    if lobby.stage == "instr":
        lobby.stage = "practice"

    # Startet den Timer im Hintergrund
    asyncio.create_task(_run_practice_countdown(lobby, pid, cd_end))

async def _run_practice_countdown(lobby: Lobby, pid: str, end_time: float):
    """Wartet den Countdown ab und schaltet dann auf 'running'."""
    # Warten bis Zeit abgelaufen
    delay = end_time - now()
    if delay > 0:
        await asyncio.sleep(delay)
        
    # Check ob Spieler noch da ist
    if pid in lobby.practice_sessions:
        sess = lobby.practice_sessions[pid]
        sess.state = "running"
        sess.started_at = now() # Jetzt geht die Zeit los (für Charts/Logs)
        
        # State Update an Client senden (damit Overlay weggeht und Spielfeld kommt)
        if pid in lobby.players and lobby.players[pid].ws:
            await lobby.players[pid].ws.send_json({
                "type": "state", 
                "lobby": lobby_public_state(lobby, recipient_pid=pid)
            })

# Hilfsfunktionen fürs Loggen in der Practice-Session
def _log_practice_offer(lobby, session, offer):
    # Ähnlich wie log_test_event, aber isoliert
    t_abs = now()
    t_rel = t_abs - lobby.started_at
    payoffs = calculate_payoffs(offer.price, t_rel, lobby)
    
    dt_obj = datetime.fromtimestamp(t_abs)
    
    role = session.role if offer.proposer == session.pid else session.bot_role
    
    row = {
        "event_id": lobby.event_counter, # Shared counter, ok
        "game_code": lobby.code,
        "date": dt_obj.strftime("%Y-%m-%d"),
        "time": dt_obj.strftime("%H:%M:%S"),
        "timestamp_abs": t_abs,
        "time_relative": t_rel,
        "event_type": "OFFER",
        "treatment_key": lobby.treatment_key,
        "buyer_value": lobby.buyer_value,
        "seller_cost": lobby.seller_cost,
        "B_rate": lobby.discount_rate_per_role.get("B", 0),
        "S_rate": lobby.discount_rate_per_role.get("S", 0),
        "B_cooldown": lobby.cooldown_per_role.get("B", 0),
        "S_cooldown": lobby.cooldown_per_role.get("S", 0),
        "proposer_pid": "BOT" if offer.proposer == "BOT" else session.pid,
        "proposer_role": role,
        "accepter_pid": "",
        "accepter_role": "",
        "price": offer.price,
        "B_Gross": payoffs["B_Gross"], "B_Net": payoffs["B_Net"],
        "S_Gross": payoffs["S_Gross"], "S_Net": payoffs["S_Net"],
        "agreed_price": ""
    }
    log_test_event(row)

def _log_practice_end(lobby, session, price, event_type, accepter_role_key):
    t_abs = now()
    t_rel = t_abs - lobby.started_at
    payoffs = calculate_payoffs(price, t_rel, lobby)
    dt_obj = datetime.fromtimestamp(t_abs)

    # Wer hat das Angebot gemacht? Das Gegenteil vom Akzeptierer
    proposer_role = "S" if accepter_role_key == "B" else "B"
    proposer_pid = "Unknown" 
    # Wenn Bot akzeptiert (accepter=BotRole), war Mensch Proposer
    if accepter_role_key == session.bot_role:
        proposer_pid = session.pid
    else:
        proposer_pid = "BOT"

    row = {
        "event_id": lobby.event_counter,
        "game_code": lobby.code,
        "date": dt_obj.strftime("%Y-%m-%d"),
        "time": dt_obj.strftime("%H:%M:%S"),
        "timestamp_abs": t_abs,
        "time_relative": t_rel,
        "event_type": event_type,
        "treatment_key": lobby.treatment_key,
        "buyer_value": lobby.buyer_value,
        "seller_cost": lobby.seller_cost,
        "B_rate": lobby.discount_rate_per_role.get("B", 0),
        "S_rate": lobby.discount_rate_per_role.get("S", 0),
        "B_cooldown": lobby.cooldown_per_role.get("B", 0),
        "S_cooldown": lobby.cooldown_per_role.get("S", 0),
        "proposer_pid": proposer_pid,
        "proposer_role": proposer_role,
        "accepter_pid": "BOT" if accepter_role_key == session.bot_role else session.pid,
        "accepter_role": accepter_role_key,
        "price": price,
        "B_Gross": payoffs["B_Gross"], "B_Net": payoffs["B_Net"],
        "S_Gross": payoffs["S_Gross"], "S_Net": payoffs["S_Net"],
        "agreed_price": price
    }
    log_test_event(row)

async def check_practice_finished(lobby: Lobby):
    """Prüft, ob BEIDE Spieler ihre Bot-Runde fertig haben -> Warteraum für echtes Spiel."""
    
    # Müssen 2 Spieler sein und beide müssen fertig sein
    if len(lobby.players) < 2:
        return
        
    all_finished = True
    for pid in lobby.players:
        if pid not in lobby.practice_sessions or not lobby.practice_sessions[pid].finished:
            all_finished = False
            break
            
    if not all_finished:
        return

    # Beide fertig -> Übergang in den "Ready"-Modus (Warteraum)
    print(f"Lobby {lobby.code}: Alle Übungsrunden beendet. Wechsel in Warteraum.")
    
    lobby.practice_completed = True
    lobby.started = False  # Global aus
    lobby.stage = "ready"
    
    await send_state_all(lobby)



lobbies: Dict[str, Lobby] = {}

# === NEU: Home-WebSocket-Clients ===================================
home_clients: Set[WebSocket] = set()

def lobby_list_item(lb: Lobby) -> dict:
    """Minimaldaten für die Lobbyliste auf der Startseite."""
    return {
        "code": lb.code,
        "created_at": lb.created_at,
        "players": len(lb.players),
        "started": lb.started,
        "finished": lb.finished,
        "treatment": lb.treatment_key,
    }

async def broadcast_home(message: dict):
    """Schickt message an alle verbundenen Home-Clients (/ws/home)."""
    dead = []
    for ws in list(home_clients):
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        home_clients.discard(ws)


# =============================================================================
# Helper
# =============================================================================

now = lambda: time.time()

def calculate_payoffs(price: float, t_rel: float, lobby: Lobby) -> Dict[str, float]:
    """Berechnet Brutto- und Netto-Payoffs."""
    bv = lobby.buyer_value
    sc = lobby.seller_cost
    rb = lobby.discount_rate_per_role.get("B", 0.0) # <--- B
    rs = lobby.discount_rate_per_role.get("S", 0.0) # <--- S
    
    mult_b = math.exp(-rb * t_rel)
    mult_s = math.exp(-rs * t_rel)

    gross_b = round(max(0, bv - price), 2)
    gross_s = round(max(0, price - sc), 2)
    net_b = round(gross_b * mult_b, 4)
    net_s = round(gross_s * mult_s, 4)
            
    return {
        "B_Gross": gross_b, "B_Net": net_b, # <--- Keys angepasst
        "S_Gross": gross_s, "S_Net": net_s, # <--- Keys angepasst
    }

def generate_lobby_code(length: int = 5) -> str:
    """Generiert einen Code, der weder aktiv NOCH historisch (CSV) existiert."""
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(random.choices(alphabet, k=length))
        
        # Prüfung 1: Läuft diese Lobby gerade? (Im RAM)
        if code in lobbies:
            continue
            
        # Prüfung 2: Gab es diese Lobby früher schon? (Im History Set)
        if code in USED_GAME_CODES:
            continue
            
        # Code ist frei -> Reservieren
        USED_GAME_CODES.add(code)
        return code

def assign_role_for_pid(lobby: Lobby, pid: str) -> str:
    if pid in lobby.pid_label:
        return lobby.pid_label[pid]
    
    # Wir verteilen jetzt S (Seller) und B (Buyer)
    if "S" not in lobby.pid_label.values():
        lobby.pid_label[pid] = "S" 
    elif "B" not in lobby.pid_label.values():
        lobby.pid_label[pid] = "B" 
    else:
        lobby.pid_label[pid] = "X"
        
    return lobby.pid_label[pid]

async def broadcast(lobby: Lobby, payload: dict, except_ws: Optional[WebSocket] = None):
    dead: List[str] = []
    for p in lobby.players.values():
        if p.ws is None:
            continue
        if except_ws is not None and p.ws == except_ws:
            continue
        try:
            await p.ws.send_json(payload)
        except Exception:
            dead.append(p.pid)
    for pid in dead:
        if pid in lobby.players:
            lobby.players[pid].ws = None

def cooldown_remaining_for_pid(lobby: Lobby, pid: str) -> float:
    role = lobby.pid_label.get(pid)
    if not role:
        return 0.0
    
    cd = float(lobby.cooldown_per_role.get(role, 0.0))
    last_action = float(lobby.last_action_ts.get(pid, 0.0))
    
    if last_action <= 0.0:
        return 0.0
        
    return max(0.0, cd - (now() - last_action))

def all_instr_ack(lobby: Lobby) -> bool:
    return len(lobby.players) == 2 and all(
        lobby.instr_ack.get(pid, False) for pid in lobby.players
    )

def lobby_public_state(lobby: Lobby, recipient_pid: Optional[str] = None) -> dict:
    players_view = []
    cd_map: Dict[str, float] = {}
    
    # 1. COOLDOWNS BERECHNEN
    def calc_cd(last_ts, role_key):
        if last_ts <= 0: return 0.0
        cd_dur = lobby.cooldown_per_role.get(role_key, 0.0)
        return max(0.0, cd_dur - (now() - last_ts))

    for pid, st in lobby.players.items():
        players_view.append({
            "pid": pid,
            "connected": st.ws is not None,
        })
        
        val = 0.0
        if lobby.stage == "practice" and recipient_pid in lobby.practice_sessions:
            sess = lobby.practice_sessions[recipient_pid]
            if pid == recipient_pid:
                val = calc_cd(sess.last_action_ts, sess.role)
            else:
                val = calc_cd(sess.last_bot_action_ts, sess.bot_role)     
        else:
            val = cooldown_remaining_for_pid(lobby, pid)
            
        cd_map[pid] = round(val, 2)

    # 2. INSTRUCTIONS & TEXTE
    my_role = lobby.pid_label.get(recipient_pid)

    if lobby.treatment_key in TREATMENTS:
        tr = TREATMENTS[lobby.treatment_key]
    else:
        tr = next(iter(TREATMENTS.values()))

    raw_instr = tr["instructions_html"]
    current_role_key = my_role if my_role in ["B", "S"] else "B" 
    opp_role_key = "S" if current_role_key == "B" else "B"

    active_cooldown = lobby.cooldown_per_role.get(current_role_key, 10.0)
    disc_rate_me = lobby.discount_rate_per_role.get(current_role_key, 0.0)
    disc_rate_opp = lobby.discount_rate_per_role.get(opp_role_key, 0.0)

    fmt_data = {
        "me": "Teilnehmer",
        "opp": "Verhandlungspartner",
        "opp_dat": "Verhandlungspartner",
        "opp_gen": "Verhandlungspartners",
        "bv": int(lobby.buyer_value),
        "sc": int(lobby.seller_cost),
        "cd": int(active_cooldown),
    }

    if my_role == "B": 
        fmt_data.update({"me": "Käufer", "opp": "Verkäufer", "opp_dat": "Verkäufer", "opp_gen": "Verkäufers"})
    elif my_role == "S": 
        fmt_data.update({"me": "Verkäufer", "opp": "Käufer", "opp_dat": "Käufer", "opp_gen": "Käufers"})

    fmt_data["my_cost_factor"] = round(disc_rate_me * 100, 2)

    if tr.get("hide_opponent_discount", False):
        fmt_data["opp_cost_factor_text"] = f"Der Kostenfaktor des {fmt_data['opp_gen']} ist nicht bekannt"
        fmt_data["profit_info_text"] = (
            f"Der Bruttogewinn für Sie und dem {fmt_data['opp_dat']} wird bei jedem angegebenen Angebot automatisch angezeigt. "
            f"Sie können nur Ihren eigenen Nettogewinn einsehen, da der Kostenfaktor des {fmt_data['opp_gen']} Ihnen nicht bekannt ist."
        )
    else:
        fmt_data["opp_cost_factor"] = round(disc_rate_opp * 100, 2)
        fmt_data["opp_cost_factor_text"] = f"Der Kostenfaktor des {fmt_data['opp_gen']} beträgt <strong>{fmt_data['opp_cost_factor']}%</strong>"
        fmt_data["profit_info_text"] = f"Der Brutto- und Nettogewinn für Sie und dem {fmt_data['opp_dat']} wird bei jedem abgegebenen Angebot automatisch angezeigt"

    final_instr = raw_instr.format(**fmt_data)

    # 3. DATENQUELLE, ZEIT & LABELS
    
    source_offers = []
    source_last_offers = {}
    
    effective_started = lobby.started 
    effective_started_at = lobby.started_at
    current_pid_label = lobby.pid_label.copy()
    
    # --- WICHTIG: Lokale Variable für den Stage-Namen, damit wir das Original-Objekt nicht kaputt machen! ---
    client_stage = lobby.stage 

    if lobby.stage == "practice":
        if recipient_pid in lobby.practice_sessions:
            sess = lobby.practice_sessions[recipient_pid]
            source_offers = sess.offers
            
            # Label fixen
            current_pid_label["BOT"] = sess.bot_role

            # LOGIK: In welchem Practice-Zustand sind wir?
            
            if sess.state == "countdown":
                # Wir manipulieren nur die lokale Variable für die Antwort
                client_stage = "practice_countdown"
                lobby.countdown_end_at = sess.countdown_end_at # Das ist ok, da global ungenutzt in practice
                
                effective_started = False 
                effective_started_at = 0.0

            elif sess.state == "running" and not sess.finished:
                # Spiel läuft
                effective_started = True  
                effective_started_at = sess.started_at
            
            else:
                # Fertig -> Warteraum
                effective_started = False 
                effective_started_at = sess.started_at
            
            # Offers mappen
            source_last_offers = {"B": None, "S": None}
            for o in source_offers:
                r = sess.role if o.proposer == recipient_pid else sess.bot_role
                source_last_offers[r] = o
        else:
            effective_started = False

    else:
        # Normaler Modus
        source_offers = lobby.offers
        source_last_offers = lobby.last_offer_by_role

    # 4. ANGEBOTE AUFBEREITEN
    current_offers: Dict[str, dict] = {}
    for role, off in source_last_offers.items():
        if off is None: continue
        
        opp_role = role 
        opp_cd_w = float(lobby.cooldown_per_role.get(opp_role, 0.0))
        time_since_offer = now() - off.timestamp
        accept_cooldown_info = max(0.0, opp_cd_w - time_since_offer)

        current_offers[role] = {
            "price": off.price,
            "timestamp": off.timestamp,
            "proposer": off.proposer, 
            "share_for_proposer": off.share_for_proposer,
            "accept_cooldown_remaining": round(accept_cooldown_info, 2),
            "proposer_cooldown_w": opp_cd_w,
        }

    return {
        "code": lobby.code,
        "treatment_key": lobby.treatment_key,
        "treatment_label": tr["label"],
        "instructions_html": final_instr,
        "players": players_view,
        
        "stage": client_stage, # <--- HIER nutzen wir die saubere lokale Variable
        
        "countdown_end_at": lobby.countdown_end_at,
        "started": effective_started,
        "started_at": effective_started_at,
        "finished": lobby.finished,
        "finished_at": lobby.finished_at,
        "winner": lobby.winner,
        "offers": [o.model_dump() for o in source_offers],
        "pid_label": current_pid_label,
        "ready": lobby.ready,
        "instr_ack": lobby.instr_ack,
        "me_pid": recipient_pid,
        "my_role": my_role,
        "cooldown_per_role": lobby.cooldown_per_role,
        "discount_rate_per_role": lobby.discount_rate_per_role,
        "cooldown_remaining": cd_map,
        "buyer_value": lobby.buyer_value,
        "seller_cost": lobby.seller_cost,
        "current_offers": current_offers,
        "agreed_price": lobby.agreed_price,
        "agreed_offer_role": lobby.agreed_offer_role,
        "agreed_offer_pid": lobby.agreed_offer_pid,
        "hide_opponent_discount": bool(tr.get("hide_opponent_discount", False)),
        "result_payoffs": lobby.result_payoffs,
    }


def get_treatment_counts_from_csv() -> Dict[str, int]:
    """
    Liest das Logfile und zählt pro Treatment, wie viele Spiele 
    erfolgreich mit einer EINIGUNG ('ACCEPT') beendet wurden.
    Abbrüche oder laufende Spiele in der CSV werden ignoriert.
    """
    counts = {}
    finished_codes = set() # Set für Codes, die wir schon als 'fertig' markiert haben

    if not os.path.exists(LOG_FILE):
        return counts

    try:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                evt = row.get("event_type")
                
                # HIER IST DER FILTER: Wir zählen nur, wenn "ACCEPT" passiert ist
                if evt == "ACCEPT":
                    c = row.get("game_code")
                    tk = row.get("treatment_key")
                    
                    # Sicherstellen, dass wir jedes Spiel nur 1x zählen
                    # (Falls durch Fehler doppelte Einträge existieren)
                    if c and tk and (c not in finished_codes):
                        finished_codes.add(c)
                        counts[tk] = counts.get(tk, 0) + 1
                        
    except Exception as e:
        print(f"[WARN] Fehler beim Zählen der erfolgreichen Spiele aus CSV: {e}")
    
    return counts


async def send_state_all(lobby: Lobby):
    for pid, st in lobby.players.items():
        if st.ws:
            await st.ws.send_json(
                {"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=pid)}
            )

async def start_running(lobby: Lobby, is_practice: bool = False):
    if lobby.started or lobby.finished:
        return
    
    lobby.started = True
    lobby.started_at = now()
    lobby.last_action_ts = {pid: 0.0 for pid in lobby.players} # Cooldown Reset

    if is_practice:
        # --- BOT MODUS STARTEN ---
        lobby.stage = "practice"
        lobby.practice_sessions = {}
        
        # Für jeden Spieler eine eigene Session gegen den Bot erstellen
        for pid, player in lobby.players.items():
            role = lobby.pid_label.get(pid, "B")
            bot_role = "S" if role == "B" else "B"
            
            sess = PracticeSession(
                pid=pid,
                role=role,
                bot_role=bot_role,
                offers=[]
            )
            lobby.practice_sessions[pid] = sess
            
        # Logging Start Practice (Allgemein)
        # Wir loggen hier nur einmal den Start, Details kommen pro Bot-Interaktion
        
    else:
        # --- ECHTES SPIEL STARTEN ---
        lobby.stage = "running"
        lobby.offers.clear()
        lobby.last_offer_by_role = {"B": None, "S": None}
        lobby.agreed_price = None
        lobby.winner = None
        lobby.result_payoffs = {}
        
        # Logging Start Real Game
        try:
            lobby.event_counter += 1
            dt_obj = datetime.fromtimestamp(lobby.started_at)
            log_data = {
                "event_id": lobby.event_counter,
                "game_code": lobby.code,
                "date": dt_obj.strftime("%Y-%m-%d"),
                "time": dt_obj.strftime("%H:%M:%S"),
                "timestamp_abs": lobby.started_at,
                "time_relative": 0.0,
                "event_type": "START",
                "treatment_key": lobby.treatment_key,
                "buyer_value": lobby.buyer_value,
                "seller_cost": lobby.seller_cost,
                "B_rate": lobby.discount_rate_per_role.get("B", 0),
                "S_rate": lobby.discount_rate_per_role.get("S", 0),
                "B_cooldown": lobby.cooldown_per_role.get("B", 0),
                "S_cooldown": lobby.cooldown_per_role.get("S", 0),
                # Rest leer
                "proposer_pid": "", "proposer_role": "", "accepter_pid": "", "accepter_role": "",
                "price": "", "B_Gross": "", "B_Net": "", "S_Gross": "", "S_Net": "", "agreed_price": ""
            }
            log_game_event(log_data)
        except Exception as e:
            print(f"Log Error: {e}")

    await broadcast(lobby, {
        "type": "started", 
        "started_at": lobby.started_at,
        "is_practice": is_practice 
    })
    await send_state_all(lobby)
async def check_and_start_game(lobby: Lobby):
    # Abbrüche bei laufenden/beendeten Spielen
    if lobby.started or lobby.finished: 
        return
    # Wenn wir schon im Countdown, Running oder Practice sind -> nichts tun
    if lobby.stage in ["running", "practice", "countdown"]:
        return
    if len(lobby.players) < 2:
        return

    # 1. Instruktionen müssen von allen bestätigt sein
    if not all(lobby.instr_ack.get(p, False) for p in lobby.players):
        return

    # 2. NEU: Auch für die Übungsrunde müssen beide "Bereit" sein!
    if not all(lobby.ready.get(p, False) for p in lobby.players):
        return

    # Wenn wir hier ankommen, sind alle bereit -> Countdown starten
    lobby.stage = "countdown"
    lobby.countdown_end_at = now() + COUNTDOWN_SECONDS
    
    await broadcast(lobby, {"type": "countdown", "end_at": lobby.countdown_end_at})
    await send_state_all(lobby)

    async def _wait_start():
        while not lobby.started and not lobby.finished:
            rem = lobby.countdown_end_at - now()
            if rem <= 0:
                # HIER wird entschieden: Übung oder Ernst?
                # Wenn practice_completed noch False ist -> Übungsrunde starten
                is_practice_mode = not lobby.practice_completed
                await start_running(lobby, is_practice=is_practice_mode)
                break
            await asyncio.sleep(0.2)
    
    asyncio.create_task(_wait_start())


# =============================================================================
# Routes
# =============================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@app.websocket("/ws/home")
async def ws_home(ws: WebSocket):
    await ws.accept()
    home_clients.add(ws)

    try:
        # Beim Connect einmal komplette Liste senden
        all_lobbies = [lobby_list_item(lb) for lb in lobbies.values()]
        await ws.send_json({"type": "lobbies", "lobbies": all_lobbies})

        # Falls du später noch Messages vom Client willst:
        # momentan einfach "am Leben halten"
        while True:
            await ws.receive_text()  # blockt, bis Client was sendet
    except WebSocketDisconnect:
        pass
    finally:
        home_clients.discard(ws)


@app.get("/new_lobby")
async def new_lobby(treatment: Optional[str] = Query(None)):
    available_keys = list(TREATMENTS.keys())

    if treatment and treatment in TREATMENTS:
        tk = treatment
    else:
        # Balancing Logik:
        # A) Zähle erfolgreiche aus CSV
        total_counts = get_treatment_counts_from_csv()
        
        # B) Initialisiere fehlende Keys mit 0
        for k in available_keys:
            if k not in total_counts:
                total_counts[k] = 0
        
        # C) Addiere laufende Lobbies aus dem RAM
        for lb in lobbies.values():
            if lb.treatment_key in available_keys:
                total_counts[lb.treatment_key] += 1
        
        # D) Wähle das Minimum
        min_count = min(total_counts.values())
        candidates = [k for k, v in total_counts.items() if v == min_count]
        
        # E) Zufall aus Kandidaten
        tk = random.choice(candidates)
        
        print(f"[BALANCING] Counts: {total_counts} -> Gewählt: {tk}")

    code = generate_lobby_code()
    # Fallback, falls tk ungültig wäre (sollte nicht passieren)
    params = TREATMENTS.get(tk, TREATMENTS[available_keys[0]])

    lobby = Lobby(
        code=code,
        created_at=now(),
        treatment_key=tk,
        players={},
        order=[],
        pid_label={},
        instr_ack={},
        ready={},
        cooldown_per_role=params.get("cooldown_per_role", {}).copy(),
        discount_rate_per_role=params.get("discount_rate_per_role", {}).copy(),
        buyer_value=params.get("buyer_value", 130.0),
        seller_cost=params.get("seller_cost", 30.0),
        last_activity=now(),
        stage="instr",
        started=False,
        finished=False,
        
        # --- HIER WURDE GEÄNDERT: B und S statt P1 und P2 ---
        last_offer_by_role={"B": None, "S": None},
        # ----------------------------------------------------
        
        result_payoffs={},
    )
    lobbies[code] = lobby

    # Home-Clients informieren
    await broadcast_home({
        "type": "lobby_created",
        "lobby": lobby_list_item(lobby),
    })

    # Hier der ursprüngliche JSON-Return
    return {
        "ok": True,
        "lobby": code,
        "treatment": tk
    }




@app.get("/lobbies")
async def list_lobbies():
    data = []
    for lb in lobbies.values():
        data.append({
            "code": lb.code,
            "created_at": lb.created_at,
            "players": len(lb.players),
            "started": lb.started,
            "finished": lb.finished,
            "treatment": lb.treatment_key,
        })
    return {"lobbies": data}

@app.get("/lobby_status/{code}")
async def lobby_status(code: str):
    lb = lobbies.get(code)
    if lb is None:
        return JSONResponse({"ok": False, "reason": "not_found"}, status_code=404)
    num_active = sum(1 for p in lb.players.values() if p.ws is not None)
    joinable = (not lb.started) and (len(lb.players) < 2)
    reason = "ok" if joinable else ("running" if lb.started else "full")
    return {
        "ok": joinable,
        "reason": reason,
        "started": lb.started,
        "num_active": num_active,
        "treatment": lb.treatment_key,
    }

@app.get("/lobby/{code}", response_class=HTMLResponse)
async def lobby_page(request: Request, code: str):
    lobby = lobbies.get(code)
    if lobby is None:
        return HTMLResponse("Unbekannte Lobby.", status_code=404)

    key = f"pid_{code}"
    pid_cookie = request.cookies.get(key)

    if not pid_cookie or pid_cookie not in lobby.players:
        pid = secrets.token_hex(8)
        lobby.players[pid] = PlayerState(pid=pid)
        lobby.order.append(pid)
        assign_role_for_pid(lobby, pid)
        lobby.last_activity = now()
        resp = templates.TemplateResponse(
            "lobby.html",
            {"request": request, "code": code, "pid": pid, "treatment": lobby.treatment_key},
        )
        resp.set_cookie(key, pid, httponly=True, samesite="lax")
        return resp
    else:
        pid = pid_cookie
        resp = templates.TemplateResponse(
            "lobby.html",
            {"request": request, "code": code, "pid": pid, "treatment": lobby.treatment_key},
        )
        return resp

@app.get("/admin/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    return templates.TemplateResponse("admin_login.html", {"request": request, "error": None})

@app.post("/admin/login")
async def admin_login(request: Request, password: str = Form(...)):
    if password == ADMIN_PASSWORD:
        resp = RedirectResponse(url="/admin", status_code=302)
        resp.set_cookie(ADMIN_COOKIE, _ADMIN_TOKEN, httponly=True, samesite="lax")
        return resp
    html = templates.get_template("admin_login.html").render({"request": {}, "error": "Falsches Passwort"})
    return HTMLResponse(html, status_code=401)

@app.post("/admin/logout")
async def admin_logout():
    resp = RedirectResponse(url="/admin/login", status_code=302)
    resp.delete_cookie(ADMIN_COOKIE)
    return resp

@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    if not _is_admin(request):
        return RedirectResponse("/admin/login", status_code=302)
    return templates.TemplateResponse("admin.html", {"request": request})


# =============================================================================
# WebSocket
# =============================================================================

@app.websocket("/ws/{lobby_code}")
async def ws_lobby(ws: WebSocket, lobby_code: str):
    await ws.accept()

    lobby = lobbies.get(lobby_code)
    if lobby is None:
        await ws.send_json({"type": "error", "msg": "Unbekannte Lobby."})
        await ws.close(code=4000, reason="unknown-lobby")
        return

    key = f"pid_{lobby_code}"
    pid = ws.cookies.get(key)
    if not pid:
        await ws.send_json({"type": "error", "msg": "Kein Beitrittstoken."})
        await ws.close(code=4005, reason="no-token")
        return
    if pid not in lobby.players:
        await ws.send_json({"type": "error", "msg": "Ungültiges Token."})
        await ws.close(code=4006, reason="invalid-token")
        return

    active = [p.pid for p in lobby.players.values() if p.ws is not None]
    if len(active) >= 2 and pid not in active:
        await ws.send_json({"type": "error", "msg": "Lobby ist voll (max 2)."})
        await ws.close(code=4001, reason="lobby-full")
        return

    lobby.players[pid].ws = ws
    lobby.last_activity = now()

    await ws.send_json(
        {"type": "joined", "lobby": lobby_public_state(lobby, recipient_pid=pid)}
    )
    await broadcast(
        lobby,
        {"type": "info", "msg": "Verhandlungspartner ist beigetreten."},
        except_ws=ws,
    )
    await send_state_all(lobby)

    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            lobby.last_activity = now()

            if kind == "get_state":
                await ws.send_json(
                    {"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=pid)}
                )

            elif kind == "instr_ack":
                lobby.instr_ack[pid] = True
                
                # SOFORT STARTEN: Wer bestätigt, fängt an zu üben.
                if not lobby.practice_completed:
                    init_practice_for_player(lobby, pid)
                    await ws.send_json(
                        {"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=pid)}
                    )
                else:
                    if all_instr_ack(lobby) and lobby.stage == "instr":
                        lobby.stage = "ready"
                    await send_state_all(lobby)

            elif kind == "toggle_ready":
                if lobby.started or lobby.finished:
                    continue
                lobby.ready[pid] = not lobby.ready.get(pid, False)
                await send_state_all(lobby)
                await check_and_start_game(lobby)

            elif kind == "offer":
                # Validierung
                if not lobby.started or lobby.finished:
                     if lobby.stage not in ["running", "practice"]:
                        continue
                
                rem = cooldown_remaining_for_pid(lobby, pid)
                if rem > 0:
                    await ws.send_json({"type": "error", "msg": f"Wartezeit aktiv ({rem:.1f}s)."})
                    continue

                try:
                    price = float(msg.get("price"))
                except:
                    continue
                if not (0 <= price <= lobby.buyer_value):
                     continue

                role = lobby.pid_label.get(pid)
                total_surplus = lobby.buyer_value - lobby.seller_cost
                surplus_me = (lobby.buyer_value - price) if role == "B" else (price - lobby.seller_cost)
                share = max(0.0, min(1.0, surplus_me / total_surplus)) if total_surplus > 0 else 0.0

                offer = Offer(
                    proposer=pid,
                    price=round(price, 2),
                    share_for_proposer=round(share, 4),
                    timestamp=now()
                )
                
                lobby.last_action_ts[pid] = now()

                # === WEICHE: BOT ODER MENSCH? ===
                if lobby.stage == "practice":
                    if pid in lobby.practice_sessions:
                        sess = lobby.practice_sessions[pid]
                        sess.offers.append(offer)
                        sess.last_action_ts = now() 
                        _log_practice_offer(lobby, sess, offer)
                        
                        await ws.send_json({"type": "offer", "offer": offer.model_dump()})
                        await ws.send_json({"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=pid)})
                        asyncio.create_task(bot_reaction(lobby, sess))

                else:
                    # --- REALER MODUS ---
                    lobby.offers.append(offer)
                    if role in ("B", "S"):
                        lobby.last_offer_by_role[role] = offer
                    
                    t_abs = now()
                    t_rel = t_abs - lobby.started_at
                    payoffs = calculate_payoffs(price, t_rel, lobby)
                    dt_obj = datetime.fromtimestamp(t_abs)
                    
                    log_data = {
                        "event_id": lobby.event_counter,
                        "game_code": lobby.code,
                        "date": dt_obj.strftime("%Y-%m-%d"),
                        "time": dt_obj.strftime("%H:%M:%S"),
                        "timestamp_abs": t_abs,
                        "time_relative": t_rel,
                        "event_type": "OFFER",
                        "treatment_key": lobby.treatment_key,
                        "buyer_value": lobby.buyer_value,
                        "seller_cost": lobby.seller_cost,
                        "B_rate": lobby.discount_rate_per_role.get("B", 0),
                        "S_rate": lobby.discount_rate_per_role.get("S", 0),
                        "B_cooldown": lobby.cooldown_per_role.get("B", 0),
                        "S_cooldown": lobby.cooldown_per_role.get("S", 0),
                        "proposer_pid": pid,
                        "proposer_role": role,
                        "accepter_pid": "", "accepter_role": "",
                        "price": price,
                        "B_Gross": payoffs["B_Gross"], "B_Net": payoffs["B_Net"],
                        "S_Gross": payoffs["S_Gross"], "S_Net": payoffs["S_Net"],
                        "agreed_price": ""
                    }
                    log_game_event(log_data)

                    await broadcast(lobby, {"type": "offer", "offer": offer.model_dump()})
                    await send_state_all(lobby)

            elif kind == "accept":
                if not lobby.started or lobby.finished:
                     if lobby.stage not in ["running", "practice"]:
                        continue
                
                rem = cooldown_remaining_for_pid(lobby, pid)
                if rem > 0:
                    continue

                role = lobby.pid_label.get(pid)
                
                if lobby.stage == "practice":
                    if pid in lobby.practice_sessions:
                        sess = lobby.practice_sessions[pid]
                        if sess.last_bot_price is None:
                            continue 
                        price = sess.last_bot_price
                        sess.finished = True
                        sess.agreed_price = price
                        _log_practice_end(lobby, sess, price, "ACCEPT", role) 

                        t_rel = now() - lobby.started_at
                        payoffs = calculate_payoffs(price, t_rel, lobby)
                        res_payoffs = {pid: payoffs[f"{role}_Net"]}

                        await ws.send_json({
                            "type": "practice_ended",
                            "price": price,
                            "payoffs": res_payoffs
                        })
                        await ws.send_json({"type": "state", "lobby": lobby_public_state(lobby, recipient_pid=pid)})
                        await check_practice_finished(lobby)

                else:
                    opp_role = "S" if role == "B" else "B"
                    opp_offer = lobby.last_offer_by_role.get(opp_role)
                    if opp_offer is None:
                        continue
                    
                    price = opp_offer.price
                    now_ts = now()
                    t_rel = max(0.0, now_ts - lobby.started_at)
                    
                    payoffs_calc = calculate_payoffs(price, t_rel, lobby)
                    res_payoffs = {}
                    for p_id, p_role in lobby.pid_label.items():
                        k = f"{p_role}_Net"
                        if k in payoffs_calc:
                            res_payoffs[p_id] = payoffs_calc[k]
                            
                    lobby.agreed_price = price
                    lobby.result_payoffs = res_payoffs
                    lobby.winner = pid
                    lobby.finished = True
                    lobby.finished_at = now_ts
                    
                    dt_obj = datetime.fromtimestamp(now_ts)
                    log_data = {
                        "event_id": lobby.event_counter,
                        "game_code": lobby.code,
                        "date": dt_obj.strftime("%Y-%m-%d"),
                        "time": dt_obj.strftime("%H:%M:%S"),
                        "timestamp_abs": now_ts,
                        "time_relative": t_rel,
                        "event_type": "ACCEPT",
                        "treatment_key": lobby.treatment_key,
                        "buyer_value": lobby.buyer_value,
                        "seller_cost": lobby.seller_cost,
                        "B_rate": lobby.discount_rate_per_role.get("B", 0),
                        "S_rate": lobby.discount_rate_per_role.get("S", 0),
                        "B_cooldown": lobby.cooldown_per_role.get("B", 0),
                        "S_cooldown": lobby.cooldown_per_role.get("S", 0),
                        "proposer_pid": opp_offer.proposer,
                        "proposer_role": opp_role,
                        "accepter_pid": pid,
                        "accepter_role": role,
                        "price": price,
                        "B_Gross": payoffs_calc["B_Gross"], "B_Net": payoffs_calc["B_Net"],
                        "S_Gross": payoffs_calc["S_Gross"], "S_Net": payoffs_calc["S_Net"],
                        "agreed_price": price
                    }
                    log_game_event(log_data)
                    
                    await broadcast(lobby, {"type": "accepted", "price": price})
                    await send_state_all(lobby)
                    await broadcast(lobby, {
                        "type": "ended",
                        "reason": "Einigung",
                        "result": {
                            "accepted": True,
                            "price": price,
                            "payoffs_by_pid": res_payoffs
                        }
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WS Error {pid}: {e}")
    finally:
        # === HIER IST DIE NEUE LOGIK FÜR DAS LÖSCHEN BEIM DISCONNECT ===
        
        # 1. Prüfen: Ist das der Ersteller? (Erste Person im 'order'-Array)
        is_creator = (len(lobby.order) > 0 and lobby.order[0] == pid)

        # 2. Wenn Ersteller und Lobby nicht beendet -> Löschen
        if is_creator and not lobby.finished:
            print(f"[LOBBY] Ersteller {pid} hat Lobby {lobby_code} verlassen -> LÖSCHEN.")

            # Aus der globalen Liste entfernen
            if lobby_code in lobbies:
                del lobbies[lobby_code]

            # Home-Screen informieren (damit sie dort verschwindet)
            await broadcast_home({
                "type": "lobby_deleted",
                "code": lobby_code
            })

            # Den anderen Spieler (falls vorhanden) informieren/rauswerfen
            for other_pid, player in lobby.players.items():
                if other_pid != pid and player.ws:
                    try:
                        await player.ws.send_json({"type": "error", "msg": "Der Ersteller hat die Lobby geschlossen."})
                        # Optional: WS schließen, damit er auf die Startseite geht
                        # await player.ws.close()
                    except:
                        pass
        else:
            # NORMALES Cleanup (wenn kein Ersteller oder Spiel schon vorbei)
            if pid in lobby.players and lobby.players[pid].ws is ws:
                lobby.players[pid].ws = None
            lobby.last_activity = now()
            await send_state_all(lobby)


# =============================================================================
# Hintergrund-Task: Idle-Cleanup
# =============================================================================

CHECK_INTERVAL = 10.0      
IDLE_SECONDS = 60 * 5  

async def idle_cleanup_loop():
    while True:
        try:
            now_ts = now()
            remove_codes: List[str] = []
            for code, lb in list(lobbies.items()):
                active = any(p.ws is not None for p in lb.players.values())
                if not active and not lb.finished:
                    remove_codes.append(code)
                elif (
                    not lb.finished
                    and (now_ts - (lb.last_activity or lb.created_at)) > IDLE_SECONDS
                ):
                    await broadcast(lb, {"type": "idle_timeout", "seconds": 0})
                    await asyncio.sleep(0.5)
                    remove_codes.append(code)

            for code in remove_codes:
                lobbies.pop(code, None)
        except Exception:
            pass
        await asyncio.sleep(CHECK_INTERVAL)

@app.on_event("startup")
async def _startup():
    # Einmaliges Laden der historischen Codes beim Server-Start
    load_existing_codes_from_csv()
    asyncio.create_task(idle_cleanup_loop())