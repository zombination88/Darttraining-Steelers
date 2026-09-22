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

SHEET_URL = "[https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0](https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0)"

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
        scope = ["[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)", "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"]
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
    heim, gast, datum = sess.get("heim_team", ""), sess.get("gast_team", ""), sess.get("datum", "")
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

@st.dialog("📸 Spielbericht Original", width="large")
def open_image_dialog(b64_str):
    st.image(base64.b64decode(b64_str), use_container_width=True)
    if st.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("♻️ Liga-Notfall-Wiederherstellung", width="large")
def open_liga_rollback_dialog():
    st.warning("⚠️ Achtung: Dies stellt NUR gelöschte Liga-Spiele (Wettkämpfe) inkl. Fotos aus der Cloud wieder her. Dein normales Teamtraining bleibt davon komplett unberührt!")
    pwd = st.text_input("Admin-Passwort zur Bestätigung:", type="password")
    if pwd != "1521":
        if pwd != "": st.error("Nur für Administratoren!")
        return
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict: creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)", "[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet_obj = client.open_by_url(SHEET_URL)
        try:
            backup_ws = spreadsheet_obj.worksheet("backups")
            all_vals = backup_ws.get_all_values()
            if len(all_vals) > 1:
                backups = list(reversed(all_vals[1:]))
                confirm = st.checkbox("Ja, ich möchte alte Liga-Daten aus der Cloud laden.")
                for i, b in enumerate(backups[:10]):
                    ts = b[0]
                    json_str = b[1]
                    try:
                        data_preview = json.loads(json_str)
                        liga_games = [s for s in data_preview if s.get("is_wettkampf")]
                        data_info = f"{len(liga_games)} Liga-Spiele gesichert"
                    except: data_info = "Fehlerhaftes JSON"
                    c_t, c_b = st.columns([3, 1])
                    c_t.markdown(f"**Speicherpunkt:** {ts} *(Inhalt: {data_info})*")
                    with c_b:
                        if st.button("Liga-Daten Laden", key=f"rest_liga_{i}", disabled=not confirm, use_container_width=True):
                            try:
                                backup_data = json.loads(json_str)
                                backup_liga = [s for s in backup_data if s.get("is_wettkampf")]
                                current_other = [s for s in st.session_state.sessions_list if not s.get("is_wettkampf")]
                                merged_data = current_other + backup_liga
                                sichere_sessions = make_serializable(merged_data)
                                new_json_str = json.dumps(sichere_sessions, ensure_ascii=False)
                                normal_sessions = [s for s in sichere_sessions if not s.get("is_wettkampf")]
                                liga_sessions_list = [s for s in sichere_sessions if s.get("is_wettkampf")]
                                completed_liga_list = [s for s in liga_sessions_list if s.get("is_locked")]
                                ws_normal = ensure_worksheet(spreadsheet_obj, "sessions")
                                chunked_save(ws_normal, normal_sessions)
                                ws_liga = ensure_worksheet(spreadsheet_obj, "liga_sessions")
                                chunked_save(ws_liga, liga_sessions_list)
                                ws_completed_liga = ensure_worksheet(spreadsheet_obj, "completed_liga")
                                chunked_save(ws_completed_liga, completed_liga_list)
                                st.session_state.sessions_list = merged_data
                                st.success("✅ Liga-Daten erfolgreich wiederhergestellt!")
                                st.rerun()
                            except Exception as e: st.error(f"Fehler: {e}")
                    st.divider()
            else: st.info("Noch keine Cloud-Backups vorhanden.")
        except Exception as e: st.error("Konnte Backup-Tabelle nicht finden.")
    except Exception as e: st.error(f"Verbindungsfehler zur Google Cloud: {e}")

@st.dialog("➕ Neue Session starten")
def open_new_session_dialog():
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
                new_session = {"id": f"S-{max_id + 1}", "datum": session_datum.strftime("%d.%m.%Y"), "start_time": None, "end_time": None, "modus": spielmodus, "boards_count": gewaehlte_boards_zahl, "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds, "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus, "spieler": aktive_spieler, "gaeste": gaeste, "results": {}, "is_liga": False}
                if spielmodus in ["Koop 2vs2 (Up & Down)", "Standard-Training (Einzel + Coop)"]: get_or_create_teams(new_session, training_sessions)
                st.session_state.sessions_list.append(new_session)
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()

@st.dialog("⚙️ Session bearbeiten")
def open_edit_session_dialog(session_id):
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
            sess.update({"datum": session_datum.strftime("%d.%m.%Y"), "start_time": edit_start_time.strip() or None, "end_time": edit_end_time.strip() or None, "modus": spielmodus, "boards_count": int(anzahl_boards.split()[0]), "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds, "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus, "spieler": aktive_spieler, "gaeste": gaeste})
            st.session_state.sessions_list[real_idx] = sess
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("🗑️ Session Löschen (Admin)")
def open_delete_session_dialog(session_id):
    st.warning(f"Willst du die Session **{session_id}** wirklich unwiderruflich löschen?")
    pwd = st.text_input("Admin-Passwort zur Bestätigung:", type="password", key=f"del_pwd_{session_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c2:
        if st.button("🗑️ Unwiderruflich löschen", type="primary", use_container_width=True):
            if pwd == "1521":
                delete_session(session_id)
                st.success("Session wurde erfolgreich gelöscht!")
                st.rerun()
            else: st.error("Falsches Admin-Passwort!")

@st.dialog("📋 Board-Erfassung & Tracking")
def open_board_dialog(board_name, session_id, edit_round=None):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    if edit_round: current_round = edit_round
    else:
        completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
        current_round = max(completed_rounds) + 1 if completed_rounds else 1
    if current_round > total_rounds and not edit_round:
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
        btn_text = "Korrektur speichern" if edit_round else "Ergebnis abschließen"
        if st.button(btn_text, type="primary", use_container_width=True, disabled=not is_valid_result):
            if is_valid_result:
                if "results" not in sess: sess["results"] = {}
                sess["results"][(current_round, board_name)] = {"s1": current_p1, "s2": current_p2, "ergebnis": ergebnis, "winner": winner, "loser": loser, "180_s1": in_180_1, "180_s2": in_180_2, "avg_s1": in_avg_1, "avg_s2": in_avg_2}
                st.session_state.sessions_list[real_idx] = sess
                smart_sync_and_save(st.session_state.sessions_list)
                st.rerun()
    with cb2:
        if st.button("Schließen", use_container_width=True): st.rerun()

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
                sess["results"][(round_num, board_name)] = {"s1": auto_p[0], "s2": auto_p[1], "ergebnis": "0:0", "winner": "", "loser": "", "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0}
            if slot_num == 1: sess["results"][(round_num, board_name)]["s1"] = final_name
            else: sess["results"][(round_num, board_name)]["s2"] = final_name
            smart_sync_and_save(st.session_state.sessions_list)
            st.rerun()

@st.dialog("📊 Session Endstand & Zusammenfassung", width="large")
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
    st.markdown("#### 📋 Alle Spielergebnisse (Detail-Ansicht)")
    for r in range(1, total_rounds + 1):
        r_head = f"Doppelrunde {r - singles_rounds} (Coop)" if is_standard_training and r > singles_rounds else f"Runde {r} (Einzel)" if is_standard_training else f"Runde {r}"
        has_matches = any(rnd == r and m.get("winner") for (rnd, b), m in res.items())
        if has_matches:
            with st.expander(f"🎯 {r_head}"):
                for b_name in get_boards_list(sess, r):
                    m_info = res.get((r, b_name))
                    if m_info and m_info.get("winner"): st.markdown(f"**{b_name}:** {m_info['s1']} vs {m_info['s2']} ➔ **{m_info['ergebnis']}** *(Sieger: {m_info['winner']})*")
    st.divider()
    if singles_rounds > 0 and not is_pure_coop:
        last_played_round = max([r for (r, b), info in res.items() if info.get("winner") and r <= singles_rounds] + [0])
        if last_played_round > 0:
            st.markdown(f"#### 🎯 Einzel-Phase (Stand nach Runde {last_played_round}/{singles_rounds})")
            w, l = {}, {}
            b_list = get_boards_list(sess, last_played_round)
            for b in b_list:
                m_inf = res.get((last_played_round, b))
                if m_inf and m_inf.get("winner"): w[b], l[b] = m_inf.get("winner"), m_inf.get("loser")
                else: w[b], l[b] = "-", "-"
            for b_idx, b_name in enumerate(b_list):
                if b_idx == 0: platz1, platz2 = w.get("Kaiser B1", "-"), w.get("Board 2", "-") if len(b_list) > 1 else l.get("Kaiser B1", "-")
                else: platz1, platz2 = l.get(b_list[b_idx-1], "-"), w.get(b_list[b_idx+1], "-") if b_idx+1 < len(b_list) else l.get(b_list[b_idx], "-")
                m_inf = res.get((last_played_round, b_name))
                m_str = f"{m_inf['s1']} vs {m_inf['s2']} ➔ {m_inf['ergebnis']}" if m_inf and m_inf.get("winner") else "Match ausstehend."
                st.markdown(f"<div style='border: 1px solid #444; border-radius: 8px; padding: 10px; margin-bottom: 10px; background-color: #1e1e1e;'><h5 style='margin: 0; padding-bottom: 5px; color: #fff;'>{b_name}</h5><p style='margin: 0; font-size: 0.85em; color: gray;'>{m_str}</p><p style='margin: 5px 0 0 0; font-size: 0.95em;'>🥇 1. Platz: <b>{platz1}</b></p><p style='margin: 0; font-size: 0.95em;'>🥈 2. Platz: <b>{platz2}</b></p></div>", unsafe_allow_html=True)
            st.divider()
        else: st.info("Noch keine Einzel-Matches beendet.")
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
                    for s_
