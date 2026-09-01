st.markdown("### 🔴 Live-Übersicht (Aktive Session)")
    active_sessions = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
    if not active_sessions:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Live-Übersicht zu sehen.")
    else:
        curr_sess = active_sessions[0]
        st.caption(f"Aktive Session: ID **{curr_sess['id']}** vom {curr_sess['datum']} ({curr_sess['modus']} · {curr_sess['boards']})")
        
        boards_count = curr_sess.get("boards_count", 6)
        active_boards_list = get_boards_list(boards_count)
        total_rounds = curr_sess.get("total_rounds", 4)
        
        # Grid-Layout für die Boards
        live_cols = st.columns(len(active_boards_list))
        for b_i, b_name in enumerate(active_boards_list):
            with live_cols[b_i]:
                # Kachel-Design für jedes Board
                with st.container(border=True):
                    res = curr_sess.get("results", {})
                    # Berechnen der Runden-Statistik
                    completed_rounds = [r for (r, b) in res.keys() if b == b_name]
                    rounds_played = len(completed_rounds)
                    next_r = max(completed_rounds) + 1 if completed_rounds else 1
                    
                    st.markdown(f"<h4 style='text-align: center; margin-bottom: 5px;'>{b_name}</h4>", unsafe_allow_html=True)
                    
                    if next_r <= total_rounds:
                        players_now = get_board_players(curr_sess, min(next_r, total_rounds), b_name)
                        
                        # Runden-Informationen
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em; margin-top: -10px;'>Gespielte Runden: {rounds_played} <br> Aktuelle Runde: {next_r}/{total_rounds}</p>", unsafe_allow_html=True)
                        
                        # Matchup
                        st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1em;'>{players_now[0]}</div>", unsafe_allow_html=True)
                        st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 4px 0;'>VS</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1em;'>{players_now[1]}</div>", unsafe_allow_html=True)
                        
                        st.divider()
                        
                        # Scoreboard-Platzhalter (Legs und Punkte)
                        st.markdown("<p style='text-align: center; font-size: 0.9em; margin-bottom: 0px;'>Aktueller Leg-Stand</p>", unsafe_allow_html=True)
                        st.markdown("<h3 style='text-align: center; margin-top: 0px;'>0 : 0</h3>", unsafe_allow_html=True)
                        st.markdown("<p style='text-align: center; color: gray; font-size: 0.85em;'>Leg 1 | Punkte: 501 - 501</p>", unsafe_allow_html=True)
                        
                        # Direkter Button zur Eingabe
                        if st.button("🎯 Ergebnis eintragen", key=f"live_btn_{b_name}_{next_r}", use_container_width=True):
                            open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))
                    else:
                        st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em; margin-top: -10px;'>Alle {total_rounds} Runden beendet</p>", unsafe_allow_html=True)
                        st.success("✅ Board abgeschlossen")
