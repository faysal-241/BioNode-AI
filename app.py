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

# Helper distance calculation
def get_distance_km(lat1, lon1, lat2, lon2):
    import math
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# Helper to map upazilas to coordinates
@st.cache_data
def get_upazila_coordinates_map():
    up_coords = {}
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
    for div in BD_HIERARCHY:
        for dist in div["districts"]:
            d_lat = dist["lat"]
            d_lon = dist["lon"]
            for up in dist["upazilas"]:
                up_name = up["name"]
                if up_name in GPS_DATA_PRESETS:
                    up_coords[up_name] = GPS_DATA_PRESETS[up_name]
                else:
                    up_coords[up_name] = {"lat": d_lat, "lon": d_lon}
    return up_coords

# Helper to find neighboring upazilas within 30km
def get_neighboring_upazilas(target_lat, target_lon, max_dist_km=30.0):
    coords_map = get_upazila_coordinates_map()
    neighbors = []
    for name, coords in coords_map.items():
        dist = get_distance_km(target_lat, target_lon, coords["lat"], coords["lon"])
        if 0.1 < dist <= max_dist_km:
            neighbors.append(f"{name} ({dist:.1f} km)")
    return neighbors

# Seasonal metadata helper
def get_current_season_profile():
    month = datetime.datetime.now().month
    if month in [12, 1, 2]:
        return "Winter/Dry Season (High risk of respiratory/influenza-like infections, cold-weather diarrhea)"
    elif month in [3, 4, 5]:
        return "Summer/Pre-Monsoon (High risk of heat stroke, water scarcity, diarrheal outbreaks/Cholera)"
    elif month in [6, 7, 8, 9]:
        return "Monsoon/Rainy Season (Extremely high risk of Dengue, Chikungunya, Typhoid, and waterborne diseases due to flooding/water-logging)"
    else:
        return "Post-Monsoon Transition (Moderate risk of Dengue and gastrointestinal infections)"

# Pre-aggregate patient data for optimal LLM prompt structure
def aggregate_data_for_ai(cases):
    if not cases:
        return "No active case records found."
    
    df = pd.DataFrame(cases)
    df['dt'] = pd.to_datetime(df['timestamp'], errors='coerce')
    now = datetime.datetime.now()
    threshold_15d = now - datetime.timedelta(days=15)
    
    # Coordinates map
    coords_map = get_upazila_coordinates_map()
    
    active_clusters = []
    baseline_observations = []
    
    for loc, group in df.groupby('location'):
        total_cases = len(group)
        symptom_counts = group['symptom'].value_counts().to_dict()
        symptom_str = ", ".join(f"{sym} ({count} cases)" for sym, count in symptom_counts.items())
        
        ages = pd.to_numeric(group['age'], errors='coerce').dropna()
        age_str = f"Avg Age: {int(ages.mean())} (Min: {int(ages.min())}, Max: {int(ages.max())})" if not ages.empty else "N/A"
        
        # Calculate trend
        if 'dt' in group.columns and not group['dt'].isnull().all():
            recent_count = sum(group['dt'] >= threshold_15d)
            older_count = sum(group['dt'] < threshold_15d)
            if older_count == 0 and recent_count > 0:
                trend = "New Outbreak (Emerging)"
            elif recent_count > older_count:
                trend = f"Increasing (Last 15 days: {recent_count} vs Prior 15 days: {older_count})"
            elif recent_count < older_count:
                trend = f"Decreasing (Last 15 days: {recent_count} vs Prior 15 days: {older_count})"
            else:
                trend = f"Stable (Last 15 days: {recent_count} vs Prior 15 days: {older_count})"
        else:
            trend = "N/A"
            
        # Get coordinates for neighboring upazila calculation
        loc_coords = coords_map.get(loc, None)
        neighbors = []
        if loc_coords:
            neighbors = get_neighboring_upazilas(loc_coords["lat"], loc_coords["lon"])
        
        loc_data = {
            'location': loc,
            'total_cases': total_cases,
            'symptoms': symptom_str,
            'age_info': age_str,
            'trend': trend,
            'neighbors': neighbors[:8] # Limit to top 8 closest neighbors to avoid token bloating
        }
        
        # Classify into clusters vs baseline based on case threshold (3 or more cases = Active Cluster)
        if total_cases >= 3:
            active_clusters.append(loc_data)
        else:
            baseline_observations.append(loc_data)
            
    summary_lines = []
    summary_lines.append(f"## SEASONAL CONTEXT")
    summary_lines.append(f"Current Season: {get_current_season_profile()}\n")
    
    summary_lines.append(f"## ACTIVE OUTBREAK CLUSTERS (Threshold: >= 3 Cases)")
    if not active_clusters:
        summary_lines.append("No active outbreak clusters detected based on threshold.\n")
    else:
        for idx, item in enumerate(active_clusters, 1):
            neighbors_str = ", ".join(item['neighbors']) if item['neighbors'] else "None"
            summary_lines.append(
                f"**{idx}. Location: {item['location']}**\n"
                f"   - Case Count: {item['total_cases']}\n"
                f"   - Mapped Symptoms: {item['symptoms']}\n"
                f"   - Patient Demographics: {item['age_info']}\n"
                f"   - Trend Indicator: {item['trend']}\n"
                f"   - Adjacent Vulnerable Upazilas (within 30km): {neighbors_str}\n"
            )
            
    summary_lines.append(f"## BASELINE SURVEILLANCE OBSERVATIONS (Threshold: 1-2 Cases - Normal Baseline)")
    if not baseline_observations:
        summary_lines.append("No baseline observations recorded.\n")
    else:
        for idx, item in enumerate(baseline_observations, 1):
            summary_lines.append(
                f"**{idx}. Location: {item['location']}**\n"
                f"   - Case Count: {item['total_cases']}\n"
                f"   - Symptoms logged: {item['symptoms']}\n"
                f"   - Trend Indicator: {item['trend']}\n"
            )
            
    return "\n".join(summary_lines)

