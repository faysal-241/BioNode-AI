import streamlit as st
from neo4j import GraphDatabase
import pandas as pd
import plotly.express as px

# Neo4j ক্লাউড ডেটাবেসের তথ্য
URI = st.secrets["NEO4J_URI"]

# সাইডবার মেনু
st.sidebar.title("Navigation")
menu = st.sidebar.radio("", ["Dashboard", "Data Entry", "AI Alerts"])

# ১. মেইন ড্যাশবোর্ড পেজ (Live Heatmap for Cloud)
if menu == "Dashboard":
    st.title("📊 Live Epidemic Dashboard (Cloud)")
    st.markdown("---")
    
    with st.spinner("Fetching live geospatial data..."):
        try:
            driver = GraphDatabase.driver(URI, auth=(st.secrets["NEO4J_USERNAME"], st.secrets["NEO4J_PASSWORD"]))
            with driver.session() as session:
                # মোট রোগীর সংখ্যা
                total_patients = session.run("MATCH (p:Patient) RETURN count(p) AS total").single()["total"]
                
                # হাই-রিস্ক জোন
                outbreak_query = session.run("MATCH (p:Patient) WITH p.location AS loc, count(p) AS cases WHERE cases >= 2 RETURN count(loc) AS total_outbreaks")
                active_outbreaks = outbreak_query.single()["total_outbreaks"]
                
                # ম্যাপের ডেটা (এখানে symptom একবচনে ফিক্স করা হয়েছে)
                map_result = session.run("MATCH (p:Patient) WHERE p.latitude IS NOT NULL RETURN p.latitude AS lat, p.longitude AS lon, p.location AS location, p.symptom AS symptom")
                map_data = pd.DataFrame([record.data() for record in map_result])
            driver.close()
            
            # KPI কার্ডস
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric(label="Total Outbreak Cases", value=total_patients, delta="Live Data")
            with col2:
                st.metric(label="High Risk Zones", value=active_outbreaks, delta="Alerts Active", delta_color="inverse")
            with col3:
                st.metric(label="BioNode AI Status", value="Secured", delta="Local Offline Mode")
                
            st.markdown("---")
            
            # হিটম্যাপ লজিক
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

# ২. ডেটা এন্ট্রি পেজ (Showcase Version)
elif menu == "Data Entry":
    st.title("📝 Enter New Patient Data")
    st.info("💡 For the full strict validation module, please see the local offline version.")

# ৩. এআই অ্যালার্ট পেজ (Showcase Version)
elif menu == "AI Alerts":
    st.title("🤖 BioNode AI - Security Protocol")
    st.warning("🔒 **Strict Data Privacy Protocol Active**")
    st.write("Due to medical data compliance, our core Predictive AI engine (Llama 3) operates entirely offline. It cannot be exposed to this public cloud link.")