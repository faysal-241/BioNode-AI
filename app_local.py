import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import datetime
import json
import ollama

# Neo4j ক্লাউড ডেটাবেসের কানেকশন
URI = st.secrets["NEO4J_URI"]
USERNAME = st.secrets["NEO4J_USERNAME"]
PASSWORD = st.secrets["NEO4J_PASSWORD"]

# হিটম্যাপের জন্য বরিশালের এলাকার জিপিএস (GPS) কো-অর্ডিনেটস
GPS_DATA = {
    "Barishal Sadar": {"lat": 22.7010, "lon": 90.3535},
    "Bakerganj": {"lat": 22.5528, "lon": 90.3344},
    "Babuganj": {"lat": 22.8333, "lon": 90.3000},
    "Wazirpur": {"lat": 22.8167, "lon": 90.2333},
    "Banaripara": {"lat": 22.7833, "lon": 90.1667}
}

st.sidebar.title("Navigation")
menu = st.sidebar.radio("", ["Dashboard", "Strict Data Entry", "AI Alerts"])

# ১. মেইন ড্যাশবোর্ড (Live Heatmap & KPIs)
if menu == "Dashboard":
    st.title("📊 Live Epidemic Dashboard")
    st.markdown("---")
    
    with st.spinner("Fetching live geospatial data..."):
        try:
            driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
            with driver.session() as session:
                # মোট রোগীর সংখ্যা
                total_patients = session.run("MATCH (p:Patient) RETURN count(p) AS total").single()["total"]
                
                # হাই-রিস্ক জোন (যেখানে ২ বা তার বেশি রোগী আছে)
                outbreak_query = session.run(
                    "MATCH (p:Patient) WITH p.location AS loc, count(p) AS cases WHERE cases >= 2 RETURN count(loc) AS total_outbreaks"
                )
                active_outbreaks = outbreak_query.single()["total_outbreaks"]
                
                # ম্যাপের ডেটা
                map_result = session.run("MATCH (p:Patient) RETURN p.latitude AS lat, p.longitude AS lon, p.location AS location, p.symptom AS symptom")
                map_data = pd.DataFrame([record.data() for record in map_result])
            driver.close()
            
            # --- প্রফেশনাল KPI কার্ডস ---
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Outbreak Cases", value=total_patients, delta="Live Data")
            with col2:
                st.metric(label="High Risk Zones", value=active_outbreaks, delta="Alerts Active", delta_color="inverse")
            with col3:
                st.metric(label="BioNode AI Status", value="Online", delta="Monitoring...")
                
            st.markdown("---")
            
            # --- লাইভ হিটম্যাপ ---
            if not map_data.empty and 'lat' in map_data.columns and 'lon' in map_data.columns:
                st.subheader("🔥 Live Geospatial Infection Heatmap")
                
                import plotly.express as px
                
                fig = px.density_mapbox(
                    map_data, 
                    lat='lat', 
                    lon='lon', 
                    z=[1]*len(map_data), 
                    radius=45, 
                    center=dict(lat=22.7010, lon=90.3535), 
                    zoom=8.5, 
                    mapbox_style="carto-darkmatter", 
                    color_continuous_scale="YlOrRd", 
                    hover_name="location",
                    hover_data={"lat": False, "lon": False, "symptom": True}
                )
                
                fig.update_layout(
                    height=650, 
                    margin={"r":0,"t":0,"l":0,"b":0}, 
                    coloraxis_showscale=False 
                )
                
                st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
                
            else:
                st.info("🗺️ No map data available yet. Please add patients from the Data Entry page.")
                
        except Exception as e:
            st.error("❌ Database connection error.")
            st.write(e)
