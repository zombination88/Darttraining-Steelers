# INSTRUKTION: DIESE REGELN DÜRFEN BEI CODE-UPDATES NIEMALS VERLETZT WERDEN
# 1. BACKUPS: Das Rolling-Backup in Google Sheets darf maximal 20 Einträge umfassen (ältere löschen).
# 2. JSON-EXPORT: Vor jedem json.dumps() MUSS die Hilfsfunktion make_serializable() aufgerufen werden, um Tupel/Datumsformate abzusichern!
# 3. KOOP-TEAMS: Es dürfen niemals exakt gleiche 2er-Teams aus der vorherigen Session gebildet werden.
# 4. ANTI-DOPPEL-PAUSE: Das Freilos in Runde 1 muss rotieren. Wer im letzten Match pausiert hat, darf nicht nochmal aussetzen.
# 5. ZEITMANAGEMENT: Globale Ø-Zeiten (Min/Runde, Min/Leg) inkl. Nacht-Übergang müssen im Session-Reiter berechnet bleiben.
# 6. KADER-STATS: Im Reiter Kader werden MVP, Dauerbrenner, Bester Avg und 180er Maschine angezeigt (nicht nur 50% Quoten). Bei Gleichstand: Tooltip!
# 7. HEADER: Der Titel oben links muss das Logo beinhalten und "Wehringer Steelers — Teamtraining" lauten.
# 8. SPIELMODI & LOGIK:
#    - Standard-Training (Einzel + Coop): X Runden Einzel (max 6 Boards), dann Y Runden Doppel (nur B1 & B2). 
#    - Koop 2vs2 (Up & Down): Reine Doppel-Session (0 Einzel). Gespielt wird exklusiv auf Kaiser B1 & Board 2.
#    - Up & Down (Einzel): Klassisch. Sieger steigt auf (Ri. B1), Verlierer ab. Kaiser der Vorsession startet ganz unten.
# 9. FREUNDSCHAFTSPIELE: Flexibel wählbar als 4er- oder 6er-Team mit variablen Boards, Blind Setup, Kreuz-Runde und PDF-Export. 
#    - WICHTIG: Im Reiter Freundschaftsspiele wird bei abgeschlossenen Spielen nur der PDF-Download angezeigt. Der Korrigieren/Bearbeiten-Button ist dort entfernt und nur im Match-Archiv erreichbar.
# 10. TAB-STRUKTUR & UI: Die Reiter müssen exakt in der definierten Reihenfolge (Übersicht, Kader, Session, Freundschaftsspiele, Match-Archiv, Modus & Regeln) und mit sämtlichen Statistik- und Blitz-Erfassungs-Blöcken aufgebaut sein.

import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import gspread
from google.oauth2.service_account import Credentials
import io
import os
import random
import math

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
            if len(all_vals) > 21:
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

def save_completed_backup(serializable_sessions):
    """Sicherer Tresor: Führt alte abgeschlossene Spiele mit neuen zusammen (Merge-System) und speichert in einer Zeile."""
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

def is_session_completed(sess):
    if sess.get("is_liga"):
        from_conf = get_liga_config(sess)
        total_matches = sum([len(r) for r in from_conf])
        played = len([k for k, v in sess.get("results", {}).items() if v.get("played")])
        return played == total_matches

    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    for r in range(1, total_rounds + 1):
        boards_in_round = get_boards_list(sess, r)
        for b_name in boards_in_round:
            match_info = res.get((r, b_name))
            if not match_info or not match_info.get("winner"):
                return False
    return True

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

c_logo, c_title = st.columns([1, 4])
with c_logo:
    for logo_path in ["logo.png.png", "logo.png"]:
        try:
            st.image(logo_path, width=80)
            break
        except:
            pass

with c_title:
    st.markdown("<h1 style='margin: 0; padding-top: 8px; font-size: 1.8rem;'>Wehringer Steelers — Teamtraining</h1>", unsafe_allow_html=True)

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

training_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga")]
liga_sessions = [s for s in st.session_state.sessions_list if s.get("is_liga")]

tab_übersicht, tab_kader, tab_session, tab_liga, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Freundschaftsspiele", "Match-Archiv", "Modus & Regeln"])

def get_or_create_teams(session, all_training_sessions):
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
                prev_teams = prev_sess.get("coop_teams", [])
                if len(prev_teams) % 2 != 0:
                    n_prev = len(prev_teams)
                    last_rel_round = prev_total - prev_singles
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
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if is_standard_training and total_rounds > 2 else total_rounds)
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

@st.dialog("🔄 Spieler auswechseln")
def open_substitution_dialog(board_name, session_id, round_num, slot_num, current_player):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    alle_spieler = list(set(sess.get("spieler", kader) + [current_player]))
    if "-" not in alle_spieler: alle_spieler.append("-")
    alle_spieler.sort()

    st.write(f"### Auswechslung für {board_name} (Runde {round_num})")
    idx = alle_spieler.index(current_player) if current_player in alle_spieler else 0
    new_sel = st.selectbox("Aus Kader wählen:", alle_spieler, index=idx, key=f"sub_sel_{session_id}_{board_name}_{round_num}_{slot_num}")
    new_txt = st.text_input("Oder neuen Gast eintragen:", placeholder="Name...", key=f"sub_txt_{session_id}_{board_name}_{round_num}_{slot_num}")
    
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

