import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import re
import io
import os

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

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
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
            if len(all_vals) > 21:
                rows_to_delete = len(all_vals) - 21
                for _ in range(rows_to_delete):
                    try:
                        backup_ws.delete_rows(2)
                    except AttributeError:
                        backup_ws.delete_row(2)
        except Exception:
            pass
    except Exception:
        pass

def save_completed_backup(serializable_sessions):
    """Sicherer Tresor: Führt alte abgeschlossene Spiele mit neuen zusammen und speichert in einer Zeile."""
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(SHEET_URL)
        
        try:
            vault_ws = spreadsheet.worksheet("completed_backup")
        except:
            vault_ws = spreadsheet.add_worksheet(title="completed_backup", rows=2, cols=2)
            vault_ws.append_row(["Last_Updated", "JSON_Data_Completed"])
            
        existing_vault_data = []
        try:
            val = vault_ws.cell(2, 2).value
            if val:
                existing_vault_data = json.loads(val)
        except Exception:
            pass
            
        vault_dict = {s["id"]: s for s in existing_vault_data}
        
        for s in serializable_sessions:
            if s.get("is_liga") and s.get("is_locked"):
                vault_dict[s["id"]] = s
            elif not s.get("is_liga") and s.get("end_time"):
                vault_dict[s["id"]] = s
                
        merged_vault = list(vault_dict.values())
        
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
        json_str = json.dumps(merged_vault, ensure_ascii=False)
        
        vault_ws.clear()
        vault_ws.update([["Last_Updated", "JSON_Data_Completed"], [ts, json_str]])
    except Exception:
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
        save_completed_backup(sichere_sessions)
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
        fresh_dict = {s["id"]: s for s in fresh_data}
        for sess in updated_sessions:
            fresh_dict[sess["id"]] = sess
            
        final_data = list(fresh_dict.values())
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

tab_übersicht, tab_kader, tab_session, tab_liga, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Freundschaftsspiele", "Match-Archiv", "Modus & Regeln"])

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

def get_or_create_teams(session, all_sessions):
    if "coop_teams" in session and session["coop_teams"]:
        return session["coop_teams"]
    
    spieler = [p for p in session.get("spieler", []) if p != "-"]
    prev_pairs = set()
    prev_resting_players = set()
    training_sessions = [s for s in all_sessions if not s.get("is_liga")]
    all_sorted = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
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
    if board_name not in boards: return ["-", "-"]
    b_idx = boards.index(board_name)
    
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
    in_coop_phase = is_standard_training and round_num > singles_rounds
    
    spieler = session["spieler"].copy()
    
    if round_num == 1 and not in_coop_phase and not is_2v2:
        training_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga")]
        all_sessions = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
        try: s_idx = all_sessions.index(session)
        except: s_idx = 0
        
        prev_sess = all_sessions[s_idx + 1] if s_idx + 1 < len(all_sessions) else None
        if prev_sess and "results" in prev_sess:
            prev_total = prev_sess.get("total_rounds", 4)
            prev_modus = prev_sess.get("modus", "Up & Down")
            prev_is_std = (prev_modus == "Standard-Training (Einzel + Coop)")
            target_r = prev_sess.get("singles_rounds", prev_total - 2 if prev_is_std and prev_total > 2 else prev_total) if prev_is_std else prev_total
            
            prev_boards = get_boards_list(prev_sess, target_r)
            prev_results = prev_sess.get("results", {})
            prev_players_top_to_bottom = []
            for pb in prev_boards:
                match_inf = prev_results.get((target_r, pb))
                p1, p2 = (match_inf.get("winner", "-"), match_inf.get("loser", "-")) if match_inf else get_board_players(prev_sess, target_r, pb)
                if p1 != "-" and p1 not in prev_players_top_to_bottom: prev_players_top_to_bottom.append(p1)
                if p2 != "-" and p2 not in prev_players_top_to_bottom: prev_players_top_to_bottom.append(p2)
            
            returning_players = [p for p in reversed(prev_players_top_to_bottom) if p in spieler]
            new_players = [p for p in spieler if p not in prev_players_top_to_bottom]
            ordered_players = new_players + returning_players
            for p in spieler:
                if p not in ordered_players: ordered_players.append(p)
            spieler = ordered_players[:len(spieler)]

    pairs = []
    if is_2v2 or in_coop_phase:
        teams = get_or_create_teams(session, st.session_state.sessions_list)
        n_teams = len(teams)
        rel_round = (round_num - singles_rounds) if in_coop_phase else round_num
        resting_team_idx = (rel_round - 1) % n_teams if n_teams % 2 != 0 else -1
        active_teams = [t for i, t in enumerate(teams) if i != resting_team_idx]
        
        if rel_round == 1:
            if b_idx < len(active_teams) // 2:
                return [active_teams[b_idx * 2], active_teams[b_idx * 2 + 1] if b_idx * 2 + 1 < len(active_teams) else "-"]
            return ["-", "-"]
        else:
            prev_r = round_num - 1
            res = session.get("results", {})
            w, l = {}, {}
            for b in boards:
                match_info = res.get((prev_r, b))
                w[b], l[b] = (match_info["winner"], match_info["loser"]) if match_info and match_info.get("winner") else ("-", "-")
                    
            if b_idx == 0:
                top_w, next_w = w.get("Kaiser B1", "-"), w.get("Board 2", "-")
                return [top_w if top_w != "-" else (active_teams[0] if active_teams else "-"), next_w if next_w != "-" else (active_teams[1] if len(active_teams) > 1 else "-")]
            elif b_idx == 1 and len(boards) > 1:
                top_l, next_l = l.get("Kaiser B1", "-"), l.get("Board 2", "-")
                return [top_l if top_l != "-" else (active_teams[2] if len(active_teams) > 2 else "-"), next_l if next_l != "-" else (active_teams[3] if len(active_teams) > 3 else "-")]
        return ["-", "-"]
    else:
        boards_count = session.get("boards_count", 6)
        if round_num == 1:
            for i in range(0, min(boards_count * 2, len(spieler) - len(spieler) % 2), 2): pairs.append((spieler[i], spieler[i+1]))
            while len(pairs) <= b_idx: pairs.append((spieler[0] if spieler else "-", spieler[1] if len(spieler) > 1 else "-"))
            if len(spieler) % 2 != 0: pairs[-1] = (spieler[-1], "-")
            return list(pairs[b_idx])
        
        prev_r = round_num - 1
        res = session.get("results", {})
        w, l = {}, {}
        for b in boards:
            match_info = res.get((prev_r, b))
            w[b], l[b] = (match_info["winner"], match_info["loser"]) if match_info and match_info.get("winner") else ("-", "-")
                
        if b_idx == 0:
            top_w, next_w = w.get("Kaiser B1", "-"), w.get("Board 2", "-") if len(boards) > 1 else w.get("Kaiser B1", "-")
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
        for r in range(1, singles_rounds + 1):
            for rb in get_boards_list(session, 1):
                match_info = res.get((r, rb))
                if not match_info or not match_info.get("winner"): return False
        return True
        
    boards = get_boards_list(session, next_r)
    if board_name not in boards: return False
    b_idx = boards.index(board_name)
    res, prev_r = session.get("results", {}), next_r - 1
    
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

