import streamlit as st
import pandas as pd
from datetime import datetime
import json
import random

# --- SEITEN-KONFIGURATION ---
st.set_page_config(
    page_title="Wehringer Steelers Dart Training",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- GLOBAL STYLES (MOBILE OPTIMIZED & DARK THEME) ---
st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
    }
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.5rem;
        padding-right: 0.5rem;
        max-width: 900px;
    }
    h1, h2, h3 {
        color: #ffffff !important;
    }
    /* Cards */
    .css-1r6slb0, .stCard, div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
        border-radius: 12px;
    }
    /* Buttons */
    .stButton>button {
        border-radius: 8px;
        font-weight: bold;
    }
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        overflow-x: auto;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 6px 6px 0px 0px;
        padding: 8px 12px;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# --- DEFAULT STATE INITIALIZATION ---
if 'players' not in st.session_state:
    st.session_state.players = [
        "Dennis Güttner", "Thomas Schaudt", "Wolfgang Scheider", 
        "Michael Mayer", "Stefan Braun", "Andreas Huber", 
        "Christian Lang", "Florian Wagner", "Markus Bauer", "Tobias Keller"
    ]

if 'sessions' not in st.session_state:
    st.session_state.sessions = []

if 'active_session_id' not in st.session_state:
    st.session_state.active_session_id = None

if 'match_history' not in st.session_state:
    st.session_state.match_history = []

# --- HILFSFUNKTIONEN FÜR UP & DOWN ---
def get_session_by_id(sid):
    for s in st.session_state.sessions:
        if s["id"] == sid:
            return s
    return None