st.sidebar.title("Navigation")
menu = st.sidebar.radio("", ["Dashboard", "Strict Data Entry", "AI Alerts"])

# Filters only for Dashboard
time_filter = "All Time"
severity_filter = "All Active Zones (1+ cases)"
if menu == "Dashboard":
    st.sidebar.markdown("---")
    st.sidebar.subheader("Filters")
    time_filter = st.sidebar.selectbox("Select Time Range", ["All Time", "Last 7 Days", "Last 14 Days", "Last 30 Days"])
    severity_filter = st.sidebar.selectbox("Outbreak Severity Zone", ["All Active Zones (1+ cases)", "Risk Zones (2 cases)", "Alert Zones (3+ cases)"])

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
                # Group by location to compute counts and join unique symptoms
                map_data_grouped = map_data.groupby('location').agg({
                    'lat': 'first',
                    'lon': 'first',
                    'symptom': lambda x: ", ".join(sorted(list(set(s for s in x if s)))),
                }).reset_index()
                
                # Add case count
                location_counts = map_data['location'].value_counts().to_dict()
                map_data_grouped['case_count'] = map_data_grouped['location'].map(location_counts)
                
                # Apply severity filtering
                if severity_filter == "Risk Zones (2 cases)":
                    map_data_grouped = map_data_grouped[map_data_grouped['case_count'] == 2]
                elif severity_filter == "Alert Zones (3+ cases)":
                    map_data_grouped = map_data_grouped[map_data_grouped['case_count'] >= 3]
                
                if not map_data_grouped.empty:
                    st.subheader(f"🔥 Geospatial Infection Heatmap — {severity_filter}")
                    mean_lat = map_data_grouped['lat'].mean()
                    mean_lon = map_data_grouped['lon'].mean()
                    lat_span = map_data_grouped['lat'].max() - map_data_grouped['lat'].min()
                    lon_span = map_data_grouped['lon'].max() - map_data_grouped['lon'].min()
                    zoom_level = 6.2 if (lat_span > 1.5 or lon_span > 1.5) else 8.5
                    
                    fig = px.density_mapbox(
                        map_data_grouped, lat='lat', lon='lon', z='case_count', radius=40, 
                        center=dict(lat=mean_lat, lon=mean_lon), zoom=zoom_level, 
                        mapbox_style="carto-darkmatter", color_continuous_scale="YlOrRd", 
                        hover_name="location", hover_data={"lat": False, "lon": False, "symptom": True, "case_count": True}
                    )
                    fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
                    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                else:
                    st.info(f"ℹ️ No locations match the selected Outbreak Severity: {severity_filter}")
                
                # Add Active Outbreaks Table / Hotline Metrics
                st.markdown("---")
                if severity_filter == "Risk Zones (2 cases)":
                    st.subheader("📍 Active Risk Zones (2 Cases)")
                    hotspot_df = map_data_grouped.sort_values(by='case_count', ascending=False)
                elif severity_filter == "Alert Zones (3+ cases)":
                    st.subheader("📍 Active Alert Zones (3+ Cases)")
                    hotspot_df = map_data_grouped.sort_values(by='case_count', ascending=False)
                else:
                    st.subheader("📍 Active Outbreak Hotspots (>= 2 Cases)")
                    hotspot_df = map_data_grouped[map_data_grouped['case_count'] >= 2].sort_values(by='case_count', ascending=False)
                    
                if not hotspot_df.empty:
                    display_df = hotspot_df[['location', 'case_count', 'symptom']].rename(columns={
                        'location': 'Location (Upazila)',
                        'case_count': 'Total Active Cases',
                        'symptom': 'Symptoms Present'
                    })
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                else:
                    st.success("✅ No active locations matching the criteria in this timeframe.")
            else:
                st.info("🗺️ No map data available yet for the selected timeframe.")
                
        except Exception as e:
            st.error("❌ Database connection error.")
            st.write(e)
            