def get_liga_config(sess):
    t_size = sess.get("team_size", 4)
    b_count = sess.get("boards_count", 2)
    
    if t_size == 6:
        singles = [
            ("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"),
            ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4"),
            ("m5", "Einzel 5", "h5", "g5"), ("m6", "Einzel 6", "h6", "g6")
        ]
        cross = [
            ("m7", "Kreuz-Einzel 1", "h1", "g4"), ("m8", "Kreuz-Einzel 2", "h2", "g5"),
            ("m9", "Kreuz-Einzel 3", "h3", "g6"), ("m10", "Kreuz-Einzel 4", "h4", "g1"),
            ("m11", "Kreuz-Einzel 5", "h5", "g2"), ("m12", "Kreuz-Einzel 6", "h6", "g3")
        ]
        doubles = [("m13", "Doppel 1", "hd1", "gd1"), ("m14", "Doppel 2", "hd2", "gd2"), ("m15", "Doppel 3", "hd3", "gd3")]
    else:
        singles = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"), ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")]
        cross = [("m5", "Einzel 5 (Kreuz)", "h1", "g2"), ("m6", "Einzel 6 (Kreuz)", "h2", "g1"), ("m7", "Einzel 7 (Kreuz)", "h3", "g4"), ("m8", "Einzel 8 (Kreuz)", "h4", "g3")]
        doubles = [("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
        
    rounds = []
    for block in [singles, cross, doubles]:
        for i in range(0, len(block), b_count):
            rounds.append(block[i:i + b_count])
    return rounds

def generate_spielbericht_pdf(sess):
    try:
        from pypdf import PdfReader, PdfWriter
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4
    except ImportError:
        raise ImportError("Fehlende Bibliotheken (pypdf oder reportlab)")

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica-Bold", 9)
    
    c.drawString(410, 755, sess.get("datum", ""))
    c.drawString(100, 722, sess.get("heim_team", "")) 
    c.drawString(330, 722, sess.get("gast_team", ""))
    
    res, auf_h, auf_g = sess.get("results", {}), sess.get("auf_heim", {}), sess.get("auf_gast", {})
    t_size = sess.get("team_size", 4)
    
    y_coords_pdf = {
        "m1": 630, "m2": 585, "m3": 540, "m4": 495, "m5": 450, "m6": 405,
        "m7": 360, "m8": 315, "m9": 270, "m10": 225, "m11": 180, "m12": 135,
        "m13": 90, "m14": 65, "m15": 40
    } if t_size == 6 else {
        "m1": 630, "m2": 585, "m3": 540, "m4": 495, "m5": 415, "m6": 370, "m7": 325, "m8": 280, "m9": 200, "m10": 155
    }
    
    for m_key, label, h_key, g_key in [m for r in get_liga_config(sess) for m in r]:
        if m_key in res and res[m_key].get("played"):
            m_data = res[m_key]
            y = y_coords_pdf.get(m_key, 500)
            c.drawString(65, y, str(auf_h.get(h_key, "")))
            c.drawString(315, y, str(auf_g.get(g_key, "")))
            c.drawString(225, y, str(m_data.get("lh", 0)))
            c.drawString(285, y, str(m_data.get("lg", 0)))
            y_sub = y - 12
            if m_data.get("180_h", 0) > 0: c.drawString(95, y_sub, str(m_data.get("180_h", "")))
            if m_data.get("180_g", 0) > 0: c.drawString(340, y_sub, str(m_data.get("180_g", "")))

    c.save()
    packet.seek(0)
    pdf_out = io.BytesIO()
    
    pdf_path = "Bez_Schwaben_Spielbericht_2.pdf" if os.path.exists("Bez_Schwaben_Spielbericht_2.pdf") else ("Bez_Schwaben_Spielbericht.pdf" if os.path.exists("Bez_Schwaben_Spielbericht.pdf") else None)
    if pdf_path:
        new_pdf = PdfReader(packet)
        original_pdf = PdfReader(open(pdf_path, "rb"))
        output = PdfWriter()
        page = original_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
        output.write(pdf_out)
    else:
        c2 = canvas.Canvas(pdf_out, pagesize=A4)
        c2.setFont("Helvetica-Bold", 12)
        c2.drawString(100, 750, "FEHLER: Originaldatei fehlt!")
        c2.save()

    pdf_out.seek(0)
    return pdf_out

def get_max_boards_for_players(num_players):
    import math
    return math.floor(num_players / 2) if num_players >= 2 else 0

@st.dialog("➕ Neue Session starten")
def open_new_session_dialog():
    pwd = st.text_input("Passwort eingeben", type="password")
    if pwd != "1521":
        if pwd: st.error("Falsches Passwort!")
        return

    session_datum = st.date_input("Datum", date.today())
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"])
    
    if spielmodus == "Standard-Training (Einzel + Coop)":
        st.write("### Runden-Aufteilung")
        singles_rounds = st.selectbox("Anzahl Einzel-Runden", list(range(1, 11)), index=3)
        coop_rounds = st.selectbox("Anzahl Doppel (Koop)-Runden", list(range(1, 11)), index=1)
        total_rounds = singles_rounds + coop_rounds
    elif spielmodus == "Koop 2vs2 (Up & Down)":
        singles_rounds, coop_rounds, total_rounds = 0, st.selectbox("Anzahl Koop-Runden", list(range(1, 11)), index=1), 0
        total_rounds = coop_rounds
    else:
        singles_rounds, coop_rounds, total_rounds = 0, 0, st.selectbox("Anzahl Runden", list(range(1, 11)), index=3)
        
    anzahl_boards = st.selectbox("Anzahl der Boards (für Einzel)", ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"], index=2)
    
    st.write("### Anwesende Spieler")
    anwesende = []
    cols = st.columns(2)
    for i, sp in enumerate(kader):
        with cols[0 if i < len(kader)//2 else 1]:
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
        st.error(f"🚨 Fehler: Zu viele Boards! Max {max_moegliche_boards} möglich.")
        can_save = False

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c2:
        if st.button("Session starten", type="primary", use_container_width=True, disabled=not can_save):
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
                get_or_create_teams(new_session, [s for s in st.session_state.sessions_list if not s.get("is_liga")])
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("⚙️ Session bearbeiten")
def open_edit_session_dialog(session_id):
    pwd = st.text_input("Passwort eingeben", type="password")
    if pwd != "1521":
        if pwd: st.error("Falsches Passwort!")
        return

    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    
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
    
    anwesende = []
    cols = st.columns(2)
    for i, sp in enumerate(kader):
        with cols[0 if i < len(kader)//2 else 1]:
            if st.checkbox(sp, value=(sp in sess.get("spieler", []))): anwesende.append(sp)
                
    curr_gaeste = sess.get("gaeste", [])
    gaeste = [x for x in [st.text_input(f"Gast {i+1}", value=curr_gaeste[i] if i<len(curr_gaeste) else "") for i in range(4)] if x.strip() != ""]
    aktive_spieler = anwesende + gaeste
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c_btn2:
        if st.button("Speichern", type="primary", use_container_width=True):
            sess.update({
                "datum": session_datum.strftime("%d.%m.%Y"), "start_time": edit_start_time.strip() or None, "end_time": edit_end_time.strip() or None,
                "modus": spielmodus, "boards_count": int(anzahl_boards.split()[0]),
                "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds,
                "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus,
                "spieler": aktive_spieler, "gaeste": gaeste
            })
            idx = st.session_state.sessions_list.index(sess)
            st.session_state.sessions_list[idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔄 Spieler auswechseln")
def open_substitution_dialog(session_id, board_name, round_num, slot_num, current_player):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    alle_spieler = list(set(sess.get("spieler", kader) + [current_player]))
    if "-" not in alle_spieler: alle_spieler.append("-")
    alle_spieler.sort()

    idx = alle_spieler.index(current_player) if current_player in alle_spieler else 0
    new_sel = st.selectbox("Aus Kader wählen:", alle_spieler, index=idx)
    new_txt = st.text_input("Oder neuen Gast eintragen:", placeholder="Name...")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col2:
        if st.button("Änderung speichern", type="primary", use_container_width=True):
            final_name = new_txt.strip() if new_txt.strip() else new_sel
            if "results" not in sess: sess["results"] = {}
            if (round_num, board_name) not in sess["results"]:
                auto_p = get_board_players(sess, round_num, board_name)
                sess["results"][(round_num, board_name)] = {"s1": auto_p[0], "s2": auto_p[1], "ergebnis": "0:0", "winner": "", "loser": "", "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0}
            if slot_num == 1: sess["results"][(round_num, board_name)]["s1"] = final_name
            else: sess["results"][(round_num, board_name)]["s2"] = final_name
            
            s_idx = st.session_state.sessions_list.index(sess)
            st.session_state.sessions_list[s_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🗑️ Session Löschen (Admin)")
def open_delete_session_dialog(session_id):
    st.warning(f"Willst du die Session **{session_id}** wirklich unwiderruflich löschen?")
    pwd = st.text_input("Passwort zur Bestätigung:", type="password")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c2:
        if st.button("🗑️ Unwiderruflich löschen", type="primary", use_container_width=True):
            if pwd == "1521":
                delete_session(session_id)
                st.success("Erfolgreich gelöscht!")
                st.rerun()
            else: st.error("Falsches Passwort!")

@st.dialog("📋 Board-Erfassung & Tracking")
def open_board_dialog(session_id, board_name):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds:
        st.warning("Alle Runden beendet.")
        if st.button("Schließen"): st.rerun()
        return

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
    
    req_win = 3 if sess.get("modus_leg", "Best of 5") == "Best of 5" else 2
    is_valid_result = True
    if current_p1 != "-" and current_p2 != "-":
        if in_score1 == in_score2: st.error("Unentschieden nicht möglich."); is_valid_result = False
        elif in_score1 > req_win or in_score2 > req_win: st.error(f"Max {req_win} Legs."); is_valid_result = False
        elif in_score1 != req_win and in_score2 != req_win: st.error(f"Sieger braucht genau {req_win} Legs."); is_valid_result = False
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Ergebnis abschließen", type="primary", use_container_width=True, disabled=not is_valid_result):
            if "results" not in sess: sess["results"] = {}
            sess["results"][(current_round, board_name)] = {
                "s1": current_p1, "s2": current_p2, "ergebnis": ergebnis, "winner": winner, "loser": loser,
                "180_s1": in_180_1, "180_s2": in_180_2, "avg_s1": in_avg_1, "avg_s2": in_avg_2
            }
            s_idx = st.session_state.sessions_list.index(sess)
            st.session_state.sessions_list[s_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
    with cb2:
        if st.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("➕ Neues Freundschaftsspiel starten", width="large")
def open_new_liga_match_dialog():
    st.write("Erstelle hier ein neues Freundschaftsspiel.")
    
    liga_type = st.radio("Art des Freundschaftsspiels", ["🏆 Standard Liga-Spiel (4er Team, 2 Boards)", "⚙️ Freies Spiel auf Liga-Basis"])
    
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum", date.today())
    heim_team = c2.text_input("Heimmannschaft", value="Wehringer Steelers")
    gast_team = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    
    if "Freies" in liga_type:
        team_mode = st.selectbox("Team-Größe", ["4er-Team", "6er-Team"])
        team_size = 6 if "6er" in team_mode else 4
        b_count = st.selectbox("Anzahl paralleler Boards", [1, 2, 3, 4, 5, 6], index=1)
    else:
        team_size = 4
        b_count = 2
        
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    selected_boards = []
    st.write(f"Wähle {b_count} Boards aus:")
    cols = st.columns(min(b_count, 4))
    for i in range(b_count):
        with cols[i % len(cols)]:
            b_sel = st.selectbox(f"Board {i+1}", board_options, index=i if i < len(board_options) else 0)
            selected_boards.append(b_sel)
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with cb2:
        if st.button("Spiel erstellen", type="primary", use_container_width=True):
            max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "L-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
            new_session = {
                "id": f"L-{max_id + 1}", "datum": session_datum.strftime("%d.%m.%Y"), "is_liga": True,
                "team_size": team_size, "boards_count": b_count, "heim_team": heim_team.strip(), "gast_team": gast_team.strip(),
                "liga_boards": selected_boards, "auf_heim": {}, "auf_gast": {}, "results": {}
            }
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("⚙️ Freundschaftsspiel bearbeiten")
def open_edit_liga_session_dialog(session_id):
    pwd = st.text_input("Passwort", type="password")
    if pwd != "1521":
        if pwd: st.error("Falsches Passwort!")
        return
    
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    
    try: curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_date = date.today()
    
    session_datum = st.date_input("Datum", curr_date)
    heim_team = st.text_input("Heim", value=sess.get("heim_team", ""))
    gast_team = st.text_input("Gast", value=sess.get("gast_team", ""))
    
    curr_boards = sess.get("liga_boards", ["Kaiser B1", "Board 2"])
    b_count = sess.get("boards_count", len(curr_boards))
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    new_boards = []
    cols = st.columns(min(b_count, 4))
    for i in range(b_count):
        with cols[i % len(cols)]:
            curr_val = curr_boards[i] if i < len(curr_boards) else board_options[i]
            b_sel = st.selectbox(f"Board {i+1}", board_options, index=board_options.index(curr_val) if curr_val in board_options else 0, key=f"el_{i}")
            new_boards.append(b_sel)
    
    if st.button("Speichern", type="primary", use_container_width=True):
        sess.update({"datum": session_datum.strftime("%d.%m.%Y"), "heim_team": heim_team.strip(), "gast_team": gast_team.strip(), "liga_boards": new_boards})
        s_idx = st.session_state.sessions_list.index(sess)
        st.session_state.sessions_list[s_idx] = sess
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🔒 Einzel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_einzel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    t_size = sess.get("team_size", 4)
    
    inputs = []
    for i in range(t_size):
        inputs.append(st.text_input(f"Position {i+1}"))
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if all(x.strip() for x in inputs):
            for i, val in enumerate(inputs):
                key = f"h{i+1}" if is_heim else f"g{i+1}"
                (sess["auf_heim"] if is_heim else sess["auf_gast"])[key] = val.strip()
            s_idx = st.session_state.sessions_list.index(sess)
            st.session_state.sessions_list[s_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
        else: st.error(f"Bitte alle {t_size} Positionen eintragen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    num_doubles = 3 if sess.get("team_size", 4) == 6 else 2
    
    auf_dict = sess.get("auf_heim", {}) if is_heim else sess.get("auf_gast", {})
    bisher = [v for k, v in auf_dict.items() if ("h" in k or "g" in k) and "d" not in k and v and v != "-"]
    for m in sess.get("results", {}).values():
        if is_heim and m.get("s1") and m.get("s1") not in bisher: bisher.append(m.get("s1"))
        if not is_heim and m.get("s2") and m.get("s2") not in bisher: bisher.append(m.get("s2"))
            
    opts = sorted(list(set(bisher))) + ["+ Anderen Spieler eingeben..."] if bisher else ["Bitte zuerst Einzel spielen...", "+ Anderen Spieler eingeben..."]
    
    doubles_data = []
    for i in range(num_doubles):
        st.markdown(f"**Doppel {i+1}**")
        c1, c2 = st.columns(2)
        s1 = c1.selectbox(f"S1", opts, key=f"d{i}s1")
        v1 = c1.text_input("Name", key=f"d{i}v1") if s1 == "+ Anderen Spieler eingeben..." else s1
        s2 = c2.selectbox(f"S2", opts, key=f"d{i}s2")
        v2 = c2.text_input("Name", key=f"d{i}v2") if s2 == "+ Anderen Spieler eingeben..." else s2
        doubles_data.append((v1.strip(), v2.strip()))
        
    if st.button("Speichern", type="primary", use_container_width=True):
        all_selected = []
        has_error = False
        for p1, p2 in doubles_data:
            if p1:
                if p1 in all_selected: st.error(f"Fehler: Der Spieler '{p1}' steht in mehreren Feldern!"); has_error = True
                all_selected.append(p1)
            if p2:
                if p2 in all_selected: st.error(f"Fehler: Der Spieler '{p2}' steht in mehreren Feldern!"); has_error = True
                all_selected.append(p2)
                
        if any(not x for x in all_selected): st.error("Bitte alle Spieler ausfüllen!")
        elif not has_error:
            for i, (p1, p2) in enumerate(doubles_data):
                key = f"hd{i+1}" if is_heim else f"gd{i+1}"
                (sess["auf_heim"] if is_heim else sess["auf_gast"])[key] = f"{p1} & {p2}"
            s_idx = st.session_state.sessions_list.index(sess)
            st.session_state.sessions_list[s_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔄 Auswechseln (Liga)")
def open_liga_sub_dialog(session_id, p_key, is_heim, curr_name):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    new_name = st.text_input("Name des Ersatzspielers:")
    if st.button("Speichern", type="primary", use_container_width=True):
        if new_name.strip():
            (sess["auf_heim"] if is_heim else sess["auf_gast"])[p_key] = new_name.strip()
            s_idx = st.session_state.sessions_list.index(sess)
            st.session_state.sessions_list[s_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🎯 Live Board (Freundschaftsspiel)")
def open_liga_live_board_dialog(session_id, m_key, board_name, m_label, p1, p2, is_right_board=False):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    res = sess.setdefault("results", {})
    m_data = res.get(m_key, {})
    
    if is_right_board:
        c1, c2 = st.columns(2)
        lg = c1.number_input("Legs Gast", 0, 3, m_data.get("lg", 0))
        e180_g = c1.number_input("180er Gast", 0, 10, m_data.get("180_g", 0))
        lh = c2.number_input("Legs Heim", 0, 3, m_data.get("lh", 0))
        e180_h = c2.number_input("180er Heim", 0, 10, m_data.get("180_h", 0))
    else:
        c1, c2 = st.columns(2)
        lh = c1.number_input("Legs Heim", 0, 3, m_data.get("lh", 0))
        e180_h = c1.number_input("180er Heim", 0, 10, m_data.get("180_h", 0))
        lg = c2.number_input("Legs Gast", 0, 3, m_data.get("lg", 0))
        e180_g = c2.number_input("180er Gast", 0, 10, m_data.get("180_g", 0))

    is_valid = (lh == 3 and lg < 3) or (lg == 3 and lh < 3)
    if not is_valid: st.error("Best of 5: Ein Spieler muss exakt 3 Legs zum Sieg haben!")

    if st.button("Speichern", type="primary", use_container_width=True, disabled=not is_valid):
        res[m_key] = {"lh": lh, "lg": lg, "played": True, "180_h": e180_h, "180_g": e180_g}
        sess["results"] = res
        s_idx = st.session_state.sessions_list.index(sess)
        st.session_state.sessions_list[s_idx] = sess
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("📝 Offizieller Spielbericht (Korrektur)", width="large")
def open_liga_bericht_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    res = sess.setdefault("results", {})
    all_valid = True
    for m_key, label, h_key, g_key in [m for r in get_liga_config(sess) for m in r]:
        m_data = res.get(m_key, {})
        with st.expander(f"{label}", expanded=False):
            c_lh, c_vs, c_lg = st.columns([2, 1, 2])
            lh = c_lh.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"blh_{m_key}")
            lg = c_lg.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"blg_{m_key}")
            if not ((lh == 0 and lg == 0) or (lh == 3 and lg < 3) or (lg == 3 and lh < 3)):
                st.error("Ungültig! Best of 5 erfordert exakt 3 Legs für den Sieger."); all_valid = False
            res[m_key] = {"lh": lh, "lg": lg, "played": True if (lh>0 or lg>0) else False, "180_h": m_data.get("180_h", 0), "180_g": m_data.get("180_g", 0)}

    is_locked = sess.get("is_locked", False)
    lock_spiel = True if is_locked else st.checkbox("🔒 Spiel endgültig abschließen & ins Archiv verschieben")

    if st.button("💾 Speichern & Schließen", type="primary", use_container_width=True, disabled=not all_valid):
        sess["is_locked"] = lock_spiel
        sess["results"] = res
        s_idx = st.session_state.sessions_list.index(sess)
        st.session_state.sessions_list[s_idx] = sess
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("📊 Spielablauf & Rundenübersicht")
def open_session_archive_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    
    for r in range(1, total_rounds + 1):
        st.markdown(f"#### 🎯 Runde {r}")
        for b_name in get_boards_list(sess, r):
            match_info = res.get((r, b_name))
            if match_info:
                with st.container(border=True):
                    st.markdown(f"**{b_name}**")
                    st.markdown(f"Ergebnis: **{match_info.get('ergebnis')}** | Sieger: **{match_info.get('winner')}**")
            else:
                st.write(f"{b_name}: Ausstehend")
    if st.button("Schließen"): st.rerun()

with tab_übersicht:
    c1, c2 = st.columns(2)
    if c1.button("➕ Neue Session", type="primary", use_container_width=True): open_new_session_dialog()
    active_t_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga") and not is_session_completed(s)]
    if c2.button("⚙️ Bearbeiten", use_container_width=True, disabled=not active_t_sessions):
        open_edit_session_dialog(active_t_sessions[0]['id'])
        
    st.write("")
    st.markdown("### 🔴 Laufende Trainings-Session")
    if not active_t_sessions:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        curr_sess = active_t_sessions[0]
        if not curr_sess.get("start_time"):
            st.info(f"Session **{curr_sess['id']}** erstellt. Spieler: {', '.join(curr_sess.get('spieler', []))}")
            if st.button("🚀 Teamtraining starten", type="primary", use_container_width=True):
                curr_sess["start_time"] = get_local_time_str()
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()
        else:
            st.caption(f"Session-ID: **{curr_sess['id']}** vom {curr_sess['datum']} | Modus: {curr_sess['modus']}")
            res = curr_sess.get("results", {})
            for b_name in get_boards_list(curr_sess, 1) if curr_sess.get("modus") != "Koop 2vs2 (Up & Down)" else ["Kaiser B1", "Board 2"]:
                next_r = max([r for (r, b), v in res.items() if b == b_name and v.get("winner")] + [0]) + 1
                with st.container(border=True):
                    st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                    if next_r <= curr_sess.get("total_rounds", 4):
                        ready = is_board_ready(curr_sess, b_name, next_r)
                        ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                        st.markdown(f"<p style='text-align: center; font-weight: bold;'>{ampel}</p>", unsafe_allow_html=True)
                        m_inf = res.get((next_r, b_name))
                        p1, p2 = (m_inf.get("s1", "-"), m_inf.get("s2", "-")) if m_inf else get_board_players(curr_sess, next_r, b_name)
                        
                        sc1, sc2 = st.columns([5, 2])
                        sc1.write(f"**{p1}**")
                        if sc2.button("🔄", key=f"s1_{b_name}"): open_substitution_dialog(curr_sess['id'], b_name, next_r, 1, p1)
                        st.markdown("<div style='text-align: center; color: #ff4b4b;'>VS</div>", unsafe_allow_html=True)
                        sc3, sc4 = st.columns([5, 2])
                        sc3.write(f"**{p2}**")
                        if sc4.button("🔄", key=f"s2_{b_name}"): open_substitution_dialog(curr_sess['id'], b_name, next_r, 2, p2)
                        
                        if st.button("🎯 Eintragen", key=f"e_{b_name}", use_container_width=True, disabled=not ready): open_board_dialog(curr_sess['id'], b_name)
                    else: st.success("✅ Abgeschlossen")

    # STATS BLOCK IMMER SICHTBAR ABER OHNE LIGA
    st.divider()
    st.markdown("### 📊 Allgemeine Statistiken")
    t_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga")]
    tot_180s = sum([int(m.get("180_s1", 0)) + int(m.get("180_s2", 0)) for s in t_sessions for m in s.get("results", {}).values() if "&" not in m.get("s1","")])
    
    k_win = "Offen"
    for s in t_sessions:
        k_m = sorted([(r, m) for (r, b), m in s.get("results", {}).items() if b == "Kaiser B1" and m.get("winner") and "&" not in m.get("winner")], key=lambda x: x[0], reverse=True)
        if k_m: k_win = k_m[0][1]["winner"]; break
            
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.metric("Training Sessions", str(len(t_sessions)))
        c2.metric("Team 180er", str(tot_180s))
        st.divider()
        c3, c4 = st.columns(2)
        c3.metric("Aktueller Kaiser", k_win)
        c4.metric("Anwesende (Schnitt)", f"{(sum([len([p for p in s.get('spieler',[]) if p!='-']) for s in t_sessions])/len(t_sessions)):.1f}" if t_sessions else "0")
        
    with st.expander("Zuletzt ausgetragene Board-Matches", expanded=False):
        for s in t_sessions[:3]:
            for (r, b), m in list(s.get("results", {}).items())[-5:]:
                if m.get("winner"): st.write(f"{s['datum']} - **{b}**: {m['s1']} vs {m['s2']} ➔ **{m['winner']}**")

with tab_kader:
    st.subheader("Kader & Spielerbilanz (Training)")
    stats = {p: {"Matches": 0, "Siege": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0} for p in kader}
    for s in [ts for ts in st.session_state.sessions_list if not ts.get("is_liga")]:
        for m in s.get("results", {}).values():
            w, s1, s2 = m.get("winner", ""), m.get("s1", ""), m.get("s2", "")
            try: l1, l2 = map(int, m.get("ergebnis", "0:0").split(":"))
            except: l1, l2 = 0, 0
            if s1 in stats and "&" not in s1:
                stats[s1]["180er"] += int(m.get("180_s1", 0)); stats[s1]["Legs_Won"] += l1; stats[s1]["Legs_Lost"] += l2
                if float(m.get("avg_s1", 0)) > 0: stats[s1]["Avg_Sum"] += float(m.get("avg_s1", 0)); stats[s1]["Avg_Count"] += 1
            if s2 in stats and "&" not in s2:
                stats[s2]["180er"] += int(m.get("180_s2", 0)); stats[s2]["Legs_Won"] += l2; stats[s2]["Legs_Lost"] += l1
                if float(m.get("avg_s2", 0)) > 0: stats[s2]["Avg_Sum"] += float(m.get("avg_s2", 0)); stats[s2]["Avg_Count"] += 1
            if w in stats: stats[w]["Siege"] += 1
            for p in [s1, s2]:
                if p in stats: stats[p]["Matches"] += 1

    valid_p = [p for p in kader if stats[p]["Matches"] >= 3]
    mvp = "N/A"
    if valid_p:
        br = max([stats[p]["Siege"]/stats[p]["Matches"] for p in valid_p])
        mvp = " & ".join([p for p in valid_p if abs(stats[p]["Siege"]/stats[p]["Matches"] - br) < 1e-9])
        
    db_count = max([stats[p]["Matches"] for p in kader], default=0)
    db = " & ".join([p for p in kader if stats[p]["Matches"] == db_count]) if db_count > 0 else "N/A"
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        c1.metric("🏆 MVP (Siegquote)", mvp)
        c2.metric("🔥 Dauerbrenner", db)
        
    for p in sorted(kader, key=lambda x: stats[x]["Siege"], reverse=True):
        with st.container(border=True):
            st.markdown(f"**{p}** — Siege: {stats[p]['Siege']}/{stats[p]['Matches']}")

with tab_session:
    st.subheader("Up & Down Sessions")
    for s in [ts for ts in st.session_state.sessions_list if not ts.get("is_liga")]:
        with st.container(border=True):
            st.markdown(f"**{s['datum']}** — {s['modus']} | ID: {s['id']}")
            if st.button("📊 Archiv ansehen", key=f"t_view_{s['id']}"): open_session_archive_dialog(s['id'])

with tab_liga:
    st.subheader("Freundschaftsspiele")
    if st.button("➕ Neues Freundschaftsspiel starten", type="primary", use_container_width=True): open_new_liga_match_dialog()
    st.divider()
    
    active_liga = [l for l in st.session_state.sessions_list if l.get("is_liga") and not l.get("is_locked")]
    if not active_liga: st.info("Keine aktiven Freundschaftsspiele.")
    else:
        for sess in active_liga:
            res, auf_h, auf_g = sess.setdefault("results", {}), sess.setdefault("auf_heim", {}), sess.setdefault("auf_gast", {})
            r_list = get_liga_config(sess)
            is_done = len([k for k, v in res.items() if v.get("played")]) == sum([len(r) for r in r_list])
            
            with st.container(border=True):
                st.markdown(f"### {sess['heim_team']} vs. {sess['gast_team']}")
                if not bool(auf_h.get(f"h{sess.get('team_size', 4)}")) or not bool(auf_g.get(f"g{sess.get('team_size', 4)}")):
                    st.warning("Phase 1: Einzel aufstellen")
                    ch, cg = st.columns(2)
                    if ch.button("🔒 Heim Aufstellen", key=f"he_{sess['id']}"): open_liga_aufstellung_einzel(sess['id'], True)
                    if cg.button("🔒 Gast Aufstellen", key=f"ge_{sess['id']}"): open_liga_aufstellung_einzel(sess['id'], False)
                elif not is_done:
                    c_idx = next((i for i, r in enumerate(r_list) if not all(res.get(m[0], {}).get("played") for m in r)), len(r_list))
                    is_dbl = c_idx >= len(r_list) - (3 if sess.get("team_size") == 6 else 2)
                    
                    if is_dbl and (not auf_h.get("hd1") or not auf_g.get("gd1")):
                        st.warning("Phase 2: Doppel aufstellen")
                        chd, cgd = st.columns(2)
                        if chd.button("🔒 Heim Doppel", key=f"hd_{sess['id']}"): open_liga_aufstellung_doppel(sess['id'], True)
                        if cgd.button("🔒 Gast Doppel", key=f"gd_{sess['id']}"): open_liga_aufstellung_doppel(sess['id'], False)
                    elif c_idx >= 1:
                        st.markdown("**🔜 Doppel bereits jetzt aufstellen (Optional)**")
                        cd1, cd2 = st.columns(2)
                        if not auf_h.get("hd1") and cd1.button("🔒 Heim Doppel", key=f"ohd_{sess['id']}"): open_liga_aufstellung_doppel(sess['id'], True)
                        if not auf_g.get("gd1") and cd2.button("🔒 Gast Doppel", key=f"ogd_{sess['id']}"): open_liga_aufstellung_doppel(sess['id'], False)
                        
                    if c_idx < len(r_list):
                        st.markdown(f"**Runde {c_idx+1} läuft:**")
                        cols = st.columns(min(len(r_list[c_idx]), 3))
                        for i, (m_k, m_l, h_k, g_k) in enumerate(r_list[c_idx]):
                            b_name = sess["liga_boards"][i % len(sess["liga_boards"])]
                            p_h, p_g = auf_h.get(h_k, "-"), auf_g.get(g_k, "-")
                            is_p = res.get(m_k, {}).get("played", False)
                            
                            with cols[i % len(cols)]:
                                with st.container(border=True):
                                    st.write(f"*{b_name}* - {m_l}")
                                    st.write(f"{p_h} vs {p_g}")
                                    # Auswechseln NUR IN KREUZ-RUNDE!
                                    if "Kreuz" in m_l and not is_p and "d" not in h_k:
                                        if st.button("🔄 H", key=f"subh_{m_k}"): open_liga_sub_dialog(sess['id'], h_k, True, p_h)
                                        if st.button("🔄 G", key=f"subg_{m_k}"): open_liga_sub_dialog(sess['id'], g_k, False, p_g)
                                        
                                    if is_p: st.success(f"{res[m_k]['lh']}:{res[m_k]['lg']}")
                                    else:
                                        if st.button("Eintragen", key=f"l_e_{m_k}"): open_liga_live_board_dialog(sess['id'], m_k, b_name, m_l, p_h, p_g, False)
                if is_done:
                    if st.button("📝 Spielbericht abschließen", key=f"l_b_{sess['id']}", use_container_width=True): open_liga_bericht_dialog(sess['id'])

    st.markdown("### 🗄️ Abgeschlossene Freundschaftsspiele (PDF-Export)")
    for l_sess in [l for l in st.session_state.sessions_list if l.get("is_liga") and l.get("is_locked")]:
        with st.container(border=True):
            st.markdown(f"**{l_sess['datum']}** | 🏆 {l_sess.get('heim_team')} vs. {l_sess.get('gast_team')}")
            try:
                st.download_button("📥 PDF laden", data=generate_spielbericht_pdf(l_sess), file_name=f"Spielbericht_{l_sess['id']}.pdf", mime="application/pdf", key=f"dl_{l_sess['id']}")
            except: pass

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    safe_data = make_serializable(st.session_state.sessions_list)
    st.download_button("📥 JSON Backup", json.dumps(safe_data, ensure_ascii=False), "steelers_backup.json", "application/json")
    
    for s in sorted(st.session_state.sessions_list, key=lambda x: int(x['id'].split('-')[1]), reverse=True):
        with st.container(border=True):
            st.markdown(f"**{s['id']}** — {s['datum']} ({'Liga' if s.get('is_liga') else 'Training'})")
            c1, c2, c3 = st.columns(3)
            if s.get("is_liga"):
                if c1.button("📝 Korrigieren", key=f"ak_{s['id']}"): open_liga_bericht_dialog(s['id'])
                if c2.button("⚙️ Bearbeiten", key=f"ae_{s['id']}"): open_edit_liga_session_dialog(s['id'])
            else:
                if c2.button("⚙️ Bearbeiten", key=f"ae_{s['id']}"): open_edit_session_dialog(s['id'])
            if c3.button("🗑️ Löschen", key=f"ad_{s['id']}"): open_delete_session_dialog(s['id'])

with tab_regeln:
    st.subheader("🎯 Modus & Regeln")
    with st.container(border=True):
        st.markdown("### 👑 Das Up & Down Prinzip (Einzel)\nGewinner steigt auf, Verlierer steigt ab.")
    with st.container(border=True):
        st.markdown("### 🤝 Koop-Modus\nFeste Teams, keine Duplikate zur Vorsession.")
    with st.container(border=True):
        st.markdown("### 💾 Backups\nAutomatisches Cloud-Backup im Hintergrund.")