@st.dialog("📊 Session Endstand & Zusammenfassung")
def open_session_summary_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
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
    if num_players < 2: return 0
    return num_players // 2

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
def open_edit_session_dialog(session_id):
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_{session_id}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return

    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
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
            if st.checkbox(sp, value=(sp in sess.get("spieler", [])), key=f"edit_kader_{sp}_{session_id}"): anwesende.append(sp)
                
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
            st.session_state.sessions_list[real_idx] = sess
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
def open_board_dialog(board_name, session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds:
        st.warning(f"{board_name} has completed all rounds.")
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
        in_score1 = st.number_input("Legs Heim", 0, 5, score1, key=f"score1_{session_id}_{board_name}")
        in_180_1 = st.number_input("🎯 180er Heim", 0, 20, t1_180, key=f"180_1_{session_id}_{board_name}")
        in_avg_1 = st.number_input("📊 Avg Heim", 0.0, 180.0, avg1, step=0.1, key=f"avg_1_{session_id}_{board_name}")
    with c2:
        st.markdown(f"**Gast:** `{current_p2}`")
        in_score2 = st.number_input("Legs Gast", 0, 5, score2, key=f"score2_{session_id}_{board_name}")
        in_180_2 = st.number_input("🎯 180er Gast", 0, 20, t2_180, key=f"180_2_{session_id}_{board_name}")
        in_avg_2 = st.number_input("📊 Avg Gast", 0.0, 180.0, avg2, step=0.1, key=f"avg_2_{session_id}_{board_name}")
        
    ergebnis = f"{in_score1}:{in_score2}"
    winner = current_p1 if in_score1 > in_score2 else (current_p2 if in_score2 > in_score1 else "-")
    loser = current_p2 if winner == current_p1 else (current_p1 if winner == current_p2 else "-")
    
    st.info(f"📊 Ergebnis: **{ergebnis}** | 🏆 Sieger: **{winner if winner != '-' else 'Unentschieden'}**")
    
    req_win = 3 if sess.get("modus_leg", "Best of 5") == "Best of 5" else 2
    is_valid_result = True
    if current_p1 != "-" and current_p2 != "-":
        if in_score1 == in_score2: st.error("Unentschieden nicht möglich."); is_valid_result = False
        elif in_score1 > req_win or in_score2 > req_win: st.error(f"Max {req_win} Legs."); is_valid_result = False
        elif in_score1 != req_win and in_score2 != req_win: st.error(f"Sieger braucht genau {req_win} Legs."); is_valid_result = False
    
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
        doubles = [
            ("m13", "Doppel 1", "hd1", "gd1"), ("m14", "Doppel 2", "hd2", "gd2"), ("m15", "Doppel 3", "hd3", "gd3")
        ]
    else:
        singles = [
            ("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"),
            ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")
        ]
        cross = [
            ("m5", "Einzel 5 (Kreuz)", "h1", "g2"), ("m6", "Einzel 6 (Kreuz)", "h2", "g1"),
            ("m7", "Einzel 7 (Kreuz)", "h3", "g4"), ("m8", "Einzel 8 (Kreuz)", "h4", "g3")
        ]
        doubles = [
            ("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")
        ]
        
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
        raise ImportError("Fehlende Bibliotheken (pypdf oder reportlab). Bitte in requirements.txt hinterlegen!")

    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=A4)
    c.setFont("Helvetica-Bold", 9)
    
    heim = sess.get("heim_team", "")
    gast = sess.get("gast_team", "")
    datum = sess.get("datum", "")
    
    c.drawString(410, 755, datum)
    c.drawString(100, 722, heim) 
    c.drawString(330, 722, gast)
    
    res = sess.get("results", {})
    auf_h = sess.get("auf_heim", {})
    auf_g = sess.get("auf_gast", {})

    t_size = sess.get("team_size", 4)
    if t_size == 6:
        y_coords_pdf = {
            "m1": 615, "m2": 570, "m3": 525, "m4": 480, "m5": 435, "m6": 390,
            "m7": 345, "m8": 300, "m9": 255, "m10": 210, "m11": 165, "m12": 120,
            "m13": 80, "m14": 55, "m15": 30
        }
    else:
        y_coords_pdf = {
            "m1": 615, "m2": 570, "m3": 525, "m4": 480,
            "m5": 400, "m6": 355, "m7": 310, "m8": 265,
            "m9": 200, "m10": 155
        }
    
    x_name_heim = 65
    x_name_gast = 315
    x_legs_heim = 225
    x_legs_gast = 285
    x_180_heim = 95
    x_180_gast = 340
    
    rounds_map = get_liga_config(sess)
    match_map = [match for round in rounds_map for match in round]

    for m_key, label, h_key, g_key in match_map:
        if m_key in res and res[m_key].get("played"):
            m_data = res[m_key]
            y = y_coords_pdf.get(m_key, 500)
            
            h_name = str(auf_h.get(h_key, ""))
            g_name = str(auf_g.get(g_key, ""))
            
            c.drawString(x_name_heim, y, h_name)
            c.drawString(x_name_gast, y, g_name)
            c.drawString(x_legs_heim, y, str(m_data.get("lh", 0)))
            c.drawString(x_legs_gast, y, str(m_data.get("lg", 0)))
            
            y_sub = y - 12
            if m_data.get("180_h", 0) > 0:
                c.drawString(x_180_heim, y_sub, str(m_data.get("180_h", "")))
            if m_data.get("180_g", 0) > 0:
                c.drawString(x_180_gast, y_sub, str(m_data.get("180_g", "")))

    c.save()
    packet.seek(0)
    
    pdf_out = io.BytesIO()
    
    if os.path.exists("Bez_Schwaben_Spielbericht_2.pdf"):
        new_pdf = PdfReader(packet)
        original_pdf = PdfReader(open("Bez_Schwaben_Spielbericht_2.pdf", "rb"))
        output = PdfWriter()
        page = original_pdf.pages[0]
        page.merge_page(new_pdf.pages[0])
        output.add_page(page)
        output.write(pdf_out)
    elif os.path.exists("Bez_Schwaben_Spielbericht.pdf"):
        new_pdf = PdfReader(packet)
        original_pdf = PdfReader(open("Bez_Schwaben_Spielbericht.pdf", "rb"))
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

