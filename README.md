# SMU Resume Roaster 🔥

Full-stack AI application that parses resumes and generates 
targeted, SMU-context-aware feedback and punchy roasts using multi-LLM routing.  
Built and deployed to **30+ users** at SMU BIA Demo Day, April 2026.
Made more than 20+ users say "Ouch" after seeing their resume roasted. 

---

## What It Does

- **Parses** unstructured PDF résumés using a custom 
  Retrieval-Augmented Generation (RAG) pipeline
- **Routes** queries across multiple LLMs (Gemini + OpenAI APIs) 
  for optimal response quality and cost efficiency
- **Generates** punchy, contextually relevant roasts using curated 
  SMU institutional knowledge — class bidding culture, grading systems, 
  and campus lore that genuinely surprised users
- **Powers** a built-in AI chatbot allowing users to argue back 
  against their roasts in real time
- **Tracks** live user engagement through an automated cloud-based 
  leaderboard

---

## What I Learned and potential improvements 

Deploying to live users revealed an intent classification gap 
I hadn't anticipated.

Users defending themselves against roasts didn't ask structured 
questions, instead they argued. They used Gen Z conversational language, 
trending memes, and emotional reactions the AI had no 
framework for. Thus the model quickly fell apart. 

Watching this failure in real time shaped how I now think about 
**user intent annotation** and **prompt design**: the gap between 
what a system is built to understand and what users actually say 
is not purely a technical problem. It is an operational one, 
and closing it requires classification logic designed from 
real user behaviour, not assumed inputs.

This is the problem I am most interested in working on.

---

## Technical Architecture

| Component | Detail |
|-----------|--------|
| **Frontend** | Streamlit |
| **LLM Routing** | Gemini API (primary) → OpenAI API (fallback) |
| **RAG Pipeline** | Custom Python pipeline ingesting 800MB+ of text |
| **Database** | SQL + Pandas for structured data management |
| **Context Source** | `smu_lore.txt` — curated SMU institutional knowledge |
| **Deployment** | Cloud-hosted, live at Demo Day |

---

## Built With

`Python` · `Streamlit` · `Google Gemini API` · `OpenAI API` · 
`RAG Pipeline` · `SQL` · `Pandas`

---

*SMU Business Intelligence & Analytics (BIA) — Demo Day, April 2026*