# ২. সিকিউরড ডেটা এন্ট্রি (এখন ক্লাউডেও কাজ করবে)
elif menu == "Strict Data Entry":
    st.title("📝 Secure Clinical Data Entry")
    st.markdown("---")
    
    # Render temporary success message if set
    if "success_message" in st.session_state and st.session_state.success_message:
        st.success(st.session_state.success_message)
        st.session_state.success_message = ""
        
    st.info("💡 **Operator Input:** Select the map location step-by-step and enter patient details.")
    
    # Reset input fields if flag is set (must be done before widgets are rendered)
    if "should_reset" in st.session_state and st.session_state.should_reset:
        st.session_state.patient_symptom = ""
        st.session_state.selected_division = "Select Division..."
        st.session_state.patient_age = 30
        if "selected_district" in st.session_state:
            st.session_state.selected_district = "Select District..."
        if "selected_upazila" in st.session_state:
            st.session_state.selected_upazila = "Select Area..."
        st.session_state.should_reset = False

    # Initialize keys if not in state
    if "patient_age" not in st.session_state:
        st.session_state.patient_age = 30
    if "patient_symptom" not in st.session_state:
        st.session_state.patient_symptom = ""
    if "selected_division" not in st.session_state:
        st.session_state.selected_division = "Select Division..."
        
    st.subheader("1. Patient Age")
    patient_age = st.number_input("Select Age", min_value=1, max_value=120, step=1, key="patient_age")
    
    st.markdown("---")
    st.subheader("2. Map Location (Deep Filtering)")
    
    patient_location = "Select Area..."
    selected_district = "Select District..."
    selected_division = "Select Division..."
    patient_lat = None
    patient_lon = None
    
    divisions_list = ["Select Division..."] + [div["name"] for div in BD_HIERARCHY]
    selected_division = st.selectbox("Division", divisions_list, key="selected_division")
    
    if selected_division != "Select Division...":
        div_data = next(div for div in BD_HIERARCHY if div["name"] == selected_division)
        districts_list = ["Select District..."] + [dist["name"] for dist in div_data["districts"]]
        selected_district = st.selectbox("District", districts_list, key="selected_district")
        
        if selected_district != "Select District...":
            dist_data = next(dist for dist in div_data["districts"] if dist["name"] == selected_district)
            upazilas_list = ["Select Area..."] + [up["name"] for up in dist_data["upazilas"]]
            selected_upazila = st.selectbox("Upazila / Area", upazilas_list, key="selected_upazila")
            
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
    patient_symptom = st.text_input("Enter Symptoms or Disease (e.g., Fever, Red rash)", key="patient_symptom")
    
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
                    
                    # Set the flag to reset values on next rerun
                    st.session_state.should_reset = True
                    st.session_state.success_message = f"✅ Data for {patient_location} ({selected_district}, {selected_division}) successfully verified and saved!"
                    st.rerun()
                except Exception as e:
                    st.error("❌ Database connection error.")
                    st.write(e)

