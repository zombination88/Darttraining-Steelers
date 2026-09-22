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
# 9. FREUNDSCHAFTSPIELE: Flexibel wählbar als 4er-, 6er-, 8er-, 10er- oder 12er-Team mit variablen Boards, Blind Setup, Kreuz-Runde und PDF-Export. 
#    - WICHTIG: Im Reiter Freundschaftsspiele wird bei abgeschlossenen Spielen nur für den PDF-Download angezeigt. Der Korrigieren/Bearbeiten-Button ist dort entfernt und nur im Match-Archiv erreichbar.
# 10. TAB-STRUKTUR & UI: Die Reiter müssen exakt in der definierten Reihenfolge (Übersicht, Kader, Session, Freundschaftsspiele, Liga (Punktspiele), Match-Archiv, Modus & Regeln) und mit sämtlichen Statistik- und Blitz-Erfassungs-Blöcken aufgebaut sein.

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import json
import gspread
from google.oauth2.service_account import Credentials
import io
import os
import random
import math
import base64
from PIL import Image
import extra_streamlit_components as stx

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

# --- LOGIN & ROLLEN-SYSTEM (COOKIES) ---
cookie_manager = stx.CookieManager()

if "role" not in st.session_state:
    st.session_state.role = "Gast"

current_cookie = cookie_manager.get(cookie="steelers_role")
if current_cookie == "Spieler":
    st.session_state.role = "Spieler"

with st.sidebar:
    st.markdown("### 🔐 Login-Bereich")
    if st.session_state.role == "Gast":
        st.info("👀 **Gast-Modus**: Du kannst alle Statistiken, Tabellen und Spielberichte ansehen.")
        pwd = st.text_input("Passwort (für Steelers-Spieler):", type="password")
        if st.button("Einloggen", use_container_width=True):
            if pwd == "20Steelers25" or pwd == "1521":
                cookie_manager.set("steelers_role", "Spieler", expires_at=datetime.now() + timedelta(days=365))
                st.session_state.role = "Spieler"
                st.success("✅ Login erfolgreich! Die Buttons rechts sind nun aktiviert.")
            else:
                st.error("Falsches Passwort!")
        st.markdown("---")
        st.caption("💡 **Info:** Einmal einloggen und dein Browser merkt sich deine Rechte per Cookie für 1 Jahr. Kein ständiges Neuanmelden nötig!")
    else:
        st.success("✅ **Spieler-Modus**: Du hast Schreibrechte für Ergebnisse & Sessions.")
        if st.button("Ausloggen", use_container_width=True):
            cookie_manager.delete("steelers_role")
            st.session_state.role = "Gast"
            st.success("Abgemeldet!")

is_admin = st.session_state.role == "Spieler"
# ------------------------------------------

SHEET_URL = "https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0"

def make_serializable(data):
    if isinstance(data, dict): return {str(k): make_serializable(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)): return [make_serializable(i) for i in data]
    elif hasattr(data, 'isoformat'): return data.isoformat()
    else: return data

@st.cache_resource
def init_connection():
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_url(SHEET_URL)
    except Exception as e:
        return None

spreadsheet = init_connection()

def ensure_worksheet(sheet_obj, title):
    try: return sheet_obj.worksheet(title)
    except:
        ws = sheet_obj.add_worksheet(title=title, rows=100, cols=2)
        ws.update([["json_data"]])
        return ws

def load_chunked(ws):
    data = ws.get_all_records()
    if not data: return []
    raw_str = "".join([str(r.get("json_data", "")) for r in data])
    if raw_str: return json.loads(raw_str)
    return []

def chunked_save(ws, data_list):
    json_str = json.dumps(data_list, ensure_ascii=False)
    chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
    rows = [["json_data"]] + [[c] for c in chunks]
    ws.clear()
    ws.update(rows)

def load_data():
    if not spreadsheet: return []
    try:
        all_sessions = []
        try: all_sessions.extend(load_chunked(spreadsheet.worksheet("sessions")))
        except Exception: pass
        try: all_sessions.extend(load_chunked(spreadsheet.worksheet("liga_sessions")))
        except Exception: pass
        try: all_sessions.extend(load_chunked(spreadsheet.worksheet("completed_liga")))
        except Exception: pass
            
        sessions = []
        for sess in all_sessions:
            fixed_results = {}
            for k, v in sess.get("results", {}).items():
                parts = k.split("_", 1)
                if len(parts) == 2 and not sess.get("is_liga") and not sess.get("is_wettkampf"):
                    fixed_results[(int(parts[0]), parts[1])] = v
                else: fixed_results[k] = v
            sess["results"] = fixed_results
            if not any(s['id'] == sess['id'] for s in sessions):
                sessions.append(sess)
        return sessions
    except Exception as e:
        st.error(f"Fehler beim Laden aus Google Sheets: {e}")
    return []

def save_backup_to_cloud(serializable_sessions):
    try:
        if not spreadsheet: return
        ws = ensure_worksheet(spreadsheet, "backups")
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
        json_str = json.dumps(serializable_sessions, ensure_ascii=False)
        ws.append_row([ts, json_str])
        try:
            all_vals = ws.get_all_values()
            if len(all_vals) > 21:
                rows_to_delete = len(all_vals) - 21
                for _ in range(rows_to_delete):
                    try: ws.delete_rows(2)
                    except: ws.delete_row(2)
        except Exception: pass
    except Exception: pass

def save_completed_backup(serializable_sessions):
    try:
        if not spreadsheet: return
        vault_ws = ensure_worksheet(spreadsheet, "completed_backup")
        existing_vault_data = []
        try:
            val = vault_ws.cell(2, 2).value
            if val: existing_vault_data = json.loads(val)
        except Exception: pass
        vault_dict = {s["id"]: s for s in existing_vault_data}
        for s in serializable_sessions:
            if not s.get("is_liga") and not s.get("is_wettkampf") and s.get("end_time"):
                vault_dict[s["id"]] = s
        merged_vault = list(vault_dict.values())
        json_str = json.dumps(merged_vault, ensure_ascii=False)
        vault_ws.clear()
        vault_ws.update([["Last_Updated", "JSON_Data_Completed"], [get_local_time_str(), json_str]])
    except Exception: pass

def save_data(sessions):
    if not spreadsheet: return
    serializable_sessions = []
    for sess in sessions:
        sess_copy = sess.copy()
        fixed_results = {}
        for k, v in sess.get("results", {}).items():
            if isinstance(k, tuple) and len(k) == 2: fixed_results[f"{k[0]}_{k[1]}"] = v
            else: fixed_results[k] = v
        sess_copy["results"] = fixed_results
        serializable_sessions.append(sess_copy)
    try:
        sichere_sessions = make_serializable(serializable_sessions)
        normal_sessions = [s for s in sichere_sessions if not s.get("is_wettkampf")]
        liga_sessions_list = [s for s in sichere_sessions if s.get("is_wettkampf") and not s.get("is_locked")]
        completed_liga_list = [s for s in sichere_sessions if s.get("is_wettkampf") and s.get("is_locked")]
        
        chunked_save(ensure_worksheet(spreadsheet, "sessions"), normal_sessions)
        chunked_save(ensure_worksheet(spreadsheet, "liga_sessions"), liga_sessions_list)
        chunked_save(ensure_worksheet(spreadsheet, "completed_liga"), completed_liga_list)
        save_backup_to_cloud(sichere_sessions)
        save_completed_backup(sichere_sessions)
    except Exception as e: st.error(f"Fehler beim Speichern in Google Sheets: {e}")

def get_local_time_str():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%H:%M")
    except: return datetime.now().strftime("%H:%M")

