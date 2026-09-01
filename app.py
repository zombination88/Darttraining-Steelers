st.markdown("### 🔴 Laufende Session")
    active_sessions = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
    if not active_sessions:
        st.info("Derzeit läuft keine aktive Session. Starte eine neue Session, um die Übersicht zu sehen.")
    else:
        curr_sess = active_sessions[0]
        st.caption(f"Session-ID: **{curr_sess['id']}** vom {curr_sess['datum']} ({curr_sess['modus']})")
        
        boards_count = curr_sess.get("boards_count", 6)
        active_boards_list = get_boards_list(boards_count)
        total_rounds = curr_sess.get("total_rounds", 4)
        
        # Tagesstatistik für diese Session berechnen
        session_stats = {p: {"wins": 0, "losses": 0} for p in curr_sess.get("spieler", [])}
        for match in curr_sess.get("results", {}).values():
            if match.get("winner") in session_stats:
                session_stats[match["winner"]]["wins"] += 1
            if match.get("loser") in session_stats:
                session_stats[match["loser"]]["losses"] += 1
        
        # Zeilenumbruch nach jeweils 3 Boards für bessere Lesbarkeit der Namen
        cols_per_row = 3
        for i in range(0, len(active_boards_list), cols_per_row):
            cols = st.columns(cols_per_row)
            for j in range(cols_per_row):
                if i + j < len(active_boards_list):
                    b_name = active_boards_list[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            res = curr_sess.get("results", {})
                            completed_rounds = [r for (r, b) in res.keys() if b == b_name]
                            rounds_played = len(completed_rounds)
                            next_r = max(completed_rounds) + 1 if completed_rounds else 1
                            
                            st.markdown(f"<h4 style='text-align: center; margin-bottom: 0;'>{b_name}</h4>", unsafe_allow_html=True)
                            
                            if next_r <= total_rounds:
                                players_now = get_board_players(curr_sess, min(next_r, total_rounds), b_name)
                                p1, p2 = players_now[0], players_now[1]
                                
                                p1_stat = f"{session_stats.get(p1, {}).get('wins', 0)}S - {session_stats.get(p1, {}).get('losses', 0)}N" if p1 != "Offen" else ""
                                p2_stat = f"{session_stats.get(p2, {}).get('wins', 0)}S - {session_stats.get(p2, {}).get('losses', 0)}N" if p2 != "Offen" else ""
                                
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Runde {next_r}/{total_rounds}</p>", unsafe_allow_html=True)
                                
                                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1em;'>{p1}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='text-align: center; color: gray; font-size: 0.8em;'>{p1_stat}</div>", unsafe_allow_html=True)
                                
                                st.markdown("<div style='text-align: center; color: #ff4b4b; font-size: 0.9em; margin: 5px 0;'>VS</div>", unsafe_allow_html=True)
                                
                                st.markdown(f"<div style='text-align: center; font-weight: bold; font-size: 1.1em;'>{p2}</div>", unsafe_allow_html=True)
                                st.markdown(f"<div style='text-align: center; color: gray; font-size: 0.8em; margin-bottom: 15px;'>{p2_stat}</div>", unsafe_allow_html=True)
                                
                                if st.button("🎯 Ergebnis eintragen", key=f"live_btn_{b_name}_{next_r}", use_container_width=True):
                                    open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))
                            else:
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle {total_rounds} Runden beendet</p>", unsafe_allow_html=True)
                                st.success("✅ Board abgeschlossen")