# ২. ডেটা এন্ট্রি (Live Map Selection & Strict Validation)
elif menu == "Strict Data Entry":
    st.title("📝 Secure Clinical Data Entry")
    st.markdown("---")
    
    st.info("💡 **Operator Input:** Select the map location step-by-step and enter patient details.")
    
    # ১. Age Box
    st.subheader("1. Patient Age")
    patient_age = st.number_input("Select Age", min_value=1, max_value=120, step=1)
    
    st.markdown("---")
    
    # ২. Live Map Location Box (st.form ছাড়া, যাতে সাথে সাথে কাজ করে)
    st.subheader("2. Map Location (Deep Filtering)")
    
    patient_location = "Select Area..." # ডিফল্ট ভ্যালু
    
    # ধাপ ১: Division
    division = st.selectbox("Division", ["Select Division...", "Barishal"])
    
    if division == "Barishal":
        # ধাপ ২: District (শুধু Barishal সিলেক্ট করলেই এটি আসবে)
        district = st.selectbox("District", ["Select District...", "Barishal"])
        
        if district == "Barishal":
            # ধাপ ৩: Upazila / Area (আসল গুগল ম্যাপ লোকেশন)
            patient_location = st.selectbox("Upazila / Area", ["Select Area...", "Barishal Sadar", "Bakerganj", "Babuganj", "Wazirpur", "Banaripara"])
            
    st.markdown("---")
    
    # ৩. Symptom / Disease Box
    st.subheader("3. Clinical Symptoms")
    patient_symptom = st.text_input("Enter Symptoms or Disease (e.g., Fever, Red rash)")
    
    # সাবমিট বাটন
    if st.button("Validate & Save to Cloud"):
        errors = []
        
        # ভ্যালিডেশন ১: লোকেশন ঠিকমতো সিলেক্ট করেছে কি না?
        if patient_location == "Select Area...":
            errors.append("Map Location Error: You must select the deep location up to the Upazila/Area level.")
            
        # ভ্যালিডেশন ২: লক্ষণের বক্সে কেউ লোকেশনের নাম লিখেছে কি না?
        forbidden_locations_in_symptom = ["barishal", "bakerganj", "babuganj", "wazirpur", "banaripara", "dhaka"]
        if any(loc in patient_symptom.lower() for loc in forbidden_locations_in_symptom):
            errors.append("Wrong Input! You typed a map location in the Disease/Symptom box. Please type only medical conditions.")
            
        # ভ্যালিডেশন ৩: লক্ষণের বক্সে নাম্বার আছে কি না বা খালি কি না?
        if not patient_symptom.strip():
            errors.append("Symptom box cannot be empty.")
        elif any(char.isdigit() for char in patient_symptom):
            errors.append("Wrong Input! You cannot put numbers in the Disease/Symptom box.")
            
        # যদি কোনো ভুল থাকে, স্ক্রিনে অ্যালার্ট দেখাবে
        if errors:
            for error in errors:
                st.error(f"❌ {error}")
        
        # সব পারফেক্ট হলে ক্লাউডে সেভ হবে
        else:
            with st.spinner("Saving data to the cloud..."):
                try:
                    # অটোমেটিক জিপিএস এবং সময় বের করা
                    patient_lat = GPS_DATA[patient_location]["lat"]
                    patient_lon = GPS_DATA[patient_location]["lon"]
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    # Neo4j ক্লাউডে সেভ করা
                    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
                    with driver.session() as session:
                        session.run(
                            """
                            CREATE (p:Patient {
                                age: $age, 
                                location: $location, 
                                symptom: $symptom, 
                                latitude: $lat, 
                                longitude: $lon, 
                                timestamp: $time
                            })
                            """,
                            age=patient_age, location=patient_location, symptom=patient_symptom, 
                            lat=patient_lat, lon=patient_lon, time=current_time
                        )
                    driver.close()
                    
                    st.success(f"✅ Data for {patient_location} successfully verified and saved with GPS coordinates!")
                    
                except Exception as e:
                    st.error("❌ Database connection error.")
                    st.write(e)
# ৩. এআই অ্যালার্ট পেজ (Predictive AI)
elif menu == "AI Alerts":
    st.title("🚨 Predictive AI & Early Warnings")
    st.markdown("---")
    
    st.info("💡 **BioNode AI Engine:** Click the button below to scan the live database for outbreak patterns.")
    
    if st.button("Scan for Epidemic Patterns"):
        with st.spinner("AI is analyzing live geospatial data..."):
            try:
                # ১. ডেটাবেস থেকে প্যাটার্ন খোঁজা (একই এলাকায় একই রোগ ২ বা তার বেশি হলে)
                driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
                with driver.session() as session:
                    result = session.run(
                        """
                        MATCH (p:Patient) 
                        WITH p.location AS location, p.symptom AS symptom, count(p) AS case_count 
                        WHERE case_count >= 2 
                        RETURN location, symptom, case_count
                        """
                    )
                    outbreaks = [record.data() for record in result]
                driver.close()
                
                # ২. যদি কোনো বিপদের প্যাটার্ন না থাকে
                if len(outbreaks) == 0:
                    st.success("✅ No epidemic patterns detected. The situation is normal.")
                
                # ৩. যদি বিপদের প্যাটার্ন পাওয়া যায় (Outbreak Detected)
                else:
                    st.error(f"⚠️ **WARNING! {len(outbreaks)} Outbreak Pattern(s) Detected!**")
                    
                    # প্রতিটি বিপদের জন্য Llama 3-কে দিয়ে অ্যালার্ট লেখানো
                    for outbreak in outbreaks:
                        loc = outbreak["location"]
                        symp = outbreak["symptom"]
                        cases = outbreak["case_count"]
                        
                        st.markdown(f"### 📍 Red Alert in: {loc}")
                        st.write(f"**Condition:** {symp} | **Live Cases:** {cases}")
                        
                        # Llama 3-এর জন্য সহজ ও কড়া প্রম্পট
                        prompt = f"""
                        You are an expert Epidemiologist AI. 
                        There is a sudden outbreak of '{symp}' with {cases} cases in a place called '{loc}'. 
                        Write a short, urgent warning (maximum 3 sentences) suggesting what local doctors should do immediately to stop this from spreading.
                        """
                        
                        # অফলাইন এআই (Ollama) কল করা
                        response = ollama.chat(model='llama3', messages=[{'role': 'user', 'content': prompt}])
                        ai_advice = response['message']['content']
                        
                        # এআইয়ের অ্যালার্ট স্ক্রিনে সুন্দর করে দেখানো
                        st.warning(f"**🤖 AI Epidemiologist Advice:**\n\n{ai_advice}")
                        st.markdown("---")
                        
            except Exception as e:
                st.error("❌ Error running AI Analysis. Ensure Database and Ollama are active.")
                st.write(e)