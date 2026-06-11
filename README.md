# BioNode-AI 🦠

**BioNode-AI** is a hybrid, production-ready Epidemic Intelligence System designed for rural and nationwide clinical data capture, geospatial infection visualization, and AI-driven early outbreak reporting in Bangladesh.

---

## 🚀 Core Features

### 1. Nationwide Geographical Geo-Hierarchy
- Full coverage of **all 8 divisions, 64 districts, and 494 upazilas** of Bangladesh.
- Dynamic cascading dropdowns (Division → District → Upazila) load hierarchy profiles seamlessly from `database/bangladesh_hierarchy.json` (compiled from geocoding databases).
- **Fallback Coordinate Jitter:** If specific high-resolution GPS coordinates are unavailable, the system resolves coordinates at the District level and applies a randomized offset ($\pm 0.015$ degrees) to prevent overlapping map nodes.

### 2. Secure Clinical Data Validation
- **Location Contamination Filter:** Real-time extraction of 500+ administrative names dynamically validates input text. The system blocks operators from writing geographic names inside clinical symptom fields to prevent database pollution.
- Blocks empty submissions or numeric inputs in symptom logs.

### 3. Density-Weighted Infection Heatmap
- Patient logs are grouped by location in Python to calculate the **active case counts** per Upazila.
- Plotted via Plotly's `density_mapbox` using `z='case_count'` as the density weight. Outbreak clusters glow brighter and larger to visually flag hotspots.
- Interactive hover tooltips present case counts and list of unique symptoms present in that location.

### 4. Advanced Pre-Aggregated AI Prompt Engine
- Pre-processes patient case datasets in Python before running AI prompts:
  - Counts active cases per location.
  - Lists symptom frequency.
  - Generates demographic age stats (average, min, max).
  - Computes a **30-Day Trend Indicator** (Emerging, Increasing, Stable, or Decreasing) based on bi-weekly splits.
- FEeds a clean, markdown-formatted epidemiological summary to Llama-3, reducing tokens and ensuring logical, highly accurate risk grading.
- **Robust Fallback:** If there are 0 cases in the last 30 days, the AI automatically evaluates the last 30 records overall, ensuring system uptime under low-traffic conditions.

### 5. Color-Coded Risk Grading & Outbreak Reports
- Renders AI alerts in styled banners by calculated risk level:
  - 🔴 **High Risk:** Increasing trends, emerging outbreaks, or clusters with $\ge 3$ cases.
  - 🟡 **Medium Risk:** Stable clusters or moderate case counts.
  - 🟢 **Low Risk:** Decreasing trends or isolated cases.
- **Downloadable Logs:** Operators can download a formatted official epidemiological report as a `.txt` file containing the nationwide summary, active hotspots, and prevention recommendations.

---

## 🛠️ Tech Stack & Architecture

- **Frontend:** Streamlit Web Application Dashboard
- **Database:** Neo4j Graph Database (AuraDB Cloud or Local Community Edition)
- **AI Core (Cloud):** Groq Cloud API (`llama-3.1-8b-instant`)
- **AI Core (Local/Offline Support):** Ollama (`llama3` model running locally)
- **Mapping Engine:** Plotly Express (`density_mapbox`)
- **Data Engineering:** Pandas

---

## ⚙️ Setup & Secrets Configuration

### 1. Requirements
Ensure you have Python 3.8+ installed. Install the dependencies:
```bash
pip install -r requirements.txt
```

### 2. Streamlit Secrets Config
Create a `.streamlit/secrets.toml` file in the root directory:
```toml
# Neo4j Database Credentials
NEO4J_URI = "neo4j+s://<YOUR_NEO4J_INSTANCE_ID>.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "<YOUR_NEO4J_PASSWORD>"

# Cloud LLM Key (Used by app.py)
GROQ_API_KEY = "<YOUR_GROQ_API_KEY>"
```

---

## 🏃 Running the Application

### Option A: Online Cloud Version (Recommended)
Uses Groq API for lightning-fast, zero-setup AI prediction.
```bash
python3 -m streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### Option B: Local/Offline Development
Uses Ollama to run predictions completely offline on your local machine. Ensure Ollama is installed and running (`ollama run llama3`).
```bash
python3 -m streamlit run app_local.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 📂 Project Structure
```
BioNode-AI/
├── .streamlit/
│   ├── secrets.toml          # Database credentials & API keys (gitignore)
│   └── secrets.toml.example  # Secrets template
├── database/
│   └── bangladesh_hierarchy.json # Administrative divisions, districts, upazilas and coordinates
├── app.py                    # Main Cloud-enabled application
├── app_local.py              # Offline/Local Ollama development application
├── requirements.txt          # Python dependencies
└── README.md                 # System documentation
```