def calculate_board_players(session, round_num):
    """Berechnet die Spieler für die Boards einer Runde basierend auf Vorrunden-Ergebnissen."""
    mode = session["mode"] # "Einzel (Coop)" oder "Doppel (Coop)"
    active_players = list(session["starting_players"])
    num_players = len(active_players)
    
    # Bei Runde 1: Initial-Zuweisung (sortiert nach letztem Rang oder gemischt)
    if round_num == 1:
        # Falls es eine Sortierung vom Vorabend gibt, hier anwenden, sonst Liste wie sie ist
        sorted_players = active_players[:]
        boards = []
        board_idx = 1
        
        if mode.startswith("Einzel"):
            i = 0
            while i < len(sorted_players):
                if i + 1 < len(sorted_players):
                    boards.append({
                        "board_id": board_idx,
                        "p1": sorted_players[i],
                        "p2": sorted_players[i+1]
                    })
                    i += 2
                else:
                    # Ungerade: Letzter kriegt Platzhalter (-)
                    boards.append({
                        "board_id": board_idx,
                        "p1": sorted_players[i],
                        "p2": "-"
                    })
                    i += 1
                board_idx += 1
        else: # Doppel (Coop)
            # Vier Spieler pro Board (2v2)
            i = 0
            while i < len(sorted_players):
                team1 = [sorted_players[i]]
                if i + 1 < len(sorted_players):
                    team1.append(sorted_players[i+1])
                team2 = []
                if i + 2 < len(sorted_players):
                    team2.append(sorted_players[i+2])
                if i + 3 < len(sorted_players):
                    team2.append(sorted_players[i+3])
                
                # Wenn Team2 leer oder unvollständig
                p1_str = " & ".join(team1)
                p2_str = " & ".join(team2) if team2 else "-"
                
                boards.append({
                    "board_id": board_idx,
                    "p1": p1_str,
                    "p2": p2_str
                })
                i += 4
                board_idx += 1
        return boards

    else:
        # Für Runde > 1: Hole Ergebnisse der Vorrunde
        prev_round = round_num - 1
        prev_boards = calculate_board_players(session, prev_round)
        
        winners = []
        losers = []
        
        # Wir sammeln Gewinner und Verlierer sortiert nach Board-Nummer (1 bis N)
        for b in prev_boards:
            b_id = b["board_id"]
            match_key = f"R{prev_round}_B{b_id}"
            
            # Prüfen ob Match gespielt wurde
            if match_key in session["results"]:
                res = session["results"][match_key]
                w = res["winner"]
                l = res["loser"]
                winners.append(w)
                losers.append(l)
            else:
                # Fallback falls nicht eingetragen
                winners.append(b["p1"])
                losers.append(b["p2"])
        
        # Up & Down Logik:
        # Board 1: Gewinner bleibt/kommt von unten. Verlierer steigt ab.
        # Board 2..N: Gewinner steigt auf, Verlierer steigt ab.
        # Spezialfall ungerade Spieleranzahl: Wer auf dem allerletzten Board verliert, hat in dieser Runde Pause (-)
        
        # Ordnen wir die Spieler für die neue Runde:
        # Gewinner von Board 2..N steigen auf und spielen mit Gewinner Board 1 (oder rangieren sich ein)
        # Standard Up & Down:
        # Liste aller Spieler sortiert nach "Stärke" von oben nach unten ermitteln:
        # Board 1 Gewinner bleibt oben. Board 1 Verlierer + Board 2 Gewinner...
        
        # Bauen wir die neue Spieler-Reihenfolge basierend auf Auf-/Abstieg:
        # Gewinner wandern nach oben, Verlierer nach unten.
        ordered_for_next = []
        
        # Kombiniere: Gewinner steigen auf (Board i Gewinner kommt über Verlierer Board i-1)
        # Einfacher Ansatz:
        # Alle Gewinner nach oben (nach Board-Reihenfolge), alle Verlierer nach unten (nach Board-Reihenfolge)
        # Oder echtes Up & Down:
        # Wir bilden feste Paarungen durch Verschiebung:
        
        # Sammle alle Akteure der Vorrunde in ihrer aktuellen Reihenfolge
        all_prev_actors = []
        for b in prev_boards:
            all_prev_actors.append(b["p1"])
            all_prev_actors.append(b["p2"])
            
        # Wenn wir die Gewinner und Verlierer haben:
        # Board 1: Gewinner (bleibt/wird Board 1 P1), Verlierer (geht zu Board 2)
        # Board i: Gewinner (steigt auf zu Board i-1 P2), Verlierer (geht zu Board i+1)
        
        # Lassen wir das System deterministisch über Gewinner/Verlierer-Listen laufen:
        # Gewinner von Board 1, 2, 3... 
        # Verlierer von Board 1, 2, 3...
        
        # Bei ungerader Spieleranzahl ist der letzte Verlierer ein "-"
        # WICHTIG: Derjenige, der auf dem letzten Board verloren hat, kriegt das Freilos (-) in der neuen Runde!
        
        active_winners = [w for w in winners if w != "-"]
        active_losers = [l for l in losers if l != "-"]
        
        # Wer kriegt das Freilos (-) in Runde `round_num`? 
        # Der Verlierer des allerletzten Boards der Vorrunde!
        freilos_player = None
        if len(losers) > 0 and losers[-1] != "-":
            freilos_player = losers[-1]
            active_losers = [l for l in losers[:-1] if l != "-"] # Letzter Verlierer raus für diese Runde
        
        # Neue Setzliste zusammenbauen:
        # Gewinner von oben nach unten, Verlierer von oben nach unten, plus Freilos am Ende
        combined = active_winners + active_losers
        if freilos_player:
            combined.append(freilos_player) # Der bekommt das "-" als Gegner
            
        # Jetzt wieder in Boards aufteilen
        boards = []
        board_idx = 1
        i = 0
        while i < len(combined):
            p1 = combined[i]
            p2 = combined[i+1] if i + 1 < len(combined) else "-"
            
            # Wenn p2 das Freilos-Objekt ist oder umgekehrt:
            boards.append({
                "board_id": board_idx,
                "p1": p1,
                "p2": p2
            })
            i += 2
            board_idx += 1
            
        return boards

# --- HEADER BEREICH ---
col_head1, col_head2, col_head3 = st.columns([4, 1, 1])
with col_head1:
    st.title("🎯 Wehringer Steelers")
with col_head2:
    with st.popover("🎵"):
        st.markdown("### 🎵 Vereinslied")
        st.audio("https://www.soundhelix.com/examples/mp3/Song-1.mp3", format="audio/mp3")
        st.caption("Unser Einlauf-Song für den Dartabend!")
with col_head3:
    if st.button("🔄"):
        st.rerun()

# --- HAUPTNAVIGATION (TABS) ---
tab_übersicht, tab_modst, tab_kader, tab_session, tab_archiv = st.tabs([
    "Übersicht", "Modus & Regeln", "Kader", "Session", "Match-Archiv"
])

