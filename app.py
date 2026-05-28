import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import plotly.express as px
import datetime
from groq import Groq  # নতুন এআই প্যাকেজ যোগ করা হলো

# Neo4j ক্লাউড ডেটাবেসের কানেকশন
URI = st.secrets["NEO4J_URI"]
USERNAME = st.secrets["NEO4J_USERNAME"]
PASSWORD = st.secrets["NEO4J_PASSWORD"]

# Groq API ক্লায়েন্ট সেটআপ (এখানে আপনার নোটপ্যাডের চাবিটি বসান)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# হিটম্যাপের জন্য বরিশাল জেলার জিপিএস (GPS) ডেটা
GPS_DATA = {
    "Barishal Sadar": {"lat": 22.7010, "lon": 90.3535},
    "Bakerganj": {"lat": 22.5528, "lon": 90.3344},
    "Babuganj": {"lat": 22.8333, "lon": 90.3000},
    "Wazirpur": {"lat": 22.8167, "lon": 90.2333},
    "Banaripara": {"lat": 22.7833, "lon": 90.1667},
    "Agailjhara": {"lat": 22.9667, "lon": 90.1500},
    "Gournadi": {"lat": 22.9736, "lon": 90.2264},
    "Hizla": {"lat": 22.9000, "lon": 90.5167},
    "Mehendiganj": {"lat": 22.8250, "lon": 90.5333},
    "Muladi": {"lat": 22.9167, "lon": 90.4167}
}

st.sidebar.title("Navigation")
menu = st.sidebar.radio("", ["Dashboard", "Strict Data Entry", "AI Alerts"])

# ১. মেইন ড্যাশবোর্ড
if menu == "Dashboard":
    st.title("📊 Live Epidemic Dashboard (Cloud)")
    st.markdown("---")
    
    with st.spinner("Fetching live geospatial data..."):
        try:
            driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
            with driver.session() as session:
                total_patients = session.run("MATCH (p:Patient) RETURN count(p) AS total").single()["total"]
                
                outbreak_query = session.run("MATCH (p:Patient) WITH p.location AS loc, count(p) AS cases WHERE cases >= 2 RETURN count(loc) AS total_outbreaks")
                active_outbreaks = outbreak_query.single()["total_outbreaks"]
                
                map_result = session.run("MATCH (p:Patient) WHERE p.latitude IS NOT NULL RETURN p.latitude AS lat, p.longitude AS lon, p.location AS location, p.symptom AS symptom")
                map_data = pd.DataFrame([record.data() for record in map_result])
            driver.close()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Outbreak Cases", value=total_patients, delta="Live Data")
            with col2:
                st.metric(label="High Risk Zones", value=active_outbreaks, delta="Alerts Active", delta_color="inverse")
            with col3:
                st.metric(label="BioNode AI Status", value="Cloud Active", delta="Groq Llama 3")
                
            st.markdown("---")
            
            if not map_data.empty:
                st.subheader("🔥 Live Geospatial Infection Heatmap")
                fig = px.density_mapbox(
                    map_data, lat='lat', lon='lon', z=[1]*len(map_data), radius=45, 
                    center=dict(lat=22.7010, lon=90.3535), zoom=8.5, 
                    mapbox_style="carto-darkmatter", color_continuous_scale="YlOrRd", 
                    hover_name="location", hover_data={"lat": False, "lon": False, "symptom": True}
                )
                fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
            else:
                st.info("🗺️ No map data available yet.")
                
        except Exception as e:
            st.error("❌ Database connection error.")
            st.write(e)