@st.dialog("➕ Neues Freundschaftsspiel starten", width="large")
def open_new_liga_match_dialog():
    st.write("Erstelle hier ein neues Freundschaftsspiel.")
    
    match_type = st.radio("Modus-Auswahl", [
        "🏆 Standard Liga-Spiel (4er-Team, 2 Boards)",
        "⚙️ Freies Spiel auf Liga-Basis (wählbare Teamgröße & Boards)"
    ])
    
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum des Spiels", date.today())
    heim_team = c2.text_input("Heimmannschaft", value="Wehringer Steelers")
    gast_team = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    
    if "Freies Spiel" in match_type:
        team_size = st.selectbox("Team-Größe", [4, 6], format_func=lambda x: f"{x}er-Team")
        b_count = st.selectbox("Anzahl paralleler Boards", [1, 2, 3, 4, 5, 6], index=1)
    else:
        team_size = 4
        b_count = 2
        
    st.write("Wähle die Boards aus (von links nach rechts):")
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    selected_boards = []
    cols = st.columns(min(b_count, 4))
    for i in range(b_count):
        with cols[i % len(cols)]:
            default_idx = i if i < len(board_options) else 0
            b_sel = st.selectbox(f"Board {i+1}", board_options, index=default_idx, key=f"liga_b_sel_{i}")
            selected_boards.append(b_sel)
    
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with cb2:
        if st.button("Spiel erstellen", type="primary", use_container_width=True):
            max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "L-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
            new_session = {
                "id": f"L-{max_id + 1}",
                "datum": session_datum.strftime("%d.%m.%Y"),
                "is_liga": True,
                "team_size": team_size,
                "boards_count": b_count,
                "heim_team": heim_team.strip(),
                "gast_team": gast_team.strip(),
                "liga_boards": selected_boards,
                "auf_heim": {},
                "auf_gast": {},
                "results": {}
            }
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("⚙️ Freundschaftsspiel bearbeiten")
def open_edit_liga_session_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    pwd = st.text_input("Passwort eingeben", type="password", key=f"edit_pwd_{session_id}")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return
    
    try: curr_date = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_date = date.today()
    
    session_datum = st.date_input("Datum", curr_date)
    heim_team = st.text_input("Heimmannschaft", value=sess.get("heim_team", ""))
    gast_team = st.text_input("Gastmannschaft", value=sess.get("gast_team", ""))
    
    curr_boards = sess.get("liga_boards", ["Kaiser B1", "Board 2"])
    b_count = sess.get("boards_count", len(curr_boards))
    
    board_options = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    new_boards = []
    cols = st.columns(min(b_count, 4))
    for i in range(b_count):
        with cols[i % len(cols)]:
            curr_val = curr_boards[i] if i < len(curr_boards) else board_options[i]
            b_sel = st.selectbox(f"Board {i+1}", board_options, index=board_options.index(curr_val) if curr_val in board_options else 0, key=f"edit_liga_b_{session_id}_{i}")
            new_boards.append(b_sel)
    
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c_btn2:
        if st.button("Speichern", type="primary", use_container_width=True):
            sess.update({
                "datum": session_datum.strftime("%d.%m.%Y"),
                "heim_team": heim_team.strip(),
                "gast_team": gast_team.strip(),
                "liga_boards": new_boards
            })
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔒 Einzel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_einzel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    t_size = sess.get("team_size", 4)
    st.write(f"### Aufstellung: {team_name}")
    st.info(f"Trage hier die {t_size} Einzelspieler als Text ein.")
    
    inputs = []
    for i in range(t_size):
        inputs.append(st.text_input(f"Position {i+1}", key=f"auf_{session_id}_{is_heim}_{i}"))
        
    if st.button("Speichern", type="primary", use_container_width=True):
        if all(x.strip() for x in inputs):
            update_dict = {}
            for i, val in enumerate(inputs):
                key = f"h{i+1}" if is_heim else f"g{i+1}"
                update_dict[key] = val.strip()
            if is_heim:
                sess["auf_heim"].update(update_dict)
            else:
                sess["auf_gast"].update(update_dict)
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
        else:
            st.error(f"Bitte alle {t_size} Positionen eintragen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    t_size = sess.get("team_size", 4)
    num_doubles = 3 if t_size == 6 else 2
    
    st.write(f"### Doppel-Aufstellung: {team_name}")
    st.markdown("🚨 **Wichtig:** Jeder Spieler darf in den Doppel insgesamt nur **1x** vorkommen (keine Dubletten).")
    
    auf_dict = sess.get("auf_heim", {}) if is_heim else sess.get("auf_gast", {})
    bisherige_spieler = []
    for k, v in auf_dict.items():
        if ("h" in k or "g" in k) and not "d" in k:
            if v and v != "-": bisherige_spieler.append(v)
            
    for m_key, m_data in sess.get("results", {}).items():
        if is_heim:
            if m_data.get("s1") and m_data.get("s1") not in bisherige_spieler: bisherige_spieler.append(m_data.get("s1"))
            if m_data.get("s2") and m_data.get("s2") not in bisherige_spieler: bisherige_spieler.append(m_data.get("s2"))
            
    bisherige_spieler = list(set(bisherige_spieler))
    bisherige_spieler.sort()
    options = bisherige_spieler if bisherige_spieler else ["Bitte zuerst Einzel spielen..."]
    options_with_custom = options + ["+ Anderen Spieler eingeben..."]
    
    doubles_data = []
    for d_idx in range(num_doubles):
        st.markdown(f"**Doppel {d_idx+1}**")
        c1, c2 = st.columns(2)
        p1_sel = c1.selectbox(f"Spieler 1 (Doppel {d_idx+1})", options_with_custom, key=f"d{d_idx+1}_p1_sel_{session_id}_{is_heim}")
        p1 = c1.text_input(f"Name Spieler 1", key=f"d{d_idx+1}_p1_txt_{session_id}_{is_heim}") if p1_sel == "+ Anderen Spieler eingeben..." else p1_sel
        
        p2_sel = c2.selectbox(f"Spieler 2 (Doppel {d_idx+1})", options_with_custom, key=f"d{d_idx+1}_p2_sel_{session_id}_{is_heim}")
        p2 = c2.text_input(f"Name Spieler 2", key=f"d{d_idx+1}_p2_txt_{session_id}_{is_heim}") if p2_sel == "+ Anderen Spieler eingeben..." else p2_sel
        doubles_data.append((p1.strip() if p1 else "", p2.strip() if p2 else ""))
        
    if st.button("Speichern", type="primary", use_container_width=True):
        all_selected = []
        for p1, p2 in doubles_data:
            if p1: all_selected.append(p1)
            if p2: all_selected.append(p2)
            
        seen = set()
        duplicates = set()
        for player in all_selected:
            if player in seen:
                duplicates.add(player)
            seen.add(player)
            
        if any(not x for x in all_selected):
            st.error("🚨 Bitte alle Spieler für die Doppel ausfüllen!")
        elif duplicates:
            dup_names = ", ".join([f"'{d}'" for d in duplicates])
            st.error(f"🚨 Fehler: Der Spieler {dup_names} steht in mehreren Feldern! Jeder Spieler darf nur 1x in den Doppel aufgestellt werden.")
        else:
            update_dict = {}
            for d_idx, (p1, p2) in enumerate(doubles_data):
                key = f"hd{d_idx+1}" if is_heim else f"gd{d_idx+1}"
                update_dict[key] = f"{p1} & {p2}"
            if is_heim:
                sess["auf_heim"].update(update_dict)
            else:
                sess["auf_gast"].update(update_dict)
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🔄 Spieler auswechseln")
def open_liga_sub_dialog(session_id, p_key, is_heim, curr_name):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    st.write(f"Auswechslung für **{curr_name}**")
    new_name = st.text_input("Name des Ersatzspielers:")
        
    if st.button("Auswechslung Speichern", type="primary", use_container_width=True):
        if new_name.strip():
            if is_heim:
                sess["auf_heim"][p_key] = new_name.strip()
            else:
                sess["auf_gast"][p_key] = new_name.strip()
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🎯 Live Board (Freundschaftsspiel)")
def open_liga_live_board_dialog(session_id, m_key, board_name, m_label, p1, p2, is_right_board=False):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    res = sess.setdefault("results", {})
    m_data = res.get(m_key, {})
    
    st.write(f"### {board_name} — {m_label}")
    st.caption("Best of 5 (Wer zuerst 3 Legs hat, gewinnt).")
    
    if is_right_board:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Gast (Anwurf links):** `{p1}`")
            lg = st.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"lg_{session_id}_{m_key}")
            e180_g = st.number_input("180er Gast", 0, 10, m_data.get("180_g", 0), key=f"180g_{session_id}_{m_key}")
        with c2:
            st.markdown(f"**Heim:** `{p2}`")
            lh = st.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"lh_{session_id}_{m_key}")
            e180_h = st.number_input("180er Heim", 0, 10, m_data.get("180_h", 0), key=f"180h_{session_id}_{m_key}")
    else:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"**Heim (Anwurf links):** `{p1}`")
            lh = st.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"lh_{session_id}_{m_key}")
            e180_h = st.number_input("180er Heim", 0, 10, m_data.get("180_h", 0), key=f"180h_{session_id}_{m_key}")
        with c2:
            st.markdown(f"**Gast:** `{p2}`")
            lg = st.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"lg_{session_id}_{m_key}")
            e180_g = st.number_input("180er Gast", 0, 10, m_data.get("180_g", 0), key=f"180g_{session_id}_{m_key}")

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
            sess["results"] = res
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
    with cb2:
        if st.button("Abbrechen", use_container_width=True): st.rerun()

