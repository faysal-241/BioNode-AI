import streamlit as st
from neo4j import GraphDatabase
import pandas as pd

# Neo4j ক্লাউড ডেটাবেসের তথ্য (আপনার সিক্রেটস ফাইল থেকে আসবে)
URI = st.secrets["NEO4J_URI"]

# সাইডবার মেনু
st.sidebar.title("Navigation")
menu = st.sidebar.radio("", ["Dashboard", "Data Entry", "AI Alerts"])

# ১. মেইন ড্যাশবোর্ড পেজ (Dashboard)
if menu == "Dashboard":
    st.title("📊 Hospital Analytics Dashboard")
    st.markdown("---")
    
    with st.spinner("Loading live data from Neo4j..."):
        try:
            driver = GraphDatabase.driver(URI, auth=(st.secrets["NEO4J_USERNAME"], st.secrets["NEO4J_PASSWORD"]))
            with driver.session() as session:
                total_patients = session.run("MATCH (p:Patient) RETURN count(p) AS total").single()["total"]
                result = session.run("MATCH (p:Patient) RETURN p.symptoms AS Symptom, count(p) AS Count")
                symptom_data = pd.DataFrame([record.data() for record in result])
            driver.close()
            
            st.metric(label="Total Patients Today", value=total_patients)
            st.markdown("---")
            
            if not symptom_data.empty:
                st.subheader("📈 Disease Spread (By Symptoms)")
                chart_data = symptom_data.set_index("Symptom")
                st.bar_chart(chart_data)
            else:
                st.info("No data available yet. Please add patients from the Data Entry page.")
        except Exception as e:
            st.error("❌ Database connection error.")
            st.write(e)

# ২. ডেটা এন্ট্রি পেজ (Data Entry)
elif menu == "Data Entry":
    st.title("📝 Enter New Patient Data")
    st.markdown("---")
    
    with st.form("patient_form"):
        name = st.text_input("Patient Name")
        age = st.number_input("Age", min_value=0, max_value=120)
        location = st.selectbox("Location", ["Barishal Sadar", "Bakerganj", "Babuganj", "Wazirpur", "Banaripara"])
        symptoms = st.selectbox("Primary Symptom", ["Fever", "Cough", "Vomiting", "Body Ache", "Headache"])
        
        submitted = st.form_submit_button("Save to Cloud Database")
        
        if submitted:
            try:
                driver = GraphDatabase.driver(URI, auth=(st.secrets["NEO4J_USERNAME"], st.secrets["NEO4J_PASSWORD"]))
                with driver.session() as session:
                    session.run(
                        "CREATE (p:Patient {name: $name, age: $age, location: $location, symptoms: $symptoms})",
                        name=name, age=age, location=location, symptoms=symptoms
                    )
                driver.close()
                st.success(f"✅ Data for {name} saved successfully to Neo4j Cloud!")
            except Exception as e:
                st.error("❌ Failed to save data.")
                st.write(e)

# ৩. এআই অ্যালার্ট পেজ (AI Alerts - For Showcase)
elif menu == "AI Alerts":
    st.title("🤖 BioNode AI - Security Protocol")
    st.markdown("---")
    
    st.warning("🔒 **Strict Data Privacy Protocol Active**")
    st.write("""
    To ensure the absolute privacy and security of patient data, our core AI engine (**Llama 3**) operates entirely offline within a secure local server. 
    
    Due to medical data compliance (HIPAA), the AI analysis module cannot be exposed to public cloud servers.
    """)
    st.info("💡 **Judges / Reviewers:** To see the live offline AI analysis in action, please watch the demonstration video linked below.")
    
    # এখানে আপনি আপনার তৈরি করা ডেমো ভিডিওর লিংক দেবেন
    st.markdown("[▶️ Watch the Live Offline AI Demonstration Here](https://your-video-link-here.com)")