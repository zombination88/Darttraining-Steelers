# INSTRUKTION: DIESE REGELN DÜRFEN BEI CODE-UPDATES NIEMALS VERLETZT WERDEN
# 1. BACKUPS: Das Rolling-Backup in Google Sheets darf max 20 Einträge umfassen. Abgeschlossene Spiele landen im 'completed_backup' Tresor (Merge-Verfahren).
# 2. JSON-EXPORT: Vor jedem json.dumps() MUSS die Hilfsfunktion make_serializable() aufgerufen werden!
# 3. KOOP-TEAMS: Es dürfen niemals exakt gleiche 2er-Teams aus der vorherigen Session gebildet werden.
# 4. ANTI-DOPPEL-PAUSE: Das Freilos in Runde 1 muss rotieren.
# 5. ZEITMANAGEMENT: Globale Ø-Zeiten (Min/Runde, Min/Leg) berechnen.
# 6. KADER-STATS: MVP (min 3 Matches), Dauerbrenner, Bester Avg und 180er Maschine (mit Tooltips bei Gleichstand).
# 7. HEADER: Logo und "Wehringer Steelers — Teamtraining" als Titel.
# 8. STATISTIKEN ÜBERSICHT: Die allgemeinen Statistiken in der Übersicht filtern Liga-Spiele aus und sind immer sichtbar.
# 9. DIALOGE: Dialoge MÜSSEN über session_id arbeiten, nicht über session_idx (IndexError Schutz!).
# 10. REITER-STRUKTUR: [Übersicht, Kader, Session, Freundschaftsspiele, Match-Archiv, Modus & Regeln]. Modus & Regeln enthält NUR Trainingstexte.

import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import collections
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

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

def make_serializable(sessions):
    """Konvertiert Tupel-Schlüssel in den Ergebnissen in Strings für JSON-Export und Speicherung."""
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
    return serializable_sessions

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
                            try:
                                r_num = int(parts[0])
                                b_name = parts[1]
                                fixed_results[(r_num, b_name)] = v
                            except:
                                fixed_results[k] = v
                        else:
                            fixed_results[k] = v
                    sess["results"] = fixed_results
                    sessions.append(sess)
                return sessions
    except Exception as e:
        st.error(f"Fehler beim Laden aus Google Sheets: {e}")
    return []

def save_backup_to_cloud(serializable_sessions):
    """Erstellt vollautomatisch einen zeitgestempelten Snapshot im 'backups' Tabellenblatt (max 20 Einträge)."""
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
                    try: backup_ws.delete_rows(2)
                    except AttributeError: backup_ws.delete_row(2)
        except Exception: pass
    except Exception: pass

def save_completed_backup(serializable_sessions):
    """Speichert alle abgeschlossenen Spiele dauerhaft als Tresor in einem separaten Tabellenblatt (Merge-Verfahren)."""
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_url(SHEET_URL)
        
        try: backup_ws = spreadsheet.worksheet("completed_backup")
        except: backup_ws = spreadsheet.add_worksheet(title="completed_backup", rows=2, cols=2); backup_ws.update([["Last_Updated", "JSON_Data_Completed"], ["", "[]"]])
            
        existing_vault_data = []
        try:
            raw_vault = backup_ws.cell(2, 2).value
            if raw_vault and raw_vault != "[]":
                existing_vault_data = json.loads(raw_vault)
        except Exception: pass
            
        vault_dict = {s["id"]: s for s in existing_vault_data}
        
        for s in serializable_sessions:
            is_completed = False
            if s.get("is_liga"):
                if s.get("is_locked"): is_completed = True
            else:
                if s.get("end_time"): is_completed = True
            if is_completed: vault_dict[s["id"]] = s
                
        merged_completed_sessions = list(vault_dict.values())
        
        from zoneinfo import ZoneInfo
        ts = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d %H:%M:%S")
        json_str = json.dumps(merged_completed_sessions, ensure_ascii=False)
        backup_ws.update([["Last_Updated", "JSON_Data_Completed"], [ts, json_str]])
    except Exception: pass

def save_data(sessions):
    if not sheet_conn: return
    serializable_sessions = make_serializable(sessions)
    json_str = json.dumps(serializable_sessions, ensure_ascii=False)
    try:
        sheet_conn.clear()
        sheet_conn.update([["json_data"], [json_str]])
        save_backup_to_cloud(serializable_sessions)
        save_completed_backup(serializable_sessions)
    except Exception as e:
        st.error(f"Fehler beim Speichern in Google Sheets: {e}")

def get_local_time_str():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Europe/Berlin")).strftime("%H:%M")
    except Exception: return datetime.now().strftime("%H:%M")

def is_session_completed(sess):
    if sess.get("is_liga"): return sess.get("is_locked", False)
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    for r in range(1, total_rounds + 1):
        boards_in_round = get_boards_list(sess, r)
        for b_name in boards_in_round:
            if not res.get((r, b_name), {}).get("winner"):
                return False
    return True

def check_session_completion_time(sess):
    if sess.get("is_liga"): return
    if is_session_completed(sess) and not sess.get("end_time"): 
        sess["end_time"] = get_local_time_str()

def smart_sync_and_save(updated_sessions):
    for sess in updated_sessions: check_session_completion_time(sess)
    fresh_data = load_data()
    if fresh_data:
        existing_ids = {s["id"] for s in fresh_data}
        for sess in updated_sessions:
            if sess["id"] not in existing_ids: fresh_data.append(sess)
            else:
                for idx, fs in enumerate(fresh_data):
                    if fs["id"] == sess["id"]: fresh_data[idx] = sess
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
    logo_loaded = False
    for logo_path in ["logo.png.png", "logo.png"]:
        try:
            st.image(logo_path, width=80)
            logo_loaded = True
            break
        except:
            pass

with c_title:
    st.markdown("<h1 style='margin: 0; padding-top: 8px; font-size: 1.8rem;'>Wehringer Steelers — Teamtraining</h1>", unsafe_allow_html=True)

c_mus, c_sync, c_dummy = st.columns([1, 1, 4])
with c_mus:
    try:
        with st.popover("🎵"): st.audio("vereinssong.mp3")
    except Exception: pass
with c_sync:
    if st.button("🔄", help="Manuell aktualisieren"):
        st.session_state.sessions_list = load_data(); st.rerun()

kader = [
    "Andreas Böhm", "Andrino Czombera", "Dennis Güttner", "Marco Eser", 
    "Maximilian Zientner", "Michael Kummer", "Michael Mak", "Michael Neumeier", 
    "Thomas Schaudt", "Wolfgang Scheider"
]

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

training_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga")]
liga_sessions = [s for s in st.session_state.sessions_list if s.get("is_liga")]

tab_übersicht, tab_kader, tab_session, tab_liga, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Freundschaftsspiele", "Match-Archiv", "Modus & Regeln"])

