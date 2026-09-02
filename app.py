import streamlit as st
import pandas as pd
from datetime import date
import json
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wehringer Steeler - Teamtraining", layout="centered")

# --- KONFIGURATION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0"

@st.cache_resource
def init_connection():
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_url(SHEET_URL).worksheet("sessions")
        return sheet
    except Exception as e:
        return None

sheet_conn = init_connection()

def load_data():
    if not sheet_conn:
        return []
        
    try:
        data = sheet_conn.get_all_records()
        if data and "json_data" in data[0]:
            raw_str = data[0]["json_data"]
            if raw_str:
                raw_data = json.loads(raw_str)
                sessions = []
                for sess in raw_data:
                    fixed_results = {}
                    for k, v in sess.get("results", {}).items():
                        parts = k.split("_", 1)
                        if len(parts) == 2:
                            r_num = int(parts[0])
                            b_name = parts[1]
                            fixed_results[(r_num, b_name)] = v
                    sess["results"] = fixed_results
                    sessions.append(sess)
                return sessions
    except Exception as e:
        st.error(f"Fehler beim Laden aus Google Sheets: {e}")
    return []

def save_data(sessions):
    if not sheet_conn:
        return
        
    serializable_sessions = []
    for sess in sessions:
        sess_copy = sess.copy()
        fixed_results = {}
        for (r_num, b_name), v in sess.get("results", {}).items():
            fixed_results[f"{r_num}_{b_name}"] = v
        sess_copy["results"] = fixed_results
        serializable_sessions.append(sess_copy)
    
    json_str = json.dumps(serializable_sessions, ensure_ascii=False)
    try:
        sheet_conn.clear()
        sheet_conn.update([["json_data"], [json_str]])
    except Exception as e:
        st.error(f"Fehler beim Speichern in Google Sheets: {e}")

col1, col2 = st.columns([1, 6])
with col1:
    try:
        st.image("logo.png.png", width=85)
    except Exception:
        pass
with col2:
    st.markdown("<h1 style='margin: 0; padding-top: 12px; font-size: 2.2rem;'>Wehringer Steeler - Teamtraining</h1>", unsafe_allow_html=True)

kader = [
    "Andreas Böhm",
    "Andrino Czombera",
    "Dennis Güttner",
    "Marco Eser",
    "Maximilian Zientner",
    "Michael Kummer",
    "Michael Mak",
    "Michael Neumeier",
    "Thomas Schaudt",
    "Wolfgang Scheider"
]

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

tab_übersicht, tab_kader, tab_session, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv", "BDV-Regeln"])

def get_boards_list(boards_count):
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_board_players(session, round_num, board_name):
    boards_count = session.get("boards_count", 6)
    boards = get_boards_list(boards_count)
    if board_name not in boards:
        return ["Offen", "Offen"]
    b_idx = boards.index(board_name)
    
    is_2v2 = (session.get("modus") == "Koop 2vs2 (Up & Down)")
    
    if round_num == 1:
        spieler = session["spieler"]
        pairs = []
        
        if is_2v2:
            teams = []
            for i in range(0, len(spieler)-1, 2):
                teams.append(f"{spieler[i]} & {spieler[i+1]}")
            if len(spieler) % 2 != 0:
                teams.append(f"{spieler[-1]} & Offen")
                
            for i in range(0, min(boards_count * 2, len(teams) - len(teams) % 2), 2):
                pairs.append((teams[i], teams[i+1]))
            while len(pairs) <= b_idx:
                t1 = teams[0] if len(teams) > 0 else "Offen"
                t2 = teams[1] if len(teams) > 1 else "Offen"
                pairs.append((t1, t2))
        else:
            for i in range(0, min(boards_count * 2, len(spieler) - len(spieler) % 2), 2):
                pairs.append((spieler[i], spieler[i+1]))
            while len(pairs) <= b_idx:
                pairs.append((spieler[0] if spieler else "Offen", spieler[1] if len(spieler) > 1 else "Offen"))
        
        return list(pairs[b_idx])
    
    prev_r = round_num - 1
    res = session.get("results", {})
    w = {}
    l = {}
    for b in boards:
        match_info = res.get((prev_r, b))
        if match_info and match_info.get("winner"):
            w[b] = match_info["winner"]
            l[b] = match_info["loser"]
        else:
            def_players = get_board_players(session, prev_r, b)
            w[b] = def_players[0]
            l[b] = def_players[1]
            
    if b_idx == 0:
        return [w["Kaiser B1"], w.get("Board 2", "Offen") if boards_count > 1 else w["Kaiser B1"]]
    
    if b_idx > 0:
        prev_board = boards[b_idx - 1]
        next_board = boards[b_idx + 1] if b_idx + 1 < boards_count else None
        
        loser_from_above = l.get(prev_board, "Offen")
        winner_from_below = w.get(next_board, "Offen") if next_board else l.get(boards[b_idx], "Offen")
        return [loser_from_above, winner_from_below]
        
    return ["Offen", "Offen"]

def is_board_ready(session, board_name, next_r):
    if next_r == 1:
        return True
    
    boards_count = session.get("boards_count", 6)
    boards = get_boards_list(boards_count)
    if board_name not in boards:
        return False
        
    b_idx = boards.index(board_name)
    res = session.get("results", {})
    prev_r = next_r - 1
    
    req_boards = []
    if b_idx == 0:
        req_boards.append(boards[0])
        if boards_count > 1:
            req_boards.append(boards[1])
    else:
        req_boards.append(boards[b_idx - 1])
        if b_idx + 1 < boards_count:
            req_boards.append(boards[b_idx + 1])
        else:
            req_boards.append(boards[b_idx])
            
    for rb in req_boards:
        found = False
        for (r, b), v in res.items():
            if r == prev_r and b == rb and v.get("winner"):
