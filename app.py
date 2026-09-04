import streamlit as st
import pandas as pd
from datetime import date, datetime
import json
import collections
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

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

SHEET_URL = "https://docs.google.com/spreadsheets/d/1Z0TqSb-4qCES7gMrFv0MUCVdcnRV5kiaDCokzKTrr-8/edit?gid=0#gid=0"

@st.cache_resource
def init_connection():
    try:
        creds_dict = json.loads(st.secrets["google_json"])
        if "private_key" in creds_dict:
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
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
    if not sheet_conn: return []
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
        
        try: backup_ws = spreadsheet.worksheet("backups")
        except: backup_ws = spreadsheet.add_worksheet(title="backups", rows=100, cols=2); backup_ws.append_row(["Timestamp", "JSON_Data"])
        
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
        for b_name in get_boards_list(sess, r):
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

@st.dialog("➕ Neue Session starten")
def open_new_session_dialog():
    pwd = st.text_input("Passwort", type="password")
    if pwd != "1521":
        if pwd: st.error("Falsches Passwort!")
        return
    session_datum = st.date_input("Datum", date.today())
    leg_modus = st.selectbox("Leg-Modus", ["Best of 5", "Best of 3"])
    spielmodus = st.selectbox("Spielmodus", ["Standard-Training (Einzel + Coop)", "Up & Down", "Koop 2vs2 (Up & Down)"])
    if spielmodus == "Standard-Training (Einzel + Coop)":
        singles_rounds, coop_rounds = st.selectbox("Einzel-Runden", list(range(1, 11)), index=3), st.selectbox("Doppel-Runden", list(range(1, 11)), index=1)
        total_rounds = singles_rounds + coop_rounds
    elif spielmodus == "Koop 2vs2 (Up & Down)": singles_rounds, coop_rounds, total_rounds = 0, st.selectbox("Koop-Runden", list(range(1, 11)), index=1), 0; total_rounds = coop_rounds
    else: singles_rounds, coop_rounds, total_rounds = 0, 0, st.selectbox("Runden", list(range(1, 11)), index=3)
    anzahl_boards = st.selectbox("Boards (für Einzel)", ["6 Boards", "5 Boards", "4 Boards", "3 Boards", "2 Boards", "1 Board"], index=2)
    anwesende = [sp for sp in kader if st.checkbox(sp, value=True)]
    gaeste = [x for x in [st.text_input(f"Gast {i+1}") for i in range(4)] if x.strip()]
    aktive = anwesende + gaeste
    b_zahl = int(anzahl_boards.split()[0])
    max_b = len(aktive) // 2
    if len(aktive) < 2: st.error("Min 2 Spieler!"); return
    if b_zahl > max_b: st.error(f"Max {max_b} Boards möglich!"); return
    
    if st.button("Starten", type="primary", use_container_width=True):
        new_id = f"S-{max([int(s['id'].split('-')[1]) for s in st.session_state.sessions_list if '-' in s['id'] and s['id'].split('-')[1].isdigit()] + [0]) + 1}"
        ns = {"id": new_id, "datum": session_datum.strftime("%d.%m.%Y"), "start_time": None, "end_time": None, "modus": spielmodus, "boards_count": b_zahl, "singles_rounds": singles_rounds if spielmodus == "Standard-Training (Einzel + Coop)" else total_rounds, "total_rounds": total_rounds, "boards": anzahl_boards, "modus_leg": leg_modus, "spieler": aktive, "gaeste": gaeste, "results": {}, "is_liga": False}
        if "Koop" in spielmodus or "Standard" in spielmodus: get_or_create_teams(ns, [s for s in st.session_state.sessions_list if not s.get("is_liga")])
        st.session_state.sessions_list.append(ns); smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("⚙️ Session bearbeiten")
