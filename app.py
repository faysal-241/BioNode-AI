import streamlit as st

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
    
    # একটি সুন্দর ও গোছানো ডেটা এন্ট্রি ফর্ম
    with st.form("patient_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            age = st.number_input("Patient Age", min_value=0, max_value=120, value=25)
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            
        with col2:
            location = st.selectbox("Location / Zone", ["Barishal Sadar", "Bakerganj", "Babuganj", "Banaripara"])
            symptoms = st.multiselect("Symptoms (Select all that apply)", 
                                      ["Fever", "Cough", "Diarrhea", "Vomiting", "Headache", "Body Ache"])
            
        # WHO Novelty Check-এর জন্য স্পেশাল ইনপুট বক্স
        new_symptom = st.text_input("New/Unknown Symptom (If any) - For WHO Novelty Check")
        
        # সাবমিট বাটন
        submitted = st.form_submit_button("💾 Save Patient Data")
        
        if submitted:
            st.success(f"✅ Data temporarily saved for a {age}-year-old {gender} from {location}!")