import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import plotly.express as px
import datetime
import json
import random
from groq import Groq  # নতুন এআই প্যাকেজ যোগ করা হলো

# Neo4j ক্লাউড ডেটাবেসের কানেকশন
URI = st.secrets["NEO4J_URI"]
USERNAME = st.secrets["NEO4J_USERNAME"]
PASSWORD = st.secrets["NEO4J_PASSWORD"]

# Groq API ক্লায়েন্ট সেটআপ (এখানে আপনার নোটপ্যাডের চাবিটি বসান)
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Load Bangladesh administrative divisions, districts, and upazilas
@st.cache_data
def load_bd_hierarchy():
    with open("database/bangladesh_hierarchy.json", "r", encoding="utf-8") as f:
        return json.load(f)

BD_HIERARCHY = load_bd_hierarchy()

# Get all lowercased location names for dynamic input validation
@st.cache_data
def get_all_locations_set():
    names = set()
    for div in BD_HIERARCHY:
        names.add(div["name"].lower())
        names.add(div["bn_name"].lower())
        for dist in div["districts"]:
            names.add(dist["name"].lower())
            names.add(dist["bn_name"].lower())
            for up in dist["upazilas"]:
                names.add(up["name"].lower())
                names.add(up["bn_name"].lower())
    return names

ALL_LOCATION_NAMES = get_all_locations_set()

# Helper to calculate time threshold
def get_time_threshold(filter_option):
    if filter_option == "All Time":
        return None
    days = 7 if "7" in filter_option else (14 if "14" in filter_option else 30)
    threshold = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    return threshold

st.sidebar.title("Navigation")
menu = st.sidebar.radio("", ["Dashboard", "Strict Data Entry", "AI Alerts"])

# Time filter only for Dashboard
time_filter = "All Time"
if menu == "Dashboard":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")
    time_filter = st.sidebar.selectbox("Select Time Range", ["All Time", "Last 7 Days", "Last 14 Days", "Last 30 Days"])

