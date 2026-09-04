# INSTRUKTION: DIESE REGELN DÜRFEN BEI CODE-UPDATES NIEMALS VERLETZT WERDEN
# 1. BACKUPS: Das Rolling-Backup in Google Sheets darf maximal 20 Einträge umfassen (ältere löschen).
# 2. JSON-EXPORT: Vor jedem json.dumps() MUSS die Hilfsfunktion make_serializable() aufgerufen werden, um Tupel abzufangen!
# 3. KOOP-TEAMS: Es dürfen niemals exakt gleiche 2er-Teams aus der vorherigen Session gebildet werden.
# 4. ANTI-DOPPEL-PAUSE: Das Freilos in Runde 1 muss rotieren. Wer im letzten Match pausiert hat, darf nicht nochmal aussetzen.
# 5. ZEITMANAGEMENT: Globale Ø-Zeiten (Min/Runde, Min/Leg) inkl. Nacht-Übergang müssen im Session-Reiter berechnet bleiben.
# 6. KADER-STATS: Im Reiter Kader werden MVP, Dauerbrenner, Bester Avg und 180er Maschine angezeigt (nicht nur 50% Quoten). Bei Gleichstand: Tooltip!
# 7. HEADER: Der Titel oben links muss das Logo beinhalten und "Wehringer Steelers — Teamtraining" lauten.
# 8. SPIELMODI & LOGIK:
#    - Standard-Training (Einzel + Coop): X Runden Einzel (max 6 Boards), dann Y Runden Doppel (nur B1 & B2). 
#    - Koop 2vs2 (Up & Down): Reine Doppel-Session (0 Einzel). Gespielt wird exklusiv auf Kaiser B1 & Board 2.
#    - Up & Down (Einzel): Klassisch. Sieger steigt auf (Ri. B1), Verlierer ab. Kaiser der Vorsession startet ganz unten.
# 9. LIGA-BETRIEB: Komplett vom Training isolierter Modus (Schwaben 4. BezLiga) mit 2-Board Live Tracking, Blind Setup, Kreuz-Runde und eigenen Stats.

import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import re

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

# --- KONFIGURATION ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0"

