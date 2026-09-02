<!-- ... existing code ... -->
if "sessions_list" not in st.session_state:
    st.session_state.sessions_list = load_data()

tab_übersicht, tab_kader, tab_session, tab_archiv, tab_bdv = st.tabs(["Übersicht", "Kader", "Session", "Match-Archiv", "BDV-Regeln"])
<!-- ... existing code ... -->
with tab_übersicht:
    st.subheader("Übersicht & Live-Status")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("➕ Neue Session", type="primary", use_container_width=True, key="quick_start_btn"):
            open_new_session_dialog()
    with col_btn2:
        active_sessions_for_btn = [s for s in st.session_state.sessions_list if not is_session_completed(s)]
        if active_sessions_for_btn:
            if st.button("⚙️ Session bearbeiten", use_container_width=True, key="edit_active_btn"):
                open_edit_session_dialog(st.session_state.sessions_list.index(active_sessions_for_btn[0]))
        else:
            st.button("⚙️ Session bearbeiten", use_container_width=True, disabled=True)
        
    st.write("")
    
    # MOBILE OPTIMIERUNG: 2x2 Grid anstelle von 4 Spalten
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Up & Down Abende", value=str(len(st.session_state.sessions_list)), delta="Runden pro Abend")
        st.metric(label="Aktive Spieler", value="10", delta="im Kader")
    with col2:
        st.metric(label="Gespielte Matches", value="Dynamisch", delta="siehe Kader")
        st.metric(label="Aktueller Kaiser", value="Noch offen", delta="Training")
        
    st.write("")
