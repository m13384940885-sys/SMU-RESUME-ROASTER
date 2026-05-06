# export_broad_to_jsonl.py
# Exports your SQLite database (or CSV) to JSONL for AI use

import sqlite3
import json
import pandas as pd

# ────────────────────────────────────────────────
# CHANGE THIS PATH to match your database file
# ────────────────────────────────────────────────
DB_PATH = "/Users/kyleju/Desktop/smu_student_life.db"
OUTPUT_JSONL = "/Users/kyleju/Desktop/Confess extraction/smu_broad_student_life.jsonl"

# Connect to the database
print("Connecting to database...")
conn = sqlite3.connect(DB_PATH)

# Read all data from the 'confessions' table
print("Reading data...")
df = pd.read_sql_query("SELECT * FROM confessions", conn)

conn.close()

print(f"Rows loaded: {len(df):,}")

# Optional: only export higher-quality rows (uncomment if you want to slim it down)
# df = df[df['quality_flag'].isin(['high', 'medium'])]

# Create prompt-completion style rows
print("Creating JSONL...")
rows = []
for _, row in df.iterrows():
    entry = {
        "prompt": "Share a relatable SMU student life confession or experience.",
        "completion": row['cleaned_text'],
        "category": row.get('auto_tags', 'general'),
        "quality_flag": row.get('quality_flag', 'medium'),
        "word_count": int(row.get('word_count', 0)),
        "tags": row.get('auto_tags', ''),
        "date": row.get('date', ''),
        "source_id": row.get('id', '')
    }
    rows.append(entry)

# Write to JSONL (one JSON object per line)
with open(OUTPUT_JSONL, 'w', encoding='utf-8') as f:
    for entry in rows:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')

print("\nDone!")
print(f"JSONL file created: {OUTPUT_JSONL}")
print(f"Total entries exported: {len(rows):,}")
print("\nSample first entry:")
print(json.dumps(rows[0], indent=2, ensure_ascii=False))