# ==========================================
# 1. TAB: ÜBERSICHT
# ==========================================
with tab_übersicht:
    active_session = get_session_by_id(st.session_state.active_session_id)
    
    if not active_session:
        st.info("👋 Keine aktive Session gestartet. Starte oben im Tab **'Session'** einen neuen Trainingstag!")
    else:
        st.markdown(f"### 🔴 Laufende Session")
        st.caption(f"Session-ID: **{active_session['id']}** vom {active_session['date']} ({active_session['mode']})")
        
        total_rounds = active_session["total_rounds"]
        
        # Wir ermitteln die aktuelle Runde für jedes Board oder global
        # Finde heraus, welche Runde gerade aktiv ist (erste Runde, in der nicht alle Ergebnisse vorliegen)
        current_round = 1
        for r in range(1, total_rounds + 1):
            boards_in_r = calculate_board_players(active_session, r)
            all_done = True
            for b in boards_in_r:
                if f"R{r}_B{b['board_id']}" not in active_session["results"]:
                    all_done = False
                    break
            if not all_done:
                current_round = r
                break
            if r == total_rounds:
                current_round = total_rounds # Finale beendet
                
        boards = calculate_board_players(active_session, current_round)
        
        st.markdown(f"#### Runde {current_round}/{total_rounds} ({len(boards)} Boards aktiv)")
        
        # Prüfen ob alle Spiele dieser Runde fertig sind
        round_complete = True
        for b in boards:
            if f"R{current_round}_B{b['board_id']}" not in active_session["results"]:
                round_complete = False
                break
                
        for b in boards:
            b_id = b["board_id"]
            p1 = b["p1"]
            p2 = b["p2"]
            match_key = f"R{current_round}_B{b_id}"
            has_result = match_key in active_session["results"]
            
            # Ampel Status bestimmen
            # Board 1 ist immer spielbar, wenn Runde dran ist. Andere Boards warten evtl. auf Vorrunden.
            is_spielbar = True 
            status_text = "🟢 Spielbar"
            if has_result:
                status_text = "✅ Beendet"
            elif not is_spielbar:
                status_text = "🔴 Wartet"
                
            with st.container(border=True):
                st.markdown(f"<h4 style='text-align: center; margin-bottom: 0px;'>Kaiser B{b_id}</h4>", unsafe_allow_html=True)
                st.markdown(f"<p style='text-align: center; color: {'#2ecc71' if not has_result else '#3498db'}; font-weight: bold; margin-top: 2px;'>{status_text} <span style='font-weight: normal; font-size: 12px; color: #aaa;'>| Runde {current_round}/{total_rounds}</span></p>", unsafe_allow_html=True)
                
                col_p1, col_vs, col_p2 = st.columns([5, 1, 5])
                with col_p1:
                    st.markdown(f"**{p1}**")
                with col_vs:
                    st.markdown("<p style='text-align: center; color: #e74c3c; font-weight: bold;'>VS</p>", unsafe_allow_html=True)
                with col_p2:
                    st.markdown(f"<div style='text-align: right;'><b>{p2}</b></div>", unsafe_allow_html=True)
                    
                # Eintragen Button / Modal
                if not has_result and p2 != "-":
                    with st.expander("🎯 Eintragen"):
                        with st.form(key=f"form_{current_round}_{b_id}"):
                            st.markdown(f"Ergebnis für **{p1}** vs **{p2}**")
                            legs_p1 = st.number_input(f"Legs {p1}", min_value=0, max_value=10, value=0, key=f"l1_{current_round}_{b_id}")
                            legs_p2 = st.number_input(f"Legs {p2}", min_value=0, max_value=10, value=0, key=f"l2_{current_round}_{b_id}")
                            
                            c_sub1, c_sub2 = st.columns(2)
                            with c_sub1:
                                s_180_p1 = st.number_input(f"180er {p1}", min_value=0, value=0, key=f"180_1_{current_round}_{b_id}")
                                avg_p1 = st.number_input(f"Avg {p1}", min_value=0.0, value=0.0, step=0.1, key=f"avg_1_{current_round}_{b_id}")
                            with c_sub2:
                                s_180_p2 = st.number_input(f"180er {p2}", min_value=0, value=0, key=f"180_2_{current_round}_{b_id}")
                                avg_p2 = st.number_input(f"Avg {p2}", min_value=0.0, value=0.0, step=0.1, key=f"avg_2_{current_round}_{b_id}")
                                
                            submitted = st.form_submit_button("Ergebnis abschließen")
                            if submitted:
                                if legs_p1 == legs_p2:
                                    st.error("Unentschieden ist beim Darttraining nicht vorgesehen! Bitte einen Sieger ermitteln.")
                                else:
                                    winner = p1 if legs_p1 > legs_p2 else p2
                                    loser = p2 if legs_p1 > legs_p2 else p1
                                    
                                    active_session["results"][match_key] = {
                                        "p1": p1, "p2": p2,
                                        "legs_p1": legs_p1, "legs_p2": legs_p2,
                                        "winner": winner, "loser": loser,
                                        "180_p1": s_180_p1, "180_p2": s_180_p2,
                                        "avg_p1": avg_p1, "avg_p2": avg_p2
                                    }
                                    st.success("Ergebnis gespeichert!")
                                    st.rerun()
                elif p2 == "-":
                    st.caption("ℹ️ In dieser Runde spielfrei (Freilos).")
                elif has_result:
                    res = active_session["results"][match_key]
                    st.success(f"Ergebnis: {res['p1']} {res['legs_p1']} : {res['legs_p2']} {res['p2']} (Sieger: {res['winner']})")

        # Allgemeine Statistiken Box (unter den laufenden Boards)
        st.markdown("---")
        st.markdown("### 📊 Allgemeine Statistiken")
        c_stat1, c_stat2, c_stat3 = st.columns(3)
        with c_stat1:
            st.metric("Aktive Spieler", len(active_session["starting_players"]))
        with c_stat2:
            st.metric("Gespielte Runden", f"{current_round}/{total_rounds}")
        with c_stat3:
            total_180s = sum(
                res.get("180_p1", 0) + res.get("180_p2", 0) 
                for res in active_session["results"].values()
            )
            st.metric("Gesamte 180er", total_180s)

