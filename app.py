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
    
    with st.popover("🎵 ▾", help="Vereinssong abspielen"):
        try:
            with open("vereinssong.mp3", "rb") as audio_file:
                audio_bytes = audio_file.read()
            st.audio(audio_bytes, format="audio/mp3")
        except Exception:
            st.warning("`vereinssong.mp3` nicht gefunden.")

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

tab_übersicht, tab_kader, tab_session, tab_archiv = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv"])

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 4)
    modus = session.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num is not None and round_num > singles_rounds
    
    if in_coop_phase:
        return ["Kaiser B1", "Board 2"]
        
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_resting_player(session, round_num):
    spieler = session.get("spieler", [])
    boards = get_boards_list(session, round_num)
    boards_count = len(boards)
    max_active = boards_count * 2
    
    if len(spieler) <= max_active or len(spieler) % 2 == 0:
        return None
        
    res = session.get("results", {})
    if round_num == 1:
        return spieler[-1]
        
    prev_r = round_num - 1
    last_board = boards[-1]
    prev_match = res.get((prev_r, last_board))
    if prev_match and prev_match.get("loser"):
        return prev_match.get("loser")
    
    shift = (round_num - 1) % len(spieler)
    return spieler[shift]

def get_board_players(session, round_num, board_name):
    boards = get_boards_list(session, round_num)
    if board_name not in boards:
        return ["-", "-"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    max_active_pl = len(boards) * 2
    has_resting = (len(spieler) > max_active_pl and len(spieler) % 2 != 0)
    resting_p = get_resting_player(session, round_num) if has_resting else None
    active_spieler = [p for p in spieler if p != resting_p] if resting_p else spieler.copy()
    
    if round_num == 1 and not in_coop_phase:
        all_sessions = st.session_state.sessions_list
        try:
            s_idx = all_sessions.index(session)
        except:
            s_idx = 0
        
        prev_sess = None
        if s_idx + 1 < len(all_sessions):
            prev_sess = all_sessions[s_idx + 1]
            
        if prev_sess and "results" in prev_sess:
            prev_total = prev_sess.get("total_rounds", 4)
            prev_modus = prev_sess.get("modus", "Up & Down")
            prev_is_std = (prev_modus == "Standard-Training (Einzel + Coop)")
            prev_singles = prev_sess.get("singles_rounds", prev_total - 2 if prev_is_std and prev_total > 2 else prev_total)
            target_r = prev_singles if prev_is_std else prev_total
            
            prev_boards = get_boards_list(prev_sess, target_r)
            prev_results = prev_sess.get("results", {})
            
            prev_players_bottom_to_top = []
            for pb in reversed(prev_boards):
                match_inf = prev_results.get((target_r, pb))
                p1, p2 = "-", "-"
                if match_inf:
                    p1 = match_inf.get("s1", "-")
                    p2 = match_inf.get("s2", "-")
                else:
                    p_pair = get_board_players(prev_sess, target_r, pb)
                    p1, p2 = p_pair[0], p_pair[1]
                if p2 != "-" and p2 not in prev_players_bottom_to_top:
                    prev_players_bottom_to_top.append(p2)
                if p1 != "-" and p1 not in prev_players_bottom_to_top:
                    prev_players_bottom_to_top.append(p1)
            
            returning_players = [p for p in prev_players_bottom_to_top if p in active_spieler]
            new_players = [p for p in active_spieler if p not in prev_players_bottom_to_top]
            
            ordered_players = new_players + returning_players
            for p in active_spieler:
                if p not in ordered_players:
                    ordered_players.append(p)
            active_spieler = ordered_players[:len(active_spieler)]

    pairs = []
    
    if is_2v2 or in_coop_phase:
        teams = []
        all_sessions = st.session_state.sessions_list
        try:
            s_idx = all_sessions.index(session)
        except:
            s_idx = 0
            
        if in_coop_phase:
            coop_shift = (s_idx + (round_num - singles_rounds)) % len(active_spieler)
            active_spieler = active_spieler[coop_shift:] + active_spieler[:coop_shift]
            
        for i in range(0, len(active_spieler)-1, 2):
            teams.append(f"{active_spieler[i]} & {active_spieler[i+1]}")
        if len(active_spieler) % 2 != 0:
            teams.append(f"{active_spieler[-1]} & -")
            
        coop_boards_cnt = 2
        for i in range(0, min(coop_boards_cnt * 2, len(teams) - len(teams) % 2), 2):
            pairs.append((teams[i], teams[i+1]))
        while len(pairs) <= b_idx:
            t1 = teams[0] if len(teams) > 0 else "-"
            t2 = teams[1] if len(teams) > 1 else "-"
            pairs.append((t1, t2))
        return list(pairs[b_idx])
    else:
        boards_count = session.get("boards_count", 4)
        
        if round_num == 1:
            for i in range(0, min(boards_count * 2, len(active_spieler) - len(active_spieler) % 2), 2):
                pairs.append((active_spieler[i], active_spieler[i+1]))
            while len(pairs) <= b_idx:
                pairs.append((active_spieler[0] if active_spieler else "-", active_spieler[1] if len(active_spieler) > 1 else "-"))
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
            return [w.get("Kaiser B1", "-"), w.get("Board 2", "-") if len(boards) > 1 else w.get("Kaiser B1", "-")]
        
        if b_idx > 0 and b_idx < len(boards) - 1:
            prev_board = boards[b_idx - 1]
            next_board = boards[b_idx + 1]
            loser_from_above = l.get(prev_board, "-")
            winner_from_below = w.get(next_board, "-")
            return [loser_from_above, winner_from_below]
            
        if b_idx == len(boards) - 1:
            prev_board = boards[b_idx - 1]
            loser_from_above = l.get(prev_board, "-")
            if has_resting:
                return [loser_from_above, resting_p if resting_p else "-"]
            else:
                loser_from_current = l.get(boards[b_idx], "-")
                return [loser_from_above, loser_from_current]
            
    return ["-", "-"]

def is_board_ready(session, board_name, next_r):
    if next_r == 1:
        return True
    
    modus = session.get("modus", "Up & Down")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if modus == "Standard-Training (Einzel + Coop)" and total_rounds > 2 else total_rounds)
    
    if modus == "Standard-Training (Einzel + Coop)" and next_r == singles_rounds + 1:
        return True
        
    boards = get_boards_list(session, next_r)
    if board_name not in boards:
        return False
        
    b_idx = boards.index(board_name)
    res = session.get("results", {})
    prev_r = next_r - 1
    
    req_boards = []
    if b_idx == 0:
        req_boards.append(boards[0])
        if len(boards) > 1:
            req_boards.append(boards[1])
    else:
        req_boards.append(boards[b_idx - 1])
        if b_idx + 1 < len(boards):
            req_boards.append(boards[b_idx + 1])
        else:
            req_boards.append(boards[b_idx])
            
    for rb in req_boards:
        found = False
        for (r, b), v in res.items():
            if r == prev_r and b == rb and v.get("winner"):
                found = True
                break
        if not found:
            return False
            
    return True

def is_session_completed(sess):
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    for r in range(1, total_rounds + 1):
        boards_in_round = get_boards_list(sess, r)
        for b_name in boards_in_round:
            match_info = res.get((r, b_name))
            if not match_info or not match_info.get("winner"):
                return False
    return True

@st.dialog("🔄 Spieler auswechseln")
def open_substitution_dialog(board_name, session_idx, round_num, slot_num, current_player):
    sess = st.session_state.sessions_list[session_idx]
    alle_spieler = list(set(sess.get("spieler", kader) + [current_player]))
    if "-" not in alle_spieler:
        alle_spieler.append("-")
    alle_spieler.sort()

    st.write(f"### Auswechslung für {board_name} (Runde {round_num})")
    st.write(f"Aktueller Spieler: **{current_player}**")
    
    idx = alle_spieler.index(current_player) if current_player in alle_spieler else 0
    new_sel = st.selectbox("Aus Kader wählen:", alle_spieler, index=idx, key=f"sub_sel_{board_name}_{round_num}_{slot_