# ২. সিকিউরড ডেটা এন্ট্রি (এখন ক্লাউডেও কাজ করবে)
elif menu == "Strict Data Entry":
    st.title("📝 Secure Clinical Data Entry")
    st.markdown("---")
    
    st.info("💡 **Operator Input:** Select the map location step-by-step and enter patient details.")
    
    st.subheader("1. Patient Age")
    patient_age = st.number_input("Select Age", min_value=1, max_value=120, step=1)
    
    st.markdown("---")
    st.subheader("2. Map Location (Deep Filtering)")
    patient_location = "Select Area..." 
    
    division = st.selectbox("Division", ["Select Division...", "Barishal"])
    if division == "Barishal":
        district = st.selectbox("District", ["Select District...", "Barishal"])
        if district == "Barishal":
            patient_location = st.selectbox("Upazila / Area", ["Select Area...", "Barishal Sadar", "Bakerganj", "Babuganj", "Wazirpur", "Banaripara", "Agailjhara", "Gournadi", "Hizla", "Mehendiganj", "Muladi"])
            
    st.markdown("---")
    st.subheader("3. Clinical Symptoms")
    patient_symptom = st.text_input("Enter Symptoms or Disease (e.g., Fever, Red rash)")
    
    if st.button("Validate & Save to Cloud"):
        errors = []
        if patient_location == "Select Area...":
            errors.append("Map Location Error: You must select the deep location.")
            
        forbidden_locations_in_symptom = ["barishal", "bakerganj", "babuganj", "wazirpur", "banaripara", "agailjhara", "gournadi", "hizla", "mehendiganj", "muladi", "dhaka"]
        if any(loc in patient_symptom.lower() for loc in forbidden_locations_in_symptom):
            errors.append("Wrong Input! You typed a map location in the Disease box.")
            
        if not patient_symptom.strip():
            errors.append("Symptom box cannot be empty.")
        elif any(char.isdigit() for char in patient_symptom):
            errors.append("Wrong Input! You cannot put numbers in the Disease box.")
            
        if errors:
            for error in errors:
                st.error(f"❌ {error}")
        else:
            with st.spinner("Saving data to the cloud..."):
                try:
                    patient_lat = GPS_DATA[patient_location]["lat"]
                    patient_lon = GPS_DATA[patient_location]["lon"]
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
                    with driver.session() as session:
                        session.run(
                            """
                            CREATE (p:Patient {
                                age: $age, location: $location, symptom: $symptom, 
                                latitude: $lat, longitude: $lon, timestamp: $time
                            })
                            """,
                            age=patient_age, location=patient_location, symptom=patient_symptom, 
                            lat=patient_lat, lon=patient_lon, time=current_time
                        )
                    driver.close()
                    st.success(f"✅ Data for {patient_location} successfully saved!")
                except Exception as e:
                    st.error("❌ Database connection error.")
                    st.write(e)

# ৩. এআই অ্যালার্ট পেজ (Groq Cloud AI Version)
elif menu == "AI Alerts":
    st.title("🤖 BioNode AI - Live Outbreak Analysis")
    st.markdown("---")
    st.info("🧠 Analyzing live epidemiological data from the cloud using Llama-3 (Groq API)...")
    
    if st.button("Generate Live AI Alert"):
        with st.spinner("BioNode AI is analyzing data..."):
            try:
                # ১. ডেটাবেস থেকে সর্বশেষ ডেটা আনা
                driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
                with driver.session() as session:
                    # সর্বশেষ ১৫ জন রোগীর ডেটা এআই-কে দেওয়ার জন্য আনছি
                    result = session.run("MATCH (p:Patient) RETURN p.location AS location, p.symptom AS symptom, p.age AS age ORDER BY p.timestamp DESC LIMIT 15")
                    recent_cases = [record.data() for record in result]
                driver.close()
                
                if not recent_cases:
                    st.warning("No data found in the database to analyze.")
                else:
                    # ২. এআই-এর জন্য প্রম্পট (নির্দেশনা) তৈরি
                    prompt_text = f"You are an expert Epidemiologist AI. Analyze these recent patient cases from Barishal region: {recent_cases}. Write a short, highly professional medical alert summarizing the active outbreak trends and give 2 quick safety recommendations. Keep it under 4-5 sentences."
                    
                    # ৩. Groq API-কে কল করে উত্তর নিয়ে আসা
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt_text}],
                        model="llama-3.1-8b-instant",
                    )
                    ai_response = chat_completion.choices[0].message.content
                    
                    # ৪. স্ক্রিনে আউটপুট দেখানো
                    st.subheader("🚨 Real-time AI Outbreak Report")
                    st.write(ai_response)
                    
            except Exception as e:
                st.error("❌ Failed to connect with AI or Database.")
                st.write(e)