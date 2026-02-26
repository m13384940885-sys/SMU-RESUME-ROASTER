import streamlit as st
import PyPDF2
import google.generativeai as genai
import os
from dotenv import load_dotenv

# 1. Setup API
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# 2. Page Configuration (Changed back to 'centered' for that minimalist look)
st.set_page_config(page_title="SMU HR Portal", page_icon="🏢", layout="centered")

# 3. Clean Corporate CSS
st.markdown("""
    <style>
    .stApp { background-color: #FAFAFA; }
    
    /* Center all the headers */
    h1, h2, h3 { color: #151C55 !important; text-align: center; font-family: 'Helvetica Neue', sans-serif; }
    
    /* Custom Gold/Navy Buttons */
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
        return "No SMU lore found."

# 5. Initialize Chat Session State
if "chat_session" not in st.session_state:
    st.session_state.chat_session = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- TOP HEADER ---
st.title("🏢 SMU HR: Oasis Portal")
st.markdown("<p style='text-align: center; color: #666;'><b>Strictly Confidential:</b> Automated Candidate Synergy Evaluation</p>", unsafe_allow_html=True)

# THE NEW FUNNY CORPORATE LINKS
st.write("")
colA, colB, colC = st.columns(3)
with colA:
    st.link_button("🌐 SMU Oasis (Mandatory)", "https://oasis.smu.edu.sg", use_container_width=True)
with colB:
    st.link_button("📈 eBOSS (Ruin Your Life)", "https://boss.smu.edu.sg", use_container_width=True)
with colC:
    st.link_button("💼 LinkedIn (For Clout)", "https://www.linkedin.com", use_container_width=True)
st.divider()

# --- INPUT SECTION (Only visible before the chat starts) ---
if not st.session_state.messages:
    
    col1, col2, col3 = st.columns([1, 4, 1])
    
    with col2:
        roast_style = st.selectbox("Select Manager Persona:", ["Passive-Aggressive Middle Manager", "Cutthroat Tech Bro", "Disappointed HR Director"])
        
        # NEW: Let them choose what to roast
        submission_type = st.radio("What are we evaluating today?", ["📄 PDF Upload (Resume or LinkedIn Profile)", "✍️ Paste LinkedIn Bio / Text"])
        
        candidate_text = ""
        
        if "PDF" in submission_type:
            st.caption("💡 *Pro-tip: Go to your LinkedIn profile, click 'More', and hit 'Save to PDF'!*")
            uploaded_file = st.file_uploader("Upload PDF Document", type="pdf")
            if uploaded_file:
                candidate_text = extract_text_from_pdf(uploaded_file)
        else:
            candidate_text = st.text_area("Paste your LinkedIn 'About' section, latest clout post, or raw resume text here:")
        
        # Only show the button if we actually have text to roast
        if candidate_text:
            st.write("") 
            if st.button("Execute Performance Review", use_container_width=True):
                
                smu_lore = load_smu_lore()
                
                # UPDATED PROMPT: Now handles LinkedIn or Resumes
                initial_prompt = f"""
                You are a highly toxic, concise, corporate-speaking AI manager evaluating a candidate from Singapore Management University (SMU).
                Persona: {roast_style}. Do not break character.
                
                SMU Lore: {smu_lore}

                Read the following candidate profile (it might be a resume, a LinkedIn export, or a pasted bio). 
                Write a brutal, CONCISE "Performance Review". 
                
                1. Pinpoint exactly 1 or 2 specific "flaws" (e.g., their major, a specific CCA, a cringey LinkedIn buzzword, or lack of substance) and roast them ruthlessly using the SMU Lore.
                2. Summarize the rest of their "achievements" in one highly dismissive, corporate sentence.
                3. Keep the overall review short, punchy, simple to read, and highly business-professional. 

                Here is the candidate data: {candidate_text}
                """
                
                with st.spinner("Analyzing candidate clout metrics and synergies..."):
                    model = genai.GenerativeModel('gemini-3-flash-preview')
                    st.session_state.chat_session = model.start_chat(history=[])
                    response = st.session_state.chat_session.send_message(initial_prompt)
                    
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                    st.rerun() 

# --- CHAT INTERFACE ---
if st.session_state.messages:
    if st.button("← Evaluate New Candidate"):
        st.session_state.chat_session = None
        st.session_state.messages = []
        st.rerun()
        
    st.markdown("### 💬 Live Manager Evaluation")
    
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
                reminder = f"(Keep your reply incredibly concise, corporate, and stay in character as the {roast_style}.) "
                response = st.session_state.chat_session.send_message(reminder + user_reply)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})