def get_or_create_teams(session, all_sessions):
    if "coop_teams" in session and session["coop_teams"]: return session["coop_teams"]
    spieler = [p for p in session.get("spieler", []) if p != "-"]
    prev_pairs, prev_resting = set(), set()
    all_sorted = sorted(all_sessions, key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
    try:
        s_idx = all_sorted.index(session)
        if s_idx + 1 < len(all_sorted):
            p_s = all_sorted[s_idx + 1]
            if "coop_teams" in p_s:
                for t in p_s["coop_teams"]:
                    pts = t.split("&")
                    if len(pts) == 2 and "-" not in t: prev_pairs.add(frozenset([pts[0].strip(), pts[1].strip()]))
                p_t = p_s.get("coop_teams", [])
                if len(p_t) % 2 != 0:
                    r_t_str = p_t[(p_s.get("total_rounds", 4) - (p_s.get("singles_rounds", 0) if p_s.get("modus") == "Standard-Training (Einzel + Coop)" else 0) - 1) % len(p_t)]
                    for p in r_t_str.split("&"): 
                        if p.strip() and p.strip() != "-": prev_resting.add(p.strip())
            else:
                p_sp = [p for p in p_s.get("spieler", []) if p != "-"]
                for i in range(0, len(p_sp)-1, 2): prev_pairs.add(frozenset([p_sp[i], p_sp[i+1]]))
    except: pass
    import random
    best_teams = []
    for _ in range(50):
        shuffled = spieler.copy(); random.shuffle(shuffled); c_teams = []; has_forb = False
        for i in range(0, len(shuffled)-1, 2):
            p1, p2 = shuffled[i], shuffled[i+1]
            if frozenset([p1, p2]) in prev_pairs: has_forb = True; break
            c_teams.append(f"{p1} & {p2}")
        if len(shuffled) % 2 != 0: c_teams.append(f"{shuffled[-1]} & -")
        best_teams = c_teams
        if not has_forb: break
    if len(best_teams) % 2 != 0 and prev_resting:
        for _ in range(len(best_teams)):
            if not any(p in prev_resting for p in [p.strip() for p in best_teams[0].split("&") if p.strip() != "-"]): break
            best_teams = best_teams[1:] + [best_teams[0]]
    session["coop_teams"] = best_teams
    return best_teams

def get_boards_list(session, round_num=None):
    boards_count = session.get("boards_count", 6)
    modus = session.get("modus", "Up & Down")
    is_std = (modus == "Standard-Training (Einzel + Coop)")
    total = session.get("total_rounds", 6 if is_std else 4)
    singles = session.get("singles_rounds", total - 2 if total > 2 else 4)
    if (is_std and round_num is not None and round_num > singles) or modus == "Koop 2vs2 (Up & Down)": return ["Kaiser B1", "Board 2"]
    return ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"][:boards_count]

def get_board_players(session, round_num, board_name):
    boards = get_boards_list(session, round_num)
    if board_name not in boards: return ["-", "-"]
    b_idx = boards.index(board_name)
    modus = session.get("modus", "Up & Down")
    is_2v2 = (modus == "Koop 2vs2 (Up & Down)"); is_std = (modus == "Standard-Training (Einzel + Coop)")
    total = session.get("total_rounds", 6 if is_std else 4); singles = session.get("singles_rounds", total - 2 if total > 2 else 4)
    in_coop = is_std and round_num > singles
    spieler = session["spieler"].copy()
    
    if round_num == 1 and not in_coop and not is_2v2:
        all_s = sorted([s for s in st.session_state.sessions_list if not s.get("is_liga")], key=lambda x: int(x['id'].split('-')[1]) if 'id' in x and '-' in x['id'] else 0, reverse=True)
        try: s_idx = all_s.index(session)
        except: s_idx = 0
        if s_idx + 1 < len(all_s) and "results" in all_s[s_idx + 1]:
            p_s = all_s[s_idx + 1]
            target_r = p_s.get("singles_rounds", p_s.get("total_rounds", 4) - 2) if p_s.get("modus") == "Standard-Training (Einzel + Coop)" else p_s.get("total_rounds", 4)
            p_top = []
            for pb in get_boards_list(p_s, target_r):
                m_inf = p_s.get("results", {}).get((target_r, pb))
                p1, p2 = (m_inf.get("winner", "-"), m_inf.get("loser", "-")) if m_inf else get_board_players(p_s, target_r, pb)
                if p1 != "-" and p1 not in p_top: p_top.append(p1)
                if p2 != "-" and p2 not in p_top: p_top.append(p2)
            ord_p = [p for p in spieler if p not in p_top] + [p for p in reversed(p_top) if p in spieler]
            spieler = (ord_p + [p for p in spieler if p not in ord_p])[:len(spieler)]

    if is_2v2 or in_coop:
        teams = get_or_create_teams(session, [s for s in st.session_state.sessions_list if not s.get("is_liga")]); n_t = len(teams)
        rel_r = (round_num - singles) if in_coop else round_num
        rest_idx = (rel_r - 1) % n_t if n_t % 2 != 0 else -1
        act = [t for i, t in enumerate(teams) if i != rest_idx]
        if rel_r == 1:
            if b_idx < len(act) // 2: return [act[b_idx * 2], act[b_idx * 2 + 1] if b_idx * 2 + 1 < len(act) else "-"]
            return ["-", "-"]
        w, l = {}, {}; p_r = round_num - 1
        for b in boards:
            m = session.get("results", {}).get((p_r, b))
            w[b], l[b] = (m["winner"], m["loser"]) if m and m.get("winner") else ("-", "-")
        if b_idx == 0: return [w.get("Kaiser B1", act[0] if act else "-"), w.get("Board 2", act[1] if len(act) > 1 else "-")]
        elif b_idx == 1 and len(boards) > 1: return [l.get("Kaiser B1", act[2] if len(act) > 2 else "-"), l.get("Board 2", act[3] if len(act) > 3 else "-")]
        return ["-", "-"]
    else:
        if round_num == 1:
            pairs = []
            for i in range(0, min(session.get("boards_count", 6) * 2, len(spieler) - len(spieler) % 2), 2): pairs.append((spieler[i], spieler[i+1]))
            while len(pairs) <= b_idx: pairs.append((spieler[0] if spieler else "-", spieler[1] if len(spieler) > 1 else "-"))
            if len(spieler) % 2 != 0: pairs[-1] = (spieler[-1], "-")
            return list(pairs[b_idx])
        w, l = {}, {}; p_r = round_num - 1
        for b in boards:
            m = session.get("results", {}).get((p_r, b))
            w[b], l[b] = (m["winner"], m["loser"]) if m and m.get("winner") else ("-", "-")
        if b_idx == 0: return [w.get("Kaiser B1", "-"), w.get("Board 2", "-") if len(boards) > 1 else w.get("Kaiser B1", "-")]
        p_b = boards[b_idx - 1]; n_b = boards[b_idx + 1] if b_idx + 1 < len(boards) else None
        return [l.get(p_b, "-"), w.get(n_b, l.get(boards[b_idx], "-")) if n_b else l.get(boards[b_idx], "-")]

def is_board_ready(session, board_name, next_r):
    if next_r == 1: return True
    modus = session.get("modus", "Up & Down"); total = session.get("total_rounds", 4)
    singles = session.get("singles_rounds", total - 2 if modus == "Standard-Training (Einzel + Coop)" and total > 2 else total)
    if modus == "Standard-Training (Einzel + Coop)" and next_r == singles + 1:
        for r in range(1, singles + 1):
            for rb in get_boards_list(session, 1):
                if not session.get("results", {}).get((r, rb), {}).get("winner"): return False
        return True
    boards = get_boards_list(session, next_r)
    if board_name not in boards: return False
    b_idx = boards.index(board_name); req = []
    if b_idx == 0: req = [boards[0]] + ([boards[1]] if len(boards) > 1 else [])
    else: req = [boards[b_idx - 1]] + ([boards[b_idx + 1]] if b_idx + 1 < len(boards) else [boards[b_idx]])
    for rb in req:
        if not session.get("results", {}).get((next_r - 1, rb), {}).get("winner"): return False
    return True

@st.dialog("🔄 Spieler auswechseln")
def open_substitution_dialog(board_name, session_id, round_num, slot_num, current_player):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    alle_spieler = sorted(list(set(sess.get("spieler", kader) + [current_player, "-"])))
    idx = alle_spieler.index(current_player) if current_player in alle_spieler else 0
    new_sel = st.selectbox("Kader:", alle_spieler, index=idx)
    new_txt = st.text_input("Gast:")
    c1, c2 = st.columns(2)
    if c1.button("Abbrechen", use_container_width=True): st.rerun()
    if c2.button("Speichern", type="primary", use_container_width=True):
        final_name = new_txt.strip() if new_txt.strip() else new_sel
        res = sess.setdefault("results", {})
        if (round_num, board_name) not in res:
            ap = get_board_players(sess, round_num, board_name)
            res[(round_num, board_name)] = {"s1": ap[0], "s2": ap[1], "ergebnis": "0:0", "winner": "", "loser": "", "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0}
        res[(round_num, board_name)]["s1" if slot_num == 1 else "s2"] = final_name
        smart_sync_and_save(st.session_state.sessions_list); st.rerun()

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
        st.info(f"ℹ️ Standard-Training: {singles_rounds} Runden Einzel + {coop_rounds} Runden Doppel (Coop).")
    elif spielmodus == "Koop 2vs2 (Up & Down)":
        singles_rounds, coop_rounds = 0, st.selectbox("Anzahl Koop-Runden", list(range(1, 11)), index=1)
        total_rounds = coop_rounds
    else:
        singles_rounds, coop_rounds = 0, 0
        total_rounds = st.selectbox("Anzahl Runden", list(range(1, 11)), index=3)
        
    anzahl_boards = st.selectbox("Anzahl der Boards (für Einzel)", ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"], index=2)
    
    st.write("### Anwesende Spieler")
    anwesende = []
    cols = st.columns(2)
    half = len(kader) // 2
    with cols[0]:
        for spieler in kader[:half]:
            if st.checkbox(spieler, value=True, key=f"form_kader_{spieler}"): anwesende.append(spieler)
    with cols[1]:
        for spieler in kader[half:]:
            if st.checkbox(spieler, value=True, key=f"form_kader_{spieler}"): anwesende.append(spieler)
                
    st.write("### Gastspieler (optional)")
    g1 = st.text_input("Gastspieler 1", key="form_gast_1")
    g2 = st.text_input("Gastspieler 2", key="form_gast_2")
    gaeste = [x for x in [g1, g2] if x.strip() != ""]
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

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with col_b2:
        if st.button("Session starten", type="primary", use_container_width=True, disabled=not can_save):
            if can_save:
                max_id = max([int(s["id"].split("-")[1]) for s in st.session_state.sessions_list if "-" in s["id"] and s["id"].split("-")[1].isdigit()] + [0])
                new_session = {
                    "id": f"S-{max_id + 1}", "datum": session_datum.strftime("%d.%m.%Y"),
                    "start_time": None, "end_time": None, "modus": spielmodus,
                    "boards_count": gewaehlte_boards_zahl,
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

    session_datum = st.date_input("Datum", curr_date, key=f"edit_date_{session_id}")
    col_t1, col_t2 = st.columns(2)
    edit_start_time = col_t1.text_input("Startzeit (HH:MM)", value=sess.get("start_time") or "")
    edit_end_time = col_t2.text_input("Endzeit (HH:MM)", value=sess.get("end_time") or "")

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
            if st.checkbox(sp, value=(sp in sess.get("spieler", []))): anwesende.append(sp)
                
    curr_gaeste = sess.get("gaeste", [])
    gaeste = [x for x in [st.text_input(f"Gast {i+1}", value=curr_gaeste[i] if i<len(curr_gaeste) else "") for i in range(2)] if x.strip() != ""]
    aktive_spieler = anwesende + gaeste
    
    can_save = len(aktive_spieler) >= 2 and int(anzahl_boards.split()[0]) <= get_max_boards_for_players(len(aktive_spieler))
    if not can_save: st.error("Bitte überprüfe Spieler/Board Verhältnis!")

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c_btn2:
        if st.button("Speichern", type="primary", use_container_width=True, disabled=not can_save):
            if can_save:
                sess.update({
                    "datum": session_datum.strftime("%d.%m.%Y"),
                    "start_time": edit_start_time.strip() or None, "end_time": edit_end_time.strip() or None,
                    "modus": spielmodus, "boards_count": int(anzahl_boards.split()[0]),
                    "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds,
                    "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus,
                    "spieler": aktive_spieler, "gaeste": gaeste
                })
                st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("📋 Board-Erfassung & Tracking")
def open_board_dialog(board_name, session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    total_rounds = sess.get("total_rounds", 4)
    leg_modus = sess.get("modus_leg", "Best of 5")
    res = sess.setdefault("results", {})
    completed_rounds = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
    current_round = max(completed_rounds) + 1 if completed_rounds else 1
    
    if current_round > total_rounds:
        st.warning(f"{board_name} hat alle Runden beendet.")
        if st.button("Schließen", use_container_width=True): st.rerun()
        return

    modus = sess.get("modus", "Up & Down")
    is_std = (modus == "Standard-Training (Einzel + Coop)")
    singles_rounds = sess.get("singles_rounds", total_rounds - 2 if is_std and total_rounds > 2 else total_rounds)
    r_disp = f"Doppelrunde {current_round - singles_rounds} (Coop)" if is_std and current_round > singles_rounds else f"Runde {current_round}"

    st.write(f"### {board_name} — {r_disp}")
    em = res.get((current_round, board_name))
    
    if em:
        p1, p2 = em.get("s1", "-"), em.get("s2", "-")
        try: s1, s2 = map(int, em.get("ergebnis", "0:0").split(":"))
        except: s1, s2 = 0, 0
        t1, t2 = int(em.get("180_s1", 0)), int(em.get("180_s2", 0))
        a1, a2 = float(em.get("avg_s1", 0.0)), float(em.get("avg_s2", 0.0))
    else:
        ap = get_board_players(sess, current_round, board_name)
        p1, p2, s1, s2, t1, t2, a1, a2 = ap[0], ap[1], 0, 0, 0, 0, 0.0, 0.0

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**Heim:** `{p1}`")
        in_score1 = st.number_input("Legs Heim", 0, 5, s1)
        in_180_1 = st.number_input("🎯 180 Heim", 0, 20, t1)
        in_avg_1 = st.number_input("📊 Avg Heim", 0.0, 180.0, a1, step=0.1)
    with c2:
        st.markdown(f"**Gast:** `{p2}`")
        in_score2 = st.number_input("Legs Gast", 0, 5, s2)
        in_180_2 = st.number_input("🎯 180 Gast", 0, 20, t2)
        in_avg_2 = st.number_input("📊 Avg Gast", 0.0, 180.0, a2, step=0.1)
        
    req_w = 3 if leg_modus == "Best of 5" else 2
    is_v = True
    if p1 != "-" and p2 != "-":
        if in_score1 == in_score2 or in_score1 > req_w or in_score2 > req_w or (in_score1 != req_w and in_score2 != req_w):
            st.error(f"Sieger braucht genau {req_w} Legs!"); is_v = False
            
    cb1, cb2 = st.columns(2)
    if cb1.button("Speichern", type="primary", use_container_width=True, disabled=not is_v):
        res[(current_round, board_name)] = {
            "s1": p1, "s2": p2, "ergebnis": f"{in_score1}:{in_score2}",
            "winner": p1 if in_score1 > in_score2 else p2, "loser": p2 if in_score1 > in_score2 else p1,
            "180_s1": in_180_1, "180_s2": in_180_2, "avg_s1": in_avg_1, "avg_s2": in_avg_2
        }
        st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()
    if cb2.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("📊 Spielablauf & Rundenübersicht")
def open_session_archive_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    total_rounds = sess.get("total_rounds", 4)
    res = sess.get("results", {})
    modus = sess.get("modus", "Up & Down")
    is_std = (modus == "Standard-Training (Einzel + Coop)")
    singles = sess.get("singles_rounds", total_rounds - 2 if is_std and total_rounds > 2 else total_rounds)
    
    if not res: st.info("Noch keine Matches erfasst.")
    else:
        for r in range(1, total_rounds + 1):
            st.markdown(f"#### 🎯 Runde {r}")
            for b_name in get_boards_list(sess, r):
                m_inf = res.get((r, b_name))
                p_list = get_board_players(sess, r, b_name) if not m_inf else [m_inf.get("s1", "–"), m_inf.get("s2", "–")]
                erg = m_inf.get("ergebnis", "–") if m_inf else "Ausstehend"
                win = m_inf.get("winner", "–") if m_inf else "–"
                with st.container(border=True):
                    st.write(f"**{b_name}**: {p_list[0]} vs {p_list[1]} ➔ **{erg}** (Sieger: {win})")
    if st.button("Schließen", use_container_width=True): st.rerun()

@st.dialog("📊 Session Endstand & Zusammenfassung")
def open_session_summary_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    st.caption(f"Modus: {sess['modus']}")
    
    res = sess.get("results", {})
    if res:
        st.markdown("#### 🎯 Letzte Einzel-Phase")
        last_r = max([r for (r, b), i in res.items() if i.get("winner") and r <= sess.get("singles_rounds", sess.get("total_rounds", 4))] + [0])
        if last_r > 0:
            for b_name in get_boards_list(sess, last_r):
                m = res.get((last_r, b_name))
                if m and m.get("winner"):
                    with st.container(border=True):
                        st.write(f"**{b_name}** | 🥇 {m.get('winner')} | 🥈 {m.get('loser')}")
    if st.button("Schließen", use_container_width=True): st.rerun()

def get_liga_config(sess):
    t_size = sess.get("team_size", 4)
    b_count = sess.get("boards_count", 2)
    if t_size == 6:
        s = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"), ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4"), ("m5", "Einzel 5", "h5", "g5"), ("m6", "Einzel 6", "h6", "g6")]
        c = [("m7", "Kreuz-Einzel 1", "h1", "g4"), ("m8", "Kreuz-Einzel 2", "h2", "g5"), ("m9", "Kreuz-Einzel 3", "h3", "g6"), ("m10", "Kreuz-Einzel 4", "h4", "g1"), ("m11", "Kreuz-Einzel 5", "h5", "g2"), ("m12", "Kreuz-Einzel 6", "h6", "g3")]
        d = [("m13", "Doppel 1", "hd1", "gd1"), ("m14", "Doppel 2", "hd2", "gd2"), ("m15", "Doppel 3", "hd3", "gd3")]
    else:
        s = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"), ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")]
        c = [("m5", "Kreuz-Einzel 5", "h1", "g2"), ("m6", "Kreuz-Einzel 6", "h2", "g1"), ("m7", "Kreuz-Einzel 7", "h3", "g4"), ("m8", "Kreuz-Einzel 8", "h4", "g3")]
        d = [("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
    r = []
    for bl in [s, c, d]:
        for i in range(0, len(bl), b_count): r.append(bl[i:i + b_count])
    return r

@st.dialog("➕ Neues Freundschaftsspiel starten", width="large")
def open_new_liga_match_dialog():
    dt = st.date_input("Datum des Spiels", date.today())
    ht = st.text_input("Heimmannschaft", value="Wehringer Steelers")
    gt = st.text_input("Gastmannschaft", placeholder="z.B. DC Irgendwas")
    
    mode = st.radio("Spielmodus", ["🏆 Standard Liga-Spiel (4er Team, 2 Boards)", "⚙️ Freies Spiel auf Liga-Basis (flexibel)"])
    if "Standard" in mode:
        ts, bc = 4, 2
    else:
        ts = 6 if "6er" in st.selectbox("Team-Größe", ["4er-Team", "6er-Team"]) else 4
        bc = st.selectbox("Anzahl paralleler Boards", [1, 2, 3, 4, 5, 6], index=1)
        
    st.write("Wähle die Boards aus (von links nach rechts):")
    opts = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    c_b = st.columns(min(bc, 4))
    b_names = []
    for i in range(bc):
        with c_b[i % len(c_b)]:
            b_names.append(st.selectbox(f"Board {i+1}", opts, index=i, key=f"nb_{i}"))
            
    if st.button("Spiel erstellen", type="primary", use_container_width=True):
        nid = f"L-{max([int(s['id'].split('-')[1]) for s in st.session_state.sessions_list if 'L-' in s['id'] and s['id'].split('-')[1].isdigit()] + [0]) + 1}"
        ns = {
            "id": nid, "datum": dt.strftime("%d.%m.%Y"), "is_liga": True, 
            "team_size": ts, "boards_count": bc, "heim_team": ht.strip(), 
            "gast_team": gt.strip(), "liga_boards": b_names, 
            "auf_heim": {}, "auf_gast": {}, "results": {}
        }
        st.session_state.sessions_list.append(ns)
        smart_sync_and_save(st.session_state.sessions_list)
        st.rerun()

@st.dialog("⚙️ Freundschaftsspiel bearbeiten")
def open_edit_liga_session_dialog(session_id):
    pwd = st.text_input("Passwort eingeben", type="password")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return
    
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
    t_size = sess.get("team_size", 4)
    ins = [st.text_input(f"Pos {i+1}", value=sess.get("auf_heim" if is_heim else "auf_gast", {}).get(f"{'h' if is_heim else 'g'}{i+1}", ""), key=f"e_{is_heim}_{session_id}_{i}") for i in range(t_size)]
    if st.button("Speichern", type="primary"):
        if all(x.strip() for x in ins):
            d = sess.setdefault("auf_heim" if is_heim else "auf_gast", {})
            for i, v in enumerate(ins): d[f"{'h' if is_heim else 'g'}{i+1}"] = v.strip()
            st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()
        else: st.error(f"Alle {t_size} füllen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    nd = 3 if sess.get("team_size", 4) == 6 else 2
    opts = list(set([v for k,v in (sess.get("auf_heim",{}) if is_heim else sess.get("auf_gast",{})).items() if "d" not in k and v and v != "-"])) + ["+ Anderer..."]
    
    d_data = []
    for i in range(nd):
        st.markdown(f"**Doppel {i+1}**")
        c1, c2 = st.columns(2)
        s1 = c1.selectbox(f"Sp1 (D{i+1})", opts, key=f"d1_{session_id}_{i}")
        p1 = c1.text_input("Name", key=f"t1_{session_id}_{i}") if s1 == "+ Anderer..." else s1
        s2 = c2.selectbox(f"Sp2 (D{i+1})", opts, key=f"d2_{session_id}_{i}")
        p2 = c2.text_input("Name", key=f"t2_{session_id}_{i}") if s2 == "+ Anderer..." else s2
        d_data.append((p1.strip() if p1 else "", p2.strip() if p2 else ""))
        
    all_p = [p for pair in d_data for p in pair if p and p != "+ Anderer..."]
    dups = [item for item, count in collections.Counter(all_p).items() if count > 1]
    
    if dups:
        st.error(f"🚨 Fehler: Der Spieler '{dups[0]}' steht in mehreren Feldern!")
        
    if st.button("Speichern", type="primary", disabled=bool(dups)):
        if len(all_p) < nd * 2: st.error("Alle Felder füllen!")
        else:
            d = sess.setdefault("auf_heim" if is_heim else "auf_gast", {})
            for i, (p1, p2) in enumerate(d_data): d[f"{'hd' if is_heim else 'gd'}{i+1}"] = f"{p1} & {p2}"
            st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("🔄 Auswechseln")
def open_liga_sub_dialog(session_id, key, is_heim, curr_name):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    nn = st.text_input(f"Neuer Name für {curr_name}:")
    if st.button("Speichern", type="primary") and nn.strip():
        (sess["auf_heim"] if is_heim else sess["auf_gast"])[key] = nn.strip()
        st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("🎯 Live Board")
def open_liga_live_board_dialog(session_id, m_key, board_name, m_label, p_l, p_r, is_right_board):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    res = sess.setdefault("results", {}).setdefault(m_key, {})
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**{'Gast' if is_right_board else 'Heim'} (Anwurf links):** `{p_l}`")
        l1 = st.number_input(f"Legs {p_l}", 0, 3, res.get("lg" if is_right_board else "lh", 0))
        t1 = st.number_input(f"180er {p_l}", 0, 10, res.get("180_g" if is_right_board else "180_h", 0))
    with c2:
        st.markdown(f"**{'Heim' if is_right_board else 'Gast'}:** `{p_r}`")
        l2 = st.number_input(f"Legs {p_r}", 0, 3, res.get("lh" if is_right_board else "lg", 0))
        t2 = st.number_input(f"180er {p_r}", 0, 10, res.get("180_h" if is_right_board else "180_g", 0))
    
    is_v = (l1 == 3 and l2 < 3) or (l2 == 3 and l1 < 3)
    if st.button("Speichern", type="primary", disabled=not is_v):
        if is_right_board: res.update({"lg": l1, "lh": l2, "played": True, "180_g": t1, "180_h": t2})
        else: res.update({"lh": l1, "lg": l2, "played": True, "180_h": t1, "180_g": t2})
        st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("📝 Bericht & Abschluss", width="large")
def open_liga_bericht_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    res = sess.setdefault("results", {})
    all_v = True
    for mk, lab, hk, gk in [m for r in get_liga_config(sess) for m in r]:
        md = res.setdefault(mk, {})
        c1, c2 = st.columns(2)
        lh = c1.number_input(f"{lab} Heim", 0, 3, md.get("lh", 0), key=f"lh_{mk}")
        lg = c2.number_input(f"{lab} Gast", 0, 3, md.get("lg", 0), key=f"lg_{mk}")
        if (lh > 0 or lg > 0) and not ((lh==3 and lg<3) or (lg==3 and lh<3)): st.error(f"{lab} fehlerhaft!"); all_v = False
        md.update({"lh": lh, "lg": lg, "played": lh>0 or lg>0})
    lk = st.checkbox("🔒 Spiel abschließen", sess.get("is_locked", False))
    if st.button("Speichern", type="primary", disabled=not all_v):
        sess["is_locked"] = lk; st.session_state.sessions_list[real_idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

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

def generate_spielbericht_pdf(sess):
    import io; import os
    try: from pypdf import PdfReader, PdfWriter; from reportlab.pdfgen import canvas; from reportlab.lib.pagesizes import A4
    except: return None
    pac = io.BytesIO(); c = canvas.Canvas(pac, pagesize=A4); c.setFont("Helvetica-Bold", 9)
    c.drawString(410, 755, sess.get("datum", "")); c.drawString(100, 722, sess.get("heim_team", "")); c.drawString(330, 722, sess.get("gast_team", ""))
    yc = {"m1": 630, "m2": 585, "m3": 540, "m4": 495, "m5": 450, "m6": 405, "m7": 360, "m8": 315, "m9": 270, "m10": 225, "m11": 180, "m12": 135, "m13": 90, "m14": 65, "m15": 40} if sess.get("team_size") == 6 else {"m1": 630, "m2": 585, "m3": 540, "m4": 495, "m5": 415, "m6": 370, "m7": 325, "m8": 280, "m9": 200, "m10": 155}
    for mk, lab, hk, gk in [m for r in get_liga_config(sess) for m in r]:
        if sess.get("results", {}).get(mk, {}).get("played"):
            y = yc.get(mk, 500); md = sess["results"][mk]
            c.drawString(65, y, str(sess.get("auf_heim", {}).get(hk, ""))); c.drawString(315, y, str(sess.get("auf_gast", {}).get(gk, "")))
            c.drawString(225, y, str(md.get("lh", 0))); c.drawString(285, y, str(md.get("lg", 0)))
    c.save(); pac.seek(0); out = io.BytesIO()
    if os.path.exists("Bez_Schwaben_Spielbericht.pdf"):
        pw = PdfWriter(); pr = PdfReader(open("Bez_Schwaben_Spielbericht.pdf", "rb")); pg = pr.pages[0]; pg.merge_page(PdfReader(pac).pages[0]); pw.add_page(pg); pw.write(out)
    out.seek(0); return out

with tab_übersicht:
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session", type="primary", use_container_width=True, key="quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        all_sessions_sorted = sorted(st.session_state.sessions_list, key=lambda x: int(x['id'].split('-')[1]) if '-' in x['id'] else 0, reverse=True)
        active_sessions_for_btn = [s for s in all_sessions_sorted if not s.get("is_liga") and not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Bearbeiten", use_container_width=True, key="edit_active_btn"):
                open_edit_session_dialog(active_sessions_for_btn[0]["id"])
        else:
            st.button("⚙️ Bearbeiten", use_container_width=True, disabled=True)
            
    st.write("")
    st.markdown("### 🔴 Laufende Trainings-Session")
    if not active_sessions_for_btn:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        if len(active_sessions_for_btn) > 1:
            session_options = {f"{s['id']} ({s['datum']} – {s['modus']})": s for s in active_sessions_for_btn}
            selected_label = st.selectbox("Aktive Session wählen:", list(session_options.keys()), key="select_active_session_dropdown")
            curr_sess = session_options[selected_label]
        else:
            curr_sess = active_sessions_for_btn[0]

        start_t = curr_sess.get("start_time")
        if not start_t:
            st.info(f"Session **{curr_sess['id']}** wurde erstellt für den **{curr_sess['datum']}**.")
            st.write(f"👥 **Gemeldete Spieler:** {', '.join(curr_sess.get('spieler', []))}")
            st.write("")
            if st.button("🚀 Teamtraining starten", type="primary", use_container_width=True, key="start_training_btn"):
                curr_sess["start_time"] = get_local_time_str()
                smart_sync_and_save(st.session_state.sessions_list); st.rerun()
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
                all_b_names = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
                base_boards = all_b_names[:bc]
                singles_complete = True
                for b in base_boards:
                    board_completed_r = max([r for (r, board_n), v in res.items() if board_n == b and v.get("winner")] + [0])
                    if board_completed_r < singles_rounds: singles_complete = False; break
                active_boards_list = ["Kaiser B1", "Board 2"] if (singles_complete and singles_rounds > 0 and any(r <= singles_rounds for (r, b), v in res.items())) else base_boards
            else: active_boards_list = get_boards_list(curr_sess, 1)
            
            for b_name in active_boards_list:
                completed_r_for_board = [r for (r, b), v in res.items() if b == b_name and v.get("winner")]
                next_r_for_board = max(completed_r_for_board) + 1 if completed_r_for_board else 1
                
                with st.container(border=True):
                    st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                    if next_r_for_board <= total_rounds:
                        ready = is_board_ready(curr_sess, b_name, next_r_for_board)
                        ampel = "🟢 Spielbar" if ready else "🔴 Wartet"
                        st.markdown(f"<p style='text-align: center; font-weight: bold; font-size: 1.1em; margin-top: 5px; margin-bottom: 0;'>{ampel}</p>", unsafe_allow_html=True)
                        
                        existing_match = res.get((next_r_for_board, b_name))
                        if existing_match: p1, p2 = existing_match.get("s1", "-"), existing_match.get("s2", "-")
                        else: players_now = get_board_players(curr_sess, next_r_for_board, b_name); p1, p2 = players_now[0], players_now[1]
                        
                        r_head_board = f"Doppelrunde {next_r_for_board - singles_rounds}/{total_rounds - singles_rounds} (Coop)" if is_standard_training and next_r_for_board > singles_rounds else f"Runde {next_r_for_board}/{singles_rounds} (Einzel)" if is_standard_training else f"Runde {next_r_for_board}/{total_rounds}"
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>{r_head_board}</p>", unsafe_allow_html=True)
                        
                        sc1, sc2 = st.columns([5, 2])
                        sc1.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p1}</div>", unsafe_allow_html=True)
                        with sc2:
                            if st.button("🔄", key=f"sub1_{b_name}_{next_r_for_board}", help="Wechsel"): open_substitution_dialog(b_name, curr_sess['id'], next_r_for_board, 1, p1)
                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 2px 0;'>VS</div>", unsafe_allow_html=True)
                        sc3, sc4 = st.columns([5, 2])
                        sc3.markdown(f"<div style='font-weight: bold; font-size: 0.95em; padding-top: 5px;'>{p2}</div>", unsafe_allow_html=True)
                        with sc4:
                            if st.button("🔄", key=f"sub2_{b_name}_{next_r_for_board}", help="Wechsel"): open_substitution_dialog(b_name, curr_sess['id'], next_r_for_board, 2, p2)
                        st.write("")
                        if st.button("🎯 Eintragen", key=f"live_{b_name}_{next_r_for_board}", use_container_width=True, disabled=not ready): open_board_dialog(b_name, curr_sess['id'])
                    else:
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle Runden beendet</p>", unsafe_allow_html=True)
                        st.success("✅ Abgeschlossen")

    # WICHTIG: Aus der Bedingung herausgelöst! Statistiken sind nun IMMER da.
    st.write("")
    st.divider()

    st.markdown("### 📊 Allgemeine Statistiken (Training)")
    total_180s = 0
    kaiser_winner_text = "Noch offen"
    anwesende_count = 0
    
    display_sess = None
    all_sessions_sorted = sorted(training_sessions, key=lambda x: int(x['id'].split('-')[1]) if '-' in x['id'] else 0, reverse=True)
    for s in all_sessions_sorted:
        if is_session_completed(s) or s.get("results"):
            display_sess = s; break
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
                count_180s = {}; match_avgs = []
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
                            if p in stats_temp: stats_temp[p]["Matches"] += 1; stats_temp[p]["Siege"] += 1
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
            for m in reversed(all_matches[-15:]):
                with st.container(border=True):
                    st.markdown(f"**{m['Datum']} - {m['Board']}** (Runde {m['Runde']})")
                    st.caption(f"⚔️ {m['Spieler']}")
                    st.markdown(f"Ergebnis: {m['Ergebnis']} | Sieger: **{m['Sieger']}**")
        else: st.info("Bisher wurden keine Board-Matches ausgetragen.")

with tab_kader:
    st.subheader("Kader & Spielerbilanz")
    st.write("Live berechnete Bilanz des festen Stammkaders.")
    
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0} for p in kader}
    player_matches_played, total_wins, total_losses = 0, 0, 0
    
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
                    if p in stats: stats[p]["Matches"] += 1; stats[p]["Siege"] += 1; player_matches_played += 1; total_wins += 1
            if loser and " & " not in loser:
                for p in loser.split(" & "):
                    if p in stats: stats[p]["Matches"] += 1; stats[p]["Niederlagen"] += 1; player_matches_played += 1; total_losses += 1

    total_games = total_wins + total_losses
    avg_win_rate = f"{(total_wins / total_games * 100):.0f}%" if total_games > 0 else "0%"
    all_team_avgs = [stats[p]["Avg_Sum"] / stats[p]["Avg_Count"] for p in kader if stats[p]["Avg_Count"] > 0]
    overall_team_avg = f"{(sum(all_team_avgs) / len(all_team_avgs)):.1f}" if all_team_avgs else "–"
    
    valid_players = [p for p in kader if stats[p]["Matches"] >= 3]
    mvp_help, dauerbrenner_help = None, None
    if valid_players:
        best_rate = max([(stats[p]["Siege"] / stats[p]["Matches"]) for p in valid_players])
        top_mvps = [p for p in valid_players if abs((stats[p]["Siege"] / stats[p]["Matches"]) - best_rate) < 1e-9]
        mvp_text = f"{(best_rate*100):.0f}% Siege"
        if len(top_mvps) == len(kader): mvp_player = "Alle gleichauf"
        elif len(top_mvps) <= 2: mvp_player = " & ".join(top_mvps)
        else: mvp_player, mvp_help = f"{len(top_mvps)} Spieler", "Aktuelle MVPs:\n\n" + "\n".join([f"- {p}" for p in top_mvps])
    else: mvp_player, mvp_text = "N/A", "Min. 3 Matches nötig"
        
    max_matches = max([stats[p]["Matches"] for p in kader], default=0)
    if max_matches > 0:
        top_active = [p for p in kader if stats[p]["Matches"] == max_matches]
        if len(top_active) == len(kader): active_player = "Alle gleichauf"
        elif len(top_active) <= 2: active_player = " & ".join(top_active)
        else: active_player, dauerbrenner_help = f"{len(top_active)} Spieler", "Aktuelle Dauerbrenner:\n\n" + "\n".join([f"- {p}" for p in top_active])
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
    table_rows = []
    for p in kader:
        m, s, n, lw, lv, t180, acount = stats[p]["Matches"], stats[p]["Siege"], stats[p]["Niederlagen"], stats[p]["Legs_Won"], stats[p]["Legs_Lost"], stats[p]["180er"], stats[p]["Avg_Count"]
        avg_val = f"{(stats[p]['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
        quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
        table_rows.append({"Spieler": p, "Matches": m, "Siege": s, "Niederlagen": n, "Siegquote": quote, "Legs Gewonnen": lw, "Legs Verloren": lv, "🎯 180er": t180, "📊 Ø Average": avg_val})
        
    for row in sorted(table_rows, key=lambda x: (x["Siege"], x["Legs Gewonnen"]), reverse=True):
        with st.container(border=True):
            st.markdown(f"**{row['Spieler']}** — Quote: **{row['Siegquote']}**")
            st.caption(f"🏆 Siege: {row['Siege']}/{row['Matches']} | 📊 Avg: {row['📊 Ø Average']} | 🎯 180er: {row['🎯 180er']} | Legs: {row['Legs Gewonnen']}:{row['Legs Verloren']}")

    with st.expander("🤝 Doppel-Paarungen (Coop-Statistik)", expanded=False):
        pair_stats = {}
        for sess in training_sessions:
            for match in sess.get("results", {}).values():
                winner, s1, s2 = match.get("winner", ""), match.get("s1", ""), match.get("s2", "")
                try: l1, l2 = map(int, match.get("ergebnis", "0:0").split(":"))
                except: l1, l2 = 0, 0
                h1, h2 = int(match.get("180_s1", 0)), int(match.get("180_s2", 0))
                a1, a2 = float(match.get("avg_s1", 0.0)), float(match.get("avg_s2", 0.0))
                
                def process_pair(pair_str, is_won, won_legs, lost_legs, h_count, avg_val):
                    if " & " in pair_str:
                        p_members = sorted([p.strip() for p in pair_str.split("&")])
                        pair_key = " & ".join(p_members)
                        if pair_key not in pair_stats: pair_stats[pair_key] = {"Matches": 0, "Siege": 0, "Niederlagen": 0, "Legs_Won": 0, "Legs_Lost": 0, "180er": 0, "Avg_Sum": 0.0, "Avg_Count": 0}
                        pair_stats[pair_key]["Matches"] += 1
                        if is_won: pair_stats[pair_key]["Siege"] += 1
                        else: pair_stats[pair_key]["Niederlagen"] += 1
                        pair_stats[pair_key]["Legs_Won"] += won_legs
                        pair_stats[pair_key]["Legs_Lost"] += lost_legs
                        pair_stats[pair_key]["180er"] += h_count
                        if avg_val > 0: pair_stats[pair_key]["Avg_Sum"] += avg_val; pair_stats[pair_key]["Avg_Count"] += 1

                if " & " in s1: process_pair(s1, (winner == s1), l1, l2, h1, a1)
                if " & " in s2: process_pair(s2, (winner == s2), l2, l1, h2, a2)

        pair_rows = []
        for pair_name, p_data in pair_stats.items():
            m, s, n, acount = p_data["Matches"], p_data["Siege"], p_data["Niederlagen"], p_data["Avg_Count"]
            quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
            avg_val = f"{(p_data['Avg_Sum'] / acount):.1f}" if acount > 0 else "–"
            pair_rows.append({"Doppel-Team": pair_name, "Matches": m, "Siege": s, "Niederlagen": n, "Siegquote": quote, "Legs Gewonnen": p_data["Legs_Won"], "Legs Verloren": p_data["Legs_Lost"], "🎯 180er": p_data["180er"], "📊 Ø Average": avg_val})
            
        if pair_rows:
            for row in sorted(pair_rows, key=lambda x: (x["Siege"], x["Legs Gewonnen"]), reverse=True):
                with st.container(border=True):
                    st.markdown(f"**{row['Doppel-Team']}** — Quote: **{row['Siegquote']}**")
                    st.caption(f"🏆 Siege: {row['Siege']}/{row['Matches']} | 📊 Avg: {row['📊 Ø Average']} | 🎯 180er: {row['🎯 180er']} | Legs: {row['Legs Gewonnen']}:{row['Legs Verloren']}")
        else: st.info("Bisher wurden keine Doppel- oder Koop-Matches ausgetragen.")

with tab_session:
    st.subheader("Up & Down Sessions")
    st.write("Aufstieg Richtung B1 und Abstieg Richtung B6.")
    
    total_anwesende = sum([len([p for p in s.get("spieler", []) if p != "-"]) for s in training_sessions])
    avg_anwesende = f"{(total_anwesende / len(training_sessions)):.1f}" if training_sessions else "0"
    
    kaiser_count = {}
    for sess in training_sessions:
        k_matches = [(r, m) for (r, b), m in sess.get("results", {}).items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "")]
        if k_matches:
            w = sorted(k_matches, key=lambda x: x[0], reverse=True)[0][1].get("winner")
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
    if st.button("➕ Neues Freundschaftsspiel starten", type="primary", use_container_width=True): open_new_liga_match_dialog()
    st.divider()
    
    active_liga = [l for l in liga_sessions if not l.get("is_locked", False)]
    completed_liga = [l for l in liga_sessions if l.get("is_locked", False)]
    
    if not active_liga: st.info("Keine aktiven Freundschaftsspiele vorhanden.")
    else:
        for l_sess in active_liga:
            heim, gast = l_sess.get("heim_team", "Heim"), l_sess.get("gast_team", "Gast")
            res, boards = l_sess.setdefault("results", {}), l_sess.get("liga_boards", ["Kaiser B1", "Board 2"])
            auf_h, auf_g = l_sess.setdefault("auf_heim", {}), l_sess.setdefault("auf_gast", {})
            sets_h, sets_g, legs_h, legs_g = 0, 0, 0, 0
            for m_data in res.values():
                if m_data.get("played"):
                    lh, lg = m_data.get("lh", 0), m_data.get("lg", 0)
                    legs_h += lh; legs_g += lg
                    if lh > lg: sets_h += 1
                    elif lg > lh: sets_g += 1
                    
            rounds_list = get_liga_config(l_sess)
            played_count = len([k for k, v in res.items() if v.get("played")])
            is_done = (played_count == sum([len(r) for r in rounds_list]))
            
            with st.container(border=True):
                st.markdown(f"### {heim} vs. {gast}")
                st.caption(f"{l_sess['datum']} | Status: {'✅ Abgeschlossen' if is_done else '🔴 Aktiv'}")
                st.markdown(f"**Sets:** {sets_h} : {sets_g} | **Legs:** {legs_h} : {legs_g}")
                
                t_size = l_sess.get("team_size", 4)
                h_ok, g_ok = bool(auf_h.get(f"h{t_size}")), bool(auf_g.get(f"g{t_size}"))
                
                if not h_ok or not g_ok:
                    st.warning(f"Phase 1: Alle {t_size} Einzelspieler eintragen (verdeckt)")
                    c_h, c_g = st.columns(2)
                    if not h_ok and c_h.button("🔒 Heim Aufstellen", key=f"hs_{l_sess['id']}"): open_liga_aufstellung_einzel(l_sess['id'], True)
                    if not g_ok and c_g.button("🔒 Gast Aufstellen", key=f"gs_{l_sess['id']}"): open_liga_aufstellung_einzel(l_sess['id'], False)
                elif not is_done:
                    curr_idx = next((i for i, rm in enumerate(rounds_list) if not all(res.get(m[0], {}).get("played") for m in rm)), len(rounds_list))
                    is_in_doubles = (curr_idx >= len(rounds_list) - (3 if t_size == 6 else 2))
                    
                    if is_in_doubles:
                        hd_ok, gd_ok = bool(auf_h.get("hd1")), bool(auf_g.get("gd1"))
                        if not hd_ok or not gd_ok:
                            st.warning("Phase 2: Doppel-Aufstellungen eintragen")
                            c_dh, c_dg = st.columns(2)
                            if not hd_ok and c_dh.button("🔒 Heim Doppel", key=f"hds_{l_sess['id']}"): open_liga_aufstellung_doppel(l_sess['id'], True)
                            if not gd_ok and c_dg.button("🔒 Gast Doppel", key=f"gds_{l_sess['id']}"): open_liga_aufstellung_doppel(l_sess['id'], False)
                    elif curr_idx >= 1:
                        if st.button("🔜 Doppel bereits jetzt aufstellen (Optional)", key=f"opt_d_{l_sess['id']}"): open_liga_aufstellung_doppel(l_sess['id'], True); open_liga_aufstellung_doppel(l_sess['id'], False)
                                
                    if curr_idx < len(rounds_list):
                        st.markdown(f"**Runde {curr_idx + 1} / {len(rounds_list)} läuft:**")
                        cols_boards = st.columns(min(len(rounds_list[curr_idx]), 3))
                        for i, (m_key, m_label, h_key, g_key) in enumerate(rounds_list[curr_idx]):
                            b_name = boards[i % len(boards)]
                            p_h, p_g = auf_h.get(h_key, "-"), auf_g.get(g_key, "-")
                            is_p = res.get(m_key, {}).get("played", False)
                            
                            with cols_boards[i % len(cols_boards)]:
                                with st.container(border=True):
                                    st.write(f"*{b_name}* — {m_label}")
                                    show_sub = not is_p and "Kreuz" in m_label
                                    
                                    if i % 2 == 1:
                                        st.markdown(f"Gast (links): **{p_g}**")
                                        if show_sub and not "d" in g_key:
                                            if st.button("🔄", key=f"sg_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_g)
                                        st.markdown(f"Heim: **{p_h}**")
                                        if show_sub and not "d" in h_key:
                                            if st.button("🔄", key=f"sh_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_h)
                                    else:
                                        st.markdown(f"Heim (links): **{p_h}**")
                                        if show_sub and not "d" in h_key:
                                            if st.button("🔄", key=f"sh_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], h_key, True, p_h)
                                        st.markdown(f"Gast: **{p_g}**")
                                        if show_sub and not "d" in g_key:
                                            if st.button("🔄", key=f"sg_{m_key}_{l_sess['id']}"): open_liga_sub_dialog(l_sess['id'], g_key, False, p_g)
                                    
                                    if is_p: st.success(f"Ergebnis: {res[m_key]['lh']}:{res[m_key]['lg']}")
                                    else:
                                        if st.button("🎯 Eintragen", key=f"lv_{m_key}_{l_sess['id']}", use_container_width=True):
                                            open_liga_live_board_dialog(l_sess['id'], m_key, b_name, m_label, p_g if i%2==1 else p_h, p_h if i%2==1 else p_g, is_right_board=(i%2==1))

                        if curr_idx + 1 < len(rounds_list):
                            with st.expander("👀 Vorschau nächste Runde (Auswechslungen vorbereiten)", expanded=False):
                                for ni, (nm_key, nm_label, nh_key, ng_key) in enumerate(rounds_list[curr_idx + 1]):
                                    np_h, np_g = auf_h.get(nh_key, "-"), auf_g.get(ng_key, "-")
                                    st.markdown(f"**{nm_label}**: {np_h} vs {np_g}")
                if is_done or (h_ok and g_ok):
                    st.divider()
                    if st.button("📝 Spielbericht ansehen & abschließen", key=f"l_ber_{l_sess['id']}", use_container_width=True): open_liga_bericht_dialog(l_sess['id'])

    st.write(""); st.markdown("### 🗄️ Abgeschlossene Freundschaftsspiele (PDF-Export)")
    if not completed_liga: st.info("Noch keine abgeschlossenen Freundschaftsspiele im Archiv.")
    else:
        for c_sess in completed_liga:
            with st.container(border=True):
                st.markdown(f"**{c_sess['datum']}** | 🏆 {c_sess.get('heim_team')} vs. {c_sess.get('gast_team')}")
                try:
                    pdf_file = generate_spielbericht_pdf(c_sess)
                    st.download_button(label="📥 Offiziellen Spielbericht als PDF laden", data=pdf_file, file_name=f"Spielbericht_{c_sess.get('heim_team')}_vs_{c_sess.get('gast_team')}.pdf", mime="application/pdf", key=f"dl_pdf_{c_sess['id']}")
                except Exception as e: st.error(f"PDF-Generierung fehlgeschlagen: {e}")

with tab_archiv:
    st.subheader("Match-Archiv & Session-Verwaltung")
    st.caption("Die neueste Session steht hier immer ganz oben. Inklusive automatischem Cloud-Backup und lokalem JSON-Download.")
    
    if st.session_state.sessions_list:
        safe_data_for_export = make_serializable(st.session_state.sessions_list)
        backup_json_str = json.dumps(safe_data_for_export, ensure_ascii=False, indent=2)
        st.download_button("📥 JSON Backup herunterladen", data=backup_json_str, file_name=f"steelers_backup_{date.today().strftime('%Y-%m-%d')}.json", mime="application/json", use_container_width=True)
        st.write("")

    if not st.session_state.sessions_list: st.info("Keine Sessions vorhanden.")
    else:
        all_sessions_sorted = sorted(st.session_state.sessions_list, key=lambda x: int(x['id'].split('-')[1]) if '-' in x['id'] and x['id'].split('-')[1].isdigit() else 0, reverse=True)
        for sess in all_sessions_sorted:
            is_l = sess.get("is_liga", False)
            with st.container(border=True):
                if is_l:
                    status_text = "✅ [Abgeschlossen]" if sess.get("is_locked", False) else "🔴 [Aktiv]"
                    st.markdown(f"**{sess['id']}** (Freundschaftsspiel) — {sess['datum']} {status_text}\n\n🏆 {sess.get('heim_team')} vs {sess.get('gast_team')}")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("📝 Spielbericht", key=f"alv_{sess['id']}", use_container_width=True): open_liga_bericht_dialog(sess['id'])
                    if c2.button("⚙️ Bearbeiten", key=f"ale_{sess['id']}", use_container_width=True): open_edit_liga_session_dialog(sess['id'])
                    if c3.button("🗑️ Löschen", key=f"ald_{sess['id']}", use_container_width=True): open_delete_session_dialog(sess['id'])
                else:
                    status_text = "✅ [Abgeschlossen]" if is_session_completed(sess) else "🔴 [Aktiv]"
                    st_t, en_t = sess.get("start_time"), sess.get("end_time")
                    time_str = f"🕒 {st_t} – {en_t} Uhr" if (st_t and en_t) else (f"🕒 Start: {st_t} Uhr" if st_t else "🕒 noch nicht gestartet")
                    st.markdown(f"**{sess['id']}** (Training) — {sess['datum']} ({time_str}) {status_text}")
                    c1, c2, c3 = st.columns(3)
                    if c1.button("📊 Ansehen", key=f"av_{sess['id']}", use_container_width=True): open_session_summary_dialog(sess['id'])
                    if c2.button("⚙️ Bearbeiten", key=f"ae_{sess['id']}", use_container_width=True): open_edit_session_dialog(sess['id'])
                    if c3.button("🗑️ Löschen", key=f"ad_{sess['id']}", use_container_width=True): open_delete_session_dialog(sess['id'])

                    st.divider()
                    if st.checkbox(f"⚡ Runden-Schnellerfassung & Korrektur (Admin)", key=f"blitz_{sess['id']}"):
                        if st.text_input("Admin-Passwort:", type="password", key=f"bp_{sess['id']}") == "1521":
                            st.markdown(f"#### ⚡ Schnellerfassung für {sess['id']}")
                            leg_modus = sess.get("modus_leg", "Best of 5")
                            for r in range(1, sess.get("total_rounds", 4) + 1):
                                st.markdown(f"**Runde {r}**")
                                for b_name in get_boards_list(sess, r):
                                    m_inf = sess.get("results", {}).get((r, b_name))
                                    p1, p2 = get_board_players(sess, r, b_name) if not m_inf else (m_inf.get("s1", "-"), m_inf.get("s2", "-"))
                                    try: s1, s2 = int(m_inf.get("ergebnis", "0:0").split(":")[0]) if m_inf else 0, int(m_inf.get("ergebnis", "0:0").split(":")[1]) if m_inf else 0
                                    except: s1, s2 = 0, 0
                                        
                                    with st.container(border=True):
                                        st.write(f"*{b_name}*")
                                        c_p1, c_vs, c_p2 = st.columns([4, 1, 4])
                                        c_p1.markdown(f"**{p1}**"); c_vs.markdown("vs"); c_p2.markdown(f"**{p2}**")
                                        c_in1, c_in2 = st.columns(2)
                                        val1 = c_in1.number_input("Legs Heim", 0, 5, s1, key=f"bl1_{sess['id']}_{r}_{b_name}")
                                        val2 = c_in2.number_input("Legs Gast", 0, 5, s2, key=f"bl2_{sess['id']}_{r}_{b_name}")
                                        
                                        cb1, cb2 = st.columns(2)
                                        if cb1.button("💾 Speichern", key=f"bs_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                            req_w = 3 if leg_modus == "Best of 5" else 2
                                            if p1 != "-" and p2 != "-" and (val1 == val2 or val1 > req_w or val2 > req_w or (val1 != req_w and val2 != req_w)): st.error(f"🚨 Sieger braucht exakt {req_w} Legs.")
                                            else:
                                                win, los = (p1, p2) if val1 > val2 else (p2, p1)
                                                sess.setdefault("results", {})[(r, b_name)] = sess.setdefault("results", {}).get((r, b_name), {"180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0})
                                                sess["results"][(r, b_name)].update({"s1": p1, "s2": p2, "ergebnis": f"{val1}:{val2}", "winner": win, "loser": los})
                                                smart_sync_and_save(st.session_state.sessions_list); st.rerun()
                                        if cb2.button("🗑️ Leeren", key=f"bd_{sess['id']}_{r}_{b_name}", use_container_width=True):
                                            if (r, b_name) in sess.get("results", {}):
                                                del sess["results"][(r, b_name)]; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

with tab_regeln:
    st.subheader("🎯 Modus & Regeln")
    st.write("Hier findet ihr die Anleitung für den Trainingsabend, den WhatsApp-Workflow, den Auf- und Abstieg sowie den Koop-Modus.")
    with st.container(border=True):
        st.markdown("### 📱 WhatsApp-Umfrage & Session-Start\n* **Die Umfrage:** Der Teamcoach startet vor jedem Teamtraining eine Umfrage in der WhatsApp-Gruppe.\n* **Der Startschuss:** Sobald die Rückmeldungen vorliegen, erstellt der Coach den Spieltag in der App über **➕ Neue Session**.")
    with st.container(border=True):
        st.markdown("### 👑 Das Up & Down Prinzip (Einzel)\n* **Das Prinzip:** Wer auf Kaiser B1 gewinnt, bleibt König oder steigt auf. Wer verliert, wandert ein Board nach unten.")
    with st.container(border=True):
        st.markdown("### 🤝 Der Koop-Modus (Feste 2v2-Teams & Up & Down)\n* **Zufällige Teams:** Es werden feste 2er-Paarungen per Zufall gebildet, die für die gesamte Session so zusammenbleiben.\n* **Wichtige Regel:** Es dürfen **keine exakt gleichen 2er-Paarungen** aus der Vorsession zusammen spielen (wird automatisch geprüft).\n* **Up & Down für Teams:** Gespielt wird auf Kaiser B1 und Board 2 im gewohnten Up & Down System.\n* **Anti-Doppel-Pause Schutz:** Spieler, die in der letzten Session als Letztes pausieren mussten, sind in der neuen Session in Runde 1 garantiert im Einsatz.")
    with st.container(border=True):
        st.markdown("### 💾 Automatisches Cloud-Backup & JSON-Download\n* **Cloud-Audit-Trail:** Nach jeder Änderung speichert die App vollautomatisch einen vollständigen Zeit-Snapshot in einem separaten Backup-Blatt (`backups`) in unserer Google-Tabelle.\n* **Lokales JSON-Backup:** Im Reiter **Match-Archiv** könnt ihr jederzeit ein lokales Backup laden.")
    with st.container(border=True):
        st.markdown("### 🚦 Die Ampel-Anzeige & Board-Begrenzung\n* 🟢 **Spielbar:** Euer Match steht fest – ihr könnt sofort loslegen!\n* 🔴 **Wartet:** Ihr müsst noch kurz auf die Nachbarboards warten.")
    with st.container(border=True):
        st.markdown("### ⏱️ Leg-Modus Validierung\n* **Best of 5:** Der Sieger benötigt exakt 3 Legs (3:0, 3:1, 3:2).\n* **Best of 3:** Der Sieger benötigt exakt 2 Legs (2:0, 2:1).")
