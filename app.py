import io
import json
import math
import os
import random 
import re
import base64
from datetime import datetime
from urllib import parse, request

import fitz  # PyMuPDF for bulletproof PDF reading
import google.generativeai as genai # <-- Switched back to Gemini!
import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps

import ssl

# --- DUCT TAPE SSL FIX FOR MAC / CAMPUS WI-FI ---
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context
# ------------------------------------------------

# ==========================================
# ⚙️ 1. SETUP & CONFIGURATION
# ==========================================
load_dotenv()

# 👉 ADD YOUR MEME FILE NAMES HERE! 
MEME_TEMPLATES = [
    "meme.jpg",
    "meme2.jpg",
    "meme3.jpg", 
]

# Check Streamlit secrets first, then local .env for Gemini Key
try:
    api_key = st.secrets["GEMINI_API_KEY"]
except (FileNotFoundError, KeyError):
    api_key = os.getenv("GEMINI_API_KEY")

if api_key:
    # Initialize the Gemini Client with the REST fix
    genai.configure(api_key=api_key, transport="rest")
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

def get_secret_or_env(key, default=""):
    try:
        return st.secrets[key]
    except (FileNotFoundError, KeyError):
        return os.getenv(key, default)

SUPABASE_URL = get_secret_or_env("SUPABASE_URL")
SUPABASE_ANON_KEY = get_secret_or_env("SUPABASE_ANON_KEY")
LOCAL_LEADERBOARD_FILE = "hall_of_shame_local.csv"

# 2. Page Configuration
st.set_page_config(page_title="SMU HR Portal", page_icon="🏢", layout="wide")

# 3. Clean Corporate CSS
st.markdown(
    """
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
    .block-container { padding-top: 1rem; }
    </style>
""",
    unsafe_allow_html=True,
)


# ==========================================
# 🛠️ 4. HELPER FUNCTIONS
# ==========================================
def extract_text_from_pdf(uploaded_file):
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    text = "".join([page.get_text() for page in doc])
    return text

