with tab_kader:
    st.subheader("Kader & Spielerbilanz")
    st.write("Live berechnete Bilanz des festen Stammkaders (exklusive Gastspieler).")
    
    # Dynamische Berechnung aus allen Sessions
    stats = {p: {"Matches": 0, "Siege": 0, "Niederlagen": 0} for p in kader}
    total_matches_played = 0
    
    for sess in st.session_state.sessions_list:
        for match in sess.get("results", {}).values():
            winner = match.get("winner")
            loser = match.get("loser")
            total_matches_played += 1
            if winner in stats:
                stats[winner]["Matches"] += 1
                stats[winner]["Siege"] += 1
            if loser in stats:
                stats[loser]["Matches"] += 1
                stats[loser]["Niederlagen"] += 1

    # Metriken oben berechnen
    total_wins = sum(s["Siege"] for s in stats.values())
    avg_win_rate = f"{(total_wins / total_matches_played * 100):.0f}%" if total_matches_played > 0 else "0%"

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="Aktive Spieler", value=len(kader), delta="im Kader")
    with col2:
        st.metric(label="Absolvierte Spiele", value=str(total_matches_played), delta="aus Sessions")
    with col3:
        st.metric(label="Ø Siegquote", value=avg_win_rate, delta="gesamt")
        
    st.write("### Spielerübersicht & Rangliste")
    suche = st.text_input("Spieler suchen...", "")
    
    table_rows = []
    for p in kader:
        m = stats[p]["Matches"]
        s = stats[p]["Siege"]
        n = stats[p]["Niederlagen"]
        quote = f"{(s / m * 100):.0f}%" if m > 0 else "0%"
        table_rows.append({
            "Spieler": p,
            "Matches": m,
            "Siege": s,
            "Niederlagen": n,
            "Siegquote": quote
        })
        
    df_kader = pd.DataFrame(table_rows)
    if suche:
        df_kader = df_kader[df_kader["Spieler"].str.contains(suche, case=False)]
    st.dataframe(df_kader, use_container_width=True, hide_index=True)