# ৩. এআই অ্যালার্ট পেজ (Groq Cloud AI Version)
elif menu == "AI Alerts":
    st.title("🤖 BioNode AI - Predictive Outbreak Intelligence")
    st.markdown("---")
    st.info("🧠 Performing climate-informed predictive outbreak modeling and clinical triage using Llama-3...")
    
    if st.button("Generate Predictive AI Alert"):
        with st.spinner("BioNode AI is executing predictive models..."):
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
                    
                    # Pre-aggregate data in Python to present clean structured metrics to the AI
                    structured_summary = aggregate_data_for_ai(recent_cases)
                    
                    with st.expander("📊 View Pre-Aggregated Database Statistics & Proximity Matrix"):
                        st.markdown(structured_summary)
                    
                    # ২. এআই-এর জন্য প্রম্পট (JSON রেসপন্স ফরম্যাটের নির্দেশনা) তৈরি
                    prompt_text = f"""
                    You are an expert Epidemiologist AI.
                    Here is a pre-aggregated structured epidemiological summary of active patient cases in Bangladesh:
                    
                    {structured_summary}
                    
                    Return a JSON object containing an epidemiological alert, risk assessment, and predictive forecasts.
                    The JSON must strictly match the following schema:
                    {{
                      "hotspots": [
                        {{
                          "location": "Name of Upazila/District",
                          "disease": "Predicted Clinical Disease (e.g. Dengue, Cholera, Influenza-like illness, Measles). Map the raw symptoms to a target disease.",
                          "mapped_symptoms": "Comma-separated raw symptoms that led to this disease mapping",
                          "risk_level": "High" or "Medium" or "Low",
                          "case_count": number_of_cases,
                          "spreading_outlook": "Short description of potential spread based on the Weekly Trend Indicator"
                        }}
                      ],
                      "predictive_forecasts": [
                        {{
                          "vulnerable_location": "Name of adjacent Upazila/District at risk of transmission",
                          "predicted_threat": "Predicted target disease (e.g. Dengue, Waterborne Diarrhea, Typhoid)",
                          "transmission_vector": "E.g. Vector-borne (Mosquitoes), Water-runoff, or High local mobility",
                          "spread_risk": "High" or "Medium" or "Low",
                          "projection_days": 14,
                          "action_plan": "Specific preventative instruction for local health officials"
                        }}
                      ],
                      "irrelevant_cases_detected": [
                        {{
                          "location": "Location name",
                          "raw_input": "The raw symptom input that was flagged as irrelevant",
                          "reason": "Clear explanation of why it is irrelevant (e.g., physical injury, chronic non-infectious condition, or nonsense word)"
                        }}
                      ],
                      "overall_summary": "A professional 3-sentence summary of the active outbreak trends and threat level in the country based on the pre-aggregated weekly trends.",
                      "safety_recommendations": [
                        "Specific clinical action recommendation 1",
                        "Specific clinical action recommendation 2"
                      ]
                    }}
                    
                    CRITICAL INSTRUCTIONS:
                    1. CLINICAL NOISE FILTER: Analyze all raw symptom logs. If any inputs are non-infectious conditions (e.g. broken bone, fracture, cut, physical injury, chronic conditions) or nonsense terms, do NOT count them towards hotspots or outbreaks. List them in "irrelevant_cases_detected".
                    2. OUTBREAK THRESHOLD: Differentiate between baseline surveillance and active clusters.
                       - Locations listed under ACTIVE OUTBREAK CLUSTERS (having >=3 cases) should be assessed for hotspots.
                       - Locations listed under BASELINE SURVEILLANCE OBSERVATIONS (having 1-2 cases) represent normal fluctuations. Categorize them as Low Risk and do not create active alerts for them unless they contain highly contagious symptoms (e.g., acute watery diarrhea/cholera or red rash/measles).
                    3. SYMPTOM MAPPING: Map symptom clusters to actual target diseases (e.g., Fever + Joint Pain + Headache -> Dengue; Watery Stool + Vomiting -> Cholera/Diarrheal outbreak).
                    4. TRANSMISSION FORECASTING: Analyze "Adjacent Vulnerable Upazilas" near active clusters. Propose potential transmission pathways and rate their vulnerability (spread_risk) based on distance and proximity to the source cluster.
                    5. SEASONAL ANALYSIS: Use the provided SEASONAL CONTEXT to inform your projections.
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
                        
                        # Display hotspots
                        st.subheader("🚨 Active Outbreak Hotspots")
                        hotspots = ai_data.get("hotspots", [])
                        if not hotspots:
                            st.success("No active hotspots or high-risk clusters identified.")
                        else:
                            for hotspot in hotspots:
                                loc = hotspot.get("location", "Unknown")
                                disease = hotspot.get("disease", "Unknown")
                                symptoms = hotspot.get("mapped_symptoms", "Unknown")
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
                                
                                st.write(f"**Mapped Disease:** {disease} | **Symptoms:** {symptoms}")
                                st.write(f"**Spread Outlook:** {outlook}")
                                st.markdown("---")
                                
                        # Display Predictive transmission risk
                        st.subheader("🔮 Geospatial Spread & Proximity Forecasts")
                        predictions = ai_data.get("predictive_forecasts", [])
                        if not predictions:
                            st.success("No adjacent geographical spread threats predicted.")
                        else:
                            for pred in predictions:
                                target_loc = pred.get("vulnerable_location", "Unknown")
                                threat = pred.get("predicted_threat", "Unknown")
                                vector = pred.get("transmission_vector", "Unknown")
                                s_risk = pred.get("spread_risk", "Low").title()
                                plan = pred.get("action_plan", "")
                                
                                if s_risk == "High":
                                    st.error(f"⚠️ **Vulnerable Area: {target_loc}** — Transmission Risk: **{s_risk}**")
                                elif s_risk == "Medium":
                                    st.warning(f"⚠️ **Vulnerable Area: {target_loc}** — Transmission Risk: **{s_risk}**")
                                else:
                                    st.info(f"ℹ️ **Vulnerable Area: {target_loc}** — Transmission Risk: **{s_risk}**")
                                    
                                st.write(f"**Predicted Threat:** {threat} | **Transmission Route:** {vector}")
                                st.write(f"**Preventative Plan:** *{plan}*")
                                st.markdown("---")
                        
                        # Display Excluded Clinical Noise Logs
                        irrelevant_logs = ai_data.get("irrelevant_cases_detected", [])
                        if irrelevant_logs:
                            with st.expander("🛡️ Filtered Excluded Records (Clinical Triage Noise)"):
                                for item in irrelevant_logs:
                                    st.markdown(
                                        f"- **Location:** {item.get('location')} | **Input:** `\"{item.get('raw_input')}\"`\n"
                                        f"  *Reason Excluded:* {item.get('reason')}"
                                    )
                                    
                        # Display Recommendations
                        st.subheader("🛡️ Safety & Prevention Guidelines")
                        for rec in ai_data.get("safety_recommendations", []):
                            st.markdown(f"- {rec}")
                            
                        # Build a downloadable text report string
                        report_text = f"""BIONODE-AI PREDICTIVE EPIDEMIOLOGICAL REPORT
