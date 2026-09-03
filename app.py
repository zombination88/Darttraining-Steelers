# --- DAUERBRENNER LOGIK ---
    max_matches = max([stats[p]["Matches"] for p in kader], default=0)
    dauerbrenner_help = None
    
    if max_matches > 0:
        top_active = [p for p in kader if stats[p]["Matches"] == max_matches]
        if len(top_active) == len(kader):
            active_player = "Alle gleichauf"
        elif len(top_active) <= 2:
            active_player = " & ".join(top_active)
        else:
            active_player = f"{len(top_active)} Spieler"
            dauerbrenner_help = "Aktuelle Dauerbrenner:\n\n" + "\n".join([f"- {p}" for p in top_active])
        active_count = f"{max_matches} Matches"
    else:
        active_player, active_count = "N/A", "0 Matches"
    # --------------------------
        
    best_avg_player = "N/A"
    best_avg_val = 0.0
    for p in kader:
        if stats[p]["Avg_Count"] > 0:
            p_avg = stats[p]["Avg_Sum"] / stats[p]["Avg_Count"]
            if p_avg > best_avg_val:
                best_avg_val = p_avg
                best_avg_player = p
    avg_text = f"Ø {best_avg_val:.1f}" if best_avg_val > 0 else "Kein Avg erfasst"
    
    max_180_player = max(kader, key=lambda p: stats[p]["180er"])
    max_180_count = stats[max_180_player]["180er"]
    if max_180_count > 0:
        machine_player = max_180_player
        machine_text = f"{max_180_count}x geworfen"
    else:
        machine_player, machine_text = "N/A", "0 geworfen"

    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1: st.metric(label="🏆 MVP (Siegquote)", value=mvp_player, delta=mvp_text, delta_color="normal")
        with c2: st.metric(label="🔥 Dauerbrenner", value=active_player, delta=active_count, delta_color="off", help=dauerbrenner_help)
        st.divider()
        c3, c4 = st.columns(2)
        with c3: st.metric(label="📊 Bester Gesamt-Avg", value=best_avg_player, delta=avg_text, delta_color="off")
        with c4: st.metric(label="🎯 180er Maschine", value=machine_player, delta=machine_text, delta_color="off")
