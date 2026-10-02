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

# ==========================================
# INHALTSVERZEICHNIS (MASTER-STRUKTUR)
# ==========================================
# [BLOCK 1] IMPORTS & SETUP
# [BLOCK 2] SIDEBAR & LOGIN
# [BLOCK 3] GOOGLE SHEETS & DATENBANK (Laden, Speichern, Backups)
# [BLOCK 4] HILFSFUNKTIONEN (Liga-Config, Elo, Excel, etc.)
# [BLOCK 5] HAUPT-UI & TABS-SETUP
# [BLOCK 6] TAB 1: ÜBERSICHT
# [BLOCK 7] TAB 2: KADER
# [BLOCK 8] TAB 3: SESSION (TRAINING)
# [BLOCK 9] TAB 4: FREUNDSCHAFTSSPIELE
# [BLOCK 10] TAB 5: LIGA (PUNKTSPIELE)
# [BLOCK 11] TAB 6: MATCH-ARCHIV
# [BLOCK 12] TAB 7: MODUS & REGELN
# ==========================================

# ==========================================
# [BLOCK 1] IMPORTS & SETUP
# ==========================================
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
import re
from PIL import Image
import extra_streamlit_components as stx

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

cookie_manager = stx.CookieManager()

if "role" not in st.session_state:
    st.session_state.role = "Gast"

current_cookie = cookie_manager.get(cookie="steelers_role")
if current_cookie == "Spieler":
    st.session_state.role = "Spieler"


# ==========================================
# [BLOCK 2] SIDEBAR & LOGIN
# ==========================================
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
                st.rerun()
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
            st.rerun()

is_admin = st.session_state.role == "Spieler"


# ==========================================
# [BLOCK 3] GOOGLE SHEETS & DATENBANK
# ==========================================
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
    except Exception:
        return None

spreadsheet = init_connection()

def ensure_worksheet(sheet_obj, title):
    try: return sheet_obj.worksheet(title)
    except:
        ws = sheet_obj.add_worksheet(title=title, rows=100, cols=2)
        ws.update([["json_data"]])
        return ws

def load_chunked(ws):
    try:
        data = ws.get_all_records()
        if not data: return []
        raw_str = "".join([str(r.get("json_data", "")) for r in data])
        if raw_str: 
            return json.loads(raw_str)
    except Exception:
        pass
    return []

def chunked_save(ws, data_list):
    try:
        json_str = json.dumps(data_list, ensure_ascii=False)
        chunks = [json_str[i:i+40000] for i in range(0, len(json_str), 40000)]
        rows = [["json_data"]] + [[c] for c in chunks]
        ws.clear()
        try:
            ws.update("A1", rows)
        except:
            ws.update(rows)
    except Exception as e:
        st.error(f"Speicher-Fehler: {e}")

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
        
        slim_sessions = []
        for s in serializable_sessions:
            s_slim = {k: v for k, v in s.items() if k != "image_b64"}
            slim_sessions.append(s_slim)
            
        json_str = json.dumps(slim_sessions, ensure_ascii=False)
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


# ==========================================
# [BLOCK 4] HILFSFUNKTIONEN
# ==========================================
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

def calculate_elo(training_sessions, kader_list):
    def parse_s_date(s):
        try: return datetime.strptime(s.get("datum", "01.01.2026"), "%d.%m.%Y")
        except: return datetime.min
    
    sorted_sessions = sorted(training_sessions, key=lambda x: (parse_s_date(x), int(x["id"].split("-")[1]) if "-" in x["id"] and x["id"].split("-")[1].isdigit() else 0))
    elo_dict = {p: 1000 for p in kader_list}
    
    for sess in sorted_sessions:
        if not sess.get("results"): continue
        res_items = sorted(sess["results"].items(), key=lambda x: x[0][0] if isinstance(x[0], tuple) else 0)
        for k, m in res_items:
            w, l = m.get("winner", ""), m.get("loser", "")
            if w and l and w != "-" and l != "-" and "&" not in w and "&" not in l:
                if w not in elo_dict: elo_dict[w] = 1000
                if l not in elo_dict: elo_dict[l] = 1000
                
                r_w = 10 ** (elo_dict[w] / 400)
                r_l = 10 ** (elo_dict[l] / 400)
                
                e_w = r_w / (r_w + r_l)
                e_l = r_l / (r_w + r_l)
                
                elo_dict[w] = elo_dict[w] + 32 * (1 - e_w)
                elo_dict[l] = elo_dict[l] + 32 * (0 - e_l)
    return elo_dict

