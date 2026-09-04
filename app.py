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
# 9. FREUNDSCHAFTSPIELE: Flexibel wählbar als 4er-, 6er-, 8er-, 10er- oder 12er-Team mit variablen Boards, Blind Setup, Kreuz-Runde und HTML-Druckansicht. 
#    - WICHTIG: Im Reiter Freundschaftsspiele wird bei abgeschlossenen Spielen nur für den Druck angezeigt. Der Korrigieren/Bearbeiten-Button ist dort entfernt und nur im Match-Archiv erreichbar.
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
    elif t_size >= 8:
        singles = [(f"m{i+1}", f"Einzel {i+1}", f"h{i+1}", f"g{i+1}") for i in range(t_size)]
        cross = [(f"m{t_size+i+1}", f"Kreuz-Einzel {i+1}", f"h{i+1}", f"g{(i + t_size // 2) % t_size + 1}") for i in range(t_size)]
        doubles = [(f"m{t_size*2+i+1}", f"Doppel {i+1}", f"hd{i+1}", f"gd{i+1}") for i in range(t_size // 2)]
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

def get_running_score_up_to(res, all_keys, target_key):
    """Berechnet den Spielstand ('Stand') bis einschließlich des aktuellen Matches für den Spielbericht."""
    h_score = 0
    g_score = 0
    for k in all_keys:
        m_data = res.get(k, {})
        if m_data.get("played"):
            lh = m_data.get("lh", 0)
            lg = m_data.get("lg", 0)
            if lh > lg:
                h_score += 1
            elif lg > lh:
                g_score += 1
        if k == target_key:
            break
    return f"{h_score}:{g_score}"

def render_spielbericht_html(sess):
    heim = sess.get("heim_team", "Heimteam")
    gast = sess.get("gast_team", "Gastmannschaft")
    datum = sess.get("datum", "")
    res = sess.get("results", {})
    auf_h = sess.get("auf_heim", {})
    auf_g = sess.get("auf_gast", {})
    
    rounds_map = get_liga_config(sess)
    match_map = [match for round in rounds_map for match in round]
    all_match_keys = [m[0] for m in match_map]
    
    sets_h = 0
    sets_g = 0
    total_legs_h = 0
    total_legs_g = 0
    
    for m_key in all_match_keys:
        m_data = res.get(m_key, {})
        if m_data.get("played"):
            lh = m_data.get("lh", 0)
            lg = m_data.get("lg", 0)
            total_legs_h += lh
            total_legs_g += lg
            if lh > lg: sets_h += 1
            elif lg > lh: sets_g += 1

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Spielbericht: {heim} vs {gast}</title>
        <style>
            body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #000; background: #fff; margin: 15px; }}
            .sheet-border {{ border: 2px solid #000; padding: 15px; }}
            .header-top {{ display: flex; justify-content: space-between; border-bottom: 2px solid #000; padding-bottom: 8px; margin-bottom: 10px; font-weight: bold; font-size: 11pt; }}
            .league-boxes {{ font-size: 9pt; margin-bottom: 10px; }}
            .meta-info {{ display: flex; justify-content: space-between; margin-bottom: 15px; font-size: 10pt; }}
            .teams-title {{ font-size: 14pt; font-weight: bold; text-align: center; margin: 10px 0; border: 1px solid #000; padding: 6px; background: #f4f4f4; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #000; padding: 5px 6px; text-align: center; font-size: 9pt; }}
            th {{ background-color: #e6e6e6; }}
            .left {{ text-align: left; }}
            .footer {{ margin-top: 25px; display: flex; justify-content: space-between; font-size: 9pt; }}
            .sig-box {{ border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 5px; margin-top: 35px; }}
            @media print {{
                .no-print {{ display: none; }}
                body {{ margin: 0; }}
            }}
            .print-btn {{ background: #ff4b4b; color: #fff; border: none; padding: 10px 20px; font-size: 11pt; font-weight: bold; cursor: pointer; border-radius: 5px; margin-bottom: 15px; }}
        </style>
    </head>
    <body>
        <div class="no-print" style="text-align: right;">
            <button class="print-btn" onclick="window.print()">🖨️ Spielbericht drucken / Als PDF speichern</button>
        </div>
        
        <div class="sheet-border">
            <div class="header-top">
                <div>BEZIRKSSCHWABEN DARTVERBAND</div>
                <div>SCHWABEN</div>
            </div>
            
            <div class="league-boxes">
                ☑ 1. BezLiga &nbsp; ☐ 2. BezLiga &nbsp; ☐ 3. BezLiga &nbsp; ☐ 4. BezLiga &nbsp; ☐ Schwaben-Pokal
            </div>
            
            <div class="meta-info">
                <div>Datum: <b>{datum}</b></div>
                <div>Saison: <b>2026/2027</b></div>
            </div>
            
            <div class="teams-title">{heim} &nbsp;vs.&nbsp; {gast}</div>
            <div style="text-align: center; font-size: 11pt; font-weight: bold; margin-bottom: 10px;">Endergebnis: {sets_h} : {sets_g} &nbsp;&nbsp;|&nbsp;&nbsp; Gesamtlegs: {total_legs_h} : {total_legs_g}</div>
            
            <table>
                <thead>
                    <tr>
                        <th style="width: 35px;">Spt.</th>
                        <th class="left">Heimmannschaft (Spieler)</th>
                        <th style="width: 45px;">Sp.-Nr.</th>
                        <th style="width: 35px;">180</th>
                        <th style="width: 35px;">Legs</th>
                        <th style="width: 35px;">Legs</th>
                        <th style="width: 35px;">180</th>
                        <th style="width: 45px;">Sp.-Nr.</th>
                        <th class="left">Gastmannschaft (Spieler)</th>
                        <th style="width: 45px;">Stand</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for idx, (m_key, label, h_key, g_key) in enumerate(match_map, 1):
        m_data = res.get(m_key, {})
        played = m_data.get("played", False)
        h_name = auf_h.get(h_key, "-") if played or auf_h.get(h_key) else "-"
        g_name = auf_g.get(g_key, "-") if played or auf_g.get(g_key) else "-"
        lh = m_data.get("lh", "") if played else ""
        lg = m_data.get("lg", "") if played else ""
        h180 = m_data.get("180_h", "") if played and m_data.get("180_h", 0) > 0 else ""
        g180 = m_data.get("180_g", "") if played and m_data.get("180_g", 0) > 0 else ""
        stand = get_running_score_up_to(res, all_match_keys, m_key) if played else "-"
        
        html += f"""
                    <tr>
                        <td><b>{idx}</b></td>
                        <td class="left">{h_name} <span style="font-size: 7.5pt; color: #555;">({label})</span></td>
                        <td></td>
                        <td>{h180}</td>
                        <td><b>{lh}</b></td>
                        <td><b>{lg}</b></td>
                        <td>{g180}</td>
                        <td></td>
                        <td class="left">{g_name}</td>
                        <td><b>{stand}</b></td>
                    </tr>
        """
        
    html += f"""
                </tbody>
            </table>
            
            <div class="footer">
                <div class="sig-box">Unterschrift Teamcaptain Heimmannschaft</div>
                <div style="text-align: center; padding-top: 35px; font-size: 9pt;">
                    <b>Beginn:</b> ____:____ Uhr &nbsp;&nbsp;|&nbsp;&nbsp; <b>Ende:</b> ____:____ Uhr
                </div>
                <div class="sig-box">Unterschrift Teamcaptain Gastmannschaft</div>
            </div>
        </div>
    </body>
    </html>
    """
    return html

@st.dialog("📝 Offizieller Spielbericht (Druckansicht & Korrektur)", width="large")
def open_liga_bericht_dialog(session_id):
    sess = next((s for s in st.session_state.sessions_list if s["id"] == session_id), None)
    if not sess: return
    real_idx = st.session_state.sessions_list.index(sess)
    
    st.markdown("### 🖨️ Spielbericht (Druckansicht)")
    st.caption("Dieser Spielbericht ist originalgetreu nach dem Formular des Bezirksschwaben Dartverbands aufgebaut.")
    
    html_content = render_spielbericht_html(sess)
    import streamlit.components.v1 as components
    
    with st.expander("📄 Vorschau des Spielberichts", expanded=True):
        components.html(html_content, height=520, scrolling=True)
        st.download_button(
            label="📥 HTML-Spielbericht als Datei speichern",
            data=html_content,
            file_name=f"Spielbericht_{sess.get('heim_team')}_vs_{sess.get('gast_team')}.html",
            mime="text/html",
            key=f"dl_html_{session_id}"
        )
        
    st.divider()
    st.write("### Manuelle Ergebniskorrektur")
    auf_h, auf_g = sess.get("auf_heim", {}), sess.get("auf_gast", {})
    res = sess.setdefault("results", {})
    match_map = [match for round in get_liga_config(sess) for match in round]
    
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
    st.write("Isolierter Bereich für Freundschaftsspiele (flexibel als 4er-, 6er-, 8er-, 10er- oder 12er-Team mit variablen Boards, Blind Setup, Kreuz-Runde und HTML-Druckansicht).")
    
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
                st.markdown(f"### 🏆 {heim} vs. {gast} — Stand: {sets_heim}:{sets_gast}")
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
                            
                    singles_batches = math.ceil(t_size / b_count)
                    cross_batches = math.ceil(t_size / b_count)
                    is_in_doubles = (curr_round_idx >= singles_batches + cross_batches)
                    
                    if is_in_doubles:
                        h_doppel_ok = bool(auf_h.get("hd1"))
                        g_doppel_ok = bool(auf_g.get("gd1"))
                        if not h_doppel_ok or not g_doppel_ok:
                            st.warning("🚨 Die Doppel-Runden dürfen erst nach Beendigung aller Einzel-Runden und Eingabe der Doppel-Aufstellungen gestartet werden!")
                            c_dh, c_dg = st.columns(2)
                            if not h_doppel_ok and c_dh.button("🔒 Heim Doppel", key=f"hd_setup_{l_sess['id']}"):
                                open_liga_aufstellung_doppel(l_sess['id'], True)
                            if not g_doppel_ok and c_dg.button("🔒 Gast Doppel", key=f"gd_setup_{l_sess['id']}"):
                                open_liga_aufstellung_doppel(l_sess['id'], False)
                            continue
                    elif curr_round_idx >= singles_batches:
                        st.markdown("**🔜 Doppel bereits jetzt aufstellen (Optional):**")
                        c_opt1, c_opt2 = st.columns(2)
                        if not auf_h.get("hd1") and c_opt1.button("🔒 Heim Doppel", key=f"opt_hd_{l_sess['id']}"):
                            open_liga_aufstellung_doppel(l_sess['id'], True)
                        if not auf_g.get("gd1") and c_opt2.button("🔒 Gast Doppel", key=f"opt_gd_{l_sess['id']}"):
                            open_liga_aufstellung_doppel(l_sess['id'], False)
                                
                    if curr_round_idx < len(rounds_list):
                        active_matches = rounds_list[curr_round_idx]
                        st.markdown(f"**Runde {curr_round_idx + 1} / {len(rounds_list)} läuft:**")
                        
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
                                    
                                    all_match_keys = [match[0] for round in rounds_list for match in round]
                                    stand_str = get_running_score_up_to(res, all_match_keys, m_key)
                                    st.caption(f"Stand: **{stand_str}**")
                                    
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
    st.markdown("### 🗄️ Abgeschlossene Freundschaftsspiele (Druckansicht)")
    st.write("Hier findest du alle beendeten Spiele. Die Web-Druckansicht formatiert den Spielbericht perfekt im 1:1 Verbandsformat.")
    
    if not completed_liga:
        st.info("Noch keine abgeschlossenen Freundschaftsspiele im Archiv.")
    else:
        for c_sess in completed_liga:
            with st.container(border=True):
                st.markdown(f"**{c_sess['datum']}** | 🏆 {c_sess.get('heim_team')} vs. {c_sess.get('gast_team')}")
                if st.button("🖨️ Spielbericht (Druckansicht öffnen)", key=f"print_view_{c_sess['id']}", use_container_width=True):
                    open_liga_bericht_dialog(c_sess['id'])

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

with tab_regeln:
    st.subheader("🎯 Modus & Spielablauf")
    st.write("Hier findet ihr die vollständige Anleitung für den Trainingsabend, alle Spielmodi und Freundschaftsspiele.")
    
    with st.container(border=True):
        st.markdown("### 🏆 Freundschaftsspiele & Web-Druckansicht (1:1 Verbandsformat)")
        st.markdown("""
        * Eigener Bereich im Tab **Freundschaftsspiele**.
        * **Ablauf:** Die Aufstellung erfolgt in 2 Phasen (Einzel und Doppel), verdeckt (Blind Setup).
        * **Flexibel wählbar:** Als 4er-, 6er-, 8er-, 10er- oder 12er-Team mit variablen Boards (wobei pro Board immer 2 Spieler spielen).
        * **Live-Tracking & Warteschlange:** Gespielt wird auf frei wählbaren parallelen Boards. Die aktuellen Board-Matches sowie die nachfolgende Warteschlange werden übersichtlich angezeigt.
        * **1:1 Spielbericht-Druckansicht:** Die App erzeugt einen originalgetreuen Nachbau des offiziellen Spielberichts (Bezirksschwaben Dartverband) inklusive korrekter Spalten, 180er-Boxen und Spaltenstand ("Stand") ganz rechts. Über den Drucken-Button kann dieser verlustfrei als PDF oder auf Papier ausgegeben werden.
        """)
        
    with st.container(border=True):
        st.markdown("### 👑 Trainings-Modi & Logik")
        st.markdown("""
        * **Standard-Training (Einzel + Coop):** X Runden Einzel (max 6 Boards), dann Y Runden Doppel (exklusiv auf Kaiser B1 & Board 2).
        * **Koop 2vs2 (Up & Down):** Reine Doppel-Session (0 Einzel). Gespielt wird exklusiv auf Kaiser B1 & Board 2. Keine exakt gleichen 2er-Teams wie in der Vorsession.
        * **Up & Down (Einzel - Klassisch):** Sieger steigt auf (Richtung B1), Verlierer ab. Der Kaiser der Vorsession startet ganz unten.
        """)

    with st.container(border=True):
        st.markdown("### 👥 Besonderheiten & Zeitmanagement")
        st.markdown("""
        * **Anti-Doppel-Pause:** Das Freilos in Runde 1 rotiert. Wer im letzten Match pausiert hat, darf nicht nochmal aussetzen.
        * **Ungerader Kader:** Bei ungerader Spieleranzahl wird auf dem letzten Board ein Platzhalter (`-`) eingesetzt, sodass das Freilos automatisch durchwechselt.
        * **Zeitmanagement:** Im Session-Reiter werden globale Durchschnittszeiten (Min/Runde, Min/Leg) inkl. Nacht-Übergang berechnet.
        """)