def open_edit_session_dialog(session_id):
    pwd = st.text_input("Passwort", type="password")
    if pwd != "1521":
        if pwd: st.error("Falsch!")
        return
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    idx = st.session_state.sessions_list.index(sess)
    try: curr_d = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_d = date.today()
    sess["datum"] = st.date_input("Datum", curr_d).strftime("%d.%m.%Y")
    sess["start_time"] = st.text_input("Start (HH:MM)", sess.get("start_time", "")) or None
    sess["end_time"] = st.text_input("End (HH:MM)", sess.get("end_time", "")) or None
    if st.button("Speichern", type="primary"):
        st.session_state.sessions_list[idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("📋 Match eintragen")
def open_board_dialog(board_name, session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    idx = st.session_state.sessions_list.index(sess)
    res = sess.setdefault("results", {})
    r_list = [r for (r, b), v in res.items() if b == board_name and v.get("winner")]
    cr = max(r_list) + 1 if r_list else 1
    if cr > sess.get("total_rounds", 4): st.warning("Alle Runden beendet"); return
    em = res.get((cr, board_name), {})
    p1, p2 = em.get("s1", "-"), em.get("s2", "-") if em else get_board_players(sess, cr, board_name)
    try: s1, s2 = map(int, em.get("ergebnis", "0:0").split(":"))
    except: s1, s2 = 0, 0
    c1, c2 = st.columns(2)
    l1 = c1.number_input("Legs Heim", 0, 5, s1)
    t1 = c1.number_input("180 Heim", 0, 20, int(em.get("180_s1", 0)))
    a1 = c1.number_input("Avg Heim", 0.0, 180.0, float(em.get("avg_s1", 0.0)))
    l2 = c2.number_input("Legs Gast", 0, 5, s2)
    t2 = c2.number_input("180 Gast", 0, 20, int(em.get("180_s2", 0)))
    a2 = c2.number_input("Avg Gast", 0.0, 180.0, float(em.get("avg_s2", 0.0)))
    req = 3 if sess.get("modus_leg", "Best of 5") == "Best of 5" else 2
    is_v = (l1 == req and l2 < req) or (l2 == req and l1 < req)
    if not is_v and p1 != "-" and p2 != "-": st.error(f"Genau {req} Legs für Sieger!")
    if st.button("Speichern", type="primary", disabled=not is_v):
        res[(cr, board_name)] = {"s1": p1, "s2": p2, "ergebnis": f"{l1}:{l2}", "winner": p1 if l1 > l2 else p2, "loser": p2 if l1 > l2 else p1, "180_s1": t1, "180_s2": t2, "avg_s1": a1, "avg_s2": a2}
        st.session_state.sessions_list[idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("📊 Session Endstand")
def open_session_summary_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    st.write(f"### Session {sess['id']} vom {sess['datum']}")
    st.markdown(f"**Modus:** {sess['modus']}")
    if st.button("Schließen", use_container_width=True): st.rerun()

def get_liga_config(sess):
    t_size, b_count = sess.get("team_size", 4), sess.get("boards_count", 2)
    if t_size == 6:
        s = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"), ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4"), ("m5", "Einzel 5", "h5", "g5"), ("m6", "Einzel 6", "h6", "g6")]
        c = [("m7", "Kreuz-Einzel 1", "h1", "g4"), ("m8", "Kreuz-Einzel 2", "h2", "g5"), ("m9", "Kreuz-Einzel 3", "h3", "g6"), ("m10", "Kreuz-Einzel 4", "h4", "g1"), ("m11", "Kreuz-Einzel 5", "h5", "g2"), ("m12", "Kreuz-Einzel 6", "h6", "g3")]
        d = [("m13", "Doppel 1", "hd1", "gd1"), ("m14", "Doppel 2", "hd2", "gd2"), ("m15", "Doppel 3", "hd3", "gd3")]
    else:
        s = [("m1", "Einzel 1", "h1", "g1"), ("m2", "Einzel 2", "h2", "g2"), ("m3", "Einzel 3", "h3", "g3"), ("m4", "Einzel 4", "h4", "g4")]
        c = [("m5", "Einzel 5 (Kreuz)", "h1", "g2"), ("m6", "Einzel 6 (Kreuz)", "h2", "g1"), ("m7", "Einzel 7 (Kreuz)", "h3", "g4"), ("m8", "Einzel 8 (Kreuz)", "h4", "g3")]
        d = [("m9", "Doppel 1", "hd1", "gd1"), ("m10", "Doppel 2", "hd2", "gd2")]
    r = []
    for bl in [s, c, d]:
        for i in range(0, len(bl), b_count): r.append(bl[i:i + b_count])
    return r

@st.dialog("➕ Neues Freundschaftsspiel", width="large")
def open_new_liga_match_dialog():
    dt = st.date_input("Datum", date.today())
    ht, gt = st.text_input("Heim", "Wehringer Steelers"), st.text_input("Gast", "Gegner DC")
    mode = st.radio("Art", ["🏆 Standard Liga-Spiel (4er Team, 2 Boards)", "⚙️ Freies Spiel auf Liga-Basis (flexibel)"])
    if "Standard" in mode: ts, bc = 4, 2
    else: ts = 6 if "6er" in st.selectbox("Team-Größe", ["4er-Team", "6er-Team"]) else 4; bc = st.selectbox("Boards", [1,2,3,4,5,6], index=1)
    opts = ["Kaiser B1", "Board 2", "Board 3", "Board 4", "Board 5", "Board 6"]
    c_b = st.columns(min(bc, 4))
    b_names = []
    for i in range(bc):
        with c_b[i % len(c_b)]:
            b_names.append(st.selectbox(f"Board {i+1}", opts, index=i))
            
    if st.button("Erstellen", type="primary"):
        nid = f"L-{max([int(s['id'].split('-')[1]) for s in st.session_state.sessions_list if 'L-' in s['id']] + [0]) + 1}"
        ns = {"id": nid, "datum": dt.strftime("%d.%m.%Y"), "is_liga": True, "team_size": ts, "boards_count": bc, "heim_team": ht, "gast_team": gt, "liga_boards": b_names, "auf_heim": {}, "auf_gast": {}, "results": {}}
        st.session_state.sessions_list.append(ns); smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("⚙️ Freundschaftsspiel bearbeiten")
def open_edit_liga_session_dialog(session_id):
    pwd = st.text_input("Passwort eingeben", type="password")
    if pwd != "1521":
        if pwd != "": st.error("Falsches Passwort!")
        return
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    idx = st.session_state.sessions_list.index(sess)
    try: curr_d = pd.to_datetime(sess.get("datum", ""), format="%d.%m.%Y").date()
    except: curr_d = date.today()
    session_datum = st.date_input("Datum", curr_d)
    heim_team = st.text_input("Heimmannschaft", value=sess.get("heim_team", ""))
    gast_team = st.text_input("Gastmannschaft", value=sess.get("gast_team", ""))
    if st.button("Speichern", type="primary", use_container_width=True):
        sess.update({"datum": session_datum.strftime("%d.%m.%Y"), "heim_team": heim_team.strip(), "gast_team": gast_team.strip()})
        st.session_state.sessions_list[idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("🔒 Einzel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_einzel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    idx = st.session_state.sessions_list.index(sess)
    ts = sess.get("team_size", 4)
    ins = [st.text_input(f"Pos {i+1}", value=sess.get("auf_heim" if is_heim else "auf_gast", {}).get(f"{'h' if is_heim else 'g'}{i+1}", ""), key=f"e_{is_heim}_{i}") for i in range(ts)]
    if st.button("Speichern", type="primary"):
        if all(x.strip() for x in ins):
            d = sess["auf_heim"] if is_heim else sess["auf_gast"]
            for i, v in enumerate(ins): d[f"{'h' if is_heim else 'g'}{i+1}"] = v.strip()
            st.session_state.sessions_list[idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()
        else: st.error(f"Alle {ts} füllen!")

@st.dialog("🔒 Doppel-Aufstellung (Verdeckt)")
def open_liga_aufstellung_doppel(session_id, is_heim):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    idx = st.session_state.sessions_list.index(sess)
    nd = 3 if sess.get("team_size", 4) == 6 else 2
    opts = list(set([v for k,v in (sess["auf_heim"] if is_heim else sess["auf_gast"]).items() if "d" not in k and v])) + ["+ Anderer..."]
    d_data = []
    for i in range(nd):
        c1, c2 = st.columns(2)
        s1 = c1.selectbox(f"D{i+1} Sp1", opts, key=f"d1_{i}")
        p1 = c1.text_input("Name", key=f"t1_{i}") if s1 == "+ Anderer..." else s1
        s2 = c2.selectbox(f"D{i+1} Sp2", opts, key=f"d2_{i}")
        p2 = c2.text_input("Name", key=f"t2_{i}") if s2 == "+ Anderer..." else s2
        d_data.append((p1.strip() if p1 else "", p2.strip() if p2 else ""))
        
    all_p = [p for pair in d_data for p in pair if p and p != "+ Anderer..."]
    dups = [item for item, count in collections.Counter(all_p).items() if count > 1]
    
    if dups:
        st.error(f"🚨 Fehler: Der Spieler '{dups[0]}' steht in mehreren Feldern!")
        
    if st.button("Speichern", type="primary", disabled=bool(dups)):
        if len(all_p) < nd * 2: st.error("Alle Felder füllen!")
        else:
            d = sess["auf_heim"] if is_heim else sess["auf_gast"]
            for i, (p1, p2) in enumerate(d_data): d[f"{'hd' if is_heim else 'gd'}{i+1}"] = f"{p1} & {p2}"
            st.session_state.sessions_list[idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("🔄 Auswechseln")
def open_liga_sub_dialog(session_id, key, is_heim, old_n):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    nn = st.text_input("Neuer Name:")
    if st.button("Speichern", type="primary") and nn.strip():
        (sess["auf_heim"] if is_heim else sess["auf_gast"])[key] = nn.strip()
        smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("🎯 Live Board")
def open_liga_live_board_dialog(session_id, m_key, board_name, m_label, p_l, p_r, is_right_board):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
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
        smart_sync_and_save(st.session_state.sessions_list); st.rerun()

@st.dialog("📝 Bericht & Abschluss", width="large")
def open_liga_bericht_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    idx = st.session_state.sessions_list.index(sess)
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
        sess["is_locked"] = lk; st.session_state.sessions_list[idx] = sess; smart_sync_and_save(st.session_state.sessions_list); st.rerun()

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

st.markdown("""<div style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
<img src="https://raw.githubusercontent.com/zombination88/Darttraining-Steelers/main/logo.png.png" alt="Logo" width="60" onerror="this.src='https://raw.githubusercontent.com/zombination88/Darttraining-Steelers/main/logo.png'">
<h1 style='margin: 0; padding-top: 8px; font-size: 1.8rem;'>Wehringer Steelers — Teamtraining</h1></div>""", unsafe_allow_html=True)

c_mus, c_sync, c_dummy = st.columns([1, 1, 4])
with c_mus:
    try:
        with st.popover("🎵"): st.audio("vereinssong.mp3")
    except Exception: pass
with c_sync:
    if st.button("🔄", help="Aktualisieren"):
        st.session_state.sessions_list = load_data(); st.rerun()

kader = ["Andreas Böhm", "Andrino Czombera", "Dennis Güttner", "Marco Eser", "Maximilian Zientner", "Michael Kummer", "Michael Mak", "Michael Neumeier", "Thomas Schaudt", "Wolfgang Scheider"]

if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

training_sessions = [s for s in st.session_state.sessions_list if not s.get("is_liga")]
liga_sessions = [s for s in st.session_state.sessions_list if s.get("is_liga")]

tab_übersicht, tab_kader, tab_session, tab_liga, tab_archiv, tab_regeln = st.tabs(["Übersicht", "Kader", "Session", "Freundschaftsspiele", "Match-Archiv", "Modus & Regeln"])

with tab_übersicht:
    c1, c2 = st.columns(2)
    if c1.button("➕ Neue Session", type="primary", use_container_width=True): open_new_session_dialog()
    act_s = [s for s in training_sessions if not is_session_completed(s)]
    
    if act_s:
        if len(act_s) > 1:
            opts = {f"{s['id']} ({s['datum']})": s for s in act_s}
            sel_k = st.selectbox("Aktive Session wählen:", list(opts.keys()))
            cs = opts[sel_k]
        else: cs = act_s[0]
        if c2.button("⚙️ Bearbeiten", use_container_width=True): open_edit_session_dialog(cs["id"])
    else: c2.button("⚙️ Bearbeiten", disabled=True, use_container_width=True)
    
    st.markdown("### 🔴 Laufende Session")
    if not act_s: st.info("Keine aktive Session.")
    else:
        if not cs.get("start_time"):
            st.info(f"Session für {cs['datum']} erstellt."); st.write(f"👥 {', '.join(cs.get('spieler', []))}")
            if st.button("🚀 Starten", type="primary"): cs["start_time"] = get_local_time_str(); smart_sync_and_save(st.session_state.sessions_list); st.rerun()
        else:
            tr = cs.get("total_rounds", 4)
            for b in get_boards_list(cs, 1):
                cr = max([r for (r, bn), v in cs.get("results", {}).items() if bn == b and v.get("winner")] + [0]) + 1
                with st.container(border=True):
                    st.markdown(f"<h4 style='text-align: center'>{b} (Runde {cr})</h4>", unsafe_allow_html=True)
                    if cr <= tr:
                        p1, p2 = get_board_players(cs, cr, b)
                        c_a, c_b = st.columns(2)
                        c_a.markdown(f"**{p1}**"); c_b.markdown(f"**{p2}**")
                        if st.button("🎯 Eintragen", key=f"tr_{b}_{cs['id']}", use_container_width=True, disabled=not is_board_ready(cs, b, cr)): open_board_dialog(b, cs["id"])
                    else: st.success("Beendet")

    # Statistiken IMMER sichtbar, gefiltert nach Training
    st.divider(); st.markdown("### 📊 Allgemeine Statistiken (Training)")
    t180 = sum([int(m.get("180_s1", 0)) + int(m.get("180_s2", 0)) for s in training_sessions for m in s.get("results", {}).values()])
    kc = collections.Counter([m.get("winner") for s in training_sessions for (r,b), m in s.get("results", {}).items() if b == "Kaiser B1" and " & " not in m.get("s1", "")])
    kw = max(kc, key=kc.get) if kc else "Offen"
    c_m1, c_m2, c_m3 = st.columns(3)
    c_m1.metric("Sessions", len(training_sessions)); c_m2.metric("180er", t180); c_m3.metric("Kaiser", kw)

    with st.expander("Zuletzt ausgetragene Board-Matches", expanded=False):
        for sess in training_sessions:
            for (r_n, b_n), m in sess.get("results", {}).items():
                if m.get("winner"): st.write(f"**{sess['datum']} - {b_n} (Runde {r_n})**: {m['s1']} vs {m['s2']} ➔ **{m['winner']}**")

with tab_kader:
    st.subheader("Kader")
    st.info("Regel: MVP benötigt min. 3 Matches. Hover-Tooltips bei Gleichstand.")
    sts = {p: {"m": 0, "s": 0, "180": 0, "as": 0.0, "ac": 0, "n": 0, "lw": 0, "ll": 0} for p in kader}
    for s in training_sessions:
        for m in s.get("results", {}).values():
            w, l, s1, s2 = m.get("winner", ""), m.get("loser", ""), m.get("s1", ""), m.get("s2", "")
            try: l1, l2 = map(int, m.get("ergebnis", "0:0").split(":"))
            except: l1, l2 = 0, 0
            if s1 in sts and " & " not in s1:
                sts[s1]["180"] += int(m.get("180_s1", 0)); a = float(m.get("avg_s1", 0)); sts[s1]["lw"] += l1; sts[s1]["ll"] += l2
                if a>0: sts[s1]["as"] += a; sts[s1]["ac"] += 1
            if s2 in sts and " & " not in s2:
                sts[s2]["180"] += int(m.get("180_s2", 0)); a = float(m.get("avg_s2", 0)); sts[s2]["lw"] += l2; sts[s2]["ll"] += l1
                if a>0: sts[s2]["as"] += a; sts[s2]["ac"] += 1
            if w in sts and " & " not in w: sts[w]["m"] += 1; sts[w]["s"] += 1
            if l in sts and " & " not in l: sts[l]["m"] += 1; sts[l]["n"] += 1

    valid_p = [p for p in kader if sts[p]["m"] >= 3]
    mvp_help, db_help = None, None
    if valid_p:
        b_r = max([sts[p]["s"] / sts[p]["m"] for p in valid_p])
        t_mvps = [p for p in valid_p if abs((sts[p]["s"] / sts[p]["m"]) - b_r) < 1e-9]
        mvp_txt = f"{(b_r*100):.0f}% Siege"
        if len(t_mvps) <= 2: mvp_p = " & ".join(t_mvps)
        else: mvp_p, mvp_help = f"{len(t_mvps)} Spieler", "MVPs:\n" + "\n".join(t_mvps)
    else: mvp_p, mvp_txt = "N/A", "Min 3 Matches"
    
    max_m = max([sts[p]["m"] for p in kader], default=0)
    if max_m > 0:
        t_db = [p for p in kader if sts[p]["m"] == max_m]
        db_txt = f"{max_m} Matches"
        if len(t_db) <= 2: db_p = " & ".join(t_db)
        else: db_p, db_help = f"{len(t_db)} Spieler", "Dauerbrenner:\n" + "\n".join(t_db)
    else: db_p, db_txt = "N/A", "0 Matches"
    
    b_avg_p, b_avg_v = "N/A", 0.0
    for p in kader:
        if sts[p]["ac"] > 0 and sts[p]["as"]/sts[p]["ac"] > b_avg_v: b_avg_v, b_avg_p = sts[p]["as"]/sts[p]["ac"], p
    
    m180_p = max(kader, key=lambda x: sts[x]["180"])
    
    c1, c2 = st.columns(2)
    c1.metric("🏆 MVP", mvp_p, mvp_txt, help=mvp_help)
    c2.metric("🔥 Dauerbrenner", db_p, db_txt, help=db_help)
    c3, c4 = st.columns(2)
    c3.metric("📊 Bester Avg", b_avg_p, f"Ø {b_avg_v:.1f}")
    c4.metric("🎯 180er Maschine", m180_p, f"{sts[m180_p]['180']}x")
    
    with st.expander("Alle Spieler", expanded=False):
        for p in sorted(kader, key=lambda x: sts[x]["s"], reverse=True):
            st.write(f"**{p}**: {sts[p]['s']} Siege / {sts[p]['m']} Matches")

with tab_session:
    st.subheader("Zeitmanagement")
    st.info("Alle Zeiten basieren auf euren Einträgen.")
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
    c1, c2 = st.columns(2)
    c1.metric("⏱️ Ø Dauer/Runde", f"{(gt_min/gt_rounds):.1f} Min" if gt_rounds else "0.0")
    c2.metric("🎯 Ø Dauer/Leg", f"{(gt_min/gt_legs):.1f} Min" if gt_legs else "0.0")

with tab_liga:
    if st.button("➕ Neues Freundschaftsspiel", type="primary"): open_new_liga_match_dialog()
    for ls in [s for s in liga_sessions if not s.get("is_locked")]:
        with st.container(border=True):
            st.markdown(f"### {ls['heim_team']} vs {ls['gast_team']}")
            if not ls.get("auf_heim", {}).get("h1"):
                c1, c2 = st.columns(2)
                if c1.button("🔒 Heim Aufstellen", key=f"ah_{ls['id']}"): open_liga_aufstellung_einzel(ls['id'], True)
                if c2.button("🔒 Gast Aufstellen", key=f"ag_{ls['id']}"): open_liga_aufstellung_einzel(ls['id'], False)
            else:
                rc = get_liga_config(ls); res = ls.get("results", {})
                for ri, rm in enumerate(rc):
                    if not all(res.get(mk, {}).get("played") for mk, _, _, _ in rm):
                        st.markdown(f"**Runde {ri+1}**")
                        if ri >= len(rc) - (3 if ls["team_size"]==6 else 2) and not ls.get("auf_heim", {}).get("hd1"):
                            if st.button("🔒 Doppel", key=f"ad_{ls['id']}"): open_liga_aufstellung_doppel(ls['id'], True)
                        for mk, lab, hk, gk in rm:
                            ph, pg = ls["auf_heim"].get(hk, "-"), ls["auf_gast"].get(gk, "-")
                            c1, c2 = st.columns(2)
                            c1.write(f"{ph} vs {pg}")
                            # 🔄 Auswechsel-Button NUR in der Kreuzrunde sichtbar!
                            show_sub = not res.get(mk, {}).get("played") and "Kreuz" in lab
                            if show_sub:
                                if c1.button("🔄", key=f"sh_{mk}"): open_liga_sub_dialog(ls['id'], hk, True, ph)
                            if c2.button("🎯 Eintragen", key=f"tr_{mk}"): open_liga_live_board_dialog(ls['id'], mk, "Board", lab, ph, pg, False)
                        break
                st.divider()
                if st.button("📝 Abschluss", key=f"ab_{ls['id']}"): open_liga_bericht_dialog(ls['id'])
    for ls in [s for s in liga_sessions if s.get("is_locked")]:
        with st.container(border=True):
            st.write(f"✅ {ls['heim_team']} vs {ls['gast_team']}")
            pdf = generate_spielbericht_pdf(ls)
            if pdf: st.download_button("📥 PDF Bericht", pdf, f"Bericht_{ls['id']}.pdf")

with tab_archiv:
    if st.session_state.sessions_list:
        safe_data_for_export = make_serializable(st.session_state.sessions_list)
        backup_json_str = json.dumps(safe_data_for_export, ensure_ascii=False, indent=2)
        st.download_button("📥 JSON Backup", data=backup_json_str, file_name=f"steelers_backup_{date.today().strftime('%Y-%m-%d')}.json", mime="application/json")
        
    for s in sorted(st.session_state.sessions_list, key=lambda x: int(x['id'].split('-')[1]) if '-' in x['id'] else 0, reverse=True):
        with st.container(border=True):
            st.write(f"**{s['id']}** - {s['datum']} ({s.get('modus', 'Freundschaftsspiel')})")
            c1, c2, c3 = st.columns(3)
            
            if s.get("is_liga"):
                if c1.button("📝 Bericht", key=f"arch_lb_{s['id']}"): open_liga_bericht_dialog(s["id"])
                if c2.button("⚙️ Bearbeiten", key=f"arch_le_{s['id']}"): open_edit_liga_session_dialog(s["id"])
            else:
                if c1.button("📊 Ansehen", key=f"arch_v_{s['id']}"): open_session_summary_dialog(s["id"])
                if c2.button("⚙️ Bearbeiten", key=f"arch_e_{s['id']}"): open_edit_session_dialog(s["id"])
                
            if c3.button("🗑️ Löschen", key=f"del_{s['id']}"): delete_session(s['id'])
            
            if not s.get("is_liga"):
                st.divider()
                if st.checkbox("⚡ Blitz-Erfassung", key=f"blitz_check_{s['id']}"):
                    if st.text_input("Admin-Passwort:", type="password", key=f"pwd_{s['id']}") == "1521":
                        for r in range(1, s.get("total_rounds", 4) + 1):
                            st.write(f"**Runde {r}**")
                            for b in get_boards_list(s, r):
                                m_i = s.get("results", {}).get((r, b), {})
                                p1, p2 = (m_i.get("s1", "-"), m_i.get("s2", "-")) if m_i else get_board_players(s, r, b)
                                try: s1, s2 = map(int, m_i.get("ergebnis", "0:0").split(":")) if m_i else (0,0)
                                except: s1, s2 = 0,0
                                c_1, c_2, c_3 = st.columns([2,2,1])
                                v1 = c_1.number_input(p1, 0, 5, s1, key=f"bl_{s['id']}_{r}_{b}_1")
                                v2 = c_2.number_input(p2, 0, 5, s2, key=f"bl_{s['id']}_{r}_{b}_2")
                                if c_3.button("💾", key=f"bs_{s['id']}_{r}_{b}"):
                                    s.setdefault("results", {})[(r, b)] = {"s1": p1, "s2": p2, "ergebnis": f"{v1}:{v2}", "winner": p1 if v1>v2 else p2, "loser": p2 if v1>v2 else p1, "180_s1": 0, "180_s2": 0, "avg_s1": 0.0, "avg_s2": 0.0}
                                    smart_sync_and_save(st.session_state.sessions_list); st.rerun()

with tab_regeln:
    st.subheader("Regeln")
    st.write("Nur Trainings-Regeln hier. (Wie gewollt)")
    st.write("1. Anti-Doppel-Pause: Das Freilos in Runde 1 rotiert.")
    st.write("2. Up & Down: Wer gewinnt, steigt auf.")
    st.write("3. Koop-Teams: Keine exakt gleichen Paarungen der Vorsession.")