@st.cache_data
def load_smu_lore():
    try:
        with open("smu_lore.txt", "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        return "No SMU lore found. Proceeding with standard corporate hostility."

@st.cache_data
def load_smu_confessions(filepath="smu_broad_v2.csv"):
    try:
        if os.path.exists(filepath):
            return pd.read_csv(filepath)
        else:
            return pd.DataFrame()
    except Exception as e:
        print(f"Confessions file error: {e}")
        return pd.DataFrame()

def get_dynamic_lore(df, faculty, candidate_text, top_n=3):
    if df.empty:
        return "No live campus intel available right now."

    if 'quality_flag' in df.columns:
        search_df = df[df['quality_flag'].isin(['high', 'medium'])]
    else:
        search_df = df

    keywords = []
    if faculty == "LKCSB":
        keywords = ['finance', 'casing', 'snake', 'biz', 'group project', 'internship', 'networking']
    elif faculty == "SCIS":
        keywords = ['leetcode', 'basement', 'code', 'social', 'is', 'cs', 'swe']
    elif faculty == "SOE":
        keywords = ['stata', 'econs', 'stats', 'curve', 'math']
    elif faculty == "SOA":
        keywords = ['audit', 'big 4', 'accounting', 'sleep', 'ta']
    elif faculty == "SOL":
        keywords = ['law', 'reading', 'argue', 'library']
    
    candidate_lower = candidate_text.lower()
    if 'gpa' in candidate_lower: keywords.append('gpa')
    if 'dean' in candidate_lower: keywords.append('flex')
    if 'president' in candidate_lower or 'director' in candidate_lower: keywords.append('cca')

    pattern = '|'.join(keywords) if keywords else 'stress|bidding|internship|project'
    matched = search_df[search_df['cleaned_text'].astype(str).str.contains(pattern, case=False, na=False)]

    if len(matched) < top_n:
        matched = search_df.sample(min(len(search_df), top_n))
    else:
        matched = matched.sample(top_n)

    lore_strings = []
    for _, row in matched.iterrows():
        lore_strings.append(f"- Anonymous Confession: \"{row['cleaned_text']}\"")

    return "\n".join(lore_strings)

def get_score(pattern, text, default=50):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return default
    try:
        return max(1, min(100, int(match.group(1))))
    except (TypeError, ValueError):
        return default

def get_line_value(pattern, text, default="Unknown"):
    match = re.search(pattern, text, flags=re.IGNORECASE)
    return match.group(1).strip() if match else default

def clean_generated_roast(raw_roast):
    return re.sub(
        r"^(TOXICITY_SCORE|DELUSION_LEVEL|BUZZWORD_DENSITY|CORPORATE_SLAVERY_APTITUDE|ACTUAL_EMPLOYABILITY|DREAM_JOB|ACTUAL_DESTINY|MEME_CAPTION):\s*.*$",
        "",
        raw_roast,
        flags=re.IGNORECASE | re.MULTILINE,
    ).strip()

def format_roast_with_scorecard(clean_roast, toxicity, radar_scores, dream_job, actual_destiny):
    base = re.split(r"\n\s*\*\*4\.", clean_roast, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    return (
        f"{base}\n\n"
        f"**4. Final HR Scorecard:**\n"
        f"- **Toxicity Score:** {toxicity}/100\n"
        f"- **Delusion Level:** {radar_scores.get('Delusion', 50)}/100\n"
        f"- **Buzzword Density:** {radar_scores.get('Buzzwords', 50)}/100\n"
        f"- **Corporate Slavery Aptitude:** {radar_scores.get('Slavery Aptitude', 50)}/100\n"
        f"- **Actual Employability:** {radar_scores.get('Employability', 50)}/100\n"
        f"- **Dream Job:** {dream_job}\n"
        f"- **Actual Destiny:** {actual_destiny}"
    )

def generate_custom_meme(caption, template_path):
    try:
        if not os.path.exists(template_path):
            return None
            
        img = Image.open(template_path).convert("RGB")
        max_size = (600, 600)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        draw = ImageDraw.Draw(img)
        img_w, img_h = img.size

        target_size = max(24, int(img_w / 12)) 
        font = None
        
        possible_fonts = [
            "impact.ttf", "Impact.ttf",
            "/System/Library/Fonts/Supplemental/Impact.ttf",
            "/Library/Fonts/Impact.ttf",
            "C:\\Windows\\Fonts\\impact.ttf",
            "arialbd.ttf", "Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf"
        ]

        for font_path in possible_fonts:
            try:
                font = ImageFont.truetype(font_path, target_size)
                break  
            except Exception:
                continue
                
        if font is None:
            font = ImageFont.load_default()

        margin = 20
        max_width = img_w - (margin * 2)
        words = caption.upper().split()
        lines = []
        current_line = ""
        
        for word in words:
            test_line = current_line + word + " "
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font)
                text_width = bbox[2] - bbox[0]
            except AttributeError:
                text_width, _ = draw.textsize(test_line, font=font)
                
            if text_width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line.strip())
                current_line = word + " "
        if current_line:
            lines.append(current_line.strip())

        line_heights = []
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                line_heights.append(bbox[3] - bbox[1])
            except AttributeError:
                _, h = draw.textsize(line, font=font)
                line_heights.append(h)
                
        total_text_height = sum(line_heights) + (10 * (len(lines) - 1))
        
        y_text = img_h - total_text_height - 30 
        if y_text < 20: 
            y_text = 20

        for i, line in enumerate(lines):
            try:
                bbox = draw.textbbox((0, 0), line, font=font)
                text_w = bbox[2] - bbox[0]
            except AttributeError:
                text_w, _ = draw.textsize(line, font=font)
                
            x_text = (img_w - text_w) / 2

            outline_range = max(2, int(target_size / 12))
            for x_offset in range(-outline_range, outline_range+1):
                for y_offset in range(-outline_range, outline_range+1):
                    draw.text((x_text+x_offset, y_text+y_offset), line, font=font, fill="black")
            
            draw.text((x_text, y_text), line, font=font, fill="white")
            y_text += line_heights[i] + 10

        return img
    except Exception as e:
        print(f"Meme Generation Error: {e}")
        return None

def fallback_resume_from_inputs(data):
    return f"""# {data.get('name', 'Candidate Name')}
{data.get('email', 'email@example.com')} | {data.get('phone', '+65 XXXX XXXX')} | {data.get('linkedin', 'linkedin.com/in/yourname')}

## Education
- Singapore Management University, {data.get('degree', 'Degree Program')} ({data.get('grad_date', 'Expected Graduation')})

## Summary
{data.get('summary', 'Motivated undergraduate seeking internship opportunities.')}

## Skills
{data.get('skills', 'Python, SQL, Excel, PowerPoint')}

## Experience
{data.get('experience', 'No formal experience provided yet.')}
"""

