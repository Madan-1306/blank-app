# app.py
import streamlit as st
import math
import datetime as dt
import matplotlib.pyplot as plt

st.set_page_config(page_title="AI Rail Traffic Control – Dindigul ↔ Manaparai", layout="wide")

# ----------------------------
# Helpers
# ----------------------------
def hhmm_to_minutes(t_str: str) -> int:
    """'10:22' -> minutes since 00:00."""
    h, m = map(int, t_str.split(":"))
    return h * 60 + m

def minutes_to_hhmm(m: int) -> str:
    m = int(round(m))
    h = (m // 60) % 24
    mm = m % 60
    return f"{h:02d}:{mm:02d}"

def travel_time_minutes(distance_km, speed_kmph):
    return 60.0 * distance_km / speed_kmph

def build_schedule(distance_km, v_exp, v_freight, dep_exp_planned, dep_freight_planned, headway_min,
                   w_exp=3.0, w_freight=1.0):
    """
    Returns the better of two safe schedules:
    A) Hold Freight at A (Express first)
    B) Delay Express at A (Freight first)
    """
    t_exp_run = travel_time_minutes(distance_km, v_exp)
    t_fre_run = travel_time_minutes(distance_km, v_freight)

    # ---- Option A: Hold Freight (Express first) ----
    dep_exp_A = dep_exp_planned
    arr_exp_A = dep_exp_A + t_exp_run
    # Freight must depart after Express clears B + headway
    dep_fre_A = max(dep_freight_planned, arr_exp_A + headway_min)
    arr_fre_A = dep_fre_A + t_fre_run
    delay_exp_A = max(0.0, dep_exp_A - dep_exp_planned)  # usually 0
    delay_fre_A = max(0.0, dep_fre_A - dep_freight_planned)
    score_A = w_exp * delay_exp_A + w_freight * delay_fre_A

    plan_A = dict(
        name="Option A – Hold Freight; Express first",
        dep_exp=dep_exp_A, arr_exp=arr_exp_A,
        dep_fre=dep_fre_A, arr_fre=arr_fre_A,
        delay_exp=delay_exp_A, delay_fre=delay_fre_A,
        score=score_A
    )

    # ---- Option B: Delay Express (Freight first) ----
    dep_fre_B = dep_freight_planned
    arr_fre_B = dep_fre_B + t_fre_run
    # Express must depart after Freight clears B + headway
    dep_exp_B = max(dep_exp_planned, arr_fre_B + headway_min)
    arr_exp_B = dep_exp_B + t_exp_run
    delay_exp_B = max(0.0, dep_exp_B - dep_exp_planned)
    delay_fre_B = max(0.0, dep_fre_B - dep_freight_planned)  # usually 0
    score_B = w_exp * delay_exp_B + w_freight * delay_fre_B

    plan_B = dict(
        name="Option B – Delay Express; Freight first",
        dep_exp=dep_exp_B, arr_exp=arr_exp_B,
        dep_fre=dep_fre_B, arr_fre=arr_fre_B,
        delay_exp=delay_exp_B, delay_fre=delay_fre_B,
        score=score_B
    )

    best = plan_A if plan_A["score"] <= plan_B["score"] else plan_B
    return best, plan_A, plan_B, (t_exp_run, t_fre_run)

def plot_time_distance(plan, distance_km, base_min, title):
    """Time–distance chart."""
    t0 = base_min
    t1 = int(max(plan["arr_exp"], plan["arr_fre"]) + 10)

    ts = list(range(int(t0), int(t1)+1))
    x_exp, y_exp = [], []
    x_fre, y_fre = [], []

    # Express movement
    for t in ts:
        if t < plan["dep_exp"]:
            dist = 0.0
        elif t > plan["arr_exp"]:
            dist = distance_km
        else:
            frac = (t - plan["dep_exp"]) / (plan["arr_exp"] - plan["dep_exp"])
            dist = distance_km * frac
        x_exp.append(t)
        y_exp.append(dist)

    # Freight movement
    for t in ts:
        if t < plan["dep_fre"]:
            dist = 0.0
        elif t > plan["arr_fre"]:
            dist = distance_km
        else:
            frac = (t - plan["dep_fre"]) / (plan["arr_fre"] - plan["dep_fre"])
            dist = distance_km * frac
        x_fre.append(t)
        y_fre.append(dist)

    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(x_exp, y_exp, label="Express", linewidth=2)
    ax.plot(x_fre, y_fre, label="Freight", linewidth=2, linestyle="--")
    ax.set_title(title)
    ax.set_xlabel("Time (HH:MM)")
    ax.set_ylabel("Distance from Dindigul (km)")

    # x-axis ticks every ~5 minutes with labels as HH:MM
    ticks = list(range(int(t0), int(t1)+1, 5))
    ax.set_xticks(ticks)
    ax.set_xticklabels([minutes_to_hhmm(t) for t in ticks], rotation=45)
    ax.grid(True, alpha=0.3)
    ax.legend()
    st.pyplot(fig)

# ----------------------------
# UI
# ----------------------------
st.title("🚦 AI Rail Traffic Control (Tamil Nadu) – Dindigul → Manaparai (Single Track)")

with st.sidebar:
    st.header("Inputs")
    base_time_str = st.text_input("Base time (HH:MM)", "10:00")
    base_min = hhmm_to_minutes(base_time_str)

    distance_km = st.number_input("Section distance (km)", 1.0, 200.0, 40.0, 1.0)
    headway_min = st.number_input("Safe headway (minutes)", 1.0, 15.0, 3.0, 0.5)

    st.markdown("**Speeds**")
    v_exp = st.number_input("Express speed (km/h)", 40.0, 160.0, 110.0, 1.0)
    v_fre = st.number_input("Freight speed (km/h)", 20.0, 80.0, 40.0, 1.0)

    st.markdown("**Planned Departures (from Dindigul)**")
    dep_exp_str = st.text_input("Express planned dep", "10:22")
    dep_fre_str = st.text_input("Freight planned dep", "10:00")

    st.markdown("**Priority Weights (higher = more important to keep on time)**")
    w_exp = st.slider("Express weight", 1.0, 5.0, 3.0, 0.5)
    w_fre = st.slider("Freight weight", 1.0, 5.0, 1.0, 0.5)

    run = st.button("▶ Compute Best Plan")

st.write("This AI compares two safe plans and recommends the one with **minimum weighted delay** while respecting single-track safety (headway).")

if run:
    dep_exp_planned = hhmm_to_minutes(dep_exp_str)
    dep_fre_planned = hhmm_to_minutes(dep_fre_str)

    best, A, B, (t_exp_run, t_fre_run) = build_schedule(
        distance_km, v_exp, v_fre,
        dep_exp_planned, dep_fre_planned,
        headway_min, w_exp=w_exp, w_freight=w_fre
    )

    col1, col2 = st.columns([1,2])

    with col1:
        st.subheader("AI Recommendation")
        if best["name"].startswith("Option A"):
            st.success("✅ **Option A** – Hold **Freight** at Dindigul; let **Express** run first.")
        else:
            st.warning("✅ **Option B** – Delay **Express** at Dindigul; let **Freight** run first.")

        st.markdown(f"""
**Express**  
• Depart: **{minutes_to_hhmm(best['dep_exp'])}**  
• Arrive Manaparai: **{minutes_to_hhmm(best['arr_exp'])}**  
• Delay vs plan: **{best['delay_exp']:.1f} min**

**Freight**  
• Depart: **{minutes_to_hhmm(best['dep_fre'])}**  
• Arrive Manaparai: **{minutes_to_hhmm(best['arr_fre'])}**  
• Delay vs plan: **{best['delay_fre']:.1f} min**

**Headway enforced:** {headway_min:.1f} min
        """)

        st.info(f"Travel times → Express: **{t_exp_run:.1f} min**, Freight: **{t_fre_run:.1f} min**")

    with col2:
        st.subheader("Time–Distance Chart (Best Plan)")
        plot_time_distance(best, distance_km, base_min, title=best["name"])

    st.divider()
    st.subheader("Compare Both Options (details)")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"### {A['name']}")
        st.markdown(f"""
- Express: {minutes_to_hhmm(A['dep_exp'])} → {minutes_to_hhmm(A['arr_exp'])} (delay **{A['delay_exp']:.1f}** min)  
- Freight: {minutes_to_hhmm(A['dep_fre'])} → {minutes_to_hhmm(A['arr_fre'])} (delay **{A['delay_fre']:.1f}** min)  
- Weighted score: **{A['score']:.1f}**
        """)
        plot_time_distance(A, distance_km, base_min, title="Option A")

    with c2:
        st.markdown(f"### {B['name']}")
        st.markdown(f"""
- Express: {minutes_to_hhmm(B['dep_exp'])} → {minutes_to_hhmm(B['arr_exp'])} (delay **{B['delay_exp']:.1f}** min)  
- Freight: {minutes_to_hhmm(B['dep_fre'])} → {minutes_to_hhmm(B['arr_fre'])} (delay **{B['delay_fre']:.1f}** min)  
- Weighted score: **{B['score']:.1f}**
        """)
        plot_time_distance(B, distance_km, base_min, title="Option B")

    st.caption("AI chooses the option with the **lower weighted score** (respecting single-track safety).")
else:
    st.info("Set inputs on the left and click **Compute Best Plan**.")

