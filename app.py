import streamlit as st
import json
import csv
import io
# Import helper logic directly from rank.py (which standardizes modules)
from rank import is_honeypot, compute_score, generate_reasoning

st.set_page_config(page_title="Redrob Candidate Ranker Sandbox", layout="wide")

st.title("💼 Redrob Candidate Ranker Sandbox")
st.markdown("""
This sandbox allows you to upload a small sample of candidates (JSON or JSONL format) to verify the reproducibility of the **Idea Architects** ranking system.
It filters honeypots and ranks candidates for the **Founding Senior AI Engineer** role.
""")

uploaded_file = st.file_uploader("Upload candidate sample (JSON or JSONL)", type=["json", "jsonl"])

if uploaded_file is not None:
    try:
        # Load candidates
        candidates = []
        content = uploaded_file.getvalue().decode("utf-8")
        
        # Check if JSON array or JSONL lines
        if uploaded_file.name.endswith(".jsonl"):
            for line in content.splitlines():
                if line.strip():
                    candidates.append(json.loads(line))
        else:
            try:
                candidates = json.loads(content)
                if not isinstance(candidates, list):
                    candidates = [candidates]
            except json.JSONDecodeError:
                # Try fallback JSONL parsing
                for line in content.splitlines():
                    if line.strip():
                        candidates.append(json.loads(line))

        st.success(f"Successfully loaded {len(candidates)} candidates.")

        if st.button("🚀 Run Ranker"):
            ranked_candidates = []
            honeypots_filtered = 0
            
            for cand in candidates:
                # Filter honeypots
                is_hp, reason = is_honeypot(cand)
                if is_hp:
                    honeypots_filtered += 1
                    continue
                    
                score, relevant_skills = compute_score(cand)
                ranked_candidates.append({
                    'candidate_id': cand.get('candidate_id', 'UNKNOWN'),
                    'score': score,
                    'candidate': cand,
                    'relevant_skills': relevant_skills
                })
            
            # Sort
            ranked_candidates.sort(key=lambda x: (-x['score'], x['candidate_id']))
            
            st.info(f"Filtered out {honeypots_filtered} honeypots. Ranking remaining {len(ranked_candidates)} candidates...")
            
            # Generate final CSV output
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['candidate_id', 'rank', 'score', 'reasoning'])
            
            preview_data = []
            for idx, item in enumerate(ranked_candidates):
                rank = idx + 1
                cid = item['candidate_id']
                score = item['score']
                cand = item['candidate']
                relevant_skills = item['relevant_skills']
                reasoning = generate_reasoning(cand, score, relevant_skills)
                
                writer.writerow([cid, rank, score, reasoning])
                preview_data.append({
                    "Rank": rank,
                    "Candidate ID": cid,
                    "Score": score,
                    "Reasoning": reasoning
                })
                
            csv_content = output.getvalue()
            
            st.subheader("📊 Ranking Preview (Top 10)")
            st.table(preview_data[:10])
            
            st.download_button(
                label="📥 Download Ranked CSV",
                data=csv_content,
                file_name="ranked_sample_submission.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"Error processing file: {e}")