def get_liga_config(sess):
    t_size = sess.get("team_size", 4)
    b_count = sess.get("boards_count", 2)
    if t_size == 12:
        singles = [(f"m{i}", f"Einzel {i}", f"h{i}", f"g{i}") for i in range(1, 13)]
        cross = [(f"m{i+12}", f"Kreuz-Einzel {i}", f"h{i}", f"g{(i+5)%12 + 1}") for i in range(1, 13)]
        doubles = [(f"m{i+24}", f"Doppel {i}", f"hd{i}", f"gd{i}") for i in range(1, 7)]
    elif t_size == 10:
        singles = [(f"m{i}", f"Einzel {i}", f"h{i}", f"g{i}") for i in range(1, 11)]
        cross = [(f"m{i+10}", f"Kreuz-Einzel {i}", f"h{i}", f"g{(i+4)%10 + 1}") for i in range(1, 11)]
        doubles = [(f"m{i+20}", f"Doppel {i}", f"hd{i}", f"gd{i}") for i in range(1, 6)]
    elif t_size == 8:
        singles = [(f"m{i}", f"Einzel {i}", f"h{i}", f"g{i}") for i in range(1, 9)]
        cross = [(f"m{i+8}", f"Kreuz-Einzel {i}", f"h{i}", f"g{(i+3)%8 + 1}") for i in range(1, 9)]
        doubles = [(f"m{i+16}", f"Doppel {i}", f"hd{i}", f"gd{i}") for i in range(1, 5)]
    elif t_size == 6:
        singles = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"),("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4"),("m5", "Einzel 5", "h5", "g5"), ("m6", "Einzel 6", "h6", "g6")]
        cross = [("m7", "Kreuz-Einzel 1", "h1", "g4"), ("m8", "Kreuz-Einzel 2", "h2", "g5"),("m9", "Kreuz-Einzel 3", "h3", "g6"), ("m10", "Kreuz-Einzel 4", "h4", "g1"),("m11", "Kreuz-Einzel 5", "h5", "g2"), ("m12", "Kreuz-Einzel 6", "h6", "g3")]
        doubles = [("m13", "Doppel 1", "hd1", "gd1"), ("m14", "Doppel 2", "hd2", "gd2"), ("m15", "Doppel 3", "hd3", "gd3")]
    else:
        singles = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"),("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")]
        cross = [("m5", "Einzel 5 (Kreuz)", "h1", "g2"), ("m6", "Einzel 6 (Kreuz)", "h2", "g1"),("m7", "Einzel 7 (Kreuz)", "h3", "g4"), ("m8", "Einzel 8 (Kreuz)", "h4", "g3")]
        doubles = [("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
    rounds = []
    for block in [singles, cross, doubles]:
        for i in range(0, len(block), b_count): rounds.append(block[i:i + b_count])
    return rounds

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 6)
    modus = session.get("modus", "Up & Down")
    is_standard_training = (modus == "Standard-Training (Einzel + Coop)")
    total_rounds = session.get("total_rounds", 6 if is_standard_training else 4)
    singles_rounds = session.get("singles_rounds", total_rounds - 2 if total_rounds > 2 else 4)
    in_coop_phase = is_standard_training and round_num is not None and round_num > singles_rounds
    if in_coop_phase or modus == "Koop 2vs2 (Up & Down)": return ["Kaiser B1", "Board 2"]
    return ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"][:boards_count]

def is_session_completed(sess):
    if sess.get("is_liga"):
        from_conf = get_liga_config(sess)
        total_matches = sum([len(r) for r in from_conf])
        played = len([k for k, v in sess.get("results", {}).items() if v.get("played")])
        return played == total_matches
    if sess.get("is_wettkampf"):
        played = len([k for k, v in sess.get("results", {}).items() if v.get("played")])
        return played == 10
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    for r in range(1, total_rounds + 1):
        boards_in_round = get_boards_list(sess, r)
        for b_name in boards_in_round:
            match_info = res.get((r, b_name))
            if not match_info or not match_info.get("winner"): return False
    return True

def check_session_completion_time(sess):
    if sess.get("is_liga") or sess.get("is_wettkampf"): return
    if is_session_completed(sess):
        if not sess.get("end_time"): sess["end_time"] = get_local_time_str()
    else:
        if "end_time" in sess: sess["end_time"] = None

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

def import_liga_spielplan():
    plan = [
        ("15.09.2026", "FSV Wehringen", "DC Bavarian Knights Hurlach III"),
        ("21.09.2026", "SV Bergheim Darts III", "FSV Wehringen"),
        ("29.09.2026", "FSV Wehringen", "SC Eurasburg"),
        ("12.10.2026", "Rabbits Lechfeld II", "FSV Wehringen"),
        ("27.10.2026", "FSV Wehringen", "SC Eurasburg II"),
        ("10.11.2026", "FSV Wehringen", "DJK Lechhausen VII"),
        ("23.11.2026", "SV Bergheim Darts II", "FSV Wehringen"),
        ("01.12.2026", "FSV Wehringen", "TSV Schmiechen"),
        ("17.12.2026", "TSV Schmiechen II", "FSV Wehringen"),
        ("12.01.2027", "FSV Wehringen", "Dartfreunde Umbach III"),
        ("04.02.2027", "DC Bavarian Knights Hurlach III", "FSV Wehringen"),
        ("16.02.2027", "FSV Wehringen", "SV Bergheim Darts III"),
        ("01.03.2027", "SC Eurasburg", "FSV Wehringen"),
        ("09.03.2027", "FSV Wehringen", "Rabbits Lechfeld II"),
        ("17.03.2027", "SC Eurasburg II", "FSV Wehringen"),
        ("07.04.2027", "DJK Lechhausen VII", "FSV Wehringen"),
        ("13.04.2027", "FSV Wehringen", "SV Bergheim Darts II"),
        ("27.04.2027", "TSV Schmiechen", "FSV Wehringen"),
        ("11.05.2027", "FSV Wehringen", "TSV Schmiechen II"),
        ("31.05.2027", "Dartfreunde Umbach III", "FSV Wehringen")
    ]
    changed = False
    for datum, heim, gast in plan:
        exists = any(s.get("is_wettkampf") and s.get("datum") == datum for s in st.session_state.sessions_list)
        if not exists:
            max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "W-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
            new_session = {"id": f"W-{max_id + 1}", "datum": datum, "is_wettkampf": True, "heim_team": heim, "gast_team": gast, "is_heimspiel": heim == "FSV Wehringen", "auf_heim": {}, "auf_gast": {}, "results": {}, "is_locked": False}
            st.session_state.sessions_list.append(new_session)
            changed = True
    if changed: smart_sync_and_save(st.session_state.sessions_list)

def get_running_score_up_to(res, all_keys, target_key):
    h_score, g_score = 0, 0
    for k in all_keys:
        m_data = res.get(k, {})
        if m_data.get("played"):
            lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
            if lh > lg: h_score += 1
            elif lg > lh: g_score += 1
        if k == target_key: break
    return f"{h_score}:{g_score}"

def get_max_boards_for_players(num_players):
    if num_players < 2: return 0
    return num_players // 2

def get_or_create_teams(session, all_training_sessions):
    if "coop_teams" in session and session["coop_teams"]: return session["coop_teams"]
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
                    if len(parts) == 2 and "-" not in t: prev_pairs.add(frozenset([parts[0].strip(), parts[1].strip()]))
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
                        if p_clean and p_clean != "-": prev_resting_players.add(p_clean)
            else:
                prev_spiel = [p for p in prev_sess.get("spieler", []) if p != "-"]
                for i in range(0, len(prev_spiel)-1, 2): prev_pairs.add(frozenset([prev_spiel[i], prev_spiel[i+1]]))
    except: pass
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
        if len(shuffled) % 2 != 0: current_teams.append(f"{shuffled[-1]} & -")
        best_teams = current_teams
        if not has_forbidden: break
    if len(best_teams) % 2 != 0 and prev_resting_players:
        for _ in range(len(best_teams)):
            t0_players = [p.strip() for p in best_teams[0].split("&") if p.strip() != "-"]
            has_resting = any(p in prev_resting_players for p in t0_players)
            if not has_resting or len(best_teams) == 1: break
            best_teams = best_teams[1:] + [best_teams[0]]
    session["coop_teams"] = best_teams
    return best_teams

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
        all_sessions = sorted([s for s in st.session_state.sessions_list if not s.get("is_liga") and not s.get("is_wettkampf")], key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
        try: s_idx = all_sessions.index(session)
        except: s_idx = 0
        prev_sess = None
        if s_idx + 1 < len(all_sessions): prev_sess = all_sessions[s_idx + 1]
        if prev_sess and "results" in prev_sess:
            prev_total = prev_sess.get("total_rounds", 4)
            prev_modus = prev_sess.get("modus", "Up & Down")
            prev_is_std = (prev_modus == "Standard-Training (Einzel + Coop)")
            prev_singles = prev_sess.get("singles_rounds", prev_total - 2 if prev_is_std and prev_total > 2 else prev_total)
            target_r = prev_singles if prev_is_std else prev_total
            prev_boards = get_boards_list(prev_sess, target_r)
            prev_results = prev_sess.get("results", {})
            w, l = {}, {}
            for pb in prev_boards:
                match_inf = prev_results.get((target_r, pb))
                if match_inf and match_inf.get("winner"):
                    w[pb], l[pb] = match_inf["winner"], match_inf["loser"]
                else: w[pb], l[pb] = "-", "-"
            prev_players_top_to_bottom = []
            for b_idx_prev, pb in enumerate(prev_boards):
                if b_idx_prev == 0:
                    platz1 = w.get("Kaiser B1", "-")
                    platz2 = w.get("Board 2", "-") if len(prev_boards) > 1 else l.get("Kaiser B1", "-")
                else:
                    platz1 = l.get(prev_boards[b_idx_prev-1], "-")
                    platz2 = w.get(prev_boards[b_idx_prev+1], "-") if b_idx_prev+1 < len(prev_boards) else l.get(prev_boards[b_idx_prev], "-")
                if platz1 != "-" and platz1 not in prev_players_top_to_bottom: prev_players_top_to_bottom.append(platz1)
                if platz2 != "-" and platz2 not in prev_players_top_to_bottom: prev_players_top_to_bottom.append(platz2)
            prev_players_bottom_to_top = list(reversed(prev_players_top_to_bottom))
            returning_players = [p for p in prev_players_bottom_to_top if p in spieler]
            new_players = [p for p in spieler if p not in prev_players_top_to_bottom]
            ordered_players = new_players + returning_players
            for p in spieler:
                if p not in ordered_players: ordered_players.append(p)
            spieler = ordered_players[:len(spieler)]

    pairs = []
    if is_2v2 or in_coop_phase:
        all_tr = [s for s in st.session_state.sessions_list if not s.get("is_liga") and not s.get("is_wettkampf")]
        teams = get_or_create_teams(session, all_tr)
        n_teams = len(teams)
        rel_round = (round_num - singles_rounds) if in_coop_phase else round_num
        resting_team_idx = (rel_round - 1) % n_teams if n_teams % 2 != 0 else -1
        active_teams = [t for i, t in enumerate(teams) if i != resting_team_idx]
        if rel_round == 1:
            if b_idx < len(active_teams) // 2:
                return [active_teams[b_idx * 2], active_teams[b_idx * 2 + 1] if b_idx * 2 + 1 < len(active_teams) else "-"]
            else: return ["-", "-"]
        else:
            prev_r = round_num - 1
            res = session.get("results", {})
            w, l = {}, {}
            for b in boards:
                match_info = res.get((prev_r, b))
                if match_info and match_info.get("winner"): w[b], l[b] = match_info["winner"], match_info["loser"]
                else: w[b], l[b] = "-", "-"
            if b_idx == 0:
                top_w = w.get("Kaiser B1", "-")
                next_w = w.get("Board 2", "-")
                return [top_w if top_w != "-" else (active_teams[0] if active_teams else "-"), next_w if next_w != "-" else (active_teams[1] if len(active_teams) > 1 else "-")]
            elif b_idx == 1 and len(boards) > 1:
                top_l = l.get("Kaiser B1", "-")
                next_l = l.get("Board 2", "-")
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
            if match_info and match_info.get("winner"): w[b], l[b] = match_info["winner"], match_info["loser"]
            else: w[b], l[b] = "-", "-"
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
    heim, gast, datum = sess.get("heim_team", ""), sess.get("datum", "")
    c.drawString(410, 755, datum)
    c.drawString(100, 722, heim) 
    c.drawString(330, 722, gast)
    res = sess.get("results", {})
    auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
    t_size = sess.get("team_size", 4)
    if t_size == 12: y_coords_pdf = {f"m{i}": 650 - i*25 for i in range(1, 37)}
    elif t_size == 10: y_coords_pdf = {f"m{i}": 650 - i*28 for i in range(1, 31)}
    elif t_size == 8: y_coords_pdf = {f"m{i}": 630 - i*32 for i in range(1, 25)}
    elif t_size == 6: y_coords_pdf = {"m1": 615, "m2": 570, "m3": 525, "m4": 480, "m5": 435, "m6": 390, "m7": 345, "m8": 300, "m9": 255, "m10": 210, "m11": 165, "m12": 120, "m13": 80, "m14": 55, "m15": 30}
    else: y_coords_pdf = {"m1": 615, "m2": 570, "m3": 525, "m4": 480, "m5": 400, "m6": 355, "m7": 310, "m8": 265, "m9": 200, "m10": 155}
    
    x_name_heim, x_name_gast = 65, 315
    x_legs_heim, x_legs_gast = 225, 285
    x_180_heim, x_180_gast = 95, 340
    
    match_map = [match for round in get_liga_config(sess) for match in round]
    for m_key, label, h_key, g_key in match_map:
        if m_key in res and res[m_key].get("played"):
            m_data = res[m_key]
            y = y_coords_pdf.get(m_key, 500)
            
            val_h = m_data.get("s1", "")
            h_name = str(val_h if val_h and val_h.strip() not in ["", "-"] else auf_h.get(h_key, ""))
            
            val_g = m_data.get("s2", "")
            g_name = str(val_g if val_g and val_g.strip() not in ["", "-"] else auf_g.get(g_key, ""))
            
            c.drawString(x_name_heim, y, h_name)
            c.drawString(x_name_gast, y, g_name)
            c.drawString(x_legs_heim, y, str(m_data.get("lh", 0)))
            c.drawString(x_legs_gast, y, str(m_data.get("lg", 0)))
            y_sub = y - 12
            if m_data.get("180_h", 0) > 0: c.drawString(x_180_heim, y_sub, str(m_data.get("180_h", "")))
            if m_data.get("180_g", 0) > 0: c.drawString(x_180_gast, y_sub, str(m_data.get("180_g", "")))
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

def generate_calendar_pdf(wettkampf_sessions, min_d, max_d):
    import io
    import calendar
    from datetime import date
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    packet = io.BytesIO()
    doc = SimpleDocTemplate(packet, pagesize=landscape(A4), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(name='Title', parent=styles['Heading1'], fontSize=18, spaceAfter=15)
    day_style = ParagraphStyle(name='Day', fontSize=10, textColor=colors.black, spaceAfter=5)
    event_style_heim = ParagraphStyle(name='EvH', fontSize=8, textColor=colors.white, backColor=colors.HexColor('#2e7d32'), alignment=1, spaceBefore=2, spaceAfter=2)
    event_style_gast = ParagraphStyle(name='EvG', fontSize=8, textColor=colors.white, backColor=colors.HexColor('#d84315'), alignment=1, spaceBefore=2, spaceAfter=2)
    event_style_train = ParagraphStyle(name='EvT', fontSize=8, textColor=colors.white, backColor=colors.HexColor('#1976d2'), alignment=1, spaceBefore=2, spaceAfter=2)
    games_by_date = {}
    games_by_week = set()
    for s in wettkampf_sessions:
        try:
            d = datetime.strptime(s["datum"], "%d.%m.%Y").date()
            is_h = (s.get("heim_team", "") == "FSV Wehringen")
            gegner = s.get("gast_team") if is_h else s.get("heim_team")
            games_by_date[d] = {"heim": is_h, "gegner": gegner}
            games_by_week.add(d.isocalendar()[:2])
        except: pass
    curr_year, curr_month = min_d.year, min_d.month
    month_names = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
    days_of_week = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    while True:
        elements.append(Paragraph(f"{month_names[curr_month]} {curr_year}", title_style))
        data = [days_of_week]
        for week in calendar.monthcalendar(curr_year, curr_month):
            row = []
            for day in week:
                if day == 0: row.append("")
                else:
                    curr_date = date(curr_year, curr_month, day)
                    cell_content = [Paragraph(str(day), day_style)]
                    if curr_date in games_by_date:
                        g = games_by_date[curr_date]
                        if g["heim"]: cell_content.append(Paragraph(f"Heim vs<br/>{g['gegner']}", event_style_heim))
                        else: cell_content.append(Paragraph(f"Ausw. @<br/>{g['gegner']}", event_style_gast))
                    elif curr_date.weekday() == 1 and curr_date.isocalendar()[:2] not in games_by_week and min_d <= curr_date <= max_d:
                        cell_content.append(Paragraph("Training", event_style_train))
                    row.append(cell_content)
            data.append(row)
        t = Table(data, colWidths=[110] * 7)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey), ('ALIGN', (0, 0), (-1, -1), 'LEFT'), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), 0.5, colors.grey), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('BOTTOMPADDING', (0, 0), (-1, 0), 10), ('TOPPADDING', (0, 1), (-1, -1), 5), ('BOTTOMPADDING', (0, 1), (-1, -1), 5)]))
        for i in range(1, len(data)): t._argH[i] = 60
        elements.append(t)
        elements.append(Spacer(1, 30))
        if curr_year == max_d.year and curr_month == max_d.month: break
        curr_month += 1
        if curr_month > 12: curr_month, curr_year = 1, curr_year + 1
    doc.build(elements)
    return packet.getvalue()

