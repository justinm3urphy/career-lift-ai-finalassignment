import streamlit as st
import firebase_admin
from firebase_admin import credentials, storage
import google.generativeai as genai
import pdfplumber
import io
import json

# --- 1. INITIALIZE SERVICES ---
if not firebase_admin._apps:
    try:
        fb_secrets = dict(st.secrets["firebase"])
        fb_secrets["private_key"] = fb_secrets["private_key"].replace("\\n", "\n")
        BUCKET_ID = 'resume-booster-cbd24.firebasestorage.app' 
        
        cred = credentials.Certificate(fb_secrets)
        firebase_admin.initialize_app(cred, {'storageBucket': BUCKET_ID})
    except Exception as e:
        st.error(f"Firebase Init Error: {e}")
        st.stop()

# Initialize Gemini 3 Flash
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # We define the 'brain' settings here
    config = {
        "temperature": 0.2,  # Low temperature = Focused and consistent
        "top_p": 0.8,        # Top-p = Professional vocabulary filtering
    }

    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash', # Upgrading to Pro as discussed!
        generation_config=config
    )
except Exception as e:
    st.error(f"Gemini Configuration Error: {e}")

# --- 2. DYNAMIC INDUSTRY DISCOVERY ---
@st.cache_data(ttl=600) # Cache the list for 10 mins so it doesn't scan on every click
def get_available_industries():
    """Scans Firebase to find folders that actually contain PDFs."""
    bucket = storage.bucket()
    blobs = bucket.list_blobs() # List all files in the project
    
    # We use a set to keep only unique folder names
    industries = set()
    
    for blob in blobs:
        if "/" in blob.name and blob.name.lower().endswith(".pdf"):
            # The part before the first "/" is the industry name
            folder_name = blob.name.split("/")[0]
            industries.add(folder_name)
    
    # Return as a sorted list
    return sorted(list(industries))

# --- 3. THE AUTOMATIC TWIN ENGINE ---
def get_or_create_twin(industry):
    bucket = storage.bucket()
    twin_path = f"{industry}/{industry}_twin.json"
    twin_blob = bucket.blob(twin_path)

    if twin_blob.exists():
        st.toast(f"⚡ Loading Digital Twin for {industry}...")
        data = json.loads(twin_blob.download_as_string())
        return data.get("knowledge_base", ""), data.get("count", 0)

    st.info(f"🆕 Creating Digital Twin for {industry}...")
    prefix = f"{industry}/"
    blobs = list(bucket.list_blobs(prefix=prefix))
    pdf_blobs = [b for b in blobs if b.name.lower().endswith('.pdf') and b.size > 0]
    
    if not pdf_blobs:
        return None, 0

    all_text = ""
    count = 0
    progress_bar = st.progress(0, text="Generating Industry Brain...")
    
    for idx, blob in enumerate(pdf_blobs):
        try:
            content = blob.download_as_bytes()
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                page_texts = [p.extract_text() for p in pdf.pages if p.extract_text()]
                all_text += " ".join(page_texts) + " "
                count += 1
        except: continue
        progress_bar.progress((idx + 1) / len(pdf_blobs))
    
    twin_data = {"industry": industry, "count": count, "knowledge_base": all_text}
    twin_blob.upload_from_string(json.dumps(twin_data))
    progress_bar.empty()
    return all_text, count

# --- 4. UI ---
st.set_page_config(page_title="Career-Lift AI", page_icon="🚀", layout="wide")
st.title("🚀 Career-Lift AI")

# FETCH THE DYNAMIC LIST
available_industries = get_available_industries()

with st.sidebar:
    st.header("Configuration")
    
    if available_industries:
        industry_choice = st.selectbox("Industry Warehouse", available_industries)
        st.success(f"Found {len(available_industries)} industries in Firebase.")
    else:
        st.error("No valid industry folders found in Firebase Storage.")
        st.stop()
        
    st.divider()
    if st.button("🗑️ Reset Selected Twin"):
        bucket = storage.bucket()
        bucket.blob(f"{industry_choice}/{industry_choice}_twin.json").delete()
        st.cache_data.clear()
        st.rerun()

user_file = st.file_uploader("Upload your CV (PDF)", type=["pdf"])

# --- 5. EXECUTION ---
if user_file:
    knowledge, total_files = get_or_create_twin(industry_choice)
    
    if knowledge:
        if st.button("Generate AI Comparison", type="primary"):
            final_report = ""
            with st.status("🤖 Analyzing industry alignment...", expanded=True) as status:
                st.write("Reading your CV...")
                with pdfplumber.open(user_file) as pdf:
                    user_text = " ".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                
                st.write(f"Comparing against {total_files} industry benchmarks...")
                prompt = f"""
                You are an expert recruiter and ATS (Applicant Tracking System) Specialist for the {industry_choice} industry.

                TASK:
                1. Compare the CANDIDATE CV against the provided {total_files} INDUSTRY BENCHMARKS.
                2. Identify missing ATS keywords and technical competencies common in the benchmarks.

                BENCHMARKS DATA: {knowledge[:35000]}
                CANDIDATE CV: {user_text}

                OUTPUT FORMAT (Markdown):
                ### 📊 Industry Alignment Score: [X/10]

                ### ✅ Strengths (What to Keep)
                * [Point 1]
                * [Point 2]

                ### 🛠️ Required Improvements (ATS Gap Analysis)
                * **Missing Keywords:** [List specific technical terms found in benchmarks but missing in CV]
                * **Bullet Point Polish:** [Suggest stronger action verbs for their experience]

                ### 💡 Recruiter's Action Plan
                * [One specific piece of advice for an SIT student applying for this role]
                """
                
                try:
                    response = model.generate_content(prompt)
                    final_report = response.text
                    status.update(label="✅ Analysis Complete!", state="complete", expanded=False)
                except Exception as e:
                    status.update(label="❌ AI Error", state="error")
                    st.error(f"Error: {e}")
            
            if final_report:
                st.success(f"Benchmarked successfully against {total_files} records.")
                st.divider()
                st.markdown(final_report)

st.divider()
st.caption(f"v3.5 | SIT Mechanical Engineering | SBE3136 Project")