@st.dialog("📝 Offizieller Spielbericht (Korrektur)", width="large")
def open_liga_bericht_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
    res = sess.setdefault("results", {})
    match_map = [match for round in get_liga_config(sess) for match in round]
    st.write("Hier kannst du bei Bedarf alle Ergebnisse des Spielberichts manuell korrigieren.")
    
    all_valid = True
    
    for m_key, label, h_key, g_key in match_map:
        p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
        m_data = res.get(m_key, {})
        with st.expander(f"{label}: {p_heim} vs {p_gast}", expanded=False):
            c_lh, c_vs, c_lg = st.columns([2, 1, 2])
            lh = c_lh.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"blh_{session_id}_{m_key}")
            c_vs.markdown("<div style='text-align: center; padding-top: 30px;'>:</div>", unsafe_allow_html=True)
            lg = c_lg.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"blg_{session_id}_{m_key}")
            
            is_match_valid = (lh == 0 and lg == 0) or (lh == 3 and lg < 3) or (lg == 3 and lh < 3)
            if not is_match_valid:
                st.error(f"🚨 Ungültig! Best of 5 erfordert exakt 3 Legs für den Sieger.")
                all_valid = False
                
            res[m_key] = {"lh": lh, "lg": lg, "played": True if (lh>0 or lg>0) else False, "180_h": m_data.get("180_h", 0), "180_g": m_data.get("180_g", 0)}

    st.divider()
    
    is_locked = sess.get("is_locked", False)
    if not is_locked:
        lock_spiel = st.checkbox("🔒 Spiel endgültig abschließen & ins Archiv verschieben", value=False)
    else:
        lock_spiel = True
        st.info("Dieses Spiel ist bereits offiziell abgeschlossen.")

    if st.button("💾 Speichern & Schließen", type="primary", use_container_width=True, disabled=not all_valid):
        sess["is_locked"] = lock_spiel
        sess["results"] = res
        st.session_state.sessions_list[real_idx] = sess
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

