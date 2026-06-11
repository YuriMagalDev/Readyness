import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import streamlit as st
import pandas as pd
from src.garmin_client import GarminClient
from src.data_processor import DataProcessor
from src.health_monitor import HealthMonitor
from src.training_planner import TrainingPlanner

st.set_page_config(page_title="Garmin AI Coach", page_icon="🏃", layout="wide")

STATUS_COLORS = {"verde": "🟢", "amarelo": "🟡", "vermelho": "🔴"}

@st.cache_resource(show_spinner="Conectando ao Garmin...")
def get_client():
    return GarminClient()

@st.cache_data(ttl=3600, show_spinner="Carregando dados...")
def load_data():
    client = get_client()
    processor = DataProcessor()
    activities = client.get_activities(28)
    hr_data = client.get_heart_rate_stats(7)
    sleep_data = client.get_sleep(14)
    battery_data = client.get_body_battery(7)
    context = processor.build_context_summary(activities, hr_data, sleep_data, battery_data)
    return context, activities, hr_data, battery_data

page = st.sidebar.radio("Navegação", ["🟢 Hoje", "📅 Plano Semanal", "📊 Dados"])

try:
    context, activities, hr_data, battery_data = load_data()
except Exception as e:
    st.error(f"Erro ao carregar dados: {e}")
    st.stop()

if page == "🟢 Hoje":
    st.title("Status do Dia")
    monitor = HealthMonitor()
    with st.spinner("Consultando coach..."):
        status_data = monitor.check(context)

    emoji = STATUS_COLORS.get(status_data["status"], "⚪")
    st.markdown(f"## {emoji} {status_data['status'].upper()}")
    st.info(f"**Motivo:** {status_data['motivo']}")
    st.success(f"**Recomendação:** {status_data['recomendacao']}")

    col1, col2, col3 = st.columns(3)
    col1.metric("FC Repouso média 7d", f"{context['resting_hr_avg_7d']} bpm")
    col2.metric("Body Battery médio", f"{context['morning_battery_avg']}")
    col3.metric("Dívida de sono", f"{context['sleep_debt_hours']}h")

elif page == "📅 Plano Semanal":
    st.title("Plano Semanal")
    if st.button("🔄 Gerar Plano", type="primary"):
        planner = TrainingPlanner()
        with st.spinner("Gerando plano com Sonnet..."):
            try:
                plan = planner.generate_weekly_plan(context)
                st.session_state["plano"] = plan
            except Exception as e:
                st.error(f"Erro ao gerar plano: {e}")

    if "plano" in st.session_state:
        df = pd.DataFrame(st.session_state["plano"])
        st.dataframe(df, use_container_width=True)

elif page == "📊 Dados":
    st.title("Dados do Garmin")

    st.subheader("Body Battery — 7 dias")
    battery_vals = [
        day[0]["charged"] if day and isinstance(day, list) else 0
        for day in battery_data
    ]
    st.line_chart(battery_vals)

    st.subheader("FC Repouso — 7 dias")
    hr_vals = [d.get("restingHeartRate", 0) for d in hr_data]
    st.line_chart(hr_vals)

    st.subheader("Atividades — 28 dias")
    if activities:
        df_acts = pd.DataFrame([{
            "Data": a.get("startTimeLocal", "")[:10],
            "Atividade": a.get("activityName", ""),
            "Tipo": a.get("activityType", {}).get("typeKey", ""),
            "Duração (min)": round(a.get("duration", 0) / 60),
            "FC Média": a.get("averageHR", "-"),
        } for a in activities])
        st.dataframe(df_acts, use_container_width=True)