def make_serializable(data):
    """Wandelt Tupel und Datumsformate sicher um, damit JSON nicht abstürzt."""
    if isinstance(data, dict):
        return {str(k): make_serializable(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [make_serializable(i) for i in data]
    elif hasattr(data, 'isoformat'):
        return data.isoformat()
    else:
        return data

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
                        if len(parts) == 2 and not sess.get("is_liga"):
                            r_num = int(parts[0])
                            b_name = parts[1]
                            fixed_results[(r_num, b_name)] = v
                        else:
                            fixed_results[k] = v
                    sess["results"] = fixed_results
                    sessions.append(sess)
                return sessions
    except Exception as e:
        st.error(f"Fehler beim Laden aus Google Sheets: {e}")
    return []

def save_backup_to_cloud(serializable_sessions):
    """Erstellt vollautomatisch einen zeitgestempelten Snapshot im 'backups' Tabellenblatt (Rolling: max 20 Einträge)."""
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
        spreadsheet = client.open_by_url(SHEET_URL)
        
        try:
            backup_ws = spreadsheet.worksheet("backups")
        except:
            backup_ws = spreadsheet.add_worksheet(title="backups", rows=100, cols=2)
            backup_ws.append_row(["Timestamp", "JSON_Data"])
        
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
        json_str = json.dumps(serializable_sessions, ensure_ascii=False)
        backup_ws.append_row([ts, json_str])
        
        try:
            all_vals = backup_ws.get_all_values()
            if len(all_vals) > 21: # 1 Kopfzeile + 20 Backups
                rows_to_delete = len(all_vals) - 21
                for _ in range(rows_to_delete):
                    try:
                        backup_ws.delete_rows(2)
                    except AttributeError:
                        backup_ws.delete_row(2)
        except Exception:
            pass
            
    except Exception as e:
        pass

def save_data(sessions):
    if not sheet_conn:
        return
        
    serializable_sessions = []
    for sess in sessions:
        sess_copy = sess.copy()
        fixed_results = {}
        for k, v in sess.get("results", {}).items():
            if isinstance(k, tuple) and len(k) == 2:
                fixed_results[f"{k[0]}_{k[1]}"] = v
            else:
                fixed_results[k] = v
        sess_copy["results"] = fixed_results
        serializable_sessions.append(sess_copy)
        
    try:
        sichere_sessions = make_serializable(serializable_sessions)
        json_str = json.dumps(sichere_sessions, ensure_ascii=False)
        sheet_conn.clear()
        sheet_conn.update([["json_data"], [json_str]])
        save_backup_to_cloud(sichere_sessions)
    except Exception as e:
        st.error(f"Fehler beim Speichern in Google Sheets: {e}")

def get_local_time_str():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%H:%M")
    except Exception:
        return datetime.now().strftime("%H:%M")

def check_session_completion_time(sess):
    if sess.get("is_liga"):
        return
    if is_session_completed(sess):
        if not sess.get("end_time"):
            sess["end_time"] = get_local_time_str()
    else:
        if "end_time" in sess:
            sess["end_time"] = None

def smart_sync_and_save(updated_sessions):
    for sess in updated_sessions:
        check_session_completion_time(sess)
        
    fresh_data = load_data()
    if fresh_data:
        existing_ids = {s["id"] for s in fresh_data}
        for sess in updated_sessions:
            if sess["id"] not in existing_ids:
                fresh_data.append(sess)
            else:
                for idx, fs in enumerate(fresh_data):
                    if fs["id"] == sess["id"]:
                        fresh_data[idx] = sess
        final_data = [s for s in fresh_data if s["id"] in [u["id"] for u in updated_sessions]]
        save_data(final_data)
        st.session_state.sessions_list = final_data
    else:
        save_data(updated_sessions)
        st.session_state.sessions_list = updated_sessions

def delete_session(session_id):
    fresh_data = load_data()
    if fresh_data:
        fresh_data = [s for s in fresh_data if s.get("id") != session_id]
        save_data(fresh_data)
        st.session_state.sessions_list = fresh_data
    else:
        st.session_state.sessions_list = [s for s in st.session_state.sessions_list if s.get("id") != session_id]
        save_data(st.session_state.sessions_list)

st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="https://raw.githubusercontent.com/zombination88/Darttraining-Steelers/main/logo.png.png" alt="Logo" width="60" onerror="this.src='https://raw.githubusercontent.com/zombination88/Darttraining-Steelers/main/logo.png'">
        <h1 style='margin: 0; padding-top: 8px; font-size: 1.8rem;'>Wehringer Steelers — Teamtraining</h1>
    </div>
    """, 
    unsafe_allow_html=True
)

c_mus, c_sync, c_dummy = st.columns([1, 1, 4])
with c_mus:
    try:
        with st.popover("🎵"):
            st.audio("vereinssong.mp3")
    except Exception:
        pass
with c_sync:
    if st.button("🔄", help="Manuell aktualisieren"):
        st.session_state.sessions_list = load_data()
        st.rerun()

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

# Daten strikt in Liga und Training trennen
training_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga")]
liga_sessions = [s for s in st.session_state.sessions_list if s.get("is_liga")]

tab_übersicht, tab_kader, tab_session, tab_liga, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Freundschaftsspiele", "Match-Archiv", "Modus & Regeln"])

def get_or_create_teams(session, all_training_sessions):
    """Generiert zufällige 2v2 Teams für die Session."""
    if "coop_teams" in session and session["coop_teams"]:
        return session["coop_teams"]
    
    spieler = [p for p in session.get("spieler", []) if p != "-"]
    prev_pairs = set()
    prev_resting_players = set()
    all_sorted = sorted(all_training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
    try:
        s_idx = all_sorted.index(session)
        if s_idx + 1 < len(all_sorted):
            prev_sess = all_sorted[s_idx + 1]
            if "coop_teams" in prev_sess:
                for t in prev_sess["coop_teams"]:
                    parts = t.split("&")
                    if len(parts) == 2 and "-" not in t:
                        prev_pairs.add(frozenset([parts[0].strip(), parts[1].strip()]))
                
                prev_total = prev_sess.get("total_rounds", 4)
                prev_modus = prev_sess.get("modus", "Up & Down")
                prev_is_std = (prev_modus == "Standard-Training (Einzel + Coop)")
                prev_singles = prev_sess.get("singles_rounds", prev_total - 2 if prev_is_std and prev_total > 2 else prev_total)
                prev_coop_start = prev_singles + 1 if prev_is_std else 1
                prev_teams = prev_sess.get("coop_teams", [])
                if len(prev_teams) % 2 != 0:
                    n_prev = len(prev_teams)
                    last_rel_round = prev_total - prev_coop_start + 1
                    resting_idx = (last_rel_round - 1) % n_prev
                    resting_team_str = prev_teams[resting_idx]
                    for p in resting_team_str.split("&"):
                        p_clean = p.strip()
                        if p_clean and p_clean != "-":
                            prev_resting_players.add(p_clean)
            else:
                prev_spiel = [p for p in prev_sess.get("spieler", []) if p != "-"]
                for i in range(0, len(prev_spiel)-1, 2):
                    prev_pairs.add(frozenset([prev_spiel[i], prev_spiel[i+1]]))
    except:
        pass

    import random
    best_teams = []
    for _ in range(50):
        shuffled = spieler.copy()
        random.shuffle(shuffled)
        current_teams = []
        has_forbidden = False
        for i in range(0, len(shuffled)-1, 2):
            p1, p2 = shuffled[i], shuffled[i+1]
            pair = frozenset([p1, p2])
            if pair in prev_pairs:
                has_forbidden = True
                break
            current_teams.append(f"{p1} & {p2}")
        if len(shuffled) % 2 != 0:
            current_teams.append(f"{shuffled[-1]} & -")
        
        best_teams = current_teams
        if not has_forbidden:
            break
            
    if len(best_teams) % 2 != 0 and prev_resting_players:
        for _ in range(len(best_teams)):
            t0_players = [p.strip() for p in best_teams[0].split("&") if p.strip() != "-"]
            has_resting = any(p in prev_resting_players for p in t0_players)
            if not has_resting or len(best_teams) == 1:
                break
            best_teams = best_teams[1:] + [best_teams[0]]

    session["coop_teams"] = best_teams
    return best_teams

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 6)
    modus = session.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num is not None and round_num > singles_rounds
    
    if in_coop_phase or modus == "Koop 2vs2 (Up & Down)":
        return ["Kaiser B1", "Board 2"]
        
    all_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    return all_boards[:boards_count]

def get_board_players(session, round_num, board_name):
    boards = get_boards_list(session, round_num)
    if board_name not in boards:
        return ["-", "-"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    
    if round_num == 1 and not in_coop_phase and not is_2v2:
        all_sessions = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
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
            
            prev_players_top_to_bottom = []
            for pb in prev_boards:
                match_inf = prev_results.get((target_r, pb))
                p1, p2 = "-", "-"
                if match_inf:
                    p1 = match_inf.get("winner", "-")
                    p2 = match_inf.get("loser", "-")
                else:
                    p_pair = get_board_players(prev_sess, target_r, pb)
                    p1, p2 = p_pair[0], p_pair[1]
                if p1 != "-" and p1 not in prev_players_top_to_bottom:
                    prev_players_top_to_bottom.append(p1)
                if p2 != "-" and p2 not in prev_players_top_to_bottom:
                    prev_players_top_to_bottom.append(p2)
            
            prev_players_bottom_to_top = list(reversed(prev_players_top_to_bottom))
            returning_players = [p for p in prev_players_bottom_to_top if p in spieler]
            new_players = [p for p in spieler if p not in prev_players_top_to_bottom]
            ordered_players = new_players + returning_players
            for p in spieler:
                if p not in ordered_players:
                    ordered_players.append(p)
            spieler = ordered_players[:len(spieler)]

    pairs = []
    if is_2v2 or in_coop_phase:
        teams = get_or_create_teams(session, training_sessions)
        n_teams = len(teams)
        rel_round = (round_num - singles_rounds) if in_coop_phase else round_num
        
        resting_team_idx = (rel_round - 1) % n_teams if n_teams % 2 != 0 else -1
        active_teams = [t for i, t in enumerate(teams) if i != resting_team_idx]
        
        if rel_round == 1:
            if b_idx < len(active_teams) // 2:
                t1 = active_teams[b_idx * 2]
                t2 = active_teams[b_idx * 2 + 1] if b_idx * 2 + 1 < len(active_teams) else "-"
                return [t1, t2]
            else:
                return ["-", "-"]
        else:
            prev_r = round_num - 1
            res = session.get("results", {})
            w, l = {}, {}
            for b in boards:
                match_info = res.get((prev_r, b))
                if match_info and match_info.get("winner"):
                    w[b], l[b] = match_info["winner"], match_info["loser"]
                else:
                    w[b], l[b] = "-", "-"
                    
            if b_idx == 0:
                top_w = w.get("Kaiser B1", "-")
                next_w = w.get("Board 2", "-")
                return [top_w if top_w != "-" else (active_teams[0] if active_teams else "-"), 
                        next_w if next_w != "-" else (active_teams[1] if len(active_teams) > 1 else "-")]
            elif b_idx == 1 and len(boards) > 1:
                top_l = l.get("Kaiser B1", "-")
                next_l = l.get("Board 2", "-")
                return [top_l if top_l != "-" else (active_teams[2] if len(active_teams) > 2 else "-"), 
                        next_l if next_l != "-" else (active_teams[3] if len(active_teams) > 3 else "-")]
        return ["-", "-"]
    else:
        boards_count = session.get("boards_count", 6)
        if round_num == 1:
            for i in range(0, min(boards_count * 2, len(spieler) - len(spieler) % 2), 2):
                pairs.append((spieler[i], spieler[i+1]))
            while len(pairs) <= b_idx:
                pairs.append((spieler[0] if spieler else "-", spieler[1] if len(spieler) > 1 else "-"))
            if len(spieler) % 2 != 0:
                pairs[-1] = (spieler[-1], "-")
            return list(pairs[b_idx])
        
        prev_r = round_num - 1
        res = session.get("results", {})
        w, l = {}, {}
        for b in boards:
            match_info = res.get((prev_r, b))
            if match_info and match_info.get("winner"):
                w[b], l[b] = match_info["winner"], match_info["loser"]
            else:
                w[b], l[b] = "-", "-"
                
        if b_idx == 0:
            top_w = w.get("Kaiser B1", "-")
            next_w = w.get("Board 2", "-") if len(boards) > 1 else top_w
            return [top_w, next_w if next_w != "-" else "-"]
        
        if b_idx > 0:
            prev_board = boards[b_idx - 1]
            next_board = boards[b_idx + 1] if b_idx + 1 < len(boards) else None
            loser_from_above = l.get(prev_board, "-")
            winner_from_below = w.get(next_board, "-") if next_board else l.get(boards[b_idx], "-")
            return [loser_from_above if loser_from_above != "-" else "-", winner_from_below if winner_from_below != "-" else "-"]
    return ["-", "-"]

def is_board_ready(session, board_name, next_r):
    if next_r == 1: return True
    modus = session.get("modus", "Up & Down")
    total_rounds = session.get("total_rounds", 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if modus == "Standard-Training (Einzel + Coop)" and total_rounds > 2 else total_rounds)
    if modus == "Standard-Training (Einzel + Coop)" and next_r == singles_rounds + 1:
        res = session.get("results", {})
        base_boards = get_boards_list(session, 1)
        for r in range(1, singles_rounds + 1):
            for rb in base_boards:
                match_info = res.get((r, rb))
                if not match_info or not match_info.get("winner"): return False
        return True
        
    boards = get_boards_list(session, next_r)
    if board_name not in boards: return False
    b_idx = boards.index(board_name)
    res = session.get("results", {})
    prev_r = next_r - 1
    
    req_boards = []
    if b_idx == 0:
        req_boards.append(boards[0])
        if len(boards) > 1: req_boards.append(boards[1])
    else:
        req_boards.append(boards[b_idx - 1])
        if b_idx + 1 < len(boards): req_boards.append(boards[b_idx + 1])
        else: req_boards.append(boards[b_idx])
            
    for rb in req_boards:
        found = False
        for (r, b), v in res.items():
            if r == prev_r and b == rb and v.get("winner"):
                found = True
                break
        if not found: return False
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
    all_sessions_sorted = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
    sess = all_sessions_sorted[session_idx]
    alle_spieler = list(set(sess.get("spieler", kader) + [current_player]))
    if "-" not in alle_spieler: alle_spieler.append("-")
    alle_spieler.sort()

    st.write(f"### Auswechslung für {board_name} (Runde {round_num})")
    idx = alle_spieler.index(current_player) if current_player in alle_spieler else 0
    new_sel = st.selectbox("Aus Kader wählen:", alle_spieler, index=idx, key=f"sub_sel_{board_name}_{round_num}_{slot_num}")
    new_txt = st.text_input("Oder neuen Gast eintragen:", placeholder="Name...", key=f"sub_txt_{board_name}_{round_num}_{slot_num}")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col2:
        if st.button("Änderung speichern", type="primary", use_container_width=True):
            final_name = new_txt.strip() if new_txt.strip() else new_sel
            if "results" not in sess: sess["results"] = {}
            if (round_num, board_name) not in sess["results"]:
                auto_p = get_board_players(sess, round_num, board_name)
                sess["results"][(round_num, board_name)] = {
                    "s1": auto_p[0], "s2": auto_p[1], "ergebnis": "0:0", "winner": "", "loser": "", "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0
                }
            if slot_num == 1: sess["results"][(round_num, board_name)]["s1"] = final_name
            else: sess["results"][(round_num, board_name)]["s2"] = final_name
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("📊 Spielablauf & Rundenübersicht")
def open_session_archive_dialog(session_idx):
    all_sessions_sorted = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
    sess = all_sessions_sorted[session_idx]
    start_t, end_t = sess.get("start_time", "–"), sess.get("end_time", "–")
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    st.caption(f"Modus: {sess['modus']} | Boards: {sess['boards']} | Leg-Modus: {sess['modus_leg']}")
    st.caption(f"⏱️ Start: {start_t} Uhr | Ende: {end_t} Uhr")
    
    total_minutes = 0
    if start_t != "–" and end_t != "–":
        try:
            t1 = datetime.strptime(start_t, "%H:%M")
            t2 = datetime.strptime(end_t, "%H:%M")
            diff_min = (t2 - t1).total_seconds() / 60
            if diff_min < 0: diff_min += 24 * 60
            total_minutes = diff_min
        except: pass
    
    total_rounds = sess.get("total_rounds", 4)
    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    res = sess.get("results", {})
    
    if total_minutes > 0:
        total_legs = sum([sum(map(int, m.get("ergebnis", "0:0").split(":"))) for m in res.values() if ":" in m.get("ergebnis", "")])
        avg_round = total_minutes / total_rounds if total_rounds > 0 else 0
        avg_leg = total_minutes / total_legs if total_legs > 0 else 0
        st.markdown(f"**⏱️ Session Dauer:** {int(total_minutes)} Min. | **Ø Runde:** {avg_round:.1f} Min. | **Ø Leg:** {avg_leg:.1f} Min.")
        st.divider()

    if not res:
        st.info("Für diese Session wurden noch keine Matches erfasst.")
    else:
        for r in range(1, total_rounds + 1):
            if is_standard_training and r > singles_rounds: r_display = f"Doppelrunde {r - singles_rounds}/{total_rounds - singles_rounds} (Coop)"
            else: r_display = f"Runde {r}/{singles_rounds} (Einzel)" if is_standard_training else f"Runde {r}/{total_rounds}"
            st.markdown(f"#### 🎯 {r_display}")
            boards_in_r = get_boards_list(sess, r)
            for b_name in boards_in_r:
                match_info = res.get((r, b_name))
                if match_info:
                    heim, gast, ergebnis, sieger = match_info.get("s1", "–"), match_info.get("s2", "–"), match_info.get("ergebnis", "–"), match_info.get("winner", "-")
                    t180 = f"{match_info.get('180_s1', 0)} / {match_info.get('180_s2', 0)}"
                    avg = f"{match_info.get('avg_s1', 0.0)} / {match_info.get('avg_s2', 0.0)}"
                else:
                    auto_p = get_board_players(sess, r, b_name)
                    heim, gast, ergebnis, sieger, t180, avg = auto_p[0], auto_p[1], "Ausstehend", "–", "–", "–"
            
                with st.container(border=True):
                    st.markdown(f"**{b_name}**\n\n⚔️ {heim} vs {gast}\n\nErgebnis: **{ergebnis}** | Sieger: **{sieger}**\n\n🎯 180er: {t180} | 📊 Avg: {avg}")
            
            if is_standard_training and r == singles_rounds:
                st.markdown("##### 🏆 Board-Endstand nach den Einzel-Runden:")
                for b_name in get_boards_list(sess, singles_rounds):
                    p_list = get_board_players(sess, singles_rounds, b_name)
                    m_inf = res.get((singles_rounds, b_name))
                    winner_str = m_inf.get("winner", "–") if m_inf else "–"
                    st.write(f"- **{b_name}:** {p_list[0]} vs {p_list[1]} ➔ **Sieger:** {winner_str}")
                st.divider()
                
    if st.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("📊 Session Endstand & Zusammenfassung")
def open_session_summary_dialog(session_idx):
    sess = st.session_state.sessions_list[session_idx]
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    
    start_t, end_t = sess.get("start_time", "–"), sess.get("end_time", "–")
    total_minutes = 0
    if start_t != "–" and end_t != "–":
        try:
            t1 = datetime.strptime(start_t, "%H:%M")
            t2 = datetime.strptime(end_t, "%H:%M")
            diff_min = (t2 - t1).total_seconds() / 60
            if diff_min < 0: diff_min += 24 * 60
            total_minutes = diff_min
        except: pass
        
    total_rounds = sess.get("total_rounds", 4)
    modus = sess.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    is_pure_coop = (modus == "Koop 2vs2 (Up & Down)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    res = sess.get("results", {})
    
    if total_minutes > 0:
        total_legs = sum([sum(map(int, m.get("ergebnis", "0:0").split(":"))) for m in res.values() if ":" in m.get("ergebnis", "")])
        avg_round = total_minutes / total_rounds if total_rounds > 0 else 0
        avg_leg = total_minutes / total_legs if total_legs > 0 else 0
        st.markdown(f"**⏱️ Session Dauer:** {int(total_minutes)} Min. | **Ø Runde:** {avg_round:.1f} Min. | **Ø Leg:** {avg_leg:.1f} Min.")
        st.divider()
    
    if singles_rounds > 0 and not is_pure_coop:
        last_played_round = max([r for (r, b), info in res.items() if info.get("winner") and r <= singles_rounds] + [0])
        if last_played_round > 0:
            st.markdown(f"#### 🎯 Einzel-Phase (Stand nach Runde {last_played_round}/{singles_rounds})")
            for b_name in get_boards_list(sess, last_played_round):
                match_info = res.get((last_played_round, b_name))
                if match_info and match_info.get("winner"):
                    st.markdown(f"<div style='border: 1px solid #444; border-radius: 8px; padding: 10px; margin-bottom: 10px; background-color: #1e1e1e;'><h5 style='margin: 0; padding-bottom: 5px; color: #fff;'>{b_name}</h5><p style='margin: 0; font-size: 0.95em;'>🥇 1. Platz: <b>{match_info.get('winner')}</b></p><p style='margin: 0; font-size: 0.95em;'>🥈 2. Platz: <b>{match_info.get('loser')}</b></p></div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div style='border: 1px solid #444; border-radius: 8px; padding: 10px; margin-bottom: 10px; background-color: #1e1e1e;'><h5 style='margin: 0; padding-bottom: 5px; color: #fff;'>{b_name}</h5><p style='margin: 0; font-style: italic; color: #888;'>Match ausstehend.</p></div>", unsafe_allow_html=True)
            st.divider()
        else:
            st.info("Noch keine Einzel-Matches beendet.")
            
    coop_start_round = singles_rounds + 1 if is_standard_training else 1
    has_coop = is_pure_coop or (is_standard_training and total_rounds > singles_rounds)
    
    if has_coop:
        st.markdown("#### 🤝 Koop / Doppel-Phase — Gesamtwertung")
        teams = sess.get("coop_teams", [])
        team_stats = {t: {"wins": 0, "losses": 0, "legs_won": 0, "legs_lost": 0, "matches": 0} for t in teams}
        
        for r in range(coop_start_round, total_rounds + 1):
            for b_name in get_boards_list(sess, r):
                m_info = res.get((r, b_name))
                if m_info and m_info.get("winner"):
                    winner, s1, s2 = m_info.get("winner"), m_info.get("s1"), m_info.get("s2")
                    try: l1, l2 = map(int, m_info.get("ergebnis", "0:0").split(":"))
                    except: l1, l2 = 0, 0
                    
                    for s_team, (w_l, l_l) in [(s1, (l1, l2) if winner == s1 else (l2, l1)), (s2, (l2, l1) if winner == s2 else (l1, l2))]:
                        if s_team in team_stats:
                            team_stats[s_team]["matches"] += 1
                            if winner == s_team: team_stats[s_team]["wins"] += 1
                            else: team_stats[s_team]["losses"] += 1
                            team_stats[s_team]["legs_won"] += w_l
                            team_stats[s_team]["legs_lost"] += l_l

        sorted_teams = sorted(team_stats.items(), key=lambda x: (x[1]["wins"], x[1]["legs_won"] - x[1]["legs_lost"], x[1]["legs_won"]), reverse=True)
        rank = 1
        for team_name, stats in sorted_teams:
            if stats["matches"] > 0 or len(sorted_teams) <= 5:
                medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"{rank}."))
                st.markdown(f"<div style='border: 1px solid #444; border-radius: 8px; padding: 10px; margin-bottom: 8px; background-color: #1e1e1e;'><p style='margin: 0; font-size: 1.05em;'><b>{medal} Platz {rank}: {team_name}</b></p><p style='margin: 4px 0 0 0; font-size: 0.85em; color: #aaa;'>Siege: <b>{stats['wins']}</b> | Legs: {stats['legs_won']}:{stats['legs_lost']}</p></div>", unsafe_allow_html=True)
                rank += 1

    if st.button("Schließen", use_container_width=True): st.rerun()

def get_max_boards_for_players(num_players):
    import math
    if num_players < 2: return 0
    return math.floor(num_players / 2)

@st.dialog("➕ Neue Session starten")
def open_new_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password", key="dialog_pwd_input")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return

    session_datum = st.date_input("Datum", date.today())
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"])
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        st.write("### Runden-Aufteilung")
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=3)
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 11)), index=1)
        total_rounds = singles_rounds + coop_rounds
        st.info(f"ℹ️ Standard-Training: {singles_rounds} Runden Einzel + {coop_rounds} Runden Doppel.")
    elif spielmodus == "Koop 2vs2 (Up & Down)":
        singles_rounds, coop_rounds, total_rounds = 0, st.selectbox("Anzahl Koop-Runden", list(range(1, 11)), index=1), 0
        total_rounds = coop_rounds
    else:
        singles_rounds, coop_rounds = 0, 0
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3)
        
    anzahl_boards = st.selectbox("Anzahl der Boards (für Einzel)", ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"], index=2)
    
    st.write("### Anwesende Spieler")
    anwesende = []
    cols = st.columns(2)
    half = len(kader) // 2
    for i, sp in enumerate(kader):
        with cols[0 if i < half else 1]:
            if st.checkbox(sp, value=True, key=f"form_kader_{sp}"): anwesende.append(sp)
                
    st.write("### Gastspieler (optional)")
    gaeste = [x for x in [st.text_input(f"Gastspieler {i+1}", key=f"form_gast_{i+1}") for i in range(4)] if x.strip() != ""]
    aktive_spieler = anwesende + gaeste
    gewaehlte_boards_zahl = int(anzahl_boards.split()[0])
    max_moegliche_boards = get_max_boards_for_players(len(aktive_spieler))
    
    can_save = True
    if len(aktive_spieler) < 2:
        st.error("🚨 Fehler: Bitte wähle mindestens 2 Spieler aus!")
        can_save = False
    elif gewaehlte_boards_zahl > max_moegliche_boards:
        st.error(f"🚨 Fehler: Zu viele Boards! Für {len(aktive_spieler)} Spieler sind max. {max_moegliche_boards} Boards möglich.")
        can_save = False

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c2:
        if st.button("Session starten", type="primary", use_container_width=True, disabled=not can_save):
            if can_save:
                max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
                new_session = {
                    "id": f"S-{max_id + 1}",
                    "datum": session_datum.strftime("%d.%m.%Y"),
                    "start_time": None, "end_time": None,
                    "modus": spielmodus, "boards_count": gewaehlte_boards_zahl,
                    "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds,
                    "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus,
                    "spieler": aktive_spieler, "gaeste": gaeste, "results": {}, "is_liga": False
                }
                if spielmodus in ["Koop 2vs2 (Up & Down)", "Standard-Training (Einzel + Coop)"]:
                    get_or_create_teams(new_session, training_sessions)

                st.session_state.sessions_list.append(new_session)
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()

@st.dialog("⚙️ Session bearbeiten")
def open_edit_session_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_{session_idx}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return

    sess = st.session_state.sessions_list[session_idx]
    
    try: curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_date = date.today()

    session_datum = st.date_input("Datum", curr_date)
    c1, c2 = st.columns(2)
    edit_start_time = c1.text_input("Startzeit (HH:MM)", value=sess.get("start_time") or "")
    edit_end_time = c2.text_input("Endzeit (HH:MM)", value=sess.get("end_time") or "")

    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"], index=["Best of 5", "Best of 3"].index(sess.get("modus_leg", "Best of 5")))
    modi_list = ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"]
    curr_modus = sess.get("modus", "Up & Down")
    if curr_modus not in modi_list: modi_list.append(curr_modus)
    spielmodus = st.selectbox("Spielmodus", modi_list, index=modi_list.index(curr_modus))
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        curr_total, curr_singles = sess.get("total_rounds", 6), sess.get("singles_rounds", 4)
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=curr_singles-1)
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 11)), index=(curr_total - curr_singles)-1)
        total_rounds = singles_rounds + coop_rounds
    elif spielmodus == "Koop 2vs2 (Up & Down)":
        singles_rounds, total_rounds = 0, st.selectbox("Anzahl Koop-Runden", list(range(1, 11)), index=sess.get("total_rounds", 2)-1)
    else:
        singles_rounds, total_rounds = 0, st.selectbox("Anzahl Runden", list(range(1, 11)), index=sess.get("total_rounds", 4)-1)
    
    board_opts = ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"]
    curr_b = sess.get("boards", "4 Boards")
    if curr_b not in board_opts: board_opts.append(curr_b)
    anzahl_boards = st.selectbox("Anzahl der Boards", board_opts, index=board_opts.index(curr_b))
    
    st.write("### Spieler anpassen")
    anwesende = []
    cols = st.columns(2)
    for i, sp in enumerate(kader):
        with cols[0 if i < len(kader)//2 else 1]:
            if st.checkbox(sp, value=(sp in sess.get("spieler", [])), key=f"edit_kader_{sp}_{session_idx}"): anwesende.append(sp)
                
    curr_gaeste = sess.get("gaeste", [])
    gaeste = [x for x in [st.text_input(f"Gast {i+1}", value=curr_gaeste[i] if i<len(curr_gaeste) else "") for i in range(4)] if x.strip() != ""]
    aktive_spieler = anwesende + gaeste
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c_btn2:
        if st.button("Speichern", type="primary", use_container_width=True):
            sess.update({
                "datum": session_datum.strftime("%d.%m.%Y"),
                "start_time": edit_start_time.strip() or None, "end_time": edit_end_time.strip() or None,
                "modus": spielmodus, "boards_count": int(anzahl_boards.split()[0]),
                "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds,
                "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus,
                "spieler": aktive_spieler, "gaeste": gaeste
            })
            st.session_state.sessions_list[session_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🗑️ Session Löschen (Admin)")
def open_delete_session_dialog(session_id):
    st.warning(f"Willst du die Session **{session_id}** wirklich unwiderruflich löschen?")
    pwd = st.text_input("Passwort zur Bestätigung:", type="password", key=f"del_pwd_{session_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c2:
        if st.button("🗑️ Unwiderruflich löschen", type="primary", use_container_width=True):
            if pwd == "1521":
                delete_session(session_id)
                st.success("Session wurde erfolgreich gelöscht!")
                st.rerun()
            else: st.error("Falsches Passwort!")

@st.dialog("📋 Board-Erfassung & Tracking")
def open_board_dialog(board_name, session_idx):
    all_sessions_sorted = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
    sess = all_sessions_sorted[session_idx]
    real_idx = st.session_state.sessions_list.index(sess)
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds:
        st.warning(f"{board_name} hat alle Runden beendet.")
        if st.button("Schließen"): st.rerun()
        return

    modus = sess.get("modus", "Up & Down")
    is_standard = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_standard and total_rounds > 2 else total_rounds)
    r_display = f"Doppelrunde {current_round - singles_rounds} (Coop)" if is_standard and current_round > singles_rounds else f"Runde {current_round} (Einzel)" if is_standard else f"Runde {current_round}"

    st.write(f"### {board_name} — {r_display}")
    existing_match = res.get((current_round, board_name))
    
    if existing_match:
        current_p1, current_p2 = existing_match.get("s1", "-"), existing_match.get("s2", "-")
        try: score1, score2 = map(int, existing_match.get("ergebnis", "0:0").split(":"))
        except: score1, score2 = 0, 0
        t1_180, t2_180 = int(existing_match.get("180_s1", 0)), int(existing_match.get("180_s2", 0))
        avg1, avg2 = float(existing_match.get("avg_s1", 0.0)), float(existing_match.get("avg_s2", 0.0))
    else:
        auto_players = get_board_players(sess, current_round, board_name)
        current_p1, current_p2 = auto_players[0], auto_players[1]
        score1, score2, t1_180, t2_180, avg1, avg2 = 0, 0, 0, 0, 0.0, 0.0

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Heim:** `{current_p1}`")
        in_score1 = st.number_input("Legs Heim", 0, 5, score1)
        in_180_1 = st.number_input("🎯 180er Heim", 0, 20, t1_180)
        in_avg_1 = st.number_input("📊 Avg Heim", 0.0, 180.0, avg1, step=0.1)
    with c2:
        st.markdown(f"**Gast:** `{current_p2}`")
        in_score2 = st.number_input("Legs Gast", 0, 5, score2)
        in_180_2 = st.number_input("🎯 180er Gast", 0, 20, t2_180)
        in_avg_2 = st.number_input("📊 Avg Gast", 0.0, 180.0, avg2, step=0.1)
        
    ergebnis = f"{in_score1}:{in_score2}"
    winner = current_p1 if in_score1 > in_score2 else (current_p2 if in_score2 > in_score1 else "-")
    loser = current_p2 if winner == current_p1 else (current_p1 if winner == current_p2 else "-")
    
    st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Sieger: **{winner if winner != '-' else 'Unentschieden'}**")
    
    req_win = 3 if sess.get("modus_leg", "Best of 5") == "Best of 5" else 2
    is_valid_result = True
    if current_p1 != "-" and current_p2 != "-":
        if in_score1 == in_score2: st.error("Unentschieden nicht möglich."), is_valid_result.__init__(False)
        elif in_score1 > req_win or in_score2 > req_win: st.error(f"Max {req_win} Legs."), is_valid_result.__init__(False)
        elif in_score1 != req_win and in_score2 != req_win: st.error(f"Sieger braucht genau {req_win} Legs."), is_valid_result.__init__(False)
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Ergebnis abschließen", type="primary", use_container_width=True, disabled=not is_valid_result):
            if is_valid_result:
                if "results" not in sess: sess["results"] = {}
                sess["results"][(current_round, board_name)] = {
                    "s1": current_p1, "s2": current_p2, "ergebnis": ergebnis, "winner": winner, "loser": loser,
                    "180_s1": in_180_1, "180_s2": in_180_2, "avg_s1": in_avg_1, "avg_s2": in_avg_2
                }
                st.session_state.sessions_list[real_idx] = sess
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()
    with cb2:
        if st.button("Schließen", use_container_width=True): st.rerun()

# --------------------------
# --- LIGA FUNKTIONEN ---
# --------------------------

LIGA_ROUNDS = [
    [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2")],
    [("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")],
    [("m5", "Einzel 5 (Kreuz)", "h1", "g2"), ("m6", "Einzel 6 (Kreuz)", "h2", "g1")],
    [("m7", "Einzel 7 (Kreuz)", "h3", "g4"), ("m8", "Einzel 8 (Kreuz)", "h4", "g3")],
    [("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
]
LIGA_MATCH_MAP = [match for round in LIGA_ROUNDS for match in round]

def generate_spielbericht_pdf(sess):
    """Erstellt den PDF-Spielbericht per Overlay-Verfahren mit exakter BDV-Formular-Matrix."""
    import io
    import os
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except ImportError:
        raise ImportError("Fehlende Bibliotheken (pypdf oder reportlab)")

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica", 11)
    
    heim = sess.get("heim_team", "")
    gast = sess.get("gast_team", "")
    datum = sess.get("datum", "")
    
    # 1. Metadaten eintragen (Angepasste Koordinaten für Bez_Schwaben_Spielbericht_2.pdf)
    c.drawString(460, 745, datum)
    c.drawString(110, 715, heim) 
    c.drawString(340, 715, gast)
    
    res = sess.get("results", {})
    auf_h = sess.get("auf_heim", {})
    auf_g = sess.get("auf_gast", {})

    # Matrix für die 10 Spiele (Y-Koordinaten pro Zeile von oben nach unten)
    # Block 1 (Einzel 1-4)
    y_coords = {
        "m1": 630, "m2": 590, "m3": 545, "m4": 505,
        "m5": 435, "m6": 395, "m7": 350, "m8": 305,
        "m9": 200, "m10": 120
    }
    
    # X-Spalten Definitionen
    x_name_heim = 60
    x_name_gast = 310
    
    x_legs_heim = 260
    x_legs_gast = 480
    
    x_180_heim = 65
    x_180_gast = 315
    
    for m_key, label, h_key, g_key in LIGA_MATCH_MAP:
        if m_key in res and res[m_key].get("played"):
            m_data = res[m_key]
            y = y_coords[m_key]
            
            # Spielernamen
            c.drawString(x_name_heim, y, str(auf_h.get(h_key, "")))
            c.drawString(x_name_gast, y, str(auf_g.get(g_key, "")))
            
            # Legs
            c.drawString(x_legs_heim, y, str(m_data.get("lh", 0)))
            c.drawString(x_legs_gast, y, str(m_data.get("lg", 0)))
            
            # 180er (Y-Koordinate etwas tiefer in der kleinen Zeile darunter)
            y_sub = y - 15
            if m_data.get("180_h", 0) > 0:
                c.drawString(x_180_heim, y_sub, str(m_data.get("180_h", "")))
            if m_data.get("180_g", 0) > 0:
                c.drawString(x_180_gast, y_sub, str(m_data.get("180_g", "")))

    c.save()
    packet.seek(0)
    
    pdf_out = io.BytesIO()
    
    # 2. Overlay über das Original-PDF legen
    if os.path.exists("Bez_Schwaben_Spielbericht_2.pdf"):
        new_pdf = PdfReader(packet)
        original_pdf = PdfReader(open("Bez_Schwaben_Spielbericht_2.pdf", "rb"))
        output = PdfWriter()
        page = original_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
        output.write(pdf_out)
    elif os.path.exists("Bez_Schwaben_Spielbericht.pdf"): # Fallback für alten Namen
        new_pdf = PdfReader(packet)
        original_pdf = PdfReader(open("Bez_Schwaben_Spielbericht.pdf", "rb"))
        output = PdfWriter()
        page = original_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
        output.write(pdf_out)
    else:
        # Fallback-Ausgabe, falls Datei nicht hochgeladen wurde
        c2 = canvas.Canvas(pdf_out, pagesize=A4)
        c2.drawString(100, 750, "FEHLER: Originaldatei 'Bez_Schwaben_Spielbericht_2.pdf' fehlt!")
        c2.drawString(100, 700, f"Spiel: {heim} vs {gast}")
        c2.save()

    pdf_out.seek(0)
    return pdf_out

@st.dialog("➕ Neues Liga-Spiel (4. BezLiga)", width="large")
def open_new_liga_match_dialog():
    st.write("Erstelle hier ein neues Ligaspiel. Die Aufstellung erfolgt gleich völlig unabhängig vom Trainingskader im Live-Modus.")
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum des Ligaspiels", date.today())
    heim_team = c2.text_input("Heimmannschaft", value="Wehringer Steelers")
    gast_team = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    
    st.write("Auf welchen Boards wird gespielt? (Board A: Links, Board B: Rechts)")
    c3, c4 = st.columns(2)
    b1 = c3.selectbox("Board A (Linkes Board)", ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"], index=0)
    b2 = c4.selectbox("Board B (Rechtes Board)", ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"], index=1)
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with cb2:
        if st.button("Liga-Spiel erstellen", type="primary", use_container_width=True):
            max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "L-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
            new_session = {
                "id": f"L-{max_id + 1}",
                "datum": session_datum.strftime("%d.%m.%Y"),
                "is_liga": True,
                "heim_team": heim_team.strip(),
                "gast_team": gast_team.strip(),
                "liga_boards": [b1, b2],
                "auf_heim": {},
                "auf_gast": {},
                "results": {}
            }
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("⚙️ Liga-Session bearbeiten")
def open_edit_liga_session_dialog(session_idx):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_{session_idx}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return
    
    sess = st.session_state.sessions_list[session_idx]
    
    try: curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_date = date.today()
    
    session_datum = st.date_input("Datum", curr_date)
    heim_team = st.text_input("Heimmannschaft", value=sess.get("heim_team", ""))
    gast_team = st.text_input("Gastmannschaft", value=sess.get("gast_team", ""))
    
    curr_boards = sess.get("liga_boards", ["Kaiser B1", "Board 2"])
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    c3, c4 = st.columns(2)
    b1 = c3.selectbox("Board A (Linkes Board)", board_options, index=board_options.index(curr_boards[0]) if curr_boards[0] in board_options else 0)
    b2 = c4.selectbox("Board B (Rechtes Board)", board_options, index=board_options.index(curr_boards[1]) if curr_boards[1] in board_options else 1)
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c_btn2:
        if st.button("Speichern", type="primary", use_container_width=True):
            sess.update({
                "datum": session_datum.strftime("%d.%m.%Y"),
                "heim_team": heim_team.strip(),
                "gast_team": gast_team.strip(),
                "liga_boards": [b1, b2]
            })
            st.session_state.sessions_list[session_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔒 Einzel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_einzel(session_idx, is_heim):
    sess = st.session_state.sessions_list[session_idx]
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    st.write(f"### Aufstellung: {team_name}")
    st.info("Trage hier die 4 Einzelspieler als Text ein. Der Gegner sieht diese Eingabe erst nach dem Speichern.")
    
    h1 = st.text_input("Position 1")
    h2 = st.text_input("Position 2")
    h3 = st.text_input("Position 3")
    h4 = st.text_input("Position 4")
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if h1 and h2 and h3 and h4:
            if is_heim:
                sess["auf_heim"].update({"h1": h1.strip(), "h2": h2.strip(), "h3": h3.strip(), "h4": h4.strip()})
            else:
                sess["auf_gast"].update({"g1": h1.strip(), "g2": h2.strip(), "g3": h3.strip(), "g4": h4.strip()})
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
        else:
            st.error("Bitte alle 4 Positionen eintragen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_idx, is_heim):
    sess = st.session_state.sessions_list[session_idx]
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    st.write(f"### Doppel-Aufstellung: {team_name}")
    
    auf_dict = sess.get("auf_heim", {}) if is_heim else sess.get("auf_gast", {})
    
    bisherige_spieler = []
    for k, v in auf_dict.items():
        if ("h" in k or "g" in k) and not "d" in k:
            if v and v != "-":
                bisherige_spieler.append(v)
    bisherige_spieler = list(set(bisherige_spieler))
    bisherige_spieler.sort()
    
    options = bisherige_spieler + ["Neuer Ersatzspieler..."]
    
    st.markdown("**Doppel 1**")
    c1, c2 = st.columns(2)
    d1_p1_sel = c1.selectbox("Spieler 1", options, key="d1_p1")
    d1_p1_txt = c1.text_input("Name Ersatzspieler 1", key="d1_p1_txt") if d1_p1_sel == "Neuer Ersatzspieler..." else ""
    
    d1_p2_sel = c2.selectbox("Spieler 2", options, key="d1_p2")
    d1_p2_txt = c2.text_input("Name Ersatzspieler 2", key="d1_p2_txt") if d1_p2_sel == "Neuer Ersatzspieler..." else ""
    
    st.markdown("**Doppel 2**")
    c3, c4 = st.columns(2)
    d2_p1_sel = c3.selectbox("Spieler 1", options, key="d2_p1")
    d2_p1_txt = c3.text_input("Name Ersatzspieler 3", key="d2_p1_txt") if d2_p1_sel == "Neuer Ersatzspieler..." else ""
    
    d2_p2_sel = c4.selectbox("Spieler 2", options, key="d2_p2")
    d2_p2_txt = c4.text_input("Name Ersatzspieler 4", key="d2_p2_txt") if d2_p2_sel == "Neuer Ersatzspieler..." else ""
        
    if st.button("Speichern", type="primary", use_container_width=True):
        p1 = d1_p1_txt.strip() if d1_p1_sel == "Neuer Ersatzspieler..." else d1_p1_sel
        p2 = d1_p2_txt.strip() if d1_p2_sel == "Neuer Ersatzspieler..." else d1_p2_sel
        p3 = d2_p1_txt.strip() if d2_p1_sel == "Neuer Ersatzspieler..." else d2_p1_sel
        p4 = d2_p2_txt.strip() if d2_p2_sel == "Neuer Ersatzspieler..." else d2_p2_sel
        
        if p1 and p2 and p3 and p4:
            selected_players = [p1, p2, p3, p4]
            if len(set(selected_players)) != 4:
                st.error("🚨 Fehler: Ein Spieler kann nicht mehrfach aufgestellt werden. Jeder Name darf nur 1x vorkommen!")
            else:
                d1_str = f"{p1} & {p2}"
                d2_str = f"{p3} & {p4}"
                
                if is_heim:
                    sess["auf_heim"].update({"hd1": d1_str, "hd2": d2_str})
                else:
                    sess["auf_gast"].update({"gd1": d1_str, "gd2": d2_str})
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()
        else:
            st.error("Bitte wähle für alle 4 Positionen einen Spieler aus!")

@st.dialog("🔄 Spieler auswechseln")
def open_liga_sub_dialog(session_idx, p_key, is_heim, curr_name):
    sess = st.session_state.sessions_list[session_idx]
    st.write(f"Auswechslung für **{curr_name}**")
    
    new_name = st.text_input("Name des Ersatzspielers:")
        
    if st.button("Auswechslung Speichern", type="primary", use_container_width=True):
        if new_name.strip():
            if is_heim:
                sess["auf_heim"][p_key] = new_name.strip()
            else:
                sess["auf_gast"][p_key] = new_name.strip()
            smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🎯 Live Board (Liga)")
def open_liga_live_board_dialog(session_idx, m_key, board_name, m_label, p_heim, p_gast, anwurf_gast=False):
    sess = st.session_state.sessions_list[session_idx]
    res = sess.setdefault("results", {})
    m_data = res.get(m_key, {})
    
    st.write(f"### {board_name} — {m_label}")
    
    if anwurf_gast:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Gast (Anwurf):** `{p_gast}`")
            lg = st.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key="lg")
            e180_g = st.number_input("180er Gast", 0, 10, m_data.get("180_g", 0), key="180g")
        with c2:
            st.markdown(f"**Heim:** `{p_heim}`")
            lh = st.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key="lh")
            e180_h = st.number_input("180er Heim", 0, 10, m_data.get("180_h", 0), key="180h")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Heim (Anwurf):** `{p_heim}`")
            lh = st.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key="lh")
            e180_h = st.number_input("180er Heim", 0, 10, m_data.get("180_h", 0), key="180h")
        with c2:
            st.markdown(f"**Gast:** `{p_gast}`")
            lg = st.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key="lg")
            e180_g = st.number_input("180er Gast", 0, 10, m_data.get("180_g", 0), key="180g")

    is_valid = (lh == 3 and lg < 3) or (lg == 3 and lh < 3)
    if not is_valid:
        st.error("🚨 Best of 5: Ein Spieler muss exakt 3 Legs zum Sieg haben!")

    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Speichern", type="primary", use_container_width=True, disabled=not is_valid):
            res[m_key] = {
                "lh": lh, "lg": lg, "played": True,
                "180_h": e180_h,
                "180_g": e180_g
            }
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
    with cb2:
        if st.button("Abbrechen", use_container_width=True): st.rerun()

@st.dialog("📝 Offizieller Spielbericht (Korrektur)", width="large")
def open_liga_bericht_dialog(session_idx):
    sess = st.session_state.sessions_list[session_idx]
    auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
    res = sess.setdefault("results", {})
    st.write(f"Hier kannst du bei Bedarf alle Ergebnisse manuell korrigieren.")
    
    all_valid = True
    
    for m_key, label, h_key, g_key in LIGA_MATCH_MAP:
        p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
        m_data = res.get(m_key, {})
        with st.expander(f"{label}: {p_heim} vs {p_gast}", expanded=False):
            c_lh, c_vs, c_lg = st.columns([2, 1, 2])
            lh = c_lh.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"blh_{m_key}")
            c_vs.markdown("<div style='text-align: center; padding-top: 30px;'>:</div>", unsafe_allow_html=True)
            lg = c_lg.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"blg_{m_key}")
            
            is_match_valid = (lh == 0 and lg == 0) or (lh == 3 and lg < 3) or (lg == 3 and lh < 3)
            if not is_match_valid:
                st.error(f"🚨 Ungültig! Best of 5 erfordert exakt 3 Legs für den Sieger.")
                all_valid = False
                
            res[m_key] = {"lh": lh, "lg": lg, "played": True if (lh>0 or lg>0) else False, "180_h": m_data.get("180_h", 0), "180_g": m_data.get("180_g", 0)}

    st.divider()
    
    is_locked = sess.get("is_locked", False)
    if not is_locked:
        lock_spiel = st.checkbox("🔒 Spiel endgültig abschließen (Verschiebt das Spiel dauerhaft ins Archiv)", value=False)
    else:
        lock_spiel = True
        st.info("Dieses Spiel ist bereits offiziell abgeschlossen und archiviert.")

    if st.button("💾 Speichern & Schließen", type="primary", use_container_width=True, disabled=not all_valid):
        sess["is_locked"] = lock_spiel
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

# --------------------------
# --- TABS RENDERING ---
# --------------------------

with tab_übersicht:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session", type="primary", use_container_width=True, key="quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        sorted_for_btn = sorted(training_sessions, key=lambda x: int(x["id"].split("-")[1]) if "id" in x and "-" in x["id"] else 0, reverse=True)
        active_sessions_for_btn = [s for s in sorted_for_btn if not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Bearbeiten", use_container_width=True, key="edit_active_btn"):
                open_edit_session_dialog(training_sessions.index(active_sessions_for_btn[0]))
        else:
            st.button("⚙️ Bearbeiten", use_container_width=True, disabled=True)
            
    st.write("")
    st.markdown("### 🔴 Laufende Trainings-Session")
    if not active_sessions_for_btn:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        curr_sess = active_sessions_for_btn[0]
        start_t = curr_sess.get("start_time")
        if not start_t:
            st.info(f"Session **{curr_sess['id']}** wurde erstellt für den **{curr_sess['datum']}**.")
            st.write(f"👥 **Gemeldete Spieler:** {', '.join(curr_sess.get('spieler', []))}")
            if st.button("🚀 Teamtraining starten", type="primary", use_container_width=True):
                curr_sess["start_time"] = get_local_time_str()
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()
        else:
            st.caption(f"Session-ID: **{curr_sess['id']}** vom {curr_sess['datum']} (Start: {start_t} Uhr) | Modus: {curr_sess['modus']}")
            total_rounds = curr_sess.get("total_rounds", 4)
            modus = curr_sess.get("modus", "Up & Down")
            is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
            singles_rounds = curr_sess.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
            res = curr_sess.get("results", {})
            
            if modus == "Koop 2vs2 (Up & Down)": active_boards_list = ["Kaiser B1", "Board 2"]
            elif is_standard_training:
                bc = curr_sess.get("boards_count", 4)
                base_boards = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"][:bc]
                singles_complete = True
                for b in base_boards:
                    if max([r for (r, board_n), v in res.items() if board_n == b and v.get("winner")] + [0]) < singles_rounds:
                        singles_complete = False; break
                active_boards_list = ["Kaiser B1", "Board 2"] if (singles_complete and singles_rounds > 0 and any(r <= singles_rounds for (r, b), v in res.items())) else base_boards
            else: active_boards_list = get_boards_list(curr_sess, 1)
            
            for b_name in active_boards_list:
                completed_r = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
                next_r = max(completed_r) + 1 if completed_r else 1
                
                with st.container(border=True):
                    st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                    if next_r <= total_rounds:
                        ready = is_board_ready(curr_sess, b_name, next_r)
                        ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                        st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                        
                        m_info = res.get((next_r, b_name))
                        p1, p2 = (m_info.get("s1", "-"), m_info.get("s2", "-")) if m_info else get_board_players(curr_sess, next_r, b_name)
                        r_head = f"Doppelrunde {next_r - singles_rounds} (Coop)" if is_standard_training and next_r > singles_rounds else f"Runde {next_r} (Einzel)" if is_standard_training else f"Runde {next_r}"
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{r_head}</p>", unsafe_allow_html=True)
                        
                        sc1, sc2 = st.columns([5, 2])
                        sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                        with sc2:
                            if st.button("🔄", key=f"sub1_{b_name}_{next_r}"): open_substitution_dialog(b_name, training_sessions.index(curr_sess), next_r, 1, p1)
                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                        sc3, sc4 = st.columns([5, 2])
                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                        with sc4:
                            if st.button("🔄", key=f"sub2_{b_name}_{next_r}"): open_substitution_dialog(b_name, training_sessions.index(curr_sess), next_r, 2, p2)
                        
                        st.write("")
                        if st.button("🎯 Eintragen", key=f"live_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                            open_board_dialog(b_name, training_sessions.index(curr_sess))
                    else:
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle Runden beendet</p>", unsafe_allow_html=True)
                        st.success("✅ Abgeschlossen")

with tab_kader:
    st.subheader("Kader & Spielerbilanz (Teamtraining)")
    
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0} for p in kader}
    for sess in training_sessions:
        for match in sess.get("results", {}).values():
            winner, loser, s1, s2 = match.get("winner", ""), match.get("loser", ""), match.get("s1", ""), match.get("s2", "")
            try: l1, l2 = map(int, match.get("ergebnis", "0:0").split(":"))
            except ValueError: l1, l2 = 0, 0
            h1, h2 = int(match.get("180_s1", 0)), int(match.get("180_s2", 0))
            a1, a2 = float(match.get("avg_s1", 0.0)), float(match.get("avg_s2", 0.0))
            
            if s1 in stats and " & " not in s1:
                stats[s1]["180er"] += h1; stats[s1]["Legs_Won"] += l1; stats[s1]["Legs_Lost"] += l2
                if a1 > 0: stats[s1]["Avg_Sum"] += a1; stats[s1]["Avg_Count"] += 1
            if s2 in stats and " & " not in s2:
                stats[s2]["180er"] += h2; stats[s2]["Legs_Won"] += l2; stats[s2]["Legs_Lost"] += l1
                if a2 > 0: stats[s2]["Avg_Sum"] += a2; stats[s2]["Avg_Count"] += 1
            if winner and " & " not in winner:
                for p in winner.split(" & "):
                    if p in stats: stats[p]["Matches"] += 1; stats[p]["Siege"] += 1
            if loser and " & " not in loser:
                for p in loser.split(" & "):
                    if p in stats: stats[p]["Matches"] += 1; stats[p]["Niederlagen"] += 1

    valid_players = [p for p in kader if stats[p]["Matches"] >= 3]
    mvp_help, dauerbrenner_help = None, None
    if valid_players:
        best_rate = max([(stats[p]["Siege"] / stats[p]["Matches"]) for p in valid_players])
        top_mvps = [p for p in valid_players if abs((stats[p]["Siege"] / stats[p]["Matches"]) - best_rate) < 1e-9]
        mvp_rate = best_rate
        mvp_text = f"{(mvp_rate*100):.0f}% Siege"
        if len(top_mvps) == len(kader): mvp_player = "Alle gleichauf"
        elif len(top_mvps) <= 2: mvp_player = " & ".join(top_mvps)
        else:
            mvp_player = f"{len(top_mvps)} Spieler"
            mvp_help = "Aktuelle MVPs:\n\n" + "\n".join([f"- {p}" for p in top_mvps])
    else: mvp_player, mvp_text = "N/A", "Min. 3 Matches nötig"
        
    max_matches = max([stats[p]["Matches"] for p in kader], default=0)
    if max_matches > 0:
        top_active = [p for p in kader if stats[p]["Matches"] == max_matches]
        if len(top_active) == len(kader): active_player = "Alle gleichauf"
        elif len(top_active) <= 2: active_player = " & ".join(top_active)
        else:
            active_player = f"{len(top_active)} Spieler"
            dauerbrenner_help = "Aktuelle Dauerbrenner:\n\n" + "\n".join([f"- {p}" for p in top_active])
        active_count = f"{max_matches} Matches"
    else: active_player, active_count = "N/A", "0 Matches"
        
    best_avg_player, best_avg_val = "N/A", 0.0
    for p in kader:
        if stats[p]["Avg_Count"] > 0:
            p_avg = stats[p]["Avg_Sum"] / stats[p]["Avg_Count"]
            if p_avg > best_avg_val: best_avg_val, best_avg_player = p_avg, p
    avg_text = f"Ø {best_avg_val:.1f}" if best_avg_val > 0 else "Kein Avg erfasst"
    
    max_180_player = max(kader, key=lambda p: stats[p]["180er"])
    max_180_count = stats[max_180_player]["180er"]
    machine_player, machine_text = (max_180_player, f"{max_180_count}x geworfen") if max_180_count > 0 else ("N/A", "0 geworfen")

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1: st.metric(label="🏆 MVP (Siegquote)", value=mvp_player, delta=mvp_text, delta_color="normal", help=mvp_help)
        with c2: st.metric(label="🔥 Dauerbrenner", value=active_player, delta=active_count, delta_color="off", help=dauerbrenner_help)
        st.divider()
        c3, c4 = st.columns(2)
        with c3: st.metric(label="📊 Bester Gesamt-Avg", value=best_avg_player, delta=avg_text, delta_color="off")
        with c4: st.metric(label="🎯 180er Maschine", value=machine_player, delta=machine_text, delta_color="off")
        
    st.write("### Spielerübersicht & Rangliste")
    table_rows = [{"Spieler": p, "Matches": stats[p]["Matches"], "Siege": stats[p]["Siege"], "Niederlagen": stats[p]["Niederlagen"], "Siegquote": f"{(stats[p]['Siege'] / stats[p]['Matches'] * 100):.0f}%" if stats[p]["Matches"] > 0 else "0%", "Legs Gewonnen": stats[p]["Legs_Won"], "Legs Verloren": stats[p]["Legs_Lost"], "🎯 180er": stats[p]["180er"], "📊 Ø Average": f"{(stats[p]['Avg_Sum'] / stats[p]['Avg_Count']):.1f}" if stats[p]["Avg_Count"] > 0 else "–"} for p in kader]
    for row in sorted(table_rows, key=lambda x: (x["Siege"], x["Legs Gewonnen"]), reverse=True):
        with st.container(border=True):
            st.markdown(f"**{row['Spieler']}** — Quote: **{row['Siegquote']}**")
            st.caption(f"🏆 Siege: {row['Siege']}/{row['Matches']} | 📊 Avg: {row['📊 Ø Average']} | 🎯 180er: {row['🎯 180er']} | Legs: {row['Legs Gewonnen']}:{row['Legs Verloren']}")

with tab_session:
    st.subheader("Up & Down Sessions")
    total_anwesende = sum([len([p for p in s.get("spieler", []) if p != "-"]) for s in training_sessions])
    avg_anwesende = f"{(total_anwesende / len(training_sessions)):.1f}" if training_sessions else "0"
    
    kaiser_count = {}
    for sess in training_sessions:
        k_m = [(r, m) for (r, b), m in sess.get("results", {}).items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "")]
        if k_m:
            w = sorted(k_m, key=lambda x: x[0], reverse=True)[0][1].get("winner")
            if w and w != "-": kaiser_count[w] = kaiser_count.get(w, 0) + 1
    rekord_kaiser = max(kaiser_count, key=kaiser_count.get) if kaiser_count else "Noch offen"
    
    gt_min, gt_rounds, gt_legs = 0, 0, 0
    for sess in training_sessions:
        st_t, en_t = sess.get("start_time"), sess.get("end_time")
        if st_t and en_t:
            try:
                diff = (datetime.strptime(en_t, "%H:%M") - datetime.strptime(st_t, "%H:%M")).total_seconds() / 60
                if diff < 0: diff += 24 * 60
                if diff > 0:
                    gt_min += diff; gt_rounds += sess.get("total_rounds", 4)
                    gt_legs += sum([sum(map(int, m.get("ergebnis", "0:0").split(":"))) for m in sess.get("results", {}).values() if ":" in m.get("ergebnis", "")])
            except: pass
            
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1: st.metric("Gespielte Abende", str(len(training_sessions)))
        with c2: st.metric("Ø Anwesende", avg_anwesende, "Spieler")
        with c3: st.metric("Rekord-Kaiser", rekord_kaiser, "Meiste B1 Siege")
        st.divider()
        c4, c5 = st.columns(2)
        with c4: st.metric("⏱️ Ø Dauer pro Runde", f"{(gt_min / gt_rounds):.1f} Min." if gt_rounds > 0 else "0.0 Min.", delta="Gesamt-Durchschnitt", delta_color="off")
        with c5: st.metric("🎯 Ø Dauer pro Leg", f"{(gt_min / gt_legs):.1f} Min." if gt_legs > 0 else "0.0 Min.", delta="Gesamt-Durchschnitt", delta_color="off")

with tab_liga:
    st.subheader("Freundschaftsspiele")
    st.write("Isolierter Bereich für Freundschaftsspiele (Format 4er-Team). Verdeckte Eingabe und automatische PDF-Ausgabe.")
    
    if st.button("➕ Neues Freundschaftsspiel starten", type="primary", use_container_width=True):
        open_new_liga_match_dialog()
        
    st.divider()
    
    if not liga_sessions:
        st.info("Noch keine Liga-Spiele angelegt.")
    else:
        active_liga = [s for s in liga_sessions if not s.get("is_locked", False)]
        if not active_liga:
            st.success("🎉 Alle aktuellen Spiele sind abgeschlossen! Du findest die PDF-Berichte ganz unten.")
            
        sorted_liga = sorted(active_liga, key=lambda x: int(x["id"].split("-")[1]) if "id" in x and "-" in x["id"] else 0, reverse=True)
        for l_sess in sorted_liga:
            real_idx = st.session_state.sessions_list.index(l_sess)
            heim = l_sess.get("heim_team", "Heim")
            gast = l_sess.get("gast_team", "Gast")
            res = l_sess.setdefault("results", {})
            boards = l_sess.get("liga_boards", ["Kaiser B1", "Board 2"])
                
            auf_h = l_sess.setdefault("auf_heim", {})
            auf_g = l_sess.setdefault("auf_gast", {})
            
            # Live Score berechnen
            sets_heim, sets_gast, legs_heim, legs_gast = 0, 0, 0, 0
            for m_data in res.values():
                if m_data.get("played"):
                    lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                    legs_heim += lh; legs_gast += lg
                    if lh > lg: sets_heim += 1
                    elif lg > lh: sets_gast += 1
                    
            is_done = len([k for k, v in res.items() if v.get("played")]) == 10
            status = "✅ Abgeschlossen" if is_done else "🔴 Aktiv"
            
            with st.container(border=True):
                st.markdown(f"### {heim} vs. {gast}")
                st.caption(f"{l_sess['datum']} | ID: {l_sess['id']} | Status: {status}")
                st.markdown(f"**Sets:** {sets_heim} : {sets_gast} | **Legs:** {legs_heim} : {legs_gast}")
                
                # Setup Phase Checks
                h_einzel_ok = all(auf_h.get(k) for k in ["h1", "h2", "h3", "h4"])
                g_einzel_ok = all(auf_g.get(k) for k in ["g1", "g2", "g3", "g4"])
                
                if not h_einzel_ok or not g_einzel_ok:
                    st.warning("⚠️ Phase 1: Es müssen zwingend beide Teams verdeckt aufgestellt werden, bevor die Boards freigegeben werden!")
                    c_h, c_g = st.columns(2)
                    if not h_einzel_ok and c_h.button("🔒 Heim Aufstellen", key=f"h_setup_{l_sess['id']}", use_container_width=True):
                        open_liga_aufstellung_einzel(real_idx, True)
                    if not g_einzel_ok and c_g.button("🔒 Gast Aufstellen", key=f"g_setup_{l_sess['id']}", use_container_width=True):
                        open_liga_aufstellung_einzel(real_idx, False)
                elif not is_done:
                    # Finde den aktuellen aktiven Block (0 bis 4)
                    curr_block = 0
                    for r_idx, round_matches in enumerate(LIGA_ROUNDS):
                        if not all(res.get(m[0], {}).get("played") for m in round_matches):
                            curr_block = r_idx
                            break
                    else:
                        curr_block = 5 # Finished
                            
                    h_doppel_ok = bool(auf_h.get("hd1"))
                    g_doppel_ok = bool(auf_g.get("gd1"))
                    
                    if curr_block == 4 and (not h_doppel_ok or not g_doppel_ok): # Doppel Runde erreicht
                        st.warning("⚠️ Phase 3: Einzel sind beendet. Bitte jetzt zwingend die Doppel aufstellen, um fortzufahren!")
                        c_dh, c_dg = st.columns(2)
                        if not h_doppel_ok and c_dh.button("🔒 Heim Doppel", key=f"hd_setup_{l_sess['id']}", use_container_width=True):
                            open_liga_aufstellung_doppel(real_idx, True)
                        if not g_doppel_ok and c_dg.button("🔒 Gast Doppel", key=f"gd_setup_{l_sess['id']}", use_container_width=True):
                            open_liga_aufstellung_doppel(real_idx, False)
                    else:
                        # Optionales Vorab-Aufstellen der Doppel ab der 2. Runde (Kreuzrunde = Block 2)
                        if curr_block >= 2 and curr_block < 4 and (not h_doppel_ok or not g_doppel_ok):
                            with st.expander("🔜 Doppel bereits jetzt aufstellen (Optional)", expanded=True):
                                st.info("Ihr könnt die Doppel-Aufstellung jetzt schon eintragen, während die Einzel noch laufen.")
                                c_dh, c_dg = st.columns(2)
                                if not h_doppel_ok and c_dh.button("🔒 Heim Doppel Aufstellen", key=f"hd_setup_opt_{l_sess['id']}", use_container_width=True):
                                    open_liga_aufstellung_doppel(real_idx, True)
                                if not g_doppel_ok and c_dg.button("🔒 Gast Doppel Aufstellen", key=f"gd_setup_opt_{l_sess['id']}", use_container_width=True):
                                    open_liga_aufstellung_doppel(real_idx, False)
                                    
                        # Zeige Live Boards für aktuelle Runde (sofern bereit)
                        if curr_block < 4 or (curr_block == 4 and h_doppel_ok and g_doppel_ok):
                            active_matches = LIGA_ROUNDS[curr_block]
                            
                            block_titles = ["Runde 1 (Einzel 1 & 2)", "Runde 1 (Einzel 3 & 4)", "Runde 2 (Kreuz-Einzel 1)", "Runde 2 (Kreuz-Einzel 2)", "Runde 3 (Doppel)"]
                            st.markdown(f"#### 🎯 {block_titles[curr_block]} läuft:")
                            
                            c_boardA, c_boardB = st.columns(2)
                            
                            for i, (m_key, m_label, h_key, g_key) in enumerate(active_matches):
                                board_col = c_boardA if i == 0 else c_boardB
                                is_anwurf_gast = (i == 1)
                                b_name = boards[0] if i == 0 else boards[1]
                                anwurf = "Gast" if is_anwurf_gast else "Heim"
                                
                                p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
                                is_played = res.get(m_key, {}).get("played", False)
                                
                                with board_col:
                                    with st.container(border=True):
                                        st.markdown(f"<h5 style='text-align: center; margin-bottom: 0;'>{b_name}</h5>", unsafe_allow_html=True)
                                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{m_label} | 🎯 Anwurf: {anwurf}</p>", unsafe_allow_html=True)
                                        
                                        # Gastspieler nach oben schieben, wenn er Anwurf hat (Rechtes Board)
                                        if is_anwurf_gast:
                                            p_top, p_bot = p_gast, p_heim
                                            k_top, k_bot = g_key, h_key
                                            t_is_heim, b_is_heim = False, True
                                        else:
                                            p_top, p_bot = p_heim, p_gast
                                            k_top, k_bot = h_key, g_key
                                            t_is_heim, b_is_heim = True, False
                                        
                                        # Top Spieler
                                        sc1, sc2 = st.columns([5, 2])
                                        sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p_top}</div>", unsafe_allow_html=True)
                                        # Auswechseln nur im Kreuz-Modus (Block 2 und 3) erlaubt
                                        if not is_played and curr_block in [2, 3]:
                                            if sc2.button("🔄", key=f"sub_t_{m_key}_{l_sess['id']}", help="Spieler auswechseln"): 
                                                open_liga_sub_dialog(real_idx, k_top, t_is_heim, p_top)
                                        
                                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                                        
                                        # Bottom Spieler
                                        sc3, sc4 = st.columns([5, 2])
                                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p_bot}</div>", unsafe_allow_html=True)
                                        if not is_played and curr_block in [2, 3]:
                                            if sc4.button("🔄", key=f"sub_b_{m_key}_{l_sess['id']}", help="Spieler auswechseln"): 
                                                open_liga_sub_dialog(real_idx, k_bot, b_is_heim, p_bot)
                                        
                                        st.write("")
                                        if is_played:
                                            if is_anwurf_gast:
                                                st.success(f"Ergebnis: {res[m_key]['lg']} : {res[m_key]['lh']}")
                                            else:
                                                st.success(f"Ergebnis: {res[m_key]['lh']} : {res[m_key]['lg']}")
                                        else:
                                            if st.button("🎯 Eintragen", key=f"live_{m_key}_{l_sess['id']}", use_container_width=True):
                                                open_liga_live_board_dialog(real_idx, m_key, b_name, m_label, p_heim, p_gast, is_anwurf_gast)

                        # Vorschau für wartende Matches (damit vorab ausgewechselt werden kann)
                        if curr_block < 3:
                            next_block = curr_block + 1
                            next_matches = LIGA_ROUNDS[next_block]
                            st.write("")
                            st.markdown(f"**🔜 Wartende Matches (als nächstes):**")
                            
                            c_nextA, c_nextB = st.columns(2)
                            for i, (m_key, m_label, h_key, g_key) in enumerate(next_matches):
                                board_col = c_nextA if i == 0 else c_nextB
                                is_anwurf_gast = (i == 1)
                                b_name = boards[0] if i == 0 else boards[1]
                                
                                p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
                                
                                with board_col:
                                    with st.container(border=True):
                                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em; margin-bottom: 5px;'>{b_name} | {m_label} | 🎯 Anwurf: {'Gast' if is_anwurf_gast else 'Heim'}</p>", unsafe_allow_html=True)
                                        
                                        if is_anwurf_gast:
                                            p_top, p_bot = p_gast, p_heim
                                            k_top, k_bot = g_key, h_key
                                            t_is_heim, b_is_heim = False, True
                                        else:
                                            p_top, p_bot = p_heim, p_gast
                                            k_top, k_bot = h_key, g_key
                                            t_is_heim, b_is_heim = True, False
                                        
                                        sc1, sc2 = st.columns([5, 2])
                                        sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px; opacity: 0.6;'>{p_top}</div>", unsafe_allow_html=True)
                                        # Auswechseln ab Kreuzrunde (Block 2 und 3) erlaubt
                                        if next_block in [2, 3]:
                                            if sc2.button("🔄", key=f"sub_t_prev_{m_key}_{l_sess['id']}", help="Spieler vorab auswechseln"): 
                                                open_liga_sub_dialog(real_idx, k_top, t_is_heim, p_top)
                                                
                                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                                        
                                        sc3, sc4 = st.columns([5, 2])
                                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px; opacity: 0.6;'>{p_bot}</div>", unsafe_allow_html=True)
                                        if next_block in [2, 3]:
                                            if sc4.button("🔄", key=f"sub_b_prev_{m_key}_{l_sess['id']}", help="Spieler vorab auswechseln"): 
                                                open_liga_sub_dialog(real_idx, k_bot, b_is_heim, p_bot)

                if is_done or (h_einzel_ok and g_einzel_ok):
                    st.divider()
                    if st.button("📝 Gesamten Spielbericht ansehen/korrigieren", key=f"l_ber_{l_sess['id']}", use_container_width=True):
                        open_liga_bericht_dialog(real_idx)

    st.divider()
    st.subheader("📈 Liga-Statistiken")
    st.write("Wertet alle gespielten Liga-Matches exakt anhand der eingetippten Namen aus.")
    
    liga_stats = {}
    
    def process_liga_player(p_name, is_win, is_doppel, e180):
        if not p_name or p_name == "-": return
        if p_name not in liga_stats:
            liga_stats[p_name] = {"e_spiele": 0, "e_siege": 0, "d_spiele": 0, "d_siege": 0, "180er": 0}
            
        if is_doppel:
            liga_stats[p_name]["d_spiele"] += 1
            if is_win: liga_stats[p_name]["d_siege"] += 1
        else:
            liga_stats[p_name]["e_spiele"] += 1
            if is_win: liga_stats[p_name]["e_siege"] += 1
            
        liga_stats[p_name]["180er"] += e180

    for sess in liga_sessions:
        auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
        res = sess.get("results", {})
        
        for m_key, m_name, h_key, g_key in LIGA_MATCH_MAP:
            m_data = res.get(m_key, {})
            if not m_data.get("played"): continue
            lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
            
            is_win_heim = lh > lg
            is_win_gast = lg > lh
            
            p_heim, p_gast = auf_h.get(h_key, ""), auf_g.get(g_key, "")
            is_doppel = "d" in h_key
            
            e180_h = m_data.get("180_h", 0)
            targets_h = str(p_heim).split("&") if is_doppel else [str(p_heim)]
            for p in targets_h: process_liga_player(p.strip(), is_win_heim, is_doppel, e180_h)
            
            e180_g = m_data.get("180_g", 0)
            targets_g = str(p_gast).split("&") if is_doppel else [str(p_gast)]
            for p in targets_g: process_liga_player(p.strip(), is_win_gast, is_doppel, e180_g)

    l_rows = []
    for p, stt in liga_stats.items():
        if stt["e_spiele"] > 0 or stt["d_spiele"] > 0:
            l_rows.append({
                "Spieler": p,
                "Einzel (S/M)": f"{stt['e_siege']}/{stt['e_spiele']}",
                "Doppel (S/M)": f"{stt['d_siege']}/{stt['d_spiele']}",
                "180er": stt['180er']
            })
            
    if l_rows:
        st.dataframe(pd.DataFrame(l_rows).sort_values(by="Einzel (S/M)", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Noch keine Statistiken für Ligamatches verfügbar.")
        
    st.divider()
    st.subheader("🗄️ Abgeschlossene Freundschaftsspiele (PDF-Export)")
    st.write("Hier findest du alle beendeten Spiele. Die PDF-Ausleitung füllt den offiziellen Spielbericht aus.")
    
    locked_liga = [s for s in liga_sessions if s.get("is_locked", False)]
    if not locked_liga:
        st.info("Noch keine abgeschlossenen Spiele vorhanden.")
    else:
        sorted_locked = sorted(locked_liga, key=lambda x: int(x["id"].split("-")[1]) if "id" in x and "-" in x["id"] else 0, reverse=True)
        for l_sess in sorted_locked:
            with st.container(border=True):
                heim = l_sess.get("heim_team", "Heim")
                gast = l_sess.get("gast_team", "Gast")
                st.markdown(f"**{l_sess['datum']} | 🏆 {heim} vs. {gast}**")
                
                try:
                    pdf_data = generate_spielbericht_pdf(l_sess)
                    st.download_button(
                        label="📥 Offiziellen Spielbericht als PDF laden",
                        data=pdf_data,
                        file_name=f"Spielbericht_{heim}_vs_{gast}.pdf",
                        mime="application/pdf",
                        key=f"pdf_dl_{l_sess['id']}"
                    )
                except Exception as e:
                    st.warning(f"PDF-Export nicht möglich: Bitte füge 'pypdf' und 'reportlab' in deine requirements.txt ein! (Fehler: {e})")

with tab_archiv:
    st.subheader("Match-Archiv (Training & Liga)")
    st.caption("Alle gespielten Sessions in chronologischer Reihenfolge.")
    
    if st.session_state.sessions_list:
        backup_json_str = json.dumps(make_serializable(st.session_state.sessions_list), ensure_ascii=False, indent=2)
        st.download_button(label="📥 Backup als JSON herunterladen", data=backup_json_str, file_name=f"steelers_backup_{date.today().strftime('%Y-%m-%d')}.json", mime="application/json", use_container_width=True)
        st.write("")

    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        # Sortiere ALLE Sessions absteigend nach echtem Datum (und bei gleichem Datum nach ID-Nummer)
        def get_sort_key(sess):
            try:
                d = datetime.strptime(sess.get("datum", "01.01.1970"), "%d.%m.%Y")
            except:
                d = datetime.strptime("01.01.1970", "%d.%m.%Y")
            try:
                num = int(sess.get("id", "").split("-")[1])
            except:
                num = 0
            return (d, num)
            
        sorted_all_sessions = sorted(st.session_state.sessions_list, key=get_sort_key, reverse=True)
        
        for sess in sorted_all_sessions:
            orig_idx = st.session_state.sessions_list.index(sess)
            is_liga = sess.get("is_liga", False)
            
            with st.container(border=True):
                if is_liga:
                    heim = sess.get("heim_team", "Heim")
                    gast = sess.get("gast_team", "Gast")
                    res = sess.get("results", {})
                    is_done = len([k for k, v in res.items() if v.get("played")]) == 10
                    status_text = "✅ [Abgeschlossen]" if is_done else "🔴 [Aktiv]"
                    st.markdown(f"**{sess['id']}** — {sess['datum']} | 🏆 {heim} vs. {gast} {status_text}")
                else:
                    status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                    st.markdown(f"**{sess['id']}** — {sess['datum']} (Training) {status_text}")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("📊 Ansehen", key=f"arch_view_{sess['id']}", use_container_width=True): 
                        if is_liga:
                            open_liga_bericht_dialog(orig_idx)
                        else:
                            open_session_summary_dialog(orig_idx)
                with c2:
                    if st.button("⚙️ Bearbeiten", key=f"arch_edit_{sess['id']}", use_container_width=True): 
                        if is_liga:
                            open_edit_liga_session_dialog(orig_idx)
                        else:
                            open_edit_session_dialog(orig_idx)
                with c3:
                    if st.button("🗑️ Löschen", key=f"arch_del_{sess['id']}", use_container_width=True): 
                        open_delete_session_dialog(sess['id'])
                
                # Blitzeintrag NUR für Trainings-Sessions anzeigen
                if not is_liga:
                    st.divider()
                    with st.expander("⚡ Blitzeintrag & Korrektur (Admin)"):
                        pwd_blitz = st.text_input("Passwort zur Freischaltung:", type="password", key=f"blitz_pwd_{sess['id']}")
                        if pwd_blitz == "1521":
                            st.success("Freigeschaltet")
                            total_rounds = sess.get("total_rounds", 4)
                            for r in range(1, total_rounds + 1):
                                st.markdown(f"**Runde {r}**")
                                boards_in_r = get_boards_list(sess, r)
                                for b_name in boards_in_r:
                                    match_info = sess.get("results", {}).get((r, b_name), {})
                                    auto_p = get_board_players(sess, r, b_name)
                                    
                                    p1 = match_info.get("s1", auto_p[0])
                                    p2 = match_info.get("s2", auto_p[1])
                                    
                                    try:
                                        s1, s2 = map(int, match_info.get("ergebnis", "0:0").split(":"))
                                    except:
                                        s1, s2 = 0, 0
                                        
                                    c_l, c_m, c_r = st.columns([4, 1, 4])
                                    with c_l:
                                        sc1 = st.number_input(f"{p1}", min_value=0, max_value=5, value=s1, key=f"blitz_{sess['id']}_{r}_{b_name}_1")
                                    with c_m:
                                        st.markdown("<div style='text-align: center; padding-top: 30px;'>:</div>", unsafe_allow_html=True)
                                    with c_r:
                                        sc2 = st.number_input(f"{p2}", min_value=0, max_value=5, value=s2, key=f"blitz_{sess['id']}_{r}_{b_name}_2")
                                    
                                    c_save, c_del = st.columns(2)
                                    with c_save:
                                        if st.button("💾 Speichern", key=f"blitz_save_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                            if sc1 == sc2:
                                                st.error("Unentschieden ist ungültig!")
                                            else:
                                                winner = p1 if sc1 > sc2 else p2
                                                loser = p2 if sc1 > sc2 else p1
                                                if "results" not in sess: sess["results"] = {}
                                                old_180_1 = match_info.get("180_s1", 0)
                                                old_180_2 = match_info.get("180_s2", 0)
                                                old_avg_1 = match_info.get("avg_s1", 0.0)
                                                old_avg_2 = match_info.get("avg_s2", 0.0)
                                                
                                                sess["results"][(r, b_name)] = {
                                                    "s1": p1, "s2": p2, "ergebnis": f"{sc1}:{sc2}",
                                                    "winner": winner, "loser": loser,
                                                    "180_s1": old_180_1, "180_s2": old_180_2,
                                                    "avg_s1": old_avg_1, "avg_s2": old_avg_2
                                                }
                                                st.session_state.sessions_list[orig_idx] = sess
                                                smart_sync_and_save(st.session_state.sessions_list)
                                                st.success("Ergebnis blitzschnell gespeichert!")
                                    with c_del:
                                        if st.button("🗑️ Leeren", key=f"blitz_del_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                            if (r, b_name) in sess.get("results", {}):
                                                del sess["results"][(r, b_name)]
                                                st.session_state.sessions_list[orig_idx] = sess
                                                smart_sync_and_save(st.session_state.sessions_list)
                                                st.success("Spielstand erfolgreich gelöscht!")
                                st.divider()

with tab_regeln:
    st.subheader("🎯 Modus & Spielablauf")
    st.write("Hier findet ihr die Anleitung für den Trainingsabend, Liga-Spiele und den Auf- und Abstieg.")
    
    with st.container(border=True):
        st.markdown("### 🏆 Liga-Betrieb (Schwaben 4. BezLiga)")
        st.markdown("""
        * **Komplett Isoliert:** Ein völlig eigenständiger Turniermodus, abgekoppelt vom Team-Kader.
        * **Ablauf:** Phase 1: Verdecktes Aufstellen beider Teams. Phase 2: Die ersten 4 Einzel. Phase 3: Automatische Kreuzrunde (Hier darf einwechselt werden). Phase 4: Doppel.
        * **Live-Tracking:** Gespielt wird klassisch auf 2 Boards. Heim hat links Anwurf, Gast rechts. Keine Average-Auswertung.
        """)
        
    with st.container(border=True):
        st.markdown("### 👑 Das Prinzip: 'Up & Down' (Training)")
        st.markdown("""
        * **Kaiser B1 ist das Top-Board:** Wer hier gewinnt, bleibt König (Kaiser) oder steigt auf. Wer verliert, wandert ein Board nach unten.
        * **Das untere Board:** Wer hier gewinnt, steigt ein Board nach oben. Wer verliert, wandert nach ganz unten (Richtung B1).
        """)

    with st.container(border=True):
        st.markdown("### 👥 Was passiert bei ungerader Spieleranzahl? (Training)")
        st.markdown("""
        * Das System setzt auf dem allerletzten Board einen **Platzhalter (`-`)** ein.
        * Wer verliert, rutscht ans letzte Board und bekommt das Freilos (die Pause). So wechselt sich die Pause automatisch ab!
        """)