def parse_doppel(val):
    if not val: return "", ""
    if "&" in val:
        parts = [p.strip() for p in val.split("&")]
        return parts[0] if len(parts) > 0 else "", parts[1] if len(parts) > 1 else ""
    return str(val).strip(), ""

def format_doppel(p1, p2):
    p1_c = str(p1).strip() if p1 and str(p1) != "-" else ""
    p2_c = str(p2).strip() if p2 and str(p2) != "-" else ""
    if p1_c and p2_c: return f"{p1_c} & {p2_c}"
    if p1_c: return p1_c
    if p2_c: return p2_c
    return "-"

# --- DIALOG FUNKTIONEN ---

@st.dialog("📆 Steelers Saison-Kalender", width="large")
def open_saison_kalender_dialog():
    import calendar
    wettkampf_sessions = [s for s in st.session_state.sessions_list if s.get("is_wettkampf")]
    d_list = []
    for s in wettkampf_sessions:
        try: d_list.append(datetime.strptime(s["datum"], "%d.%m.%Y").date())
        except: pass
    if not d_list:
        st.info("Noch keine Liga-Spiele vorhanden. Bitte Spielplan importieren.")
        if st.button("Schließen"): st.rerun()
        return
    min_d, max_d = min(d_list), max(d_list)
    ics_lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Wehringer Steelers//DE"]
    def add_ics_event(dt, title):
        ds = dt.strftime("%Y%m%d")
        ics_lines.extend(["BEGIN:VEVENT", f"DTSTART;VALUE=DATE:{ds}", f"SUMMARY:{title}", "END:VEVENT"])
    html_blocks = ["<div style='color: white;'>"]
    html_blocks.append("""<style>
    .c-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; margin-bottom: 20px;}
    .c-head { text-align: center; font-weight: bold; background: #333; padding: 4px; border-radius: 4px; font-size:0.85em;}
    .c-day { border: 1px solid #444; border-radius: 4px; min-height: 70px; padding: 4px; font-size: 0.8em; background: #1e1e1e;}
    .c-empty { border: none; background: transparent; }
    .e-h { background: #2e7d32; color: #fff; padding: 2px; border-radius: 2px; margin-top: 2px; font-weight:bold; text-align:center;}
    .e-g { background: #d84315; color: #fff; padding: 2px; border-radius: 2px; margin-top: 2px; font-weight:bold; text-align:center;}
    .e-t { background: #1976d2; color: #fff; padding: 2px; border-radius: 2px; margin-top: 2px; text-align:center;}
    </style>""")
    days_of_week = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    month_names = ["", "Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
    games_by_date = {}
    games_by_week = set()
    for s in wettkampf_sessions:
        try:
            d = datetime.strptime(s["datum"], "%d.%m.%Y").date()
            is_h = (s.get("heim_team", "") == "FSV Wehringen")
            gegner = s.get("gast_team") if is_h else s.get("heim_team")
            games_by_date[d] = {"heim": is_h, "gegner": gegner}
            games_by_week.add(d.isocalendar()[:2])
        except: pass
    curr_year, curr_month = min_d.year, min_d.month
    while True:
        html_blocks.append(f"<h4 style='margin-bottom:10px; margin-top:20px; color:#fff;'>{month_names[curr_month]} {curr_year}</h4><div class='c-grid'>")
        for dw in days_of_week: html_blocks.append(f"<div class='c-head'>{dw}</div>")
        for week in calendar.monthcalendar(curr_year, curr_month):
            for day in week:
                if day == 0: html_blocks.append("<div class='c-day c-empty'></div>")
                else:
                    curr_date = date(curr_year, curr_month, day)
                    content = f"<div style='color:#aaa; margin-bottom:2px;'>{day}</div>"
                    if curr_date in games_by_date:
                        g = games_by_date[curr_date]
                        if g["heim"]:
                            content += f"<div class='e-h'>🏠 Heim<br><span style='font-size:0.8em; font-weight:normal;'>vs {g['gegner']}</span></div>"
                            add_ics_event(curr_date, f"🎯 Heimspiel vs {g['gegner']}")
                        else:
                            content += f"<div class='e-g'>🚌 Auswärts<br><span style='font-size:0.8em; font-weight:normal;'>@ {g['gegner']}</span></div>"
                            add_ics_event(curr_date, f"🎯 Auswärts @ {g['gegner']}")
                    elif curr_date.weekday() == 1 and curr_date.isocalendar()[:2] not in games_by_week and min_d <= curr_date <= max_d:
                        content += "<div class='e-t'>🎯 Training</div>"
                        add_ics_event(curr_date, "🎯 Steelers Teamtraining")
                    html_blocks.append(f"<div class='c-day'>{content}</div>")
        html_blocks.append("</div>")
        if curr_year == max_d.year and curr_month == max_d.month: break
        curr_month += 1
        if curr_month > 12: curr_month, curr_year = 1, curr_year + 1
    html_blocks.append("</div>")
    ics_lines.append("END:VCALENDAR")
    st.markdown("".join(html_blocks), unsafe_allow_html=True)
    st.divider()
    col_pdf, col_ics = st.columns(2)
    with col_pdf:
        try:
            pdf_bytes = generate_calendar_pdf(wettkampf_sessions, min_d, max_d)
            st.download_button("📥 Kalender als PDF (A4 Querformat)", data=pdf_bytes, file_name="steelers_saison_kalender.pdf", mime="application/pdf", type="primary", use_container_width=True)
        except Exception as e: st.error(f"PDF konnte nicht erstellt werden: {e}")
    with col_ics:
        st.download_button("📥 Kalender exportieren (.ics)", data="\r\n".join(ics_lines), file_name="steelers_saison.ics", mime="text/calendar", use_container_width=True)
    if st.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("➕ Neues Freundschaftsspiel starten", width="large")
def open_new_liga_match_dialog():
    st.write("Erstelle hier ein neues Freundschaftsspiel.")
    match_type = st.radio("Modus-Auswahl", ["🏆 Standard Liga-Spiel (4er-Team, 2 Boards)", "⚙️ Freies Spiel auf Liga-Basis (wählbare Teamgröße & Boards)"])
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum des Spiels", date.today())
    heim_team = c2.text_input("Heimmannschaft", value="Wehringer Steelers")
    gast_team = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    if "Freies Spiel" in match_type:
        team_size = st.selectbox("Team-Größe", [6, 8, 10, 12], format_func=lambda x: f"{x}er-Team")
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
            new_session = {"id": f"L-{max_id + 1}", "datum": session_datum.strftime("%d.%m.%Y"), "is_liga": True, "team_size": team_size, "boards_count": b_count, "heim_team": heim_team.strip(), "gast_team": gast_team.strip(), "liga_boards": selected_boards, "auf_heim": {}, "auf_gast": {}, "results": {}, "is_locked": False}
            st.session_state.sessions_list.append(new_session)
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("⚙️ Freundschaftsspiel bearbeiten")
def open_edit_liga_session_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
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
            sess.update({"datum": session_datum.strftime("%d.%m.%Y"), "heim_team": heim_team.strip(), "gast_team": gast_team.strip(), "liga_boards": new_boards})
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
    for i in range(t_size): inputs.append(st.text_input(f"Position {i+1}", key=f"auf_{session_id}_{is_heim}_{i}"))
    if st.button("Speichern", type="primary", use_container_width=True):
        if all(x.strip() for x in inputs):
            update_dict = {}
            for i, val in enumerate(inputs):
                key = f"h{i+1}" if is_heim else f"g{i+1}"
                update_dict[key] = val.strip()
            if is_heim: sess["auf_heim"].update(update_dict)
            else: sess["auf_gast"].update(update_dict)
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()
        else: st.error(f"Bitte alle {t_size} Positionen eintragen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    team_name = sess.get("heim_team") if is_heim else sess.get("gast_team")
    t_size = sess.get("team_size", 4)
    num_doubles = t_size // 2
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
        seen, duplicates = set(), set()
        for player in all_selected:
            if player in seen: duplicates.add(player)
            seen.add(player)
        if any(not x for x in all_selected): st.error("🚨 Bitte alle Spieler für die Doppel ausfüllen!")
        elif duplicates:
            dup_names = ", ".join([f"'{d}'" for d in duplicates])
            st.error(f"🚨 Fehler: Der Spieler {dup_names} steht in mehreren Feldern! Jeder Spieler darf nur 1x in den Doppel aufgestellt werden.")
        else:
            update_dict = {}
            for d_idx, (p1, p2) in enumerate(doubles_data):
                key = f"hd{d_idx+1}" if is_heim else f"gd{d_idx+1}"
                update_dict[key] = format_doppel(p1, p2)
            if is_heim: sess["auf_heim"].update(update_dict)
            else: sess["auf_gast"].update(update_dict)
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
            if is_heim: sess["auf_heim"][p_key] = new_name.strip()
            else: sess["auf_gast"][p_key] = new_name.strip()
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
    if not is_valid: st.error("🚨 Best of 5: Ein Spieler muss exakt 3 Legs zum Sieg haben!")
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Speichern", type="primary", use_container_width=True, disabled=not is_valid):
            res[m_key] = {"lh": lh, "lg": lg, "played": True, "180_h": e180_h, "180_g": e180_g}
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
        m_data = res.get(m_key, {})
        is_played = m_data.get("played", False)
        val_h = m_data.get("s1", "")
        p_heim = val_h if is_played and val_h and val_h.strip() not in ["", "-"] else auf_h.get(h_key, "-")
        if not p_heim: p_heim = "-"
        val_g = m_data.get("s2", "")
        p_gast = val_g if is_played and val_g and val_g.strip() not in ["", "-"] else auf_g.get(g_key, "-")
        if not p_gast: p_gast = "-"
        
        with st.expander(f"{label}: {p_heim} vs {p_gast}", expanded=False):
            c_lh, c_vs, c_lg = st.columns([2, 1, 2])
            lh = c_lh.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"blh_{session_id}_{m_key}")
            c_vs.markdown("<div style='text-align: center; padding-top: 30px;'>:</div>", unsafe_allow_html=True)
            lg = c_lg.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"blg_{session_id}_{m_key}")
            is_match_valid = (lh == 0 and lg == 0) or (lh == 3 and lg < 3) or (lg == 3 and lh < 3)
            if not is_match_valid:
                st.error(f"🚨 Ungültig! Best of 5 erfordert exakt 3 Legs für den Sieger.")
                all_valid = False
            res[m_key] = {"s1": p_heim, "s2": p_gast, "lh": lh, "lg": lg, "played": True if (lh>0 or lg>0) else False, "180_h": m_data.get("180_h", 0), "180_g": m_data.get("180_g", 0)}
    st.divider()
    is_locked = sess.get("is_locked", False)
    if not is_locked: lock_spiel = st.checkbox("🔒 Spiel endgültig abschließen & ins Archiv verschieben", value=False)
    else:
        lock_spiel = True
        st.info("Dieses Spiel ist bereits offiziell abgeschlossen.")
    if st.button("💾 Speichern & Schließen", type="primary", use_container_width=True, disabled=not all_valid):
        sess["is_locked"] = lock_spiel
        sess["results"] = res
        st.session_state.sessions_list[real_idx] = sess
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("🏆 Neuen Liga-Spieltag manuell erfassen", width="large")
def open_new_wettkampf_dialog():
    c1, c2 = st.columns(2)
    session_datum = c1.date_input("Datum des Spieltags", date.today(), key="wk_datum")
    is_heimspiel = c2.checkbox("🏠 Heimspiel (FSV Wehringen ist Team 1)", value=True)
    gegner = st.text_input("Gegnerische Mannschaft", placeholder="z.B. DC Irgendwas")
    cb1, cb2 = st.columns(2)
    with cb1:
        if st.button("Abbrechen", use_container_width=True, key="wk_cancel"): st.rerun()
    with cb2:
        if st.button("Spieltag anlegen", type="primary", use_container_width=True, key="wk_save"):
            if not gegner.strip(): st.error("Bitte Gegner eintragen!")
            else:
                max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "W-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
                heim_team = "FSV Wehringen" if is_heimspiel else gegner.strip()
                gast_team = gegner.strip() if is_heimspiel else "FSV Wehringen"
                new_session = {"id": f"W-{max_id + 1}", "datum": session_datum.strftime("%d.%m.%Y"), "is_wettkampf": True, "heim_team": heim_team, "gast_team": gast_team, "is_heimspiel": is_heimspiel, "auf_heim": {}, "auf_gast": {}, "results": {}, "is_locked": False}
                st.session_state.sessions_list.append(new_session)
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()

