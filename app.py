import streamlit as st
import PyPDF2
import google.generativeai as genai
import os
import re
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
if "roast_style" not in st.session_state:
    st.session_state.roast_style = None
if "current_score" not in st.session_state:
    st.session_state.current_score = None

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
                
                st.session_state.roast_style = roast_style
                
                smu_lore = load_smu_lore()
                
                # UPDATED PROMPT: Longer, highly specific, and structured
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
                    model = genai.GenerativeModel('gemini-3-flash-preview')
                    st.session_state.chat_session = model.start_chat(history=[])
                    response = st.session_state.chat_session.send_message(initial_prompt)
                    
                    # --- NEW: Extracting the Toxicity Score ---
                    raw_roast = response.text
                    score_match = re.search(r"TOXICITY_SCORE:\s*(\d+)", raw_roast)
                    
                    toxicity_score = "N/A"
                    clean_roast = raw_roast
                    
                    if score_match:
                        toxicity_score = score_match.group(1)
                        # Remove the secret score text so the user doesn't see the raw output
                        clean_roast = re.sub(r"TOXICITY_SCORE:\s*\d+", "", raw_roast).strip()
                    
                    # Save the clean roast to history
                    st.session_state.messages.append({"role": "assistant", "content": clean_roast})
                    
                    # Save the score into session state so it survives page reloads
                    st.session_state.current_score = toxicity_score
                    
                    st.rerun()

# --- CHAT INTERFACE ---
if st.session_state.messages:
    
    colA, colB = st.columns([3, 1])
    with colA:
        # --- FIX: Changed back to the reset button ---
        if st.button("← Evaluate New Candidate", use_container_width=True):
            st.session_state.chat_session = None
            st.session_state.messages = []
            st.session_state.current_score = None
            st.session_state.roast_style = None
            st.rerun()
    
    with colB:
        # Display the giant corporate score!
        score_val = st.session_state.get("current_score", "N/A")
        delta_text = "- High Risk" if str(score_val).isdigit() and int(score_val) > 50 else "Acceptable Risk"
        st.metric(label="⚠️ Corporate Liability Score", value=f"{score_val}/100", delta=delta_text, delta_color="inverse")

    st.markdown("### 💬 Live Manager Evaluation")
    
    # --- NEW: The Download Button ---
    st.download_button(
        label="📥 Download Official Disciplinary Report",
        data=st.session_state.messages[0]["content"], # Downloads the initial roast
        file_name="SMU_HR_Warning.txt",
        mime="text/plain",
        use_container_width=True
    )
    
    st.divider()

    # Draw the chat messages...
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
    # ... (Keep your existing user_reply chat_input code here) ...

    user_reply = st.chat_input("Defend your profile...")
    
    
    if user_reply:
        # 1. The user's message block
        with st.chat_message("user"):
            st.markdown(user_reply)
        st.session_state.messages.append({"role": "user", "content": user_reply})
        
        # 2. The assistant's message block (MUST line up perfectly with the user block above)
        with st.chat_message("assistant"):
            with st.spinner("Drafting a passive-aggressive retort..."):
                
                reminder = f"(Keep your reply incredibly concise, corporate, and stay in character as the {st.session_state.roast_style}.) "
                response = st.session_state.chat_session.send_message(reminder + user_reply)
                
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
