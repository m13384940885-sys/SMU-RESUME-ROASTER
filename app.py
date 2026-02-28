import streamlit as st
import PyPDF2
import google.generativeai as genai
import os
import re
from dotenv import load_dotenv

# 1. Setup API & Environment
load_dotenv()

# Check Streamlit secrets first (for cloud), then local .env (for local testing)
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except (FileNotFoundError, KeyError):
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    # THE MAC NETWORK FIX: transport="rest" prevents the infinite spinning
    genai.configure(api_key=api_key, transport="rest")

# 2. Page Configuration 
st.set_page_config(page_title="SMU HR Portal", page_icon="🏢", layout="centered")

# 3. Clean Corporate CSS
st.markdown("""
    <style>
    .stApp { background-color: #FAFAFA; }
    h1, h2, h3 { color: #151C55 !important; text-align: center; font-family: 'Helvetica Neue', sans-serif; }
    .stButton>button {
        background-color: #151C55; 
        color: white; 
        border: 2px solid #8A704C; 
        border-radius: 4px;
        font-weight: bold;
    }
    .stButton>button:hover {
        background-color: #8A704C; 
        color: white; 
        border: 2px solid #151C55;
    }
    </style>
""", unsafe_allow_html=True)

# 4. Helper Functions
def extract_text_from_pdf(uploaded_file):
    pdf_reader = PyPDF2.PdfReader(uploaded_file)
    text = "".join([page.extract_text() for page in pdf_reader.pages])
    return text

def load_smu_lore():
    try:
        with open("smu_lore.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return "No SMU lore found. Proceeding with standard corporate hostility."

# 5. Initialize Chat Session State
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "roast_style" not in st.session_state:
    st.session_state.roast_style = None
if "current_score" not in st.session_state:
    st.session_state.current_score = None

# --- TOP HEADER ---
st.title("🏢 SMU HR: Oasis Portal")
st.markdown("<p style='text-align: center; color: #666;'><b>Strictly Confidential:</b> Automated Candidate Synergy Evaluation</p>", unsafe_allow_html=True)

# THE FUNNY CORPORATE LINKS
st.write("")
colA, colB, colC = st.columns(3)
with colA:
    st.link_button("🌐 SMU Oasis (Mandatory)", "https://oasis.smu.edu.sg", use_container_width=True)
with colB:
    st.link_button("📈 eBOSS (Ruin Your Life)", "https://boss.smu.edu.sg", use_container_width=True)
with colC:
    st.link_button("💼 LinkedIn (For Clout)", "https://www.linkedin.com", use_container_width=True)
st.divider()

# --- INPUT SECTION ---
if not st.session_state.messages:
    
    # Check for missing API Key
    if not api_key:
        st.error("🚨 HR SYSTEM OFFLINE: No GEMINI_API_KEY found. Check Streamlit Secrets or your local .env file.")
        st.stop()
        
    col1, col2, col3 = st.columns([1, 4, 1])
    
    with col2:
        roast_style = st.selectbox("Select Manager Persona:", ["Passive-Aggressive Middle Manager", "Cutthroat Tech Bro", "Disappointed HR Director"])
        submission_type = st.radio("What are we evaluating today?", ["📄 PDF Upload (Resume or LinkedIn Profile)", "✍️ Paste LinkedIn Bio / Text"])
        
        candidate_text = ""
        
        if "PDF" in submission_type:
            st.caption("💡 *Pro-tip: Go to your LinkedIn profile, click 'More', and hit 'Save to PDF'!*")
            uploaded_file = st.file_uploader("Upload PDF Document", type="pdf")
            if uploaded_file:
                candidate_text = extract_text_from_pdf(uploaded_file)
        else:
            candidate_text = st.text_area("Paste your LinkedIn 'About' section, latest clout post, or raw resume text here:")
        
        if candidate_text:
            st.write("") 
            if st.button("Execute Performance Review", use_container_width=True):
                
                st.session_state.roast_style = roast_style
                smu_lore = load_smu_lore()
                
                initial_prompt = f"""
                You are a highly toxic, corporate-speaking AI manager evaluating a candidate from Singapore Management University (SMU).
                Persona: {roast_style}. Do not break character.
                
                SMU Lore: {smu_lore}

                Read the following candidate profile. Write a brutal, highly specific, and structured "Performance Review". 
                Do NOT just give a brief summary. I want you to dig into the resume and tear apart specific details.

                Format your review with the following corporate structure:
                
                **1. Executive Summary:** Write a scathing opening paragraph summarizing why this candidate is a walking corporate liability.
                **2. Granular Synergies (or Lack Thereof):** Use bullet points to pick out at least 3 to 4 VERY SPECIFIC details from their resume/profile (e.g., a specific past internship, a useless CCA they joined, a cringey buzzword they used, or their specific major). Roast each point ruthlessly. Use the SMU Lore to make it personal and targeted.
                **3. Action Items:** Provide one final passive-aggressive sentence on what their actual career trajectory looks like (e.g., "Destined for middle management at a dying startup").
                
                **4. CRITICAL RULE:** At the very end of your response, you MUST add a new line that says exactly: "TOXICITY_SCORE: [insert number between 1 and 100 here]". Do not add any text after this score.

                Here is the candidate data: {candidate_text}
                """
                
                with st.spinner("Analyzing candidate clout metrics and synergies..."):
                    try:
                        # THE 404 FIX: Dynamically fetch the newest, active 'flash' model 
                        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                        target_model = next((m for m in available_models if 'flash' in m), available_models[0])
                        clean_model_name = target_model.replace("models/", "")
                        
                        model = genai.GenerativeModel(clean_model_name)
                        st.session_state.chat_session = model.start_chat(history=[])
                        response = st.session_state.chat_session.send_message(initial_prompt)
                        
                        raw_roast = response.text
                        score_match = re.search(r"TOXICITY_SCORE:\s*(\d+)", raw_roast)
                        
                        toxicity_score = "N/A"
                        clean_roast = raw_roast
                        
                        if score_match:
                            toxicity_score = score_match.group(1)
                            clean_roast = re.sub(r"TOXICITY_SCORE:\s*\d+", "", raw_roast).strip()
                        
                        st.session_state.messages.append({"role": "assistant", "content": clean_roast})
                        st.session_state.current_score = toxicity_score
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"🚨 Corporate Network Error: {str(e)}")
                        st.info("If you see an error, check your terminal for details.")