# ১. মেইন ড্যাশবোর্ড
if menu == "Dashboard":
    st.title("📊 Live Epidemic Dashboard (Cloud)")
    st.markdown("---")
    
    with st.spinner("Fetching live geospatial data..."):
        try:
            threshold = get_time_threshold(time_filter)
            
            driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
            with driver.session() as session:
                if threshold:
                    total_query = "MATCH (p:Patient) WHERE p.timestamp >= $threshold RETURN count(p) AS total"
                    outbreak_query_str = "MATCH (p:Patient) WHERE p.timestamp >= $threshold WITH p.location AS loc, count(p) AS cases WHERE cases >= 2 RETURN count(loc) AS total_outbreaks"
                    map_query_str = "MATCH (p:Patient) WHERE p.timestamp >= $threshold AND p.latitude IS NOT NULL RETURN p.latitude AS lat, p.longitude AS lon, p.location AS location, p.symptom AS symptom"
                    
                    total_patients = session.run(total_query, threshold=threshold).single()["total"]
                    active_outbreaks = session.run(outbreak_query_str, threshold=threshold).single()["total_outbreaks"]
                    map_result = session.run(map_query_str, threshold=threshold)
                else:
                    total_patients = session.run("MATCH (p:Patient) RETURN count(p) AS total").single()["total"]
                    active_outbreaks = session.run("MATCH (p:Patient) WITH p.location AS loc, count(p) AS cases WHERE cases >= 2 RETURN count(loc) AS total_outbreaks").single()["total_outbreaks"]
                    map_result = session.run("MATCH (p:Patient) WHERE p.latitude IS NOT NULL RETURN p.latitude AS lat, p.longitude AS lon, p.location AS location, p.symptom AS symptom")
                
                map_data = pd.DataFrame([record.data() for record in map_result])
            driver.close()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Outbreak Cases", value=total_patients, delta=f"{time_filter}")
            with col2:
                st.metric(label="High Risk Zones", value=active_outbreaks, delta="Alerts Active", delta_color="inverse")
            with col3:
                st.metric(label="BioNode AI Status", value="Cloud Active", delta="Groq Llama 3")
                
            st.markdown("---")
            
            if not map_data.empty:
                st.subheader("🔥 Live Geospatial Infection Heatmap")
                mean_lat = map_data['lat'].mean()
                mean_lon = map_data['lon'].mean()
                lat_span = map_data['lat'].max() - map_data['lat'].min()
                lon_span = map_data['lon'].max() - map_data['lon'].min()
                zoom_level = 6.2 if (lat_span > 1.5 or lon_span > 1.5) else 8.5
                
                fig = px.density_mapbox(
                    map_data, lat='lat', lon='lon', z=[1]*len(map_data), radius=40, 
                    center=dict(lat=mean_lat, lon=mean_lon), zoom=zoom_level, 
                    mapbox_style="carto-darkmatter", color_continuous_scale="YlOrRd", 
                    hover_name="location", hover_data={"lat": False, "lon": False, "symptom": True}
                )
                fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
            else:
                st.info("🗺️ No map data available yet for the selected timeframe.")
                
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
    selected_district = "Select District..."
    selected_division = "Select Division..."
    patient_lat = None
    patient_lon = None
    
    divisions_list = ["Select Division..."] + [div["name"] for div in BD_HIERARCHY]
    selected_division = st.selectbox("Division", divisions_list)
    
    if selected_division != "Select Division...":
        div_data = next(div for div in BD_HIERARCHY if div["name"] == selected_division)
        districts_list = ["Select District..."] + [dist["name"] for dist in div_data["districts"]]
        selected_district = st.selectbox("District", districts_list)
        
        if selected_district != "Select District...":
            dist_data = next(dist for dist in div_data["districts"] if dist["name"] == selected_district)
            upazilas_list = ["Select Area..."] + [up["name"] for up in dist_data["upazilas"]]
            selected_upazila = st.selectbox("Upazila / Area", upazilas_list)
            
            if selected_upazila != "Select Area...":
                patient_location = selected_upazila
                
                # Hardcoded high-resolution coordinates for Barishal region
                GPS_DATA_PRESETS = {
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
                
                if patient_location in GPS_DATA_PRESETS:
                    patient_lat = GPS_DATA_PRESETS[patient_location]["lat"]
                    patient_lon = GPS_DATA_PRESETS[patient_location]["lon"]
                else:
                    # Fallback to District center coordinates with small random offset
                    offset_lat = random.uniform(-0.015, 0.015)
                    offset_lon = random.uniform(-0.015, 0.015)
                    patient_lat = dist_data["lat"] + offset_lat
                    patient_lon = dist_data["lon"] + offset_lon
            
    st.markdown("---")
    st.subheader("3. Clinical Symptoms")
    patient_symptom = st.text_input("Enter Symptoms or Disease (e.g., Fever, Red rash)")
    
    if st.button("Validate & Save to Cloud"):
        errors = []
        if patient_location == "Select Area...":
            errors.append("Map Location Error: You must select the deep location up to the Upazila/Area level.")
            
        # Dynamic location validation: verify if user typed any known location name in the symptom box
        symptom_words = set(w.strip(".,!?()\"'-").lower() for w in patient_symptom.split())
        matched_locations = symptom_words.intersection(ALL_LOCATION_NAMES)
        if matched_locations:
            errors.append(f"Wrong Input! You typed a map location ('{', '.join(matched_locations)}') in the Disease/Symptom box. Please type only medical conditions.")
            
        if not patient_symptom.strip():
            errors.append("Symptom box cannot be empty.")
        elif any(char.isdigit() for char in patient_symptom):
            errors.append("Wrong Input! You cannot put numbers in the Disease/Symptom box.")
            
        if errors:
            for error in errors:
                st.error(f"❌ {error}")
        else:
            with st.spinner("Saving data to the cloud..."):
                try:
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
                    st.success(f"✅ Data for {patient_location} ({selected_district}, {selected_division}) successfully verified and saved!")
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
                # ১. ডেটাবেস থেকে ৩০ দিনের ডেটা আনা
                threshold_30_days = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
                
                driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
                with driver.session() as session:
                    # Query for cases in the last 30 days
                    result = session.run(
                        "MATCH (p:Patient) WHERE p.timestamp >= $threshold RETURN p.location AS location, p.symptom AS symptom, p.age AS age, p.timestamp AS timestamp ORDER BY p.timestamp DESC",
                        threshold=threshold_30_days
                    )
                    recent_cases = [record.data() for record in result]
                    
                    # Robust Fallback: If 30-day case count is 0, fetch the last 30 cases overall
                    is_fallback = False
                    if not recent_cases:
                        is_fallback = True
                        result = session.run("MATCH (p:Patient) RETURN p.location AS location, p.symptom AS symptom, p.age AS age, p.timestamp AS timestamp ORDER BY p.timestamp DESC LIMIT 30")
                        recent_cases = [record.data() for record in result]
                driver.close()
                
                if not recent_cases:
                    st.warning("No data found in the database to analyze.")
                else:
                    if is_fallback:
                        st.warning("⚠️ Note: No active cases found in the last 30 days. Fallback mode: analyzing the last 30 database records.")
                    
                    # ২. এআই-এর জন্য প্রম্পট (JSON রেসপন্স ফরম্যাটের নির্দেশনা) তৈরি
                    prompt_text = f"""
                    You are an expert Epidemiologist AI.
                    Analyze these recent patient cases from Bangladesh: {recent_cases}.
                    
                    Return a JSON object containing an epidemiological alert and risk assessment.
                    The JSON must strictly match the following schema:
                    {{
                      "hotspots": [
                        {{
                          "location": "Name of Upazila/District",
                          "disease": "Summarized disease/symptom (e.g. Dengue, Cholera, Influenza-like illness)",
                          "risk_level": "High" or "Medium" or "Low",
                          "case_count": number_of_cases,
                          "spreading_outlook": "Short description of potential spread"
                        }}
                      ],
                      "overall_summary": "A professional 3-sentence summary of the current active outbreak trends based on the provided data.",
                      "safety_recommendations": [
                        "Specific action recommendation 1",
                        "Specific action recommendation 2"
                      ]
                    }}
                    
                    Analyze the data over the timeframe provided. Focus on identifying disease clusters in same location.
                    Assign Risk Level based on cluster size and disease severity (e.g. high cases of fever/rash in same location = High Risk).
                    """
                    
                    # ৩. Groq API-কে কল করে JSON উত্তর নিয়ে আসা
                    chat_completion = client.chat.completions.create(
                        messages=[{"role": "user", "content": prompt_text}],
                        model="llama-3.1-8b-instant",
                        response_format={"type": "json_object"}
                    )
                    ai_response = chat_completion.choices[0].message.content
                    
                    # ৪. স্ক্রিনে আউটপুট দেখানো
                    try:
                        ai_data = json.loads(ai_response)
                        
                        # Display overall summary
                        st.subheader("📊 Nationwide Epidemiological Summary")
                        st.info(ai_data.get("overall_summary", ""))
                        
                        # Display hotspots as columns or cards
                        st.subheader("🚨 Active Outbreak Hotspots")
                        hotspots = ai_data.get("hotspots", [])
                        if not hotspots:
                            st.success("No active hotspots or high-risk clusters identified.")
                        else:
                            for hotspot in hotspots:
                                loc = hotspot.get("location", "Unknown")
                                disease = hotspot.get("disease", "Unknown")
                                risk = hotspot.get("risk_level", "Low").title()
                                count = hotspot.get("case_count", 1)
                                outlook = hotspot.get("spreading_outlook", "")
                                
                                # Choose visual style based on risk level
                                if risk == "High":
                                    st.error(f"🔴 **{loc}** — Risk Level: **{risk}** ({count} Cases)")
                                elif risk == "Medium":
                                    st.warning(f"🟡 **{loc}** — Risk Level: **{risk}** ({count} Cases)")
                                else:
                                    st.success(f"🟢 **{loc}** — Risk Level: **{risk}** ({count} Cases)")
                                
                                st.write(f"**Disease/Cluster:** {disease} | **Spread Outlook:** {outlook}")
                                st.markdown("---")
                        
                        # Display Recommendations
                        st.subheader("🛡️ Safety & Prevention Guidelines")
                        for rec in ai_data.get("safety_recommendations", []):
                            st.markdown(f"- {rec}")
                            
                    except Exception as json_err:
                        # Fallback to plain text rendering if JSON parse fails
                        st.subheader("🚨 Real-time AI Outbreak Report")
                        st.write(ai_response)
                        
            except Exception as e:
                st.error("❌ Failed to connect with AI or Database.")
                st.write(e)