def build_resume_draft_from_inputs(data):
    if not model: return fallback_resume_from_inputs(data)
    prompt = f"""
    You are an elite resume writer for SMU students.
    Create a one-page internship resume in concise plain text/markdown format.
    Requirements:
    - Keep it ATS-friendly and professional.
    - Use clear sections: Header, Education, Summary, Skills, Experience, Projects, Leadership, Awards.
    - Convert raw user notes into action-oriented bullet points with strong verbs and outcomes where possible.
    - Keep total length around 350-500 words.

    Student inputs:
    {json.dumps(data, ensure_ascii=True, indent=2)}
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception:
        return fallback_resume_from_inputs(data)

def add_candidate_to_leaderboard(entry):
    row = pd.DataFrame([entry])
    if os.path.exists(LOCAL_LEADERBOARD_FILE):
        old = pd.read_csv(LOCAL_LEADERBOARD_FILE)
        row = pd.concat([old, row], ignore_index=True)
    row.to_csv(LOCAL_LEADERBOARD_FILE, index=False)
    return "local"

def get_today_leaderboard(sort_mode="Most Delusional", top_n=10):
    if not os.path.exists(LOCAL_LEADERBOARD_FILE):
        return pd.DataFrame(), "local"

    df = pd.read_csv(LOCAL_LEADERBOARD_FILE)
    if "created_at" in df.columns:
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")
        df = df[df["created_at"].dt.date == datetime.now().date()]
    if sort_mode == "Most Delusional":
        df = df.sort_values("delusion", ascending=False)
    else:
        df = df.sort_values("employability", ascending=True)
    return df.head(top_n), "local"

def clear_leaderboard_data():
    if os.path.exists(LOCAL_LEADERBOARD_FILE):
        try:
            os.remove(LOCAL_LEADERBOARD_FILE)
            return True, "Deleted local CSV leaderboard."
        except Exception as exc:
            return False, f"Local CSV delete failed: {exc}"
    return True, "No leaderboard data found to delete."

def draw_radar_polygon(draw, center, radius, scores, labels):
    points = []
    spokes = len(labels)
    for i in range(spokes):
        angle = (2 * math.pi * i / spokes) - math.pi / 2
        x = center[0] + radius * math.cos(angle)
        y = center[1] + radius * math.sin(angle)
        draw.line([center, (x, y)], fill="#B5B5B5", width=2)
        draw.text((x - 55, y - 10), labels[i], fill="#2B2B2B")

    for i, score in enumerate(scores):
        angle = (2 * math.pi * i / spokes) - math.pi / 2
        factor = score / 100.0
        x = center[0] + (radius * factor) * math.cos(angle)
        y = center[1] + (radius * factor) * math.sin(angle)
        points.append((x, y))

    if len(points) >= 3:
        draw.polygon(points, fill="#8A704C", outline="#151C55")

def wrap_text_by_chars(text, width=48):
    words = text.split()
    lines = []
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if len(trial) > width:
            if line:
                lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    return lines

def generate_story_card(headshot_file, show_safe_overlay=False):
    w, h = 1080, 1920
    canvas = Image.new("RGB", (w, h), "#0E1630")
    draw = ImageDraw.Draw(canvas)
    safe_top = 250
    safe_bottom = 250
    safe_y_min = safe_top
    safe_y_max = h - safe_bottom

    top = (14, 22, 48)
    bottom = (35, 78, 125)
    for y in range(h):
        t = y / max(h - 1, 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    try:
        title_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Avenir Next.ttc", 64)
        body_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Avenir Next.ttc", 36)
        mini_font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Avenir Next.ttc", 28)
    except Exception:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
        mini_font = ImageFont.load_default()

    card = (40, 40, w - 40, h - 40)
    draw.rounded_rectangle(card, radius=36, fill="#F8FAFC", outline="#8A704C", width=5)
    draw.text((84, safe_y_min + 5), "SMU HR DISCIPLINARY NOTICE", fill="#0D1B3D", font=title_font)
    draw.text((84, safe_y_min + 78), "Share this to your Story and tag your faculty.", fill="#4A5568", font=mini_font)

    score = st.session_state.get("current_score", 50)
    draw.rounded_rectangle((84, safe_y_min + 125, 720, safe_y_min + 220), radius=20, fill="#FFE2E2", outline="#EF4444", width=3)
    draw.text((110, safe_y_min + 156), f"TOXICITY SCORE: {score}/100", fill="#B42318", font=body_font)

    dream = st.session_state.get("dream_job", "Unknown")
    destiny = st.session_state.get("actual_destiny", "Unknown")
    draw.rounded_rectangle((84, safe_y_min + 245, 996, safe_y_min + 420), radius=20, fill="#EEF2FF", outline="#4F46E5", width=2)
    draw.text((110, safe_y_min + 270), "Dream:", fill="#1E3A8A", font=body_font)
    draw.text((260, safe_y_min + 275), dream[:52], fill="#111827", font=mini_font)
    draw.text((110, safe_y_min + 335), "Actual:", fill="#1E3A8A", font=body_font)
    draw.text((260, safe_y_min + 340), destiny[:52], fill="#B91C1C", font=mini_font)

    if headshot_file is not None:
        try:
            headshot_file.seek(0)
            pic = Image.open(headshot_file)
            pic = ImageOps.exif_transpose(pic).convert("RGB")
            pic.thumbnail((260, 260))
            box = Image.new("RGB", (270, 270), "#FFFFFF")
            box.paste(pic, ((270 - pic.width) // 2, (270 - pic.height) // 2))
            canvas.paste(box, (736, safe_y_min + 125))
            draw.rounded_rectangle((730, safe_y_min + 119, 1010, safe_y_min + 399), radius=20, outline="#0D1B3D", width=3)
        except Exception:
            pass

    radar = st.session_state.get("radar_scores") or {}
    labels = list(radar.keys()) if radar else ["Delusion", "Buzzwords", "Slavery", "Employability"]
    scores = list(radar.values()) if radar else [50, 50, 50, 50]
    draw.rounded_rectangle((84, safe_y_min + 460, 996, safe_y_min + 885), radius=24, fill="#FFFFFF", outline="#D1D5DB", width=2)
    draw.text((110, safe_y_min + 485), "Clout Diagnostics", fill="#0D1B3D", font=body_font)
    draw_radar_polygon(draw, center=(540, safe_y_min + 685), radius=160, scores=scores, labels=labels)

    y = safe_y_min + 915
    draw.rounded_rectangle((84, y, 996, safe_y_max - 35), radius=24, fill="#F8FAFC", outline="#D1D5DB", width=2)
    draw.text((110, y + 25), "Manager Notes", fill="#0D1B3D", font=body_font)
    y += 80
    excerpt = (st.session_state.messages[0]["content"][:420] + "...") if st.session_state.messages else "No record"
    for line in wrap_text_by_chars(excerpt, width=58):
        if y > safe_y_max - 100:
            break
        draw.text((110, y), line, fill="#1F2937", font=mini_font)
        y += 40

    draw.text((84, safe_y_max - 70), "#SMU #GrowthMindset #AlwaysLearning", fill="#E2E8F0", font=mini_font)
    draw.text((84, safe_y_max - 35), "@smu.hr.portal", fill="#CBD5E1", font=mini_font)

    out = io.BytesIO()
    canvas.save(out, format="PNG")
    out.seek(0)
    return out

# 5. Initialize Chat Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "roast_style" not in st.session_state:
    st.session_state.roast_style = None
if "current_score" not in st.session_state:
    st.session_state.current_score = None
if "radar_scores" not in st.session_state:
    st.session_state.radar_scores = None
if "pronouns" not in st.session_state:
    st.session_state.pronouns = "They/Them"
if "dream_job" not in st.session_state:
    st.session_state.dream_job = "Unknown"
if "actual_destiny" not in st.session_state:
    st.session_state.actual_destiny = "Unknown"
if "linkedin_post" not in st.session_state:
    st.session_state.linkedin_post = ""
if "last_headshot_bytes" not in st.session_state:
    st.session_state.last_headshot_bytes = None
if "resume_draft_text" not in st.session_state:
    st.session_state.resume_draft_text = ""
if "meme_caption" not in st.session_state:
    st.session_state.meme_caption = ""


# ==========================================
# 🖥️ 6. MAIN UI
# ==========================================
# --- TOP HEADER ---
st.title("🏢 SMU HR: Oasis Portal")
st.markdown(
    "<p style='text-align: center; color: #666;'><b>Strictly Confidential:</b> Automated Candidate Synergy Evaluation</p>",
    unsafe_allow_html=True,
)

# --- LIVE GOSSIP TICKER (USING CSV) ---
try:
    ticker_df = load_smu_confessions("smu_broad_v2.csv")
    if not ticker_df.empty:
        sample_gossip = ticker_df.sample(5)['cleaned_text'].astype(str).tolist()
        ticker_text = " ⚠️ | ".join([text[:100] + "..." for text in sample_gossip])
        
        ticker_html = f"""
        <div style="width: 100%; overflow: hidden; background-color: #151C55; color: #8A704C; padding: 8px 0; border-radius: 4px; margin-bottom: 20px;">
            <div style="white-space: nowrap; animation: scroll-left 25s linear infinite; font-family: monospace; font-size: 14px;">
                <b>🔴 LIVE OASIS INTEL:</b> {ticker_text}
            </div>
        </div>
        <style>
        @keyframes scroll-left {{
            0% {{ transform: translateX(100%); }}
            100% {{ transform: translateX(-100%); }}
        }}
        </style>
        """
        st.markdown(ticker_html, unsafe_allow_html=True)
    else:
        st.warning("⚠️ HR Ticker Offline: Could not find or read 'smu_broad_v2.csv'")
except Exception as e:
    st.error(f"🚨 Ticker Crash: {str(e)}")

st.write("")
colA, colB, colC = st.columns(3)
with colA:
    st.link_button("🌐 SMU Oasis (Mandatory)", "https://oasis.smu.edu.sg", use_container_width=True)
with colB:
    st.link_button("📈 eBOSS (Ruin Your Life)", "https://boss.smu.edu.sg", use_container_width=True)
with colC:
    st.link_button("💼 LinkedIn (For Clout)", "https://www.linkedin.com", use_container_width=True)
st.divider()

main_tab, board_tab = st.tabs(["🧪 Roast Analyzer", "🏆 SMU Hall of Shame"])

with main_tab:
    # --- INPUT SECTION ---
    if not st.session_state.messages:

        if not api_key:
            st.error("🚨 HR SYSTEM OFFLINE: No GEMINI_API_KEY found. Check Streamlit Secrets or your local .env file.")
            st.stop()

        col1, col2, col3 = st.columns([1, 4, 1])

        with col2:
            roast_style = st.selectbox(
                "Select Manager Persona:",
                ["Passive-Aggressive Middle Manager", "Cutthroat Tech Bro", "Disappointed HR Director"],
            )
            pronouns = st.radio(
                "Candidate Pronouns (for accurate targeting):",
                ["He/Him", "She/Her", "They/Them"],
                horizontal=True,
            )
            submission_type = st.radio(
                "What are we evaluating today?",
                [
                    "📄 PDF Upload (Resume or LinkedIn Profile)",
                    "✍️ Paste LinkedIn Bio / Text",
                    "🛠️ No Resume? Build One Fast",
                ],
            )

            nickname = st.text_input("Candidate Alias (for leaderboard)", placeholder="e.g., FinanceBro99")
            faculty = st.selectbox("Faculty", ["Unknown", "LKCSB", "SCIS", "SOE", "SOSS", "SOL", "SOA", "Other"])

            candidate_text = ""

            if "PDF" in submission_type:
                st.caption("💡 *Pro-tip: Go to your LinkedIn profile, click 'More', and hit 'Save to PDF'!*")
                uploaded_file = st.file_uploader("Upload PDF Document", type="pdf")
                if uploaded_file:
                    candidate_text = extract_text_from_pdf(uploaded_file)
            elif "Paste" in submission_type:
                candidate_text = st.text_area("Paste your LinkedIn 'About' section, latest clout post, or raw resume text here:")
            else:
                st.markdown("#### Quick Resume Builder")
                st.caption("Answer these prompts and generate a usable draft in seconds.")
                name = st.text_input("1) Full Name", placeholder="e.g., Alex Tan")
                email = st.text_input("2) Email", placeholder="e.g., alex.2026@smu.edu.sg")
                phone = st.text_input("3) Phone", placeholder="e.g., +65 9123 4567")
                linkedin = st.text_input("4) LinkedIn URL", placeholder="e.g., linkedin.com/in/alextan")
                degree = st.text_input("5) Degree / Major", placeholder="e.g., BSc Information Systems")
                grad_date = st.text_input("6) Expected Graduation", placeholder="e.g., May 2027")
                summary = st.text_area("7) 1-2 sentence profile summary")
                skills = st.text_area("8) Skills (comma-separated)")
                experience = st.text_area("9) Past experience (part-time, internships, CCA roles)")
                projects = st.text_area("10) Projects")
                leadership = st.text_area("11) Leadership / CCA / Volunteering")
                awards = st.text_area("12) Awards / Certifications")

                resume_inputs = {
                    "name": name.strip(), "email": email.strip(), "phone": phone.strip(),
                    "linkedin": linkedin.strip(), "degree": degree.strip(), "grad_date": grad_date.strip(),
                    "summary": summary.strip(), "skills": skills.strip(), "experience": experience.strip(),
                    "projects": projects.strip(), "leadership": leadership.strip(), "awards": awards.strip(),
                }

                if st.button("⚡ Generate Quick Resume Draft", use_container_width=True):
                    if not resume_inputs["name"] or not resume_inputs["degree"]:
                        st.warning("Please fill at least name and degree/major.")
                    else:
                        with st.spinner("Generating ATS-friendly resume draft..."):
                            st.session_state.resume_draft_text = build_resume_draft_from_inputs(resume_inputs)

                if st.session_state.resume_draft_text:
                    edited_resume = st.text_area(
                        "Generated Resume Draft (Editable)",
                        value=st.session_state.resume_draft_text,
                        height=340,
                    )
                    st.session_state.resume_draft_text = edited_resume
                    candidate_text = edited_resume

            st.write("")
            headshot_file = st.file_uploader(
                "📸 Optional: Upload LinkedIn Headshot for a 'Vibe Check'",
                type=["png", "jpg", "jpeg"],
            )

            if candidate_text:
                st.write("")
                if st.button("Execute Performance Review", use_container_width=True):

                    st.session_state.roast_style = roast_style
                    st.session_state.pronouns = pronouns
                    st.session_state.linkedin_post = ""

                    if headshot_file is not None:
                        st.session_state.last_headshot_bytes = headshot_file.getvalue()
                    else:
                        st.session_state.last_headshot_bytes = None

                    smu_lore = load_smu_lore()
                    confessions_df = load_smu_confessions("smu_broad_v2.csv")
                    dynamic_lore = get_dynamic_lore(confessions_df, faculty, candidate_text)

                    initial_prompt = f"""
                    You are a highly toxic, Gen Z corporate AI HR Manager evaluating a candidate from Singapore Management University (SMU).
                    Your Persona: {roast_style}. Do not break character.
                    Candidate's Pronouns: {pronouns}. You MUST use these pronouns.
                    Candidate's Faculty: {faculty}.

                    SMU LORE & STEREOTYPES:
                    {smu_lore}
                    
                    LIVE CAMPUS INTEL (TELEGRAM CONFESSIONS):
                    Here are actual, recent anonymous confessions from the SMU student body related to this candidate's vibe/faculty:
                    {dynamic_lore}

                    YOUR MISSION:
                    Read the following candidate profile. Write a brutal, highly specific "Performance Review."
                    TONE: Combine professional corporate jargon with biting Gen Z slang.
                    
                    CRITICAL INSTRUCTION: You MUST use the "LIVE CAMPUS INTEL" provided above to make the roast feel eerily realistic. Quote or reference the specific themes of those confessions.

                    Format your review EXACTLY like this:

                    **1. Executive Summary:** A scathing opening paragraph summarizing why this candidate's career is lowkey a flop.

                    **2. Granular Synergies (or Lack Thereof):** Use bullet points to pick out at least 3 to 4 VERY SPECIFIC details from their resume. Tie their "achievements" to the toxic traits mentioned in the LIVE CAMPUS INTEL.

                    **3. Action Items:** Provide one final passive-aggressive sentence on what their actual career trajectory looks like.

                    **4. CRITICAL RULE:** At the very end of your response, you MUST add exactly these 8 lines on separate lines (Do not add any text after this):
                    TOXICITY_SCORE: [insert number between 1 and 100]
                    DELUSION_LEVEL: [insert number between 1 and 100]
                    BUZZWORD_DENSITY: [insert number between 1 and 100]
                    CORPORATE_SLAVERY_APTITUDE: [insert number between 1 and 100]
                    ACTUAL_EMPLOYABILITY: [insert number between 1 and 100]
                    DREAM_JOB: [predict their ideal fantasy career based on profile]
                    ACTUAL_DESTINY: [predict their realistic fate in one sharp sentence]
                    MEME_CAPTION: [write a hilarious, short 10-word meme caption summarizing their biggest red flag]

                    Here is the candidate text to destroy: {candidate_text}
                    """

                    with st.spinner("Accessing SMU Confessions database & analyzing synergies..."):
                        try:
                            # --- GEMINI GENERATION LOGIC ---
                            prompt_parts = [initial_prompt]
                            
                            if headshot_file:
                                img = Image.open(io.BytesIO(st.session_state.last_headshot_bytes))
                                prompt_parts.append(img)
                                prompt_parts.append("\n\nCRITICAL: The candidate has also attached their headshot. Roast their choice of background, their smile (or lack thereof), and their general 'corporate aura'.")

                            # Call Gemini API
                            response = model.generate_content(prompt_parts)
                            raw_roast = response.text

                            st.session_state.current_score = get_score(r"TOXICITY_SCORE:\s*(\d+)", raw_roast)
                            st.session_state.radar_scores = {
                                "Delusion": get_score(r"DELUSION_LEVEL:\s*(\d+)", raw_roast),
                                "Buzzwords": get_score(r"BUZZWORD_DENSITY:\s*(\d+)", raw_roast),
                                "Slavery Aptitude": get_score(r"CORPORATE_SLAVERY_APTITUDE:\s*(\d+)", raw_roast),
                                "Employability": get_score(r"ACTUAL_EMPLOYABILITY:\s*(\d+)", raw_roast),
                            }
                            st.session_state.dream_job = get_line_value(r"DREAM_JOB:\s*(.*)", raw_roast, "Corporate Unicorn")
                            st.session_state.actual_destiny = get_line_value(r"ACTUAL_DESTINY:\s*(.*)", raw_roast, "Big 4 spreadsheet gladiator")
                            st.session_state.meme_caption = get_line_value(r"MEME_CAPTION:\s*(.*)", raw_roast, "When you put Excel as a skill but can't do a VLOOKUP")

                            clean_roast = clean_generated_roast(raw_roast)
                            clean_roast = format_roast_with_scorecard(
                                clean_roast=clean_roast,
                                toxicity=st.session_state.current_score,
                                radar_scores=st.session_state.radar_scores,
                                dream_job=st.session_state.dream_job,
                                actual_destiny=st.session_state.actual_destiny,
                            )

                            st.session_state.messages = [{"role": "assistant", "content": clean_roast}]

                            entry = {
                                "created_at": datetime.now().isoformat(),
                                "nickname": nickname.strip() if nickname.strip() else "Anonymous Warrior",
                                "faculty": faculty,
                                "toxicity": st.session_state.current_score,
                                "delusion": st.session_state.radar_scores["Delusion"],
                                "employability": st.session_state.radar_scores["Employability"],
                                "actual_destiny": st.session_state.actual_destiny,
                            }
                            add_candidate_to_leaderboard(entry)

                            st.rerun()

                        except Exception as e:
                            st.error(f"🚨 Corporate Network Error: {str(e)}")

    # --- CHAT & RESULTS INTERFACE ---
    if st.session_state.messages:

        colA, colB = st.columns([1, 1])

        with colA:
            if st.button("← Evaluate New Candidate", use_container_width=True):
                # Clear all history
                st.session_state.messages = []
                st.session_state.current_score = None
                st.session_state.radar_scores = None
                st.session_state.roast_style = None
                st.session_state.linkedin_post = ""
                st.session_state.dream_job = "Unknown"
                st.session_state.actual_destiny = "Unknown"
                st.session_state.meme_caption = ""
                st.session_state.last_headshot_bytes = None
                st.session_state.resume_draft_text = ""
                st.rerun()

            score_val = st.session_state.get("current_score", 50)
            delta_text = "- High Risk" if score_val > 50 else "Acceptable Risk"
            st.metric(label="⚠️ Corporate Liability Score (Toxicity)", value=f"{score_val}/100", delta=delta_text, delta_color="inverse")

            st.write("")
            st.download_button(
                label="📥 Download Official Disciplinary Report",
                data=st.session_state.messages[0]["content"],
                file_name="SMU_HR_Warning.txt",
                mime="text/plain",
                use_container_width=True
            )

            st.write("")
            st.markdown("#### 📸 Post for Clout")
            st.caption("Export your roast to share on your Instagram Story.")
            
            hs_file = io.BytesIO(st.session_state.last_headshot_bytes) if st.session_state.get("last_headshot_bytes") else None
            
            try:
                story_img = generate_story_card(hs_file, show_safe_overlay=False)
                st.download_button(
                    label="📱 Download Instagram Story Report",
                    data=story_img,
                    file_name="SMU_HR_Story.png",
                    mime="image/png",
                    use_container_width=True,
                    type="primary"
                )
            except Exception as e:
                st.error("Failed to generate Story export.")

        with colB:
            if st.session_state.radar_scores:
                df = pd.DataFrame(dict(
                    r=list(st.session_state.radar_scores.values()),
                    theta=list(st.session_state.radar_scores.keys())
                ))
                fig = px.line_polar(df, r='r', theta='theta', line_close=True, range_r=[0,100])
                fig.update_traces(fill='toself', line_color='#151C55', fillcolor='rgba(138, 112, 76, 0.5)')
                fig.update_layout(
                    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
                    showlegend=False,
                    margin=dict(l=20, r=20, t=20, b=20),
                    height=350
                )
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("### 🔮 Career Trajectory")
                st.info(f"**Dream Job:** {st.session_state.dream_job}")
                st.error(f"**Actual Destiny:** {st.session_state.actual_destiny}")

                # 🤡 THE RANDOM MEME GENERATOR UI
                st.divider()
                st.markdown("### 🤡 Candidate Vibe Check")
                if "meme_caption" in st.session_state and st.session_state.meme_caption:
                    
                    chosen_template = random.choice(MEME_TEMPLATES)
                    meme_img = generate_custom_meme(st.session_state.meme_caption, chosen_template)
                    
                    if meme_img:
                        spacer1, img_col, spacer2 = st.columns([1, 2, 1])
                        
                        with img_col:
                            st.image(meme_img, use_container_width=True, caption=f"Template: {chosen_template}")
                    else:
                        st.warning(f"⚠️ Action Required: Make sure '{chosen_template}' is saved in your project folder!")

        st.divider()
        st.markdown("### 💬 Live Manager Evaluation")

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        # --- CRINGEY LINKEDIN POST GENERATOR ---
        if st.button("🤝 Accept Defeat & Post to LinkedIn", use_container_width=True):
            with st.spinner("Generating cringey LinkedIn post..."):
                try:
                    li_prompt = f"Based on this roast: '{st.session_state.messages[0]['content']}', write a highly satirical, buzzword-stuffed, cringey Gen Z LinkedIn post where the candidate is 'humbled' and 'grateful' for the toxic feedback. Make it exactly like the posts people make after getting rejected from McKinsey. Use hashtags like #GrowthMindset #SMU #AlwaysLearning."
                    
                    response = model.generate_content(li_prompt)
                    st.session_state.linkedin_post = response.text
                except Exception as e:
                    st.error(f"Error generating post: {e}")

        if st.session_state.linkedin_post:
            st.success("✨ Your Clout-Chasing Post is Ready:")
            st.text_area("Copy this to LinkedIn:", value=st.session_state.linkedin_post, height=200)

        # --- LIVE CHAT INPUT ---
        user_reply = st.chat_input("Defend your profile...")
        
        if user_reply:
            with st.chat_message("user"):
                st.markdown(user_reply)
            st.session_state.messages.append({"role": "user", "content": user_reply})
            
            with st.chat_message("assistant"):
                with st.spinner("Drafting a passive-aggressive retort..."):
                    try:
                        # Build a quick conversation history for Gemini
                        convo_context = f"You are acting as {st.session_state.roast_style}. Candidate pronouns: {st.session_state.pronouns}. Keep your reply incredibly concise, corporate, and toxic.\n\n"
                        for msg in st.session_state.messages:
                            role = "Candidate" if msg["role"] == "user" else "HR Manager"
                            convo_context += f"{role}: {msg['content']}\n\n"
                        
                        convo_context += f"Candidate: {user_reply}\nHR Manager:"
                        
                        response = model.generate_content(convo_context)
                        reply_text = response.text
                        
                        st.markdown(reply_text)
                        
                        # Save responses
                        st.session_state.messages.append({"role": "assistant", "content": reply_text})
                    except Exception as e:
                        st.error(f"🚨 Communication breakdown: {str(e)}")

# --- HALL OF SHAME LEADERBOARD TAB ---
with board_tab:
    st.markdown("## 🏆 SMU Hall of Shame")
    st.write("Live tracking of the most unemployable profiles submitted today.")

    sort_colA, sort_colB = st.columns([2, 1])
    with sort_colA:
        sort_mode = st.radio("Sort By:", ["Most Delusional", "Most Unemployable"], horizontal=True)
    with sort_colB:
        if st.button("🔄 Refresh Leaderboard"):
            st.rerun()

    df_leaderboard, source = get_today_leaderboard(sort_mode=sort_mode, top_n=10)

    if df_leaderboard.empty:
        st.info("No candidates roasted yet today. Be the first sacrifice!")
    else:
        st.caption(f"Data Source: {source.upper()}")
        
        display_df = df_leaderboard.copy()
        
        if "created_at" in display_df.columns:
            display_df = display_df.drop(columns=["created_at"])
            
        display_df.columns = [col.replace("_", " ").title() for col in display_df.columns]
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
    st.divider()
    with st.expander("Admin Tools"):
        if st.button("🗑️ Clear Leaderboard Data"):
            success, msg = clear_leaderboard_data()
            if success:
                st.success(msg)
                st.rerun()
            else:
                st.error(msg)