# ==========================================
# 2. TAB: MODUS & REGELN
# ==========================================
with tab_modst:
    st.markdown("### 🎯 Modus & Regeln")
    st.markdown("Hier findet ihr die Anleitung für den Trainingsabend, den Auf- und Abstieg sowie die Board-Verteilung.")
    
    with st.expander("🔄 Das 'Up & Down' (Kaiser-System)", expanded=True):
        st.markdown("""
        Das Training läuft im beliebten **Up & Down Modus** ab:
        * **Kaiser B1 ist das Top-Board:** Wer hier gewinnt, bleibt der König oder verteidigt seine Position. Wer verliert, wandert ein Board nach unten.
        * **Auf- und Abstieg:** Die Gewinner eines Boards steigen eine Etage nach oben, die Verlierer steigen eine Etage nach unten.
        * **Die Ampel zeigt euch, wann ihr dran seid:**
          * 🟢 **Spielbar:** Euer Match steht fest – ihr könnt sofort loslegen!
          * 🔴 **Wartet:** Ihr müsst noch auf die Ergebnisse der Nachbarboards warten.
        """)
        
    with st.expander("👥 Was passiert bei einer ungeraden Spieleranzahl?"):
        st.markdown("""
        Wenn wir mit einer ungeraden Anzahl an Spielern (z.B. 7 oder 9) trainieren:
        * Das System weist dem letzten Spieler auf dem untersten Board automatisch den Platzhalter **`-`** als Gegner zu.
        * **Das Wichtigste:** Wer auf dem allerletzten Board verliert, bekommt in der nächsten Runde das Freilos (die Pause). 
        * Dadurch wandert der Pausenplatz in jeder Runde fair von unten nach oben durch, und das System hält exakt die richtige Reihenfolge ein!
        """)
        
    with st.expander("📋 Board-Verteilung für eine neue Session"):
        st.markdown("""
        Beim Start einer neuen Trainingseinheit:
        * Wählt der Admin die anwesenden Spieler aus und legt die Anzahl der Runden fest.
        * Die Spieler werden für die **erste Runde** automatisch auf die Boards aufgeteilt.
        * Ab der **zweiten Runde** berechnet die App die Paarungen vollautomatisch über die Match-Ergebnisse (Gewinner steigen auf, Verlierer steigen ab).
        """)

