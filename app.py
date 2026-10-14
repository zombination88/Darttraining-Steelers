# ==========================================
# [BLOCK_1] Imports, Config & Login
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
import time
from PIL import Image
import extra_streamlit_components as stx

st.set_page_config(page_title="Wehringer Steelers - Teamtraining", layout="centered")

# --- HINWEIS AUF DIE NEUE VERSION ---
st.markdown(
    """
    <div style="background-color: #2a1111; border: 2px solid #ff4b4b; padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
        <h3 style="color: #ff4b4b; margin: 0 0 5px 0;">🚨 Es gibt eine neue Version der Steelers-App!</h3>
        <p style="color: #ccc; margin: 0 0 10px 0; font-size: 0.95rem;">Diese alte Streamlit-Version wird nicht mehr aktiv weiterentwickelt. Bitte wechsle zur neuen, modernen Web-App:</p>
        <a href="https://steelers-app-94e32.web.app/" target="_blank" style="background-color: #4CAF50; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: bold; display: inline-block;">🚀 Zur neuen Steelers-App wechseln</a>
    </div>
    """,
    unsafe_allow_html=True
)
# -------------------------------------

cookie_manager = stx.CookieManager()

if "role" not in st.session_state:
    st.session_state.role = "Gast"

if "logged_out_flag" not in st.session_state:
    st.session_state.logged_out_flag = False

current_cookie = cookie_manager.get(cookie="steelers_role")

# Nur mit Cookie synchronisieren, wenn wir als Gast starten (frischer Seitenaufruf)
if current_cookie in ["Spieler", "Admin"] and not st.session_state.logged_out_flag:
    if st.session_state.role == "Gast":
        st.session_state.role = current_cookie

with st.sidebar:
    st.markdown("### 🔐 Login-Bereich")
    if st.session_state.role == "Gast":
        st.info("👀 **Gast-Modus**: Du kannst alle Statistiken, Tabellen und Spielberichte ansehen.")
        pwd = st.text_input("Passwort eingeben:", type="password")
        if st.button("Einloggen", use_container_width=True):
            if pwd == "1521":
                st.session_state.logged_out_flag = False
                st.session_state.role = "Admin"
                cookie_manager.set("steelers_role", "Admin", expires_at=datetime.now() + timedelta(days=365))
                st.success("👑 Admin-Login erfolgreich! (Bitte einmal irgendwo klicken, um das Menü zu aktualisieren)")
            elif pwd == "20Steelers25":
                st.session_state.logged_out_flag = False
                st.session_state.role = "Spieler"
                cookie_manager.set("steelers_role", "Spieler", expires_at=datetime.now() + timedelta(days=365))
                st.success("✅ Spieler-Login erfolgreich! (Bitte einmal irgendwo klicken, um das Menü zu aktualisieren)")
            else:
                st.error("Falsches Passwort!")
        st.markdown("---")
        st.caption("💡 **Info:** Einmal einloggen und dein Browser merkt sich deine Rechte per Cookie für 1 Jahr. Kein ständiges Neuanmelden nötig!")
    else:
        if st.session_state.role == "Admin":
            st.success("👑 **Admin-Modus**: Du hast volle Rechte, inklusive Archiv-Verwaltung.")
        else:
            st.success("✅ **Spieler-Modus**: Du darfst Live-Sessions verwalten und Ergebnisse eintragen.")
            
        if st.button("Ausloggen", use_container_width=True):
            st.session_state.logged_out_flag = True
            st.session_state.role = "Gast"
            cookie_manager.delete("steelers_role")
            st.success("✅ Erfolgreich abgemeldet! (Bitte einmal Tab wechseln oder klicken, um das Menü zu aktualisieren)")

is_admin = st.session_state.role in ["Spieler", "Admin"]
is_superadmin = st.session_state.role == "Admin"
# ==========================================
# [BLOCK_2] Datenbank & Google Sheets
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
    import time
    try:
        # --- FIX: Kugelsichere Prüfung, ob das Blatt schon existiert ---
        existing_worksheets = [ws.title for ws in sheet_obj.worksheets()]
        if title in existing_worksheets:
            return sheet_obj.worksheet(title)
        else:
            # Kurze Atempause, damit Google die API-Rate nicht blockt
            time.sleep(0.5) 
            ws = sheet_obj.add_worksheet(title=title, rows=100, cols=2)
            ws.update(values=[["json_data"]], range_name="A1")
            return ws
    except Exception as e:
        # Harter Fallback, falls die Liste aus irgendeinem Grund fehlschlägt
        try:
            return sheet_obj.worksheet(title)
        except:
            ws = sheet_obj.add_worksheet(title=title, rows=100, cols=2)
            ws.update(values=[["json_data"]], range_name="A1")
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
# [BLOCK_3] Hilfsfunktionen & Logik
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
                    platz2 = w.get("Board 2", "-") if len(prev_boards) > 1 else l.