# --- CHAT INTERFACE ---
if st.session_state.messages:
    
    colA, colB = st.columns([3, 1])
    with colA:
        if st.button("← Evaluate New Candidate", use_container_width=True):
            st.session_state.chat_session = None
            st.session_state.messages = []
            st.session_state.current_score = None
            st.session_state.roast_style = None
            st.rerun()
    
    with colB:
        score_val = st.session_state.get("current_score", "N/A")
        delta_text = "- High Risk" if str(score_val).isdigit() and int(score_val) > 50 else "Acceptable Risk"
        st.metric(label="⚠️ Corporate Liability Score", value=f"{score_val}/100", delta=delta_text, delta_color="inverse")

    st.markdown("### 💬 Live Manager Evaluation")
    
    st.download_button(
        label="📥 Download Official Disciplinary Report",
        data=st.session_state.messages[0]["content"], 
        file_name="SMU_HR_Warning.txt",
        mime="text/plain",
        use_container_width=True
    )
    
    st.divider()

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    user_reply = st.chat_input("Defend your profile...")
    
    if user_reply:
        with st.chat_message("user"):
            st.markdown(user_reply)
        st.session_state.messages.append({"role": "user", "content": user_reply})
        
        with st.chat_message("assistant"):
            with st.spinner("Drafting a passive-aggressive retort..."):
                try:
                    reminder = f"(Keep your reply incredibly concise, corporate, and stay in character as the {st.session_state.roast_style}.) "
                    response = st.session_state.chat_session.send_message(reminder + user_reply)
                    
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"🚨 Communication breakdown: {str(e)}")