def generate_excel_export(sessions_list):
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            t_rows = []
            for s in [x for x in sessions_list if not x.get("is_liga") and not x.get("is_wettkampf")]:
                d = s.get("datum", "")
                m = s.get("modus", "")
                for k, match in s.get("results", {}).items():
                    if match.get("played") or match.get("winner"):
                        rnd = k[0] if isinstance(k, tuple) else "-"
                        brd = k[1] if isinstance(k, tuple) else "-"
                        t_rows.append({
                            "Datum": d, "Modus": m, "Runde": rnd, "Board": brd,
                            "Spieler 1": match.get("s1", ""), "Spieler 2": match.get("s2", ""),
                            "Ergebnis": match.get("ergebnis", ""), "Sieger": match.get("winner", ""),
                            "180 S1": match.get("180_s1", 0), "180 S2": match.get("180_s2", 0),
                            "Avg S1": match.get("avg_s1", 0.0), "Avg S2": match.get("avg_s2", 0.0)
                        })
            if t_rows: pd.DataFrame(t_rows).to_excel(writer, sheet_name="Training", index=False)
            else: pd.DataFrame([{"Info": "Keine Trainings-Daten vorhanden"}]).to_excel(writer, sheet_name="Training", index=False)
                
            l_rows = []
            for s in [x for x in sessions_list if x.get("is_liga") or x.get("is_wettkampf")]:
                d = s.get("datum", "")
                ht = s.get("heim_team", "")
                gt = s.get("gast_team", "")
                for m_key, match in s.get("results", {}).items():
                    if match.get("played"):
                        l_rows.append({
                            "Datum": d, "Heimteam": ht, "Gastteam": gt, "Match": m_key,
                            "Heimspieler": match.get("s1", ""), "Gastspieler": match.get("s2", ""),
                            "Legs Heim": match.get("lh", 0), "Legs Gast": match.get("lg", 0),
                            "180 Heim": match.get("180_h", 0), "180 Gast": match.get("180_g", 0),
                            "HF Heim": match.get("hf_h", 0), "HF Gast": match.get("hf_g", 0),
                            "SL Heim": match.get("sl_h", 0), "SL Gast": match.get("sl_g", 0)
                        })
            if l_rows: pd.DataFrame(l_rows).to_excel(writer, sheet_name="Liga_Wettkampf", index=False)
            else: pd.DataFrame([{"Info": "Keine Liga-Daten vorhanden"}]).to_excel(writer, sheet_name="Liga_Wettkampf", index=False)
            
        return output.getvalue()
    except Exception as e:
        return None

@st.dialog("🗑️ Session Löschen (Admin)")
def open_delete_session_dialog(session_id):
    st.warning(f"Willst du die Session **{session_id}** wirklich unwiderruflich löschen?")
    pwd = st.text_input("Admin-Passwort zur Bestätigung:", type="password", key=f"del_pwd_{session_id}")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Abbrechen", use_container_width=True): st.rerun()
    with c2:
        if st.button("🗑️ Unwiderruflich löschen", type="primary", use_container_width=True):
            if pwd == "1521" or pwd == "20Steelers25":
                delete_session(session_id)
                st.success("Session wurde erfolgreich gelöscht!")
                st.rerun()
            else: st.error("Falsches Admin-Passwort!")

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
            new_session = {"id": f"W-{max_id + 1}", "datum": datum, "heim_team": heim, "gast_team": gast, "is_wettkampf": True, "results": {}}
            st.session_state.sessions_list.append(new_session)
            changed = True
    if changed:
        smart_sync_and_save(st.session_state.sessions_list)


# ==========================================
# [BLOCK 5] HAUPT-UI & TABS-SETUP
# ==========================================
# (HIER KOMMT DAS DATEN-LADEN UND DIE TAB-DEFINITION HIN)
# z.B.:
# if "sessions_list" not in st.session_state:
#     st.session_state.sessions_list = load_data()
# tab_uebersicht, tab_kader, tab_session, tab_freundschaft, tab_liga, tab_archiv, tab_regeln = st.tabs([...])


# ==========================================
# [BLOCK 6] TAB 1: ÜBERSICHT
# ==========================================
# with tab_uebersicht:
#     st.header("Übersicht")
#     ...


# ==========================================
# [BLOCK 7] TAB 2: KADER
# ==========================================
# with tab_kader:
#     st.header("Kader & Statistiken")
#     ...


# ==========================================
# [BLOCK 8] TAB 3: SESSION (TRAINING)
# ==========================================
# with tab_session:
#     st.header("Trainings-Session")
#     ...


# ==========================================
# [BLOCK 9] TAB 4: FREUNDSCHAFTSSPIELE
# ==========================================
# with tab_freundschaft:
#     st.header("Freundschaftsspiele")
#     ...


# ==========================================
# [BLOCK 10] TAB 5: LIGA (PUNKTSPIELE)
# ==========================================
# with tab_liga:
#     st.header("Liga & Wettkampf")
#     ...


# ==========================================
# [BLOCK 11] TAB 6: MATCH-ARCHIV
# ==========================================
# with tab_archiv:
#     st.header("Match-Archiv")
#     ...


# ==========================================
# [BLOCK 12] TAB 7: MODUS & REGELN
# ==========================================
# with tab_regeln:
#     st.header("Regelwerk & Hilfe")
#     ...