Generated: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Timeframe: {"Last 30 Days (Fallback Overall)" if is_fallback else "Last 30 Days"}

==================================================
NATIONWIDE SUMMARY:
{ai_data.get("overall_summary", "N/A")}

==================================================
ACTIVE HOTSPOTS:
"""
                        for hotspot in hotspots:
                            loc = hotspot.get("location", "Unknown")
                            disease = hotspot.get("disease", "Unknown")
                            risk = hotspot.get("risk_level", "Low").upper()
                            count = hotspot.get("case_count", 1)
                            outlook = hotspot.get("spreading_outlook", "")
                            report_text += f"\n- {loc}: RISK: {risk} | Cases: {count}\n  Mapped Disease: {disease}\n  Outlook: {outlook}\n"
                            
                        report_text += "\n==================================================\nGEOSPATIAL TRANSMISSION PROJECTIONS:\n"
                        for pred in predictions:
                            target_loc = pred.get("vulnerable_location", "Unknown")
                            threat = pred.get("predicted_threat", "Unknown")
                            s_risk = pred.get("spread_risk", "Low").upper()
                            vector = pred.get("transmission_vector", "Unknown")
                            plan = pred.get("action_plan", "")
                            report_text += f"\n- Vulnerable: {target_loc} | Risk: {s_risk}\n  Threat: {threat}\n  Route: {vector}\n  Plan: {plan}\n"
                            
                        if irrelevant_logs:
                            report_text += "\n==================================================\nFILTERED CLINICAL TRIAGE NOISE (EXCLUDED):\n"
                            for item in irrelevant_logs:
                                report_text += f"- Loc: {item.get('location')} | Input: \"{item.get('raw_input')}\" | Reason: {item.get('reason')}\n"
                            
                        report_text += "\n==================================================\nSAFETY & PREVENTION RECOMMENDATIONS:\n"
                        for idx, rec in enumerate(ai_data.get("safety_recommendations", []), 1):
                            report_text += f"{idx}. {rec}\n"
                            
                        st.markdown("---")
                        st.download_button(
                            label="📥 Download Official Outbreak Report",
                            data=report_text,
                            file_name=f"BioNode_AI_Outbreak_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                            mime="text/plain"
                        )
                            
                    except Exception as json_err:
                        # Fallback to plain text rendering if JSON parse fails
                        st.subheader("🚨 Real-time AI Outbreak Report")
                        st.write(ai_response)
                        
            except Exception as e:
                st.error("❌ Failed to connect with AI or Database.")
                st.write(e)