@st.dialog("⚡ Blitz-Erfassung: Liga-Spielbericht", width="large")
def open_wettkampf_blitz_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    st.write("### 📸 Abtipp-Hilfe & Beleg-Upload")
    st.info("Lade ein Foto hoch. Es wird komprimiert dauerhaft als Beleg gespeichert und dient dir jetzt als Abtipp-Hilfe.")
    uploaded_file = st.file_uploader("Foto wählen", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
    if uploaded_file is not None:
        st.image(uploaded_file, use_container_width=True)
        try:
            img = Image.open(uploaded_file)
            img.thumbnail((800, 800))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=60)
            sess["image_b64"] = base64.b64encode(buffer.getvalue()).decode("utf-8")
        except Exception as e: st.error(f"Bild konnte nicht komprimiert werden: {e}")
    elif sess.get("image_b64"):
        st.success("✅ Ein Spielbericht liegt bereits als Foto im Archiv.")
    st.divider()
    
    st.write("### 🎯 Aufstellung & Ergebnisse eintragen")
    auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
    res = sess.setdefault("results", {})
    is_heimspiel = sess.get("is_heimspiel", True)
    kader_list = ["-"] + sorted(kader)
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Heim:** {sess['heim_team']}")
        for i in range(1, 5): 
            val = auf_h.get(f"h{i}", "")
            if is_heimspiel:
                idx = kader_list.index(val) if val in kader_list else 0
                auf_h[f"h{i}"] = st.selectbox(f"Heim Pos {i}", kader_list, index=idx, key=f"wk_h{i}_{sess['id']}")
            else:
                auf_h[f"h{i}"] = st.text_input(f"Heim Pos {i}", val, key=f"wk_h{i}_{sess['id']}")
                
        st.markdown("**Heim Doppel 1**")
        hd1_p1_val, hd1_p2_val = parse_doppel(auf_h.get("hd1", ""))
        c_hd1a, c_hd1b = st.columns(2)
        if is_heimspiel:
            hd1_p1 = c_hd1a.selectbox("Spieler 1", kader_list, index=kader_list.index(hd1_p1_val) if hd1_p1_val in kader_list else 0, key=f"wk_hd1a_{sess['id']}")
            hd1_p2 = c_hd1b.selectbox("Spieler 2", kader_list, index=kader_list.index(hd1_p2_val) if hd1_p2_val in kader_list else 0, key=f"wk_hd1b_{sess['id']}")
        else:
            hd1_p1 = c_hd1a.text_input("Spieler 1", hd1_p1_val, key=f"wk_hd1a_{sess['id']}")
            hd1_p2 = c_hd1b.text_input("Spieler 2", hd1_p2_val, key=f"wk_hd1b_{sess['id']}")
        auf_h["hd1"] = format_doppel(hd1_p1, hd1_p2)

        st.markdown("**Heim Doppel 2**")
        hd2_p1_val, hd2_p2_val = parse_doppel(auf_h.get("hd2", ""))
        c_hd2a, c_hd2b = st.columns(2)
        if is_heimspiel:
            hd2_p1 = c_hd2a.selectbox("Spieler 1", kader_list, index=kader_list.index(hd2_p1_val) if hd2_p1_val in kader_list else 0, key=f"wk_hd2a_{sess['id']}")
            hd2_p2 = c_hd2b.selectbox("Spieler 2", kader_list, index=kader_list.index(hd2_p2_val) if hd2_p2_val in kader_list else 0, key=f"wk_hd2b_{sess['id']}")
        else:
            hd2_p1 = c_hd2a.text_input("Spieler 1", hd2_p1_val, key=f"wk_hd2a_{sess['id']}")
            hd2_p2 = c_hd2b.text_input("Spieler 2", hd2_p2_val, key=f"wk_hd2b_{sess['id']}")
        auf_h["hd2"] = format_doppel(hd2_p1, hd2_p2)

    with c2:
        st.markdown(f"**Gast:** {sess['gast_team']}")
        for i in range(1, 5): 
            val = auf_g.get(f"g{i}", "")
            if not is_heimspiel:
                idx = kader_list.index(val) if val in kader_list else 0
                auf_g[f"g{i}"] = st.selectbox(f"Gast Pos {i}", kader_list, index=idx, key=f"wk_g{i}_{sess['id']}")
            else:
                auf_g[f"g{i}"] = st.text_input(f"Gast Pos {i}", val, key=f"wk_g{i}_{sess['id']}")
                
        st.markdown("**Gast Doppel 1**")
        gd1_p1_val, gd1_p2_val = parse_doppel(auf_g.get("gd1", ""))
        c_gd1a, c_gd1b = st.columns(2)
        if not is_heimspiel:
            gd1_p1 = c_gd1a.selectbox("Spieler 1", kader_list, index=kader_list.index(gd1_p1_val) if gd1_p1_val in kader_list else 0, key=f"wk_gd1a_{sess['id']}")
            gd1_p2 = c_gd1b.selectbox("Spieler 2", kader_list, index=kader_list.index(gd1_p2_val) if gd1_p2_val in kader_list else 0, key=f"wk_gd1b_{sess['id']}")
        else:
            gd1_p1 = c_gd1a.text_input("Spieler 1", gd1_p1_val, key=f"wk_gd1a_{sess['id']}")
            gd1_p2 = c_gd1b.text_input("Spieler 2", gd1_p2_val, key=f"wk_gd1b_{sess['id']}")
        auf_g["gd1"] = format_doppel(gd1_p1, gd1_p2)

        st.markdown("**Gast Doppel 2**")
        gd2_p1_val, gd2_p2_val = parse_doppel(auf_g.get("gd2", ""))
        c_gd2a, c_gd2b = st.columns(2)
        if not is_heimspiel:
            gd2_p1 = c_gd2a.selectbox("Spieler 1", kader_list, index=kader_list.index(gd2_p1_val) if gd2_p1_val in kader_list else 0, key=f"wk_gd2a_{sess['id']}")
            gd2_p2 = c_gd2b.selectbox("Spieler 2", kader_list, index=kader_list.index(gd2_p2_val) if gd2_p2_val in kader_list else 0, key=f"wk_gd2b_{sess['id']}")
        else:
            gd2_p1 = c_gd2a.text_input("Spieler 1", gd2_p1_val, key=f"wk_gd2a_{sess['id']}")
            gd2_p2 = c_gd2b.text_input("Spieler 2", gd2_p2_val, key=f"wk_gd2b_{sess['id']}")
        auf_g["gd2"] = format_doppel(gd2_p1, gd2_p2)

    st.divider()
    st.write("### ⚔️ Match-Ergebnisse & Auswechslungen")
    st.caption("Standardmäßig werden die Spieler aus der Aufstellung übernommen. Aktiviere '🔄 Auswechseln', um einen Spieler zu ersetzen!")
    match_plan = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"),("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4"),("m5", "Kreuz 1", "h1", "g2"), ("m6", "Kreuz 2", "h2", "g1"),("m7", "Kreuz 3", "h3", "g4"), ("m8", "Kreuz 4", "h4", "g3"),("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
    all_valid = True
    
    for m_key, label, h_key, g_key in match_plan:
        m_data = res.get(m_key, {})
        is_played = m_data.get("played", False)
        
        val_h = m_data.get("s1", "")
        def_h = val_h if is_played and val_h and val_h.strip() not in ["", "-"] else auf_h.get(h_key, "-")
        if not def_h: def_h = "-"
        
        val_g = m_data.get("s2", "")
        def_g = val_g if is_played and val_g and val_g.strip() not in ["", "-"] else auf_g.get(g_key, "-")
        if not def_g: def_g = "-"
        
        with st.expander(f"{label}: {def_h} vs {def_g}", expanded=False):
            is_doppel = "Doppel" in label
            c_name1, c_name2 = st.columns(2)
            
            with c_name1:
                if st.checkbox(f"🔄 Auswechseln (Heim)", key=f"sub_h_check_{m_key}_{sess['id']}"):
                    if is_heimspiel:
                        if is_doppel:
                            p_a, p_b = parse_doppel(def_h)
                            s1_a = st.selectbox("Heim Spieler 1", kader_list, index=kader_list.index(p_a) if p_a in kader_list else 0, key=f"s1a_{m_key}_{sess['id']}")
                            s1_b = st.selectbox("Heim Spieler 2", kader_list, index=kader_list.index(p_b) if p_b in kader_list else 0, key=f"s1b_{m_key}_{sess['id']}")
                            s1 = f"{s1_a} & {s1_b}"
                        else:
                            s1 = st.selectbox("Heim Spieler", kader_list, index=kader_list.index(def_h) if def_h in kader_list else 0, key=f"s1_{m_key}_{sess['id']}")
                    else:
                        if is_doppel:
                            p_a, p_b = parse_doppel(def_h)
                            s1_a = st.text_input("Heim Spieler 1", p_a, key=f"s1a_{m_key}_{sess['id']}")
                            s1_b = st.text_input("Heim Spieler 2", p_b, key=f"s1b_{m_key}_{sess['id']}")
                            s1 = f"{s1_a} & {s1_b}"
                        else:
                            s1 = st.text_input("Heim Spieler", def_h, key=f"s1_{m_key}_{sess['id']}")
                else:
                    st.markdown(f"**Heim:** {def_h}")
                    s1 = def_h

            with c_name2:
                if st.checkbox(f"🔄 Auswechseln (Gast)", key=f"sub_g_check_{m_key}_{sess['id']}"):
                    if not is_heimspiel:
                        if is_doppel:
                            p_a, p_b = parse_doppel(def_g)
                            s2_a = st.selectbox("Gast Spieler 1", kader_list, index=kader_list.index(p_a) if p_a in kader_list else 0, key=f"s2a_{m_key}_{sess['id']}")
                            s2_b = st.selectbox("Gast Spieler 2", kader_list, index=kader_list.index(p_b) if p_b in kader_list else 0, key=f"s2b_{m_key}_{sess['id']}")
                            s2 = f"{s2_a} & {s2_b}"
                        else:
                            s2 = st.selectbox("Gast Spieler", kader_list, index=kader_list.index(def_g) if def_g in kader_list else 0, key=f"s2_{m_key}_{sess['id']}")
                    else:
                        if is_doppel:
                            p_a, p_b = parse_doppel(def_g)
                            s2_a = st.text_input("Gast Spieler 1", p_a, key=f"s2a_{m_key}_{sess['id']}")
                            s2_b = st.text_input("Gast Spieler 2", p_b, key=f"s2b_{m_key}_{sess['id']}")
                            s2 = f"{s2_a} & {s2_b}"
                        else:
                            s2 = st.text_input("Gast Spieler", def_g, key=f"s2_{m_key}_{sess['id']}")
                else:
                    st.markdown(f"**Gast:** {def_g}")
                    s2 = def_g
                    
            st.write("")
            c_lh, c_vs, c_lg = st.columns([2, 1, 2])
            lh = c_lh.number_input("Legs Heim", 0, 3, m_data.get("lh", 0), key=f"wk_lh_{m_key}_{sess['id']}")
            c_vs.markdown("<div style='text-align: center; padding-top: 30px;'>:</div>", unsafe_allow_html=True)
            lg = c_lg.number_input("Legs Gast", 0, 3, m_data.get("lg", 0), key=f"wk_lg_{m_key}_{sess['id']}")
            c_stats1, c_stats2 = st.columns(2)
            
            ind_180_dict = m_data.get("ind_180_h", {})
            if is_heimspiel and is_doppel:
                p_a, p_b = parse_doppel(s1)
                h180_a = c_stats1.number_input(f"180er ({p_a})", 0, 10, ind_180_dict.get(p_a, 0), key=f"180ha_{m_key}_{sess['id']}")
                h180_b = c_stats1.number_input(f"180er ({p_b})", 0, 10, ind_180_dict.get(p_b, 0), key=f"180hb_{m_key}_{sess['id']}")
                h180 = h180_a + h180_b
                ind_180_h = {p_a: h180_a, p_b: h180_b}
            else:
                h180 = c_stats1.number_input("180er Heim", 0, 10, m_data.get("180_h", 0), key=f"wk_180h_{m_key}_{sess['id']}")
                ind_180_h = {s1: h180}
                
            h_hf = c_stats1.number_input("High Finish Heim (>99)", 0, 170, m_data.get("hf_h", 0), key=f"wk_hfh_{m_key}_{sess['id']}")
            h_sl = c_stats1.number_input("Short Leg Heim (<19)", 0, 18, m_data.get("sl_h", 0), key=f"wk_slh_{m_key}_{sess['id']}")
            
            ind_180_dict_g = m_data.get("ind_180_g", {})
            if not is_heimspiel and is_doppel:
                p_a, p_b = parse_doppel(s2)
                g180_a = c_stats2.number_input(f"180er ({p_a})", 0, 10, ind_180_dict_g.get(p_a, 0), key=f"180ga_{m_key}_{sess['id']}")
                g180_b = c_stats2.number_input(f"180er ({p_b})", 0, 10, ind_180_dict_g.get(p_b, 0), key=f"180gb_{m_key}_{sess['id']}")
                g180 = g180_a + g180_b
                ind_180_g = {p_a: g180_a, p_b: g180_b}
            else:
                g180 = c_stats2.number_input("180er Gast", 0, 10, m_data.get("180_g", 0), key=f"wk_180g_{m_key}_{sess['id']}")
                ind_180_g = {s2: g180}
                
            g_hf = c_stats2.number_input("High Finish Gast (>99)", 0, 170, m_data.get("hf_g", 0), key=f"wk_hfg_{m_key}_{sess['id']}")
            g_sl = c_stats2.number_input("Short Leg Gast (<19)", 0, 18, m_data.get("sl_g", 0), key=f"wk_slg_{m_key}_{sess['id']}")
            is_played = (lh > 0 or lg > 0)
            if is_played and not ((lh == 3 and lg < 3) or (lg == 3 and lh < 3)):
                st.error("🚨 Best of 5: Ein Spieler muss exakt 3 Legs haben!")
                all_valid = False
            res[m_key] = {"s1": s1, "s2": s2, "lh": lh, "lg": lg, "played": is_played, "180_h": h180, "180_g": g180, "ind_180_h": ind_180_h, "ind_180_g": ind_180_g, "hf_h": h_hf, "hf_g": g_hf, "sl_h": h_sl, "sl_g": g_sl}
    st.divider()
    is_locked = sess.get("is_locked", False)
    lock_spiel = st.checkbox("🔒 Spieltag abschließen (Wertung endgültig speichern)", value=is_locked, key=f"wk_lock_{sess['id']}")
    if st.button("💾 Speichern & Schließen", type="primary", use_container_width=True, disabled=not all_valid):
        sess["auf_heim"] = auf_h
        sess["auf_gast"] = auf_g
        sess["is_locked"] = lock_spiel
        sess["results"] = res
        st.session_state.sessions_list[real_idx] = sess
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("📊 Liga-Spielbericht", width="large")
def open_wettkampf_view_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    st.write(f"### {sess.get('heim_team')} vs. {sess.get('gast_team')}")
    st.caption(f"Datum: {sess.get('datum')} | Status: Abgeschlossen")
    res = sess.get("results", {})
    sets_h, sets_g, legs_h, legs_g = 0, 0, 0, 0
    for m_data in res.values():
        if m_data.get("played"):
            lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
            legs_h += lh; legs_g += lg
            if lh > lg: sets_h += 1
            elif lg > lh: sets_g += 1
    st.markdown(f"#### Endstand: {sets_h} : {sets_g} Sets ({legs_h} : {legs_g} Legs)")
    st.divider()
    match_plan = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"), ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4"), ("m5", "Kreuz 1", "h1", "g2"), ("m6", "Kreuz 2", "h2", "g1"), ("m7", "Kreuz 3", "h3", "g4"), ("m8", "Kreuz 4", "h4", "g3"), ("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
    for m_key, label, h_key, g_key in match_plan:
        m_data = res.get(m_key, {})
        if m_data.get("played"):
            s1, s2 = m_data.get("s1", "-"), m_data.get("s2", "-")
            lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
            hl_h = []
            if m_data.get("180_h", 0) > 0: hl_h.append(f"{m_data['180_h']}x 180")
            if m_data.get("hf_h", 0) >= 100: hl_h.append(f"HF {m_data['hf_h']}")
            if m_data.get("sl_h", 0) > 0 and m_data.get("sl_h", 0) <= 18: hl_h.append(f"SL {m_data['sl_h']}")
            hl_g = []
            if m_data.get("180_g", 0) > 0: hl_g.append(f"{m_data['180_g']}x 180")
            if m_data.get("hf_g", 0) >= 100: hl_g.append(f"HF {m_data['hf_g']}")
            if m_data.get("sl_g", 0) > 0 and m_data.get("sl_g", 0) <= 18: hl_g.append(f"SL {m_data['sl_g']}")
            h_str = f"*{', '.join(hl_h)}*" if hl_h else ""
            g_str = f"*{', '.join(hl_g)}*" if hl_g else ""
            ind_180_h = m_data.get("ind_180_h", {})
            if ind_180_h and "Doppel" in label:
                ind_h_str = [f"{p}: {v}x 180" for p, v in ind_180_h.items() if v > 0]
                if ind_h_str: h_str += f" ({', '.join(ind_h_str)})"
            ind_180_g = m_data.get("ind_180_g", {})
            if ind_180_g and "Doppel" in label:
                ind_g_str = [f"{p}: {v}x 180" for p, v in ind_180_g.items() if v > 0]
                if ind_g_str: g_str += f" ({', '.join(ind_g_str)})"
            st.markdown(f"**{label}**: {s1} **{lh} : {lg}** {s2}")
            if h_str or g_str: st.caption(f"Highlights: Heim [{h_str}] | Gast [{g_str}]")
            st.write("")
    if st.button("Schließen", use_container_width=True): st.rerun()

# --- MAIN UI ---
c_logo, c_title = st.columns([1, 4])
with c_logo:
    for logo_path in ["logo.png.png", "logo.png"]:
        try:
            st.image(logo_path, width=80)
            break
        except: pass
with c_title: st.markdown("<h1 style='margin: 0; padding-top: 8px; font-size: 1.8rem;'>Wehringer Steelers — Teamtraining</h1>", unsafe_allow_html=True)

c_mus, c_sync, c_dummy = st.columns([1, 1, 4])
with c_mus:
    try:
        with st.popover("🎵"): st.audio("vereinssong.mp3")
    except Exception: pass
with c_sync:
    if st.button("🔄", help="Manuell aktualisieren", key="main_sync_button_header"):
        st.session_state.sessions_list = load_data()
        st.rerun()

kader = [
    "Andreas Böhm", "Andrino Czombera", "Dennis Güttner", "Marco Eser",
    "Maximilian Zientner", "Michael Kummer", "Michael Mak", "Michael Neumeier",
    "Thomas Schaudt", "Wolfgang Scheider"
]

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

training_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga") and not s.get("is_wettkampf")]
liga_sessions = [s for s in st.session_state.sessions_list if s.get("is_liga")]
wettkampf_sessions = [s for s in st.session_state.sessions_list if s.get("is_wettkampf")]

tab_übersicht, tab_kader, tab_session, tab_liga, tab_wettkampf, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Freundschaftsspiele", "Liga (Punktspiele)", "Match-Archiv", "Modus & Regeln"])

if not is_admin:
    st.info("🔒 **Gast-Modus aktiv:** Du hast aktuell nur Lese-Rechte. Um Sessions zu starten oder Ergebnisse einzutragen, öffne das Seitenmenü (oben links auf `>` tippen) und logge dich als Spieler ein.")

with tab_übersicht:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if is_admin:
            if st.button("➕ Neue Session", type="primary", use_container_width=True, key="quick_start_btn"):
                open_new_session_dialog()
    with col_btn2:
        sorted_for_btn = sorted(training_sessions, key=lambda x: int(x["id"].split("-")[1]) if "id" in x and '-' in x['id'] else 0, reverse=True)
        active_sessions_for_btn = [s for s in sorted_for_btn if not is_session_completed(s)]
        if active_sessions_for_btn:
            if is_admin:
                if st.button("⚙️ Bearbeiten", use_container_width=True, key="edit_active_btn"):
                    open_edit_session_dialog(active_sessions_for_btn[0]['id'])
        else:
            if is_admin:
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
            if is_admin:
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
                            if is_admin:
                                if st.button("🔄", key=f"sub1_{curr_sess['id']}_{b_name}_{next_r}"): open_substitution_dialog(b_name, curr_sess['id'], next_r, 1, p1)
                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                        sc3, sc4 = st.columns([5, 2])
                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                        with sc4:
                            if is_admin:
                                if st.button("🔄", key=f"sub2_{curr_sess['id']}_{b_name}_{next_r}"): open_substitution_dialog(b_name, curr_sess['id'], next_r, 2, p2)
                        
                        st.write("")
                        col_e1, col_e2 = st.columns([1, 1])
                        with col_e1:
                            if is_admin:
                                if st.button("🎯 Eintragen", key=f"live_{curr_sess['id']}_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                    open_board_dialog(b_name, curr_sess['id'])
                        with col_e2:
                            prev_r = next_r - 1
                            if is_admin and prev_r > 0:
                                if st.button("✏️ Korrigieren", key=f"korr_{curr_sess['id']}_{b_name}_{prev_r}", use_container_width=True):
                                    open_board_dialog(b_name, curr_sess['id'], edit_round=prev_r)
                    else:
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle Runden beendet</p>", unsafe_allow_html=True)
                        st.success("✅ Abgeschlossen")
                        if is_admin:
                            if st.button("✏️ Letzte Runde korrigieren", key=f"korr_{curr_sess['id']}_{b_name}_{total_rounds}", use_container_width=True):
                                open_board_dialog(b_name, curr_sess['id'], edit_round=total_rounds)

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
    if not display_sess and all_sessions_sorted: display_sess = all_sessions_sorted[0]

    for sess in training_sessions:
        for match in sess.get("results", {}).values():
            s1_name, s2_name = match.get("s1", ""), match.get("s2", "")
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
                    s1_name, s2_name = m.get("s1", ""), m.get("s2", "")
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
            else: st.info("Keine Daten vorhanden.")
        with col_r:
            st.markdown("### Spitzenreiter")
            stats_temp = {p: {"Matches": 0, "Siege": 0} for p in kader}
            for sess in training_sessions:
                for match in sess.get("results", {}).values():
                    winner, loser = match.get("winner", ""), match.get("loser", "")
                    if winner and " & " not in winner:
                        for p in winner.split(" & "):
                            if p in stats_temp:
                                stats_temp[p]["Matches"] += 1
                                stats_temp[p]["Siege"] += 1
                    if loser and " & " not in loser:
                        for p in loser.split(" & "):
                            if p in stats_temp: stats_temp[p]["Matches"] += 1
            best_p, best_q, best_m = "Keiner", 0.0, 0
            for p in kader:
                m, s = stats_temp[p]["Matches"], stats_temp[p]["Siege"]
                if m > 0:
                    q = s / m
                    if q > best_q or (q == best_q and m > best_m): best_q, best_m, best_p = q, m, p
            st.markdown(f"**{best_p}** (Siegquote: {(best_q*100):.0f}% bei {best_m} Matches)")
            st.progress(best_q)

    with st.expander("📋 Ergebnisse der letzten Sessions ansehen", expanded=False):
        if not all_sessions_sorted: st.info("Noch keine Sessions vorhanden.")
        else:
            for s in all_sessions_sorted[:5]:
                col_sd, col_sb = st.columns([3, 1])
                with col_sd: st.markdown(f"**{s['datum']}** — ID: {s['id']}")
                with col_sb:
                    if st.button("📊 Ergebnisse", key=f"hist_btn_{s['id']}", use_container_width=True): open_session_summary_dialog(s['id'])
                st.divider()

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

    st.write("")
    st.markdown("### 🤝 Ewige Koop- & Doppel-Tabelle")
    st.write("Alle Doppel-Paarungen (egal an welchem Abend), die mindestens ein Match absolviert haben.")
    
    team_history = {}
    for sess in training_sessions:
        for match in sess.get("results", {}).values():
            winner, loser, s1, s2 = match.get("winner", ""), match.get("loser", ""), match.get("s1", ""), match.get("s2", "")
            if " & " in s1 or " & " in s2:
                try: l1, l2 = map(int, match.get("ergebnis", "0:0").split(":"))
                except ValueError: l1, l2 = 0, 0
                if " & " in s1:
                    t = s1
                    if t not in team_history: team_history[t] = {"matches": 0, "wins": 0, "l_won": 0, "l_lost": 0, "180s": 0}
                    team_history[t]["matches"] += 1
                    team_history[t]["l_won"] += l1
                    team_history[t]["l_lost"] += l2
                    team_history[t]["180s"] += int(match.get("180_s1", 0))
                    if winner == t: team_history[t]["wins"] += 1
                if " & " in s2:
                    t = s2
                    if t not in team_history: team_history[t] = {"matches": 0, "wins": 0, "l_won": 0, "l_lost": 0, "180s": 0}
                    team_history[t]["matches"] += 1
                    team_history[t]["l_won"] += l2
                    team_history[t]["l_lost"] += l1
                    team_history[t]["180s"] += int(match.get("180_s2", 0))
                    if winner == t: team_history[t]["wins"] += 1

    valid_teams = {k: v for k, v in team_history.items() if v["matches"] > 0}
    if not valid_teams:
        st.info("Noch keine Koop-Matches absolviert.")
    else:
        team_rows = [{"Team": t, "Matches": v["matches"], "Siege": v["wins"], "Quote": f"{(v['wins'] / v['matches'] * 100):.0f}%", "Legs": f"{v['l_won']}:{v['l_lost']}", "180er": v["180s"]} for t, v in valid_teams.items()]
        team_rows.sort(key=lambda x: (x["Siege"], x["Legs"].split(":")[0]), reverse=True)
        for rank, row in enumerate(team_rows, 1):
            with st.container(border=True):
                st.markdown(f"**{rank}. {row['Team']}** — Quote: **{row['Quote']}**")
                st.caption(f"🏆 Siege: {row['Siege']}/{row['Matches']} | 🎯 180er: {row['180er']} | Legs: {row['Legs']}")

with tab_liga:
    st.subheader("Freundschaftsspiele")
    st.write("Isolierter Bereich für Freundschaftsspiele (flexibel als 4er- oder 6er-/8er-/10er-/12er-Team mit variablen Boards, Blind Setup, Kreuz-Runde und PDF-Export).")
    
    if is_admin:
        if st.button("➕ Neues Freundschaftsspiel starten", type="primary", use_container_width=True):
            open_new_liga_match_dialog()
        
    st.divider()
    active_liga = [l for l in liga_sessions if not l.get("is_locked", False)]
    completed_liga = [l for l in liga_sessions if l.get("is_locked", False)]
    
    if not active_liga:
        st.info("Keine aktiven Freundschaftsspiele vorhanden. Starte oben ein neues Spiel.")
    else:
        for l_sess in active_liga:
            heim, gast = l_sess.get("heim_team", "Heim"), l_sess.get("gast_team", "Gast")
            res = l_sess.setdefault("results", {})
            boards = l_sess.get("liga_boards", ["Kaiser B1", "Board 2"])
            b_count = l_sess.get("boards_count", len(boards))
            auf_h, auf_g = l_sess.setdefault("auf_heim", {}), l_sess.setdefault("auf_gast", {})
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
                st.markdown(f"### {heim} vs. {gast} — Stand: {sets_heim}:{sets_gast}")
                st.caption(f"{l_sess['datum']} | ID: {l_sess['id']} | Status: {status}")
                col_s1, col_s2, col_s3, col_s4 = st.columns(4)
                col_s1.metric("Sets", f"{sets_heim} : {sets_gast}")
                col_s2.metric("Legs", f"{legs_heim} : {legs_gast}")
                col_s3.metric("Fortschritt", f"{played_matches_count}/{total_matches_count}")
                col_s4.metric("180er gesamt", f"{total_180s_liga}x")
                st.divider()
                
                t_size = l_sess.get("team_size", 4)
                h_einzel_ok, g_einzel_ok = bool(auf_h.get(f"h{t_size}")), bool(auf_g.get(f"g{t_size}"))
                if not h_einzel_ok or not g_einzel_ok:
                    st.warning(f"Phase 1: Alle {t_size} Einzelspieler eintragen (verdeckt)")
                    c_h, c_g = st.columns(2)
                    if is_admin and not h_einzel_ok:
                        if c_h.button("🔒 Heim Aufstellen", key=f"h_setup_{l_sess['id']}"): open_liga_aufstellung_einzel(l_sess['id'], True)
                    if is_admin and not g_einzel_ok:
                        if c_g.button("🔒 Gast Aufstellen", key=f"g_setup_{l_sess['id']}"): open_liga_aufstellung_einzel(l_sess['id'], False)
                elif not is_done:
                    curr_round_idx = 0
                    for r_idx, round_matches in enumerate(rounds_list):
                        if not all(res.get(m[0], {}).get("played") for m in round_matches):
                            curr_round_idx = r_idx; break
                            
                    singles_batches = math.ceil(t_size / b_count)
                    cross_batches = math.ceil(t_size / b_count)
                    is_in_doubles = (curr_round_idx >= singles_batches + cross_batches)
                    
                    if is_in_doubles:
                        h_doppel_ok, g_doppel_ok = bool(auf_h.get("hd1")), bool(auf_g.get("gd1"))
                        if not h_doppel_ok or not g_doppel_ok:
                            st.warning("🚨 Nach der Eingabe der letzten Einzelrunde (Einzel + Kreuz-Einzel) müssen nun beide Teams ihre Doppel-Aufstellungen hinterlegen!")
                            c_dh, c_dg = st.columns(2)
                            if is_admin and not h_doppel_ok:
                                if c_dh.button("🔒 Heim Doppel", key=f"hd_setup_{l_sess['id']}"): open_liga_aufstellung_doppel(l_sess['id'], True)
                            if is_admin and not g_doppel_ok:
                                if c_dg.button("🔒 Gast Doppel", key=f"gd_setup_{l_sess['id']}"): open_liga_aufstellung_doppel(l_sess['id'], False)
                            
                    if curr_round_idx < len(rounds_list) and not (is_in_doubles and (not auf_h.get("hd1") or not auf_g.get("gd1"))):
                        active_matches = rounds_list[curr_round_idx]
                        st.markdown(f"**Runde {curr_round_idx + 1} / {len(rounds_list)} läuft:**")
                        current_board_matches, waiting_queue = active_matches[:b_count], active_matches[b_count:]
                        cols_boards = st.columns(min(len(current_board_matches), 3) if len(current_board_matches) > 0 else 1)
                        for i, (m_key, m_label, h_key, g_key) in enumerate(current_board_matches):
                            b_name = boards[i % len(boards)]
                            m_data = res.get(m_key, {})
                            is_played = m_data.get("played", False)
                            
                            val_h = m_data.get("s1", "")
                            p_heim = val_h if is_played and val_h and val_h.strip() not in ["", "-"] else auf_h.get(h_key, "-")
                            if not p_heim: p_heim = "-"
                            
                            val_g = m_data.get("s2", "")
                            p_gast = val_g if is_played and val_g and val_g.strip() not in ["", "-"] else auf_g.get(g_key, "-")
                            if not p_gast: p_gast = "-"
                            
                            with cols_boards[i % len(cols_boards)]:
                                with st.container(border=True):
                                    st.write(f"*{b_name}* — {m_label}")
                                    all_match_keys = [match[0] for round in rounds_list for match in round]
                                    st.caption(f"Stand: **{get_running_score_up_to(res, all_match_keys, m_key)}**")
                                    show_sub_btn = ("Kreuz" in m_label) and not is_played
                                    if i % 2 == 1:
                                        st.markdown(f"Gast (links): **{p_gast}**")
                                        if is_admin and show_sub_btn and not "d" in g_key:
                                            if st.button("🔄", key=f"sub_g_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_gast)
                                        st.markdown(f"Heim: **{p_heim}**")
                                        if is_admin and show_sub_btn and not "d" in h_key:
                                            if st.button("🔄", key=f"sub_h_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_heim)
                                    else:
                                        st.markdown(f"Heim (links): **{p_heim}**")
                                        if is_admin and show_sub_btn and not "d" in h_key:
                                            if st.button("🔄", key=f"sub_h_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_heim)
                                        st.markdown(f"Gast: **{p_gast}**")
                                        if is_admin and show_sub_btn and not "d" in g_key:
                                            if st.button("🔄", key=f"sub_g_{l_sess['id']}_{m_key}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_gast)
                                    if is_played:
                                        st.success(f"Ergebnis: {m_data['lh']}:{m_data['lg']}")
                                    else:
                                        if is_admin:
                                            if st.button("🎯 Eintragen", key=f"live_{l_sess['id']}_{m_key}", use_container_width=True):
                                                open_liga_live_board_dialog(l_sess['id'], m_key, b_name, m_label, p_gast if i%2==1 else p_heim, p_heim if i%2==1 else p_gast, is_right_board=(i%2==1))
                        if waiting_queue:
                            st.write("")
                            st.markdown("##### 📋 Warteschlange (Nächste Spiele auf Boards):")
                            for wi, (wm_key, wm_label, wh_key, wg_key) in enumerate(waiting_queue):
                                wm_data = res.get(wm_key, {})
                                w_is_played = wm_data.get("played", False)
                                wval_h = wm_data.get("s1", "")
                                wp_h = wval_h if w_is_played and wval_h and wval_h.strip() not in ["", "-"] else auf_h.get(wh_key, "-")
                                if not wp_h: wp_h = "-"
                                wval_g = wm_data.get("s2", "")
                                wp_g = wval_g if w_is_played and wval_g and wval_g.strip() not in ["", "-"] else auf_g.get(wg_key, "-")
                                if not wp_g: wp_g = "-"
                                st.caption(f"• **{wm_label}**: {wp_h} vs {wp_g}")
                if is_done or (h_einzel_ok and g_einzel_ok):
                    st.divider()
                    if is_admin:
                        if st.button("📝 Spielbericht ansehen & abschließen", key=f"l_ber_{l_sess['id']}", use_container_width=True): open_liga_bericht_dialog(l_sess['id'])

    st.write("")
    st.markdown("### 🗄️ Abgeschlossene Freundschaftsspiele (PDF-Export)")
    st.write("Hier findest du alle beendeten Spiele. Die PDF-Ausleitung füllt den offiziellen Spielbericht aus.")
    
    if not completed_liga: st.info("Noch keine abgeschlossenen Freundschaftsspiele im Archiv.")
    else:
        for c_sess in completed_liga:
            with st.container(border=True):
                st.markdown(f"**{c_sess['datum']}** | 🏆 {c_sess.get('heim_team')} vs. {c_sess.get('gast_team')}")
                try:
                    pdf_file = generate_spielbericht_pdf(c_sess)
                    st.download_button(label="📥 Offiziellen Spielbericht als PDF laden", data=pdf_file, file_name=f"Spielbericht_{c_sess.get('heim_team')}_vs_{c_sess.get('gast_team')}.pdf", mime="application/pdf", key=f"dl_pdf_{c_sess['id']}")
                except Exception as e: st.error(f"PDF-Generierung fehlgeschlagen: {e}")

with tab_wettkampf:
    st.subheader("Liga & Wettkampf (Punktspiele)")
    
    st.markdown("### 🏆 Aktuelle Bezirksliga-Tabelle (Live vom BDV)")
    @st.cache_data(ttl=3600)
    def fetch_bdv_table():
        import pandas as pd
        import urllib.request
        import io
        url = "https://bdv-dart.liga.nu/cgi-bin/WebObjects/nuLigaDARTDE.woa/wa/groupPage?championship=Schw+2026%2F27&group=211705"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'})
            response = urllib.request.urlopen(req, timeout=5)
            html = response.read().decode('utf-8', errors='replace')
            try:
                dfs = pd.read_html(io.StringIO(html))
            except:
                dfs = pd.read_html(html)
            for df in dfs:
                if any("Mannschaft" in str(col) for col in df.columns):
                    df = df.dropna(how='all', axis=1) 
                    return df, ""
            return pd.DataFrame(), "Keine passende Tabelle gefunden"
        except Exception as e:
            return pd.DataFrame(), str(e)
            
    bdv_df, err_msg = fetch_bdv_table()
    
    if not bdv_df.empty:
        def highlight_fsv(val):
            if isinstance(val, str) and "Wehringen" in val: return 'background-color: rgba(46, 125, 50, 0.6); color: white;'
            return ''
        try:
            st.dataframe(bdv_df.style.map(highlight_fsv), use_container_width=True, hide_index=True)
        except AttributeError:
            st.dataframe(bdv_df.style.applymap(highlight_fsv), use_container_width=True, hide_index=True)
    else:
        st.warning(f"Die Daten-Sauger Methode wird vom BDV blockiert oder es fehlt ein Paket (System-Meldung: {err_msg}). Als Fallback wird die Original-Tabelle eingeblendet:")
        st.markdown(f'<iframe src="https://bdv-dart.liga.nu/cgi-bin/WebObjects/nuLigaDARTDE.woa/wa/groupPage?championship=Schw+2026%2F27&group=211705" width="100%" height="450px" style="border: none; border-radius: 8px; background: white;"></iframe>', unsafe_allow_html=True)
        
    st.caption("(Die Tabelle wird stündlich automatisch aus dem nuLiga-System des BDV aktualisiert)")
    st.divider()

    st.write("Hier trackt ihr eure offiziellen Ligaspiele. Ladet ein Foto des Spielberichts hoch und tippt die Daten in wenigen Sekunden via Blitz-Erfassung ab.")
    
    if is_admin:
        c_btn_w1, c_btn_w3, c_btn_w4 = st.columns(3)
        with c_btn_w1:
            if st.button("➕ Neuer Spieltag", type="primary", use_container_width=True): open_new_wettkampf_dialog()
        with c_btn_w3:
            if st.button("📆 Saison-Kalender öffnen", use_container_width=True): open_saison_kalender_dialog()
        with c_btn_w4:
            if st.button("♻️ Liga-Backup laden", use_container_width=True): open_liga_rollback_dialog()
    else:
        if st.button("📆 Saison-Kalender öffnen", use_container_width=True): open_saison_kalender_dialog()
        
    st.divider()
    
    if not wettkampf_sessions: st.info("Noch keine Liga-Spiele eingetragen. Lege ein Spiel manuell an.")
    else:
        l_stats = {p: {"Matches": 0, "Siege": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "HFs": [], "SLs": []} for p in kader}
        for sess in wettkampf_sessions:
            if sess.get("is_locked"):
                is_heim = sess.get("is_heimspiel", True)
                for m_key, m_data in sess.get("results", {}).items():
                    if m_data.get("played"):
                        s1, s2 = m_data.get("s1", ""), m_data.get("s2", "")
                        lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                        wehringen_players = s1 if is_heim else s2
                        wehringen_legs_won = lh if is_heim else lg
                        wehringen_legs_lost = lg if is_heim else lh
                        wehringen_won = wehringen_legs_won > wehringen_legs_lost
                        ind_180s = m_data.get("ind_180_h", {}) if is_heim else m_data.get("ind_180_g", {})
                        hf_val = m_data.get("hf_h", 0) if is_heim else m_data.get("hf_g", 0)
                        sl_val = m_data.get("sl_h", 0) if is_heim else m_data.get("sl_g", 0)
                        for p in [p.strip() for p in wehringen_players.split("&")]:
                            if p in l_stats:
                                l_stats[p]["Matches"] += 1
                                if wehringen_won: l_stats[p]["Siege"] += 1
                                l_stats[p]["Legs_Won"] += wehringen_legs_won
                                l_stats[p]["Legs_Lost"] += wehringen_legs_lost
                                l_stats[p]["180er"] += ind_180s.get(p, m_data.get("180_h", 0) if is_heim else m_data.get("180_g", 0))
                                if hf_val >= 100: l_stats[p]["HFs"].append(hf_val)
                                if 0 < sl_val <= 18: l_stats[p]["SLs"].append(sl_val)

        with st.expander("📊 Spieler-Statistik (Gesamte Saison)", expanded=True):
            table_rows = []
            for p in kader:
                if l_stats[p]["Matches"] > 0:
                    hf_str = f"{max(l_stats[p]['HFs'])} (insg. {len(l_stats[p]['HFs'])})" if l_stats[p]['HFs'] else "-"
                    sl_str = f"{min(l_stats[p]['SLs'])} (insg. {len(l_stats[p]['SLs'])})" if l_stats[p]['SLs'] else "-"
                    table_rows.append({"Spieler": p, "Matches": l_stats[p]["Matches"], "Siege": l_stats[p]["Siege"], "Quote": f"{(l_stats[p]['Siege'] / l_stats[p]['Matches'] * 100):.0f}%", "Legs": f"{l_stats[p]['Legs_Won']}:{l_stats[p]['Legs_Lost']}", "180er": l_stats[p]["180er"], "High Finish": hf_str, "Bestes SL": sl_str})
            if table_rows: st.dataframe(pd.DataFrame(table_rows).sort_values("Siege", ascending=False), hide_index=True)
            else: st.info("Noch keine abgeschlossenen Spiele zur Auswertung vorhanden.")

        st.divider()

        def parse_w_date(sess):
            try: return datetime.strptime(sess.get("datum", "01.01.2026"), "%d.%m.%Y")
            except: return datetime.min
        
        sorted_w_sessions = sorted(wettkampf_sessions, key=parse_w_date)
        active_games = [s for s in sorted_w_sessions if not s.get("is_locked", False)]
        completed_games = [s for s in sorted_w_sessions if s.get("is_locked", False)]

        if completed_games:
            with st.expander("🗄️ Abgeschlossene Liga-Spiele (Archiv)", expanded=False):
                for w_sess in completed_games:
                    with st.container(border=True):
                        st.markdown(f"#### {w_sess['datum']} | {w_sess['heim_team']} vs. {w_sess['gast_team']}")
                        res = w_sess.get("results", {})
                        sets_h, sets_g, legs_h, legs_g = 0, 0, 0, 0
                        hfs, sls, maxs = [], [], []
                        for m_key, m_data in res.items():
                            if m_data.get("played"):
                                lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                                legs_h += lh; legs_g += lg
                                if lh > lg: sets_h += 1
                                elif lg > lh: sets_g += 1
                                if m_data.get("hf_h", 0) >= 100: hfs.append(str(m_data["hf_h"]))
                                if m_data.get("hf_g", 0) >= 100: hfs.append(str(m_data["hf_g"]))
                                if m_data.get("sl_h", 0) > 0 and m_data.get("sl_h", 0) <= 18: sls.append(str(m_data["sl_h"]))
                                if m_data.get("sl_g", 0) > 0 and m_data.get("sl_g", 0) <= 18: sls.append(str(m_data["sl_g"]))
                                if m_data.get("180_h", 0) > 0: maxs.append(str(m_data["180_h"]))
                                if m_data.get("180_g", 0) > 0: maxs.append(str(m_data["180_g"]))
                        st.markdown(f"**Sets:** {sets_h}:{sets_g} | **Legs:** {legs_h}:{legs_g} | ✅ Abgeschlossen")
                        if hfs or sls or maxs: st.caption(f"🎯 **Highlights:** 180er: {sum(map(int, maxs))}x | High Finishes: {', '.join(hfs) if hfs else '-'} | Short Legs: {', '.join(sls) if sls else '-'}")

                        col_a, col_b, col_c = st.columns(3)
                        with col_a:
                            if st.button("📊 Ergebnisse", key=f"wk_res_{w_sess['id']}", use_container_width=True): open_wettkampf_view_dialog(w_sess['id'])
                        with col_b:
                            if is_admin:
                                if st.button("✏️ Bearbeiten", key=f"wk_edit_arch_{w_sess['id']}", use_container_width=True): open_wettkampf_blitz_dialog(w_sess['id'])
                        with col_c:
                            if w_sess.get("image_b64"):
                                if st.button("📸 Foto ansehen", key=f"wk_img_arch_{w_sess['id']}", use_container_width=True): open_image_dialog(w_sess["image_b64"])
                            else: st.button("📸 Kein Foto", key=f"wk_img_arch_no_{w_sess['id']}", disabled=True, use_container_width=True)
            st.write("")

        if active_games:
            st.markdown("### 🔴 Ausstehende / Aktive Spiele")
            for w_sess in active_games:
                with st.container(border=True):
                    st.markdown(f"### {w_sess['datum']} | {w_sess['heim_team']} vs. {w_sess['gast_team']}")
                    res = w_sess.get("results", {})
                    sets_h, sets_g, legs_h, legs_g = 0, 0, 0, 0
                    hfs, sls, maxs = [], [], []
                    for m_key, m_data in res.items():
                        if m_data.get("played"):
                            lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                            legs_h += lh; legs_g += lg
                            if lh > lg: sets_h += 1
                            elif lg > lh: sets_g += 1
                            if m_data.get("hf_h", 0) >= 100: hfs.append(str(m_data["hf_h"]))
                            if m_data.get("hf_g", 0) >= 100: hfs.append(str(m_data["hf_g"]))
                            if m_data.get("sl_h", 0) > 0 and m_data.get("sl_h", 0) <= 18: sls.append(str(m_data["sl_h"]))
                            if m_data.get("sl_g", 0) > 0 and m_data.get("sl_g", 0) <= 18: sls.append(str(m_data["sl_g"]))
                            if m_data.get("180_h", 0) > 0: maxs.append(str(m_data["180_h"]))
                            if m_data.get("180_g", 0) > 0: maxs.append(str(m_data["180_g"]))

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Sets", f"{sets_h} : {sets_g}")
                    col2.metric("Legs", f"{legs_h} : {legs_g}")
                    col3.markdown(f"**Status:** 🔴 Aktiv/Ausstehend")
                    if hfs or sls or maxs: st.caption(f"🎯 **Highlights:** 180er: {sum(map(int, maxs))}x | High Finishes: {', '.join(hfs) if hfs else '-'} | Short Legs: {', '.join(sls) if sls else '-'}")

                    c_b1, c_b2, c_b3 = st.columns(3)
                    with c_b1:
                        if is_admin:
                            if st.button("⚡ Blitz-Erfassung", key=f"wk_blitz_{w_sess['id']}", use_container_width=True): open_wettkampf_blitz_dialog(w_sess['id'])
                    with c_b2:
                        if w_sess.get("image_b64"):
                            if st.button("📸 Foto ansehen", key=f"wk_img_{w_sess['id']}", use_container_width=True): open_image_dialog(w_sess["image_b64"])
                        else: st.button("📸 Kein Foto", key=f"wk_img_no_{w_sess['id']}", disabled=True, use_container_width=True)
                    with c_b3:
                        if is_admin:
                            if st.button("🗑️ Löschen (Admin)", key=f"wk_del_{w_sess['id']}", use_container_width=True): open_delete_session_dialog(w_sess['id'])

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
            try: return datetime.strptime(sess.get("datum", "01.01.2026"), "%d.%m.%Y")
            except: return datetime.min
                
        sorted_sessions = sorted([s for s in st.session_state.sessions_list if not s.get("is_wettkampf", False)], key=lambda x: (parse_session_date(x), int(x["id"].split("-")[1]) if "-" in x["id"] and x["id"].split("-")[1].isdigit() else 0), reverse=True)
        
        for sess in sorted_sessions:
            is_l = sess.get("is_liga", False)
            with st.container(border=True):
                if is_l:
                    status_text = "✅ [Abgeschlossen]" if sess.get("is_locked", False) else "🔴 [Aktiv]"
                    st.markdown(f"**{sess['id']}** (Freundschaftsspiel) — {sess['datum']} {status_text}\n\n🏆 {sess.get('heim_team')} vs {sess.get('gast_team')}")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("📝 Spielbericht", key=f"arch_liga_v_{sess['id']}", use_container_width=True): open_liga_bericht_dialog(sess['id'])
                    with c2:
                        if is_admin:
                            if st.button("⚙️ Bearbeiten", key=f"arch_liga_e_{sess['id']}", use_container_width=True): open_edit_liga_session_dialog(sess['id'])
                    with c3:
                        if is_admin:
                            if st.button("🗑️ Löschen", key=f"arch_liga_d_{sess['id']}", use_container_width=True): open_delete_session_dialog(sess['id'])
                else:
                    status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                    start_t, end_t = sess.get("start_time", "–"), sess.get("end_time", "–")
                    time_display = f" | ⏱️ {start_t} - {end_t} Uhr" if start_t and start_t != "–" else ""
                    st.markdown(f"**{sess['id']}** (Training) — {sess['datum']}{time_display} {status_text}")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        if st.button("📊 Ansehen", key=f"arch_view_{sess['id']}", use_container_width=True): open_session_summary_dialog(sess['id'])
                    with c2:
                        if is_admin:
                            if st.button("⚙️ Bearbeiten", key=f"arch_edit_{sess['id']}", use_container_width=True): open_edit_session_dialog(sess['id'])
                    with c3:
                        if is_admin:
                            if st.button("🗑️ Löschen", key=f"arch_del_{sess['id']}", use_container_width=True): open_delete_session_dialog(sess['id'])
                        
                    st.divider()
                    if is_admin:
                        is_checked = st.checkbox(f"⚡ Runden-Schnellerfassung & Korrektur", key=f"blitz_check_{sess['id']}")
                        if is_checked:
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
                                    except: s1, s2 = 0, 0
                                        
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
                                                if p1 == "-" or p2 == "-": pass
                                                elif val1 == val2: st.error("🚨 Unentschieden nicht möglich.")
                                                elif val1 > req_win or val2 > req_win: st.error(f"🚨 Bei {leg_modus} max. {req_win} Legs.")
                                                elif val1 != req_win and val2 != req_win: st.error(f"🚨 Sieger braucht genau {req_win} Legs.")
                                                else:
                                                    winner = p1 if val1 > val2 else p2
                                                    loser = p2 if val1 > val2 else p1
                                                    if "results" not in sess: sess["results"] = {}
                                                    if m_info:
                                                        sess["results"][(r, b_name)]["ergebnis"] = f"{val1}:{val2}"
                                                        sess["results"][(r, b_name)]["winner"] = winner
                                                        sess["results"][(r, b_name)]["loser"] = loser
                                                    else:
                                                        sess["results"][(r, b_name)] = {"s1": p1, "s2": p2, "ergebnis": f"{val1}:{val2}", "winner": winner, "loser": loser, "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0}
                                                    smart_sync_and_save(st.session_state.sessions_list)
                                                    st.rerun()
                                        with c_b2:
                                            if st.button("🗑️ Leeren", key=f"blitz_del_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                                if (r, b_name) in sess["results"]:
                                                    del sess["results"][(r, b_name)]
                                                    smart_sync_and_save(st.session_state.sessions_list)
                                                    st.rerun()

with tab_regeln:
    st.subheader("🎯 Modus & Spielablauf")
    st.write("Hier findet ihr die vollständige Anleitung für den Trainingsabend, alle Spielmodi und Freundschaftsspiele.")
    with st.container(border=True):
        st.markdown("### 🏆 Freundschaftsspiele")
        st.markdown("""* Eigener Bereich im Tab **Freundschaftsspiele**.
        * **Ablauf:** Die Aufstellung erfolgt in 2 Phasen (Einzel und Doppel), verdeckt (Blind Setup). Doppel dürfen erst aufgestellt werden, wenn alle Einzel und Kreuz-Einzel gespielt sind.
        * **Flexibel wählbar:** Als 4er, 6er, 8er, 10er oder 12er-Team mit variablen Boards (wobei pro Board immer 2 Spieler spielen).
        * **Live-Tracking & Warteschlange:** Gespielt wird auf frei wählbaren parallelen Boards. Der Live-Spielstand im Header ("Stand") zählt die aktuellen Sets automatisch hoch.
        * **Archivierung & Regel:** Abgeschlossene Freundschaftsspiele zeigen im Tab 'Freundschaftsspiele' ausschließlich den HTML-Druck-Button für den offiziellen Spielbericht. Der Korrigieren/Bearbeiten-Button ist dort entfernt und ausschließlich im **Match-Archiv** erreichbar.""")
    with st.container(border=True):
        st.markdown("### 👑 Trainings-Modi & Logik")
        st.markdown("""* **Standard-Training (Einzel + Coop):** X Runden Einzel (max 6 Boards), dann Y Runden Doppel (exklusiv auf Kaiser B1 & Board 2).
        * **Koop 2vs2 (Up & Down):** Reine Doppel-Session (0 Einzel). Gespielt wird exklusiv auf Kaiser B1 & Board 2. Keine exakt gleichen 2er-Teams wie in der Vorsession.
        * **Up & Down (Einzel - Klassisch):** Sieger steigt auf (Ri. B1), Verlierer ab. Der Kaiser der Vorsession (Platz 1) sowie der Sieger von Board 2 (Platz 2) starten am folgenden Abend gemeinsam auf dem letzten Board (z.B. Board 4).""")
    with st.container(border=True):
        st.markdown("### 👥 Besonderheiten & Zeitmanagement")
        st.markdown("""* **Anti-Doppel-Pause:** Das Freilos in Runde 1 rotiert. Wer im letzten Match pausiert hat, darf nicht nochmal aussetzen.
        * **Ungerader Kader:** Bei ungerader Spieleranzahl wird auf dem letzten Board ein Platzhalter (`-`) eingesetzt, sodass das Freilos automatisch durchwechselt.
        * **Fehler Korrigieren:** Über den "✏️ Korrigieren" Button direkt in der laufenden Session kann die zuletzt gespielte Runde sofort repariert werden (fat-finger errors).""")