with tab_übersicht:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session", type="primary", use_container_width=True, key="quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        sorted_for_btn = sorted(training_sessions, key=lambda x: int(x["id"].split("-")[1]) if "id" in x and '-' in x['id'] else 0, reverse=True)
        active_sessions_for_btn = [s for s in sorted_for_btn if not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Bearbeiten", use_container_width=True, key="edit_active_btn"):
                open_edit_session_dialog(active_sessions_for_btn[0]['id'])
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
                            if st.button("🔄", key=f"sub1_{curr_sess['id']}_{b_name}_{next_r}"): open_substitution_dialog(b_name, curr_sess['id'], next_r, 1, p1)
                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                        sc3, sc4 = st.columns([5, 2])
                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                        with sc4:
                            if st.button("🔄", key=f"sub2_{curr_sess['id']}_{b_name}_{next_r}"): open_substitution_dialog(b_name, curr_sess['id'], next_r, 2, p2)
                        
                        st.write("")
                        if st.button("🎯 Eintragen", key=f"live_{curr_sess['id']}_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                            open_board_dialog(b_name, curr_sess['id'])
                    else:
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle Runden beendet</p>", unsafe_allow_html=True)
                        st.success("✅ Abgeschlossen")

    st.write("")
    st.divider()

    st.markdown("### 📊 Allgemeine Statistiken")
    
    total_180s = 0
    kaiser_winner_text = "Noch offen"
    anwesende_count = 0
    
    display_sess = None
    all_sessions_sorted = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
    for s in all_sessions_sorted:
        if is_session_completed(s) or s.get("results"):
            display_sess = s
            break
    if not display_sess and all_sessions_sorted:
        display_sess = all_sessions_sorted[0]

    for sess in training_sessions:
        for match in sess.get("results", {}).values():
            s1_name = match.get("s1", "")
            s2_name = match.get("s2", "")
            if s1_name and " & " not in s1_name: total_180s += int(match.get("180_s1", 0))
            if s2_name and " & " not in s2_name: total_180s += int(match.get("180_s2", 0))

    if display_sess:
        l_results = display_sess.get("results", {})
        kaiser_matches = [(r, m) for (r, b), m in l_results.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
        if kaiser_matches:
            kaiser_matches.sort(key=lambda x: x[0], reverse=True)
            kaiser_winner_text = kaiser_matches[0][1].get("winner")
        
        anwesende_count = len([p for p in display_sess.get("spieler", []) if p != "-"])

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1: st.metric(label="Sessions", value=str(len(training_sessions)), delta="gesamt")
        with c2: st.metric(label="Team 180er", value=str(total_180s), delta="geworfen")
        st.divider()
        c3, c4 = st.columns(2)
        with c3: st.metric(label="Aktueller Kaiser", value=kaiser_winner_text[:12] + "..." if len(kaiser_winner_text) > 12 else kaiser_winner_text, delta="Board 1")
        with c4: st.metric(label="Anwesende", value=str(anwesende_count), delta="Spieler")
        
    st.write("")
    with st.expander("Letzte Session & Spitzenreiter", expanded=False):
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("### Letzte Session")
            if display_sess:
                l_date = display_sess.get('datum', '–')
                count_180s = {}
                match_avgs = []
                for m in display_sess.get('results', {}).values():
                    s1_name = m.get("s1", "")
                    s2_name = m.get("s2", "")
                    if s1_name and " & " not in s1_name:
                        count_180s[s1_name] = count_180s.get(s1_name, 0) + int(m.get("180_s1", 0))
                        if float(m.get("avg_s1", 0)) > 0: match_avgs.append((s1_name, float(m.get("avg_s1", 0))))
                    if s2_name and " & " not in s2_name:
                        count_180s[s2_name] = count_180s.get(s2_name, 0) + int(m.get("180_s2", 0))
                        if float(m.get("avg_s2", 0)) > 0: match_avgs.append((s2_name, float(m.get("avg_s2", 0))))
                
                most_180_text = "Keine"
                if count_180s and max(count_180s.values()) > 0:
                    top_player = max(count_180s, key=count_180s.get)
                    most_180_text = f"{top_player} ({count_180s[top_player]}x)"
                
                best_avg_text = "–"
                if match_avgs:
                    top_avg_player, top_avg_val = max(match_avgs, key=lambda x: x[1])
                    best_avg_text = f"{top_avg_player} ({top_avg_val:.1f})"
                
                st.info(f"**Datum:** {l_date}\n\n**Kaiser B1 (Einzel):** 👑 {kaiser_winner_text}\n\n**Höchster Einzel-Average:** 📊 {best_avg_text}\n\n**Meiste 180er:** 🎯 {most_180_text}")
            else:
                st.info("Keine Daten vorhanden.")

        with col_r:
            st.markdown("### Spitzenreiter")
            stats_temp = {p: {"Matches": 0, "Siege": 0} for p in kader}
            for sess in training_sessions:
                for match in sess.get("results", {}).values():
                    winner = match.get("winner", "")
                    loser = match.get("loser", "")
                    if winner and " & " not in winner:
                        for p in winner.split(" & "):
                            if p in stats_temp:
                                stats_temp[p]["Matches"] += 1
                                stats_temp[p]["Siege"] += 1
                    if loser and " & " not in loser:
                        for p in loser.split(" & "):
                            if p in stats_temp:
                                stats_temp[p]["Matches"] += 1

            best_p = "Keiner"
            best_q = 0.0
            best_m = 0
            for p in kader:
                m = stats_temp[p]["Matches"]
                s = stats_temp[p]["Siege"]
                if m > 0:
                    q = s / m
                    if q > best_q or (q == best_q and m > best_m):
                        best_q = q
                        best_m = m
                        best_p = p

            st.markdown(f"**{best_p}** (Siegquote: {(best_q*100):.0f}% bei {best_m} Matches)")
            st.progress(best_q)

    with st.expander("Zuletzt ausgetragene Board-Matches", expanded=False):
        all_matches = []
        for sess in all_sessions_sorted:
            sess_date = sess.get("datum", "")
            for (round_num, board_name), m_info in sess.get("results", {}).items():
                if not m_info.get("winner"): continue
                all_matches.append({
                    "Datum": sess_date, "Runde": round_num, "Board": board_name,
                    "Spieler": f"{m_info['s1']} vs {m_info['s2']}",
                    "Ergebnis": m_info['ergebnis'], "Sieger": m_info['winner']
                })
                
        if all_matches:
            for m in all_matches[:15]: 
                with st.container(border=True):
                    st.markdown(f"**{m['Datum']} - {m['Board']}** (Runde {m['Runde']})")
                    st.caption(f"⚔️ {m['Spieler']}")
                    st.markdown(f"Ergebnis: {m['Ergebnis']} | Sieger: **{m['Sieger']}**")
        else:
            st.info("Bisher wurden keine Board-Matches ausgetragen.")

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
    st.write("Isolierter Bereich für Freundschaftsspiele (flexibel als 4er- oder 6er-Team mit variablen Boards, Blind Setup, Kreuz-Runde und PDF-Export).")
    
    if st.button("➕ Neues Freundschaftsspiel starten", type="primary", use_container_width=True):
        open_new_liga_match_dialog()
        
    st.divider()
    
    active_liga = [l for l in liga_sessions if not l.get("is_locked", False)]
    completed_liga = [l for l in liga_sessions if l.get("is_locked", False)]
    
    if not active_liga:
        st.info("Keine aktiven Freundschaftsspiele vorhanden. Starte oben ein neues Spiel.")
    else:
        for l_sess in active_liga:
            heim = l_sess.get("heim_team", "Heim")
            gast = l_sess.get("gast_team", "Gast")
            res = l_sess.setdefault("results", {})
            boards = l_sess.get("liga_boards", ["Kaiser B1", "Board 2"])
            b_count = l_sess.get("boards_count", len(boards))
            
            auf_h = l_sess.setdefault("auf_heim", {})
            auf_g = l_sess.setdefault("auf_gast", {})
            
            sets_heim, sets_gast, legs_heim, legs_gast, total_180s_liga = 0, 0, 0, 0, 0
            for m_data in res.values():
                total_180s_liga += int(m_data.get("180_h", 0)) + int(m_data.get("180_g", 0))
                if m_data.get("played"):
                    lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                    legs_heim += lh; legs_gast += lg
                    if lh > lg: sets_heim += 1
                    elif lg > lh: sets_gast += 1
                    
            rounds_list = get_liga_config(l_sess)
            total_matches_count = sum([len(r) for r in rounds_list])
            played_matches_count = len([k for k, v in res.items() if v.get("played")])
            is_done = (played_matches_count == total_matches_count)
            status = "✅ Abgeschlossen" if is_done else "🔴 Aktiv"
            
            with st.container(border=True):
                st.markdown(f"### {heim} vs. {gast}")
                st.caption(f"{l_sess['datum']} | ID: {l_sess['id']} | Status: {status}")
                
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Sets", f"{sets_heim} : {sets_gast}")
                col_s2.metric("Legs", f"{legs_heim} : {legs_gast}")
                col_s3.metric("Fortschritt", f"{played_matches_count}/{total_matches_count}")
                col_s4.metric("180er gesamt", f"{total_180s_liga}x")
                st.divider()
                
                t_size = l_sess.get("team_size", 4)
                h_einzel_ok = bool(auf_h.get(f"h{t_size}"))
                g_einzel_ok = bool(auf_g.get(f"g{t_size}"))
                
                if not h_einzel_ok or not g_einzel_ok:
                    st.warning(f"Phase 1: Alle {t_size} Einzelspieler eintragen (verdeckt)")
                    c_h, c_g = st.columns(2)
                    if not h_einzel_ok and c_h.button("🔒 Heim Aufstellen", key=f"h_setup_{l_sess['id']}"):
                        open_liga_aufstellung_einzel(l_sess['id'], True)
                    if not g_einzel_ok and c_g.button("🔒 Gast Aufstellen", key=f"g_setup_{l_sess['id']}"):
                        open_liga_aufstellung_einzel(l_sess['id'], False)
                elif not is_done:
                    curr_round_idx = 0
                    for r_idx, round_matches in enumerate(rounds_list):
                        if not all(res.get(m[0], {}).get("played") for m in round_matches):
                            curr_round_idx = r_idx
                            break
                            
                    num_doubles_blocks = 3 if t_size == 6 else 2
                    is_in_doubles = (curr_round_idx >= len(rounds_list) - num_doubles_blocks)
                    
                    if is_in_doubles:
                        h_doppel_ok = bool(auf_h.get("hd1"))
                        g_doppel_ok = bool(auf_g.get("gd1"))
                        if not h_doppel_ok or not g_doppel_ok:
                            st.warning("🚨 Die Doppel-Runden dürfen erst gestartet werden, wenn beide Teams ihre Doppel-Aufstellungen hinterlegt haben!")
                            c_dh, c_dg = st.columns(2)
                            if not h_doppel_ok and c_dh.button("🔒 Heim Doppel", key=f"hd_setup_{l_sess['id']}"):
                                open_liga_aufstellung_doppel(l_sess['id'], True)
                            if not g_doppel_ok and c_dg.button("🔒 Gast Doppel", key=f"gd_setup_{l_sess['id']}"):
                                open_liga_aufstellung_doppel(l_sess['id'], False)
                            continue
                    elif curr_round_idx >= 1:
                        st.markdown("**🔜 Doppel bereits jetzt aufstellen (Optional):**")
                        c_opt1, c_opt2 = st.columns(2)
                        if not auf_h.get("hd1") and c_opt1.button("🔒 Heim Doppel", key=f"opt_hd_{l_sess['id']}"):
                            open_liga_aufstellung_doppel(l_sess['id'], True)
                        if not auf_g.get("gd1") and c_opt2.button("🔒 Gast Doppel", key=f"opt_gd_{l_sess['id']}"):
                            open_liga_aufstellung_doppel(l_sess['id'], False)
                                
                    if curr_round_idx < len(rounds_list):
                        active_matches = rounds_list[curr_round_idx]
                        st.markdown(f"**Aktive Runde ({curr_round_idx + 1} / {len(rounds_list)})**")
                        
                        current_board_matches = active_matches[:b_count]
                        waiting_queue = active_matches[b_count:]
                        
                        cols_boards = st.columns(min(len(current_board_matches), 3) if len(current_board_matches) > 0 else 1)
                        for i, (m_key, m_label, h_key, g_key) in enumerate(current_board_matches):
                            b_name = boards[i % len(boards)]
                            p_heim, p_gast = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
                            is_played = res.get(m_key, {}).get("played", False)
                            
                            with cols_boards[i % len(cols_boards)]:
                                with st.container(border=True):
                                    st.write(f"*{b_name}* — {m_label}")
                                    
                                    show_sub_btn = ("Kreuz" in m_label) and not is_played
                                    
                                    if i % 2 == 1:
                                        st.markdown(f"Gast (links): **{p_gast}**")
                                        if show_sub_btn and not "d" in g_key:
                                            if st.button("🔄", key=f"sub_g_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_gast)
                                        st.markdown(f"Heim: **{p_heim}**")
                                        if show_sub_btn and not "d" in h_key:
                                            if st.button("🔄", key=f"sub_h_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_heim)
                                    else:
                                        st.markdown(f"Heim (links): **{p_heim}**")
                                        if show_sub_btn and not "d" in h_key:
                                            if st.button("🔄", key=f"sub_h_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_heim)
                                        st.markdown(f"Gast: **{p_gast}**")
                                        if show_sub_btn and not "d" in g_key:
                                            if st.button("🔄", key=f"sub_g_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_gast)
                                    
                                    if is_played:
                                        m_inf = res[m_key]
                                        st.success(f"Ergebnis: {m_inf['lh']}:{m_inf['lg']}")
                                    else:
                                        if st.button("🎯 Eintragen", key=f"live_{l_sess['id']}_{m_key}", use_container_width=True):
                                            open_liga_live_board_dialog(l_sess['id'], m_key, b_name, m_label, p_gast if i%2==1 else p_heim, p_heim if i%2==1 else p_gast, is_right_board=(i%2==1))

                        if waiting_queue:
                            st.write("")
                            st.markdown("##### 📋 Warteschlange (Nächste Spiele auf den Boards):")
                            for wi, (wm_key, wm_label, wh_key, wg_key) in enumerate(waiting_queue):
                                wp_h, wp_g = auf_h.get(wh_key, "-"), auf_g.get(wg_key, "-")
                                st.caption(f"• **{wm_label}**: {wp_h} vs {wp_g}")

                if is_done or (h_einzel_ok and g_einzel_ok):
                    st.divider()
                    if st.button("📝 Spielbericht ansehen & abschließen", key=f"l_ber_{l_sess['id']}", use_container_width=True):
                        open_liga_bericht_dialog(l_sess['id'])

    st.write("")
    st.markdown("### 🗄️ Abgeschlossene Freundschaftsspiele (PDF-Export)")
    st.write("Hier findest du alle beendeten Spiele. Die PDF-Ausleitung füllt den offiziellen Spielbericht aus.")
    
    if not completed_liga:
        st.info("Noch keine abgeschlossenen Freundschaftsspiele im Archiv.")
    else:
        for c_sess in completed_liga:
            with st.container(border=True):
                st.markdown(f"**{c_sess['datum']}** | 🏆 {c_sess.get('heim_team')} vs. {c_sess.get('gast_team')}")
                try:
                    pdf_file = generate_spielbericht_pdf(c_sess)
                    st.download_button(
                        label="📥 Offiziellen Spielbericht als PDF laden",
                        data=pdf_file,
                        file_name=f"Spielbericht_{c_sess.get('heim_team')}_vs_{c_sess.get('gast_team')}.pdf",
                        mime="application/pdf",
                        key=f"dl_pdf_{c_sess['id']}"
                    )
                except Exception as e:
                    st.error(f"PDF-Generierung fehlgeschlagen: {e}")

with tab_archiv:
    st.subheader("Match-Archiv & Verwaltung")
    st.caption("Die neueste Session steht hier immer ganz oben. Enthält Training und Freundschaftsspiele.")
    
    if st.session_state.sessions_list:
        safe_data_for_export = make_serializable(st.session_state.sessions_list)
        backup_json_str = json.dumps(safe_data_for_export, ensure_ascii=False, indent=2)
        st.download_button(label="📥 Backup als JSON herunterladen", data=backup_json_str, file_name=f"steelers_backup_{date.today().strftime('%Y-%m-%d')}.json", mime="application/json", use_container_width=True)
        st.write("")

    if not st.session_state.sessions_list:
        st.info("Keine Sessions vorhanden.")
    else:
        def parse_session_date(sess):
            try:
                return datetime.strptime(sess.get("datum", "01.01.2026"), "%d.%m.%Y")
            except:
                return datetime.min
                
        sorted_sessions = sorted(
            st.session_state.sessions_list, 
            key=lambda x: (parse_session_date(x), int(x["id"].split("-")[1]) if "-" in x["id"] and x["id"].split("-")[1].isdigit() else 0), 
            reverse=True
        )
        
        for sess in sorted_sessions:
            is_l = sess.get("is_liga", False)
            
            with st.container(border=True):
                if is_l:
                    status_text = "✅ [Abgeschlossen]" if sess.get("is_locked", False) else "🔴 [Aktiv]"
                    st.markdown(f"**{sess['id']}** (Freundschaftsspiel) — {sess['datum']} {status_text}\n\n🏆 {sess.get('heim_team')} vs {sess.get('gast_team')}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("📝 Spielbericht", key=f"arch_liga_v_{sess['id']}", use_container_width=True):
                            open_liga_bericht_dialog(sess['id'])
                    with c2:
                        if st.button("⚙️ Bearbeiten", key=f"arch_liga_e_{sess['id']}", use_container_width=True):
                            open_edit_liga_session_dialog(sess['id'])
                    with c3:
                        if st.button("🗑️ Löschen", key=f"arch_liga_d_{sess['id']}", use_container_width=True):
                            open_delete_session_dialog(sess['id'])
                else:
                    status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                    start_t = sess.get("start_time", "–")
                    end_t = sess.get("end_time", "–")
                    time_display = f" | ⏱️ {start_t} - {end_t} Uhr" if start_t and start_t != "–" else ""
                    st.markdown(f"**{sess['id']}** (Training) — {sess['datum']}{time_display} {status_text}")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("📊 Ansehen", key=f"arch_view_{sess['id']}", use_container_width=True): open_session_summary_dialog(sess['id'])
                    with c2:
                        if st.button("⚙️ Bearbeiten", key=f"arch_edit_{sess['id']}", use_container_width=True): open_edit_session_dialog(sess['id'])
                    with c3:
                        if st.button("🗑️ Löschen", key=f"arch_del_{sess['id']}", use_container_width=True): open_delete_session_dialog(sess['id'])
                        
                    st.divider()
                    
                    is_checked = st.checkbox(f"⚡ Runden-Schnellerfassung & Korrektur (Admin)", key=f"blitz_check_{sess['id']}")
                    if is_checked:
                        blitz_pwd = st.text_input("Admin-Passwort:", type="password", key=f"blitz_pwd_{sess['id']}")
                        if blitz_pwd == "1521":
                            st.markdown(f"#### ⚡ Schnellerfassung für {sess['id']}")
                            total_rounds = sess.get("total_rounds", 4)
                            leg_modus = sess.get("modus_leg", "Best of 5")
                            
                            for r in range(1, total_rounds + 1):
                                st.markdown(f"**Runde {r}**")
                                boards_in_r = get_boards_list(sess, r)
                                for b_name in boards_in_r:
                                    m_info = sess.get("results", {}).get((r, b_name))
                                    p1, p2 = get_board_players(sess, r, b_name) if not m_info else (m_info.get("s1", "-"), m_info.get("s2", "-"))
                                    
                                    try:
                                        s1 = int(m_info.get("ergebnis", "0:0").split(":")[0]) if m_info else 0
                                        s2 = int(m_info.get("ergebnis", "0:0").split(":")[1]) if m_info else 0
                                    except:
                                        s1, s2 = 0, 0
                                        
                                    with st.container(border=True):
                                        st.write(f"*{b_name}*")
                                        c_p1, c_vs, c_p2 = st.columns([4, 1, 4])
                                        c_p1.markdown(f"**{p1}**")
                                        c_vs.markdown("vs")
                                        c_p2.markdown(f"**{p2}**")
                                        
                                        c_in1, c_in2 = st.columns(2)
                                        val1 = c_in1.number_input("Legs Heim", min_value=0, max_value=5, value=s1, key=f"blitz_l1_{sess['id']}_{r}_{b_name}")
                                        val2 = c_in2.number_input("Legs Gast", min_value=0, max_value=5, value=s2, key=f"blitz_l2_{sess['id']}_{r}_{b_name}")
                                        
                                        c_b1, c_b2 = st.columns(2)
                                        with c_b1:
                                            if st.button("💾 Speichern", key=f"blitz_save_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                                req_win = 3 if leg_modus == "Best of 5" else 2
                                                if p1 == "-" or p2 == "-":
                                                    pass
                                                elif val1 == val2:
                                                    st.error("🚨 Unentschieden nicht möglich.")
                                                elif val1 > req_win or val2 > req_win:
                                                    st.error(f"🚨 Bei {leg_modus} max. {req_win} Legs.")
                                                elif val1 != req_win and val2 != req_win:
                                                    st.error(f"🚨 Sieger braucht genau {req_win} Legs.")
                                                else:
                                                    winner = p1 if val1 > val2 else p2
                                                    loser = p2 if val1 > val2 else p1
                                                    if "results" not in sess: sess["results"] = {}
                                                    
                                                    if m_info:
                                                        sess["results"][(r, b_name)]["ergebnis"] = f"{val1}:{val2}"
                                                        sess["results"][(r, b_name)]["winner"] = winner
                                                        sess["results"][(r, b_name)]["loser"] = loser
                                                    else:
                                                        sess["results"][(r, b_name)] = {
                                                            "s1": p1, "s2": p2, "ergebnis": f"{val1}:{val2}",
                                                            "winner": winner, "loser": loser,
                                                            "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0
                                                        }
                                                    smart_sync_and_save(st.session_state.sessions_list)
                                                    st.rerun()
                                        with c_b2:
                                            if st.button("🗑️ Leeren", key=f"blitz_del_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                                if (r, b_name) in sess["results"]:
                                                    del sess["results"][(r, b_name)]
                                                    smart_sync_and_save(st.session_state.sessions_list)
                                                    st.rerun()
                        elif blitz_pwd:
                            st.error("Falsches Passwort!")

with tab_regeln:
    st.subheader("🎯 Modus & Spielablauf")
    st.write("Hier findet ihr die vollständige Anleitung für den Trainingsabend, den WhatsApp-Workflow, den Auf- und Abstieg sowie den Koop-Modus.")
    
    with st.container(border=True):
        st.markdown("### 📱 WhatsApp-Umfrage & Session-Start")
        st.markdown("""
        * **Die Umfrage:** Der Teamcoach startet vor jedem Teamtraining eine Umfrage in der WhatsApp-Gruppe, wer an diesem Abend dabei ist.
        * **Der Startschuss:** Sobald die Rückmeldungen vorliegen, erstellt der Coach den Spieltag in der App über **➕ Neue Session**. Am Trainingsabend selbst klickt er auf **🚀 Teamtraining starten**, wodurch die offizielle Zeiterfassung beginnt.
        """)

    with st.container(border=True):
        st.markdown("### 👑 Das Up & Down Prinzip (Einzel)")
        st.markdown("""
        * **Das Prinzip:** Wer auf Kaiser B1 gewinnt, bleibt König (Kaiser) oder steigt auf. Wer verliert, wandert ein Board nach unten. Wer ganz unten gewinnt, steigt nach oben auf.
        """)

    with st.container(border=True):
        st.markdown("### 🤝 Der Koop-Modus (Feste 2v2-Teams & Up & Down)")
        st.markdown("""
        * **Zufällige Teams:** Es werden feste 2er-Paarungen per Zufall gebildet, die für die gesamte Session so zusammenbleiben.
        * **Wichtige Regel:** Es dürfen **keine exakt gleichen 2er-Paarungen** aus der Vorsession zusammen spielen (wird automatisch geprüft).
        * **Up & Down für Teams:** Gespielt wird auf Kaiser B1 und Board 2 im gewohnten Up & Down System (Gewinner steigen auf, Verlierer steigen ab).
        * **Anzahl der Runden:** Die Anzahl der Runden wird frei festgelegt (z.B. 2 Runden).
        * **Automatisches Pausen-Freilos:** Bei einer ungeraden Teamanzahl (z.B. 5 Teams) rotiert das aussetzende Team in jeder Runde automatisch weiter, sodass im Laufe des Abends jeder gleich oft pausiert.
        * **Anti-Doppel-Pause Schutz:** Spieler, die in der letzten Session als Letztes pausieren mussten, sind in der neuen Session in Runde 1 garantiert im Einsatz.
        * **Strikte Reihenfolge:** Im Standard-Training wird die Koop-Phase erst freigeschaltet, wenn **alle Einzel-Runden komplett zu Ende gespielt und eingetragen** sind.
        """)

    with st.container(border=True):
        st.markdown("### 🏆 Freundschaftsspiele")
        st.markdown("""
        * Eigener Bereich im Tab **Freundschaftsspiele**.
        * **Ablauf:** Die Aufstellung erfolgt in 2 Phasen (Einzel und Doppel), verdeckt (Blind Setup).
        * **Flexibel wählbar:** Als 4er- oder 6er-Team mit variablen Boards (wobei pro Board immer 2 Spieler spielen).
        * **Live-Tracking & Warteschlange:** Gespielt wird auf frei wählbaren parallelen Boards. Die aktuellen Board-Matches sowie die nachfolgende Warteschlange werden übersichtlich angezeigt.
        * **Archivierung & Regel:** Abgeschlossene Freundschaftsspiele zeigen im Tab 'Freundschaftsspiele' ausschließlich den PDF-Download-Button. Der Korrigieren/Bearbeiten-Button ist dort entfernt und ausschließlich im **Match-Archiv** erreichbar.
        """)

    with st.container(border=True):
        st.markdown("### 💾 Automatisches Cloud-Backup & JSON-Download")
        st.markdown("""
        * **Cloud-Audit-Trail:** Nach jeder Änderung, jedem Spielerwechsel und jedem eingetragenen Match-Ergebnis speichert die App vollautomatisch einen vollständigen Zeit-Snapshot in einem separaten Backup-Blatt (`backups`) in unserer Google-Tabelle.
        * **Lokales JSON-Backup:** Im Reiter **Match-Archiv** könnt ihr jederzeit per Klick ein aktuelles Backup aller Sessions als JSON-Datei auf euer Endgerät herunterladen.
        """)

    with st.container(border=True):
        st.markdown("### 🚦 Die Ampel-Anzeige & Board-Begrenzung")
        st.markdown("""
        * 🟢 **Spielbar:** Euer Match steht fest – ihr könnt sofort loslegen!
        * 🔴 **Wartet:** Ihr müsst noch kurz auf die Nachbarboards warten.
        * **Keine leeren Boards:** Die App sperrt zu viele Boards automatisch, wenn nicht genügend Spieler da sind.
        """)

    with st.container(border=True):
        st.markdown("### ⏱️ Leg-Modus Validierung")
        st.markdown("""
        * **Best of 5:** Der Sieger benötigt exakt 3 Legs (3:0, 3:1, 3:2).
        * **Best of 3:** Der Sieger benötigt exakt 2 Legs (2:0, 2:1).
        """)