# ==========================================
# 3. TAB: KADER
# ==========================================
with tab_kader:
    st.markdown("### 👥 Kader & Saison-Bilanzen")
    st.markdown("Hier seht ihr die gesammelten Live-Werte aller Spieler aus allen gespielten Sessions.")
    
    # Aggregiere Statistiken aus match_history
    player_stats = {p: {"matches": 0, "wins": 0, "losses": 0, "180s": 0, "total_avg": 0.0, "avg_count": 0} for p in st.session_state.players}
    
    for ses in st.session_state.sessions:
        for m in ses["results"].values():
            p1, p2 = m["p1"], m["p2"]
            w, l = m["winner"], m["loser"]
            
            for p in [p1, p2]:
                if p != "-" and p not in player_stats:
                    player_stats[p] = {"matches": 0, "wins": 0, "losses": 0, "180s": 0, "total_avg": 0.0, "avg_count": 0}
            
            if p1 != "-":
                player_stats[p1]["matches"] += 1
                player_stats[p1]["180s"] += m.get("180_p1", 0)
                if m.get("avg_p1", 0) > 0:
                    player_stats[p1]["total_avg"] += m["avg_p1"]
                    player_stats[p1]["avg_count"] += 1
            if p2 != "-":
                player_stats[p2]["matches"] += 1
                player_stats[p2]["180s"] += m.get("180_p2", 0)
                if m.get("avg_p2", 0) > 0:
                    player_stats[p2]["total_avg"] += m["avg_p2"]
                    player_stats[p2]["avg_count"] += 1
                    
            if w in player_stats:
                player_stats[w]["wins"] += 1
            if l in player_stats:
                player_stats[l]["losses"] += 1

    # In DataFrame umwandeln
    data_list = []
    for p, st_val in player_stats.items():
        avg_val = round(st_val["total_avg"] / st_val["avg_count"], 1) if st_val["avg_count"] > 0 else 0.0
        data_list.append({
            "Spieler": p,
            "Matches": st_val["matches"],
            "Siege": st_val["wins"],
            "Niederlagen": st_val["losses"],
            "180er": st_val["180s"],
            "Avg": avg_val
        })
        
    df_kader = pd.DataFrame(data_list)
    if not df_kader.empty:
        df_kader = df_kader.sort_values(by=["Siege", "Avg"], ascending=[False, False])
        st.dataframe(df_kader, use_container_width=True, hide_index=True)
    else:
        st.info("Noch keine Spieldaten vorhanden.")

# ==========================================
# 4. TAB: SESSION (ADMIN)
# ==========================================
with tab_session:
    st.markdown("### ⚙️ Session-Verwaltung")
    
    password = st.text_input("Admin-Passwort für Neue Session", type="password")
    
    if password == "1521":
        st.success("Admin-Modus aktiv")
        
        with st.form("new_session_form"):
            st.markdown("#### ➕ Neue Session starten")
            session_date = st.date_input("Datum", value=datetime.now())
            mode = st.selectbox("Spielmodus", ["Einzel (Coop)", "Doppel (Coop)"])
            total_rounds = st.number_input("Anzahl Runden", min_value=1, max_value=10, value=4)
            
            selected_players = st.multiselect(
                "Anwesende Spieler auswählen",
                options=st.session_state.players,
                default=st.session_state.players[:8]
            )
            
            submit_session = st.form_submit_button("Session starten")
            if submit_session:
                if len(selected_players) < 2:
                    st.error("Bitte mindestens 2 Spieler auswählen!")
                else:
                    new_id = f"S-{len(st.session_state.sessions) + 1}"
                    new_ses = {
                        "id": new_id,
                        "date": session_date.strftime("%d.%m.%Y"),
                        "mode": mode,
                        "total_rounds": total_rounds,
                        "starting_players": selected_players,
                        "results": {}
                    }
                    st.session_state.sessions.append(new_ses)
                    st.session_state.active_session_id = new_id
                    st.success(f"Session {new_id} erfolgreich gestartet!")
                    st.rerun()
    elif password:
        st.error("Falsches Passwort!")
    else:
        st.info("Bitte Admin-Passwort eingeben, um eine neue Session zu starten.")

# ==========================================
# 5. TAB: MATCH-ARCHIV
# ==========================================
with tab_archiv:
    st.markdown("### 🗄️ Match-Archiv")
    if not st.session_state.sessions:
        st.info("Bisher keine vergangenen Sessions im Archiv.")
    else:
        for ses in reversed(st.session_state.sessions):
            with st.expander(f"Session {ses['id']} vom {ses['date']} ({ses['mode']})"):
                st.write(f"**Teilnehmer:** {', '.join(ses['starting_players'])}")
                if not ses["results"]:
                    st.caption("Keine Ergebnisse eingetragen.")
                else:
                    for k, v in ses["results"].items():
                        st.markdown(f"- **{k}**: {v['p1']} ({v['legs_p1']}) vs {v['p2']} ({v['legs_p2']}) | Sieger: **{v['winner']}**")