<!-- ... existing code ... -->
                                st.write("")
                                if st.button("🎯 Ergebnis eintragen", key=f"live_btn_{b_name}_{next_r}", use_container_width=True, disabled=not ready):
                                    open_board_dialog(b_name, st.session_state.sessions_list.index(curr_sess))
                            else:
                                st.markdown(f"<p style='text-align: center; color: gray; font-size: 0.85em;'>Alle {total_rounds} Runden beendet</p>", unsafe_allow_html=True)
                                st.success("✅ Abgeschlossen")

    st.write("")
    
    # MOBILE OPTIMIERUNG: Lange Texte und Historie in einklappbare Container packen
    with st.expander("📊 Letzte Session - Details & Highlights", expanded=False):
        display_sess = None
        for s in st.session_state.sessions_list:
            if is_session_completed(s) or s.get("results"):
                display_sess = s
                break
        if not display_sess and st.session_state.sessions_list:
            display_sess = st.session_state.sessions_list[0]
            
        if display_sess:
            l_date = display_sess.get('datum', '–')
            l_results = display_sess.get('results', {})
            
            kaiser_winner = "Noch offen"
            kaiser_matches = [(r, m) for (r, b), m in l_results.items() if b == "Kaiser B1" and m.get("winner") and " & " not in m.get("s1", "") and " & " not in m.get("s2", "")]
            if kaiser_matches:
                kaiser_matches.sort(key=lambda x: x[0], reverse=True)
                kaiser_winner = kaiser_matches[0][1].get("winner")
            
            count_180s = {}
            match_avgs = []
            for m in l_results.values():
                s1_name = m.get("s1", "")
                s2_name = m.get("s2", "")
                c1 = int(m.get("180_s1", 0))
                c2 = int(m.get("180_s2", 0))
                a1 = float(m.get("avg_s1", 0.0))
                a2 = float(m.get("avg_s2", 0.0))
                
                if s1_name and " & " not in s1_name: count_180s[s1_name] = count_180s.get(s1_name, 0) + c1
                if s2_name and " & " not in s2_name: count_180s[s2_name] = count_180s.get(s2_name, 0) + c2
                
                if s1_name and " & " not in s1_name and a1 > 0: match_avgs.append((s1_name, a1))
                if s2_name and " & " not in s2_name and a2 > 0: match_avgs.append((s2_name, a2))
            
            most_180_text = "Keine"
            if count_180s:
                top_player = max(count_180s, key=count_180s.get)
                if count_180s[top_player] > 0:
                    most_180_text = f"{top_player} ({count_180s[top_player]}x)"
            
            best_avg_text = "–"
            if match_avgs:
                top_avg_player, top_avg_val = max(match_avgs, key=lambda x: x[1])
                best_avg_text = f"{top_avg_player} ({top_avg_val:.1f})"
            
            st.info(f"**Datum:** {l_date}\n\n**Kaiser B1 (Einzel):** 👑 {kaiser_winner}\n\n**Höchster Einzel-Average:** 📊 {best_avg_text}\n\n**Meiste 180er:** 🎯 {most_180_text}\n\n**Fahrstuhl-Award:** Offen")
        else:
            st.info("**Datum:** –\n\n**Kaiser B1 (Einzel):** Noch offen\n\n**Höchster Einzel-Average:** –\n\n**Meiste 180er:** –\n\n**Fahrstuhl-Award:** Offen")

    with st.expander("📈 Spitzenreiter & Formkurve", expanded=False):
        st.caption("Sortiert nach Siegquote und absolvierten Matches")
        
        stats_temp = {p: {"Matches": 0, "Siege": 0} for p in kader}
        for sess in st.session_state.sessions_list:
            for match in sess.get("results", {}).values():
                winner = match.get("winner", "")
                loser = match.get("loser", "")
                if winner and " & " not in winner:
                    for p in winner.split(" & "):
                        if p in stats_temp:
                            stats_temp[p]["Matches"] += 1
                            stats_temp[p]["Siege"] += 1
                if loser and " & " not in loser:
                    for p in loser.split(" & "):
                        if p in stats_temp:
                            stats_temp[p]["Matches"] += 1

        best_p = "Keiner"
        best_q = 0.0
        best_m = 0
        for p in kader:
            m = stats_temp[p]["Matches"]
            s = stats_temp[p]["Siege"]
            if m > 0:
                q = s / m
                if q > best_q or (q == best_q and m > best_m):
                    best_q = q
                    best_m = m
                    best_p = p

        st.markdown(f"**{best_p}** (Siegquote: {(best_q*100):.0f}% bei {best_m} Matches)")
        st.progress(best_q)

    with st.expander("🎯 Zuletzt ausgetragene Board-Matches", expanded=False):
        st.caption("Letzte Ergebnisse")
        
        all_matches = []
        for sess in st.session_state.sessions_list:
            sess_date = sess.get("datum", "")
            for (round_num, board_name), m_info in sess.get("results", {}).items():
                if not m_info.get("winner"):
                    continue
                all_matches.append({
                    "Datum": sess_date,
                    "Runde": round_num,
                    "Board": board_name,
                    "Spieler": f"{m_info['s1']} vs {m_info['s2']}",
                    "Ergebnis": m_info['ergebnis'],
                    "Sieger": m_info['winner'] if m_info['winner'] else "Offen"
                })
                
        if all_matches:
            df_matches = pd.DataFrame(all_matches)
            st.dataframe(df_matches, use_container_width=True, hide_index=True)
        else:
            st.info("Bisher wurden keine Board-Matches ausgetragen.")

with tab_kader:
<!-- ... existing code ... -->
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
        st.metric(label="Ø Siegquote", value=avg_win_rate, delta="gesamt")
    with col2:
        st.metric(label="Absolvierte Matches", value=str(player_matches_played), delta="aus Sessions")
        st.metric(label="Team-Gesamtschnitt", value=overall_team_avg, delta="Ø Average")
        
    st.write("")
    
    with st.expander("📈 Team-Entwicklung (Gesamt-Average über Sessions)", expanded=False):
        if team_session_avgs:
            df_trend = pd.DataFrame(team_session_avgs)
            st.line_chart(df_trend.set_index("Datum"))
        else:
            st.info("Noch nicht genügend Average-Daten vorhanden, um die Team-Entwicklung anzuzeigen.")

    st.write("### Spielerübersicht & Rangliste")
<!-- ... existing code ... -->
        df_kader = df_kader[df_kader["Spieler"].str.contains(suche, case=False)]
    st.dataframe(df_kader, use_container_width=True, hide_index=True)

    # DOPPEL-PAARUNGEN / COOP-STATISTIK FÜR DIE LIGA
    st.write("")
    with st.expander("🤝 Doppel-Paarungen (Coop-Statistik für die Liga)", expanded=False):
        st.caption("Auswertung aller Doppel- und Koop-Matches zur Findung der perfekten Ligapaarungen.")
        
        pair_stats = {}
<!-- ... existing code ... -->
