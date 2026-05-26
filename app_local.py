import streamlit as st
from neo4j import GraphDatabase
import ollama
import pandas as pd

# ডেটাবেস কানেকশন সেটআপ (secrets.toml থেকে ডেটা নিচ্ছে)
URI = st.secrets["NEO4J_URI"]
AUTH = (st.secrets["NEO4J_USERNAME"], st.secrets["NEO4J_PASSWORD"])

# ডেটাবেসে রোগীর ডেটা সেভ করার ফাংশন
def save_patient_to_db(age, gender, location, symptoms, new_symptom):
    with GraphDatabase.driver(URI, auth=AUTH) as driver:
        with driver.session() as session:
            # Cypher Query (গ্রাফ ডেটাবেসের ভাষা, যা ডেটা সেভ করে)
            query = """
            CREATE (p:Patient {
                age: $age, 
                gender: $gender, 
                location: $location, 
                symptoms: $symptoms, 
                new_symptom: $new_symptom
            })
            """
            session.run(query, age=age, gender=gender, location=location, symptoms=symptoms, new_symptom=new_symptom)

# ১. পেজের মূল সেটিং
st.set_page_config(page_title="BioNode AI", page_icon="🚨", layout="wide")

# ২. সাইডবার
st.sidebar.title("🧬 BioNode AI")
st.sidebar.info("Hybrid Epidemic Intelligence")
menu = st.sidebar.radio("Navigation", ["Dashboard", "Data Entry", "AI Alerts"])

# ৩. মূল ড্যাশবোর্ড
if menu == "Dashboard":
    st.title("🚨 BioNode AI: Live Dashboard")
    st.markdown("---")
    
    st.subheader("Real-Time Live Summary")
    col_1, col_2, col_3 = st.columns(3)
    
    with col_1:
        st.metric(label="Total Patients Today", value="0")
        with col_2:
            st.metric(label="Top Symptom", value="Waiting...")
        with col_3:
            st.metric(label="High-Risk Zone", value="Safe")
            
    st.success("System architecture loaded successfully! Ready for data integration.")

# ৪. ডেটা এন্ট্রি পোর্টাল (অফলাইন মডিউল)
elif menu == "Data Entry":
    st.title("📝 Data Entry Portal")
    st.markdown("---")
    st.info("Please enter patient details below. Data will be securely synced to the BioNode Cloud.")
    
    with st.form("patient_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            age = st.number_input("Patient Age", min_value=0, max_value=120, value=25)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            
        with col2:
            location = st.selectbox("Location / Zone", ["Barishal Sadar", "Bakerganj", "Babuganj", "Banaripara"])
            symptoms = st.multiselect("Symptoms (Select all that apply)", 
                                      ["Fever", "Cough", "Diarrhea", "Vomiting", "Headache", "Body Ache"])
            
        new_symptom = st.text_input("New/Unknown Symptom (If any) - For WHO Novelty Check")
        submitted = st.form_submit_button("💾 Save Patient Data")
        
        # সাবমিট বাটনে ক্লিক করলে যা হবে:
        if submitted:
            # লক্ষণগুলোকে টেক্সট বানিয়ে নেওয়া হচ্ছে ডেটাবেসে রাখার সুবিধার জন্য
            symptoms_text = ", ".join(symptoms)
            
            # ডেটাবেসে সেভ করার ফাংশনটি কল করা হলো
            try:
                save_patient_to_db(age, gender, location, symptoms_text, new_symptom)
                st.success(f"✅ Data successfully saved to Neo4j Cloud for a {age}-year-old {gender} from {location}!")
                st.balloons() # কানেকশন সফল হলে স্ক্রিনে বেলুন উড়বে!
            except Exception as e:
                st.error(f"❌ Connection Error. Please check your secrets.toml file. Error details: {e}")

    # ৫. এআই অ্যালার্ট পেজ (AI Alerts)
# ৫. এআই অ্যালার্ট পেজ (AI Alerts - Connected to Neo4j)
elif menu == "AI Alerts":
    st.title("🤖 Live AI Alerts & Analysis")
    st.markdown("---")
    st.info("Offline AI Engine (Llama 3) is now connected to Neo4j Cloud Database!")
    
    # ইউজারকে প্রশ্ন লেখার বদলে সরাসরি একটি বাটন দেওয়া হলো
    if st.button("Analyze Live Database"):
        with st.spinner("BioNode AI is fetching data and thinking..."):
            try:
                # ধাপ ১: Neo4j ডেটাবেস থেকে তাজা ডেটা টেনে আনা
                driver = GraphDatabase.driver(URI, auth=(st.secrets["NEO4J_USERNAME"], st.secrets["NEO4J_PASSWORD"]))
                
                with driver.session() as session:
                    # আমরা শুধু লোকেশন এবং লক্ষণগুলো (symptoms) আনছি
                    result = session.run("MATCH (p:Patient) RETURN p.location AS location, p.symptoms AS symptoms LIMIT 10")
                    
                    # ধাপ ২: ডেটাগুলো সাজিয়ে একটি টেক্সট বানানো
                    data_text = ""
                    for record in result:
                        data_text += f"Location: {record['location']}, Symptom: {record['symptoms']}\n"
                
                driver.close()

                # ধাপ ৩: অফলাইন এআই-কে ডেটা খাইয়ে প্রম্পট দেওয়া
                if data_text == "":
                    st.warning("Database is empty. Please enter some data first.")
                else:
                    ai_prompt = f"Here is the latest patient data from our hospital:\n{data_text}\nBased on this data, is there any risk of an outbreak? Give a short medical warning."
                    
                    # Llama 3 কে প্রম্পটটি পাঠানো হচ্ছে
                    response = ollama.chat(model='llama3', messages=[
                        {'role': 'user', 'content': ai_prompt}
                    ])
                    
                    st.success("✅ Live Analysis Complete!")
                    st.markdown("### 🚨 BioNode AI Warning:")
                    # এআইয়ের উত্তর স্ক্রিনে দেখানো
                    st.write(response['message']['content'])
                    
            except Exception as e:
                st.error("❌ Error connecting to Database or AI. Please check everything.")
                st.write(e)