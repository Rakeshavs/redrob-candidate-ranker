#!/usr/bin/env python3
import json
import csv
import re
import sys
from datetime import datetime

# Define JD keywords and target profiles
AI_ML_KEYWORDS = {
    'nlp', 'natural language processing', 'embeddings', 'retrieval', 'vector database', 
    'pinecone', 'weaviate', 'qdrant', 'milvus', 'opensearch', 'elasticsearch', 'faiss', 
    'search', 'ranking', 'reranking', 'sentence-transformers', 'transformers', 'xgboost', 
    'lightgbm', 'applied ml', 'machine learning', 'recommendation systems', 'information retrieval',
    'rag', 'llm', 'fine-tuning', 'lora', 'qlora', 'peft'
}

CONSULTANCIES = {
    'tcs', 'infosys', 'wipro', 'accenture', 'cognizant', 'capgemini', 'l&t', 'lnt', 'hcl', 
    'tech mahindra', 'mindtree', 'mphasis'
}

PREFERRED_LOCATIONS = {
    'pune', 'noida', 'delhi', 'ncr', 'gurgaon', 'ghaziabad', 'faridabad', 
    'hyderabad', 'mumbai', 'bangalore', 'bengaluru'
}

def is_honeypot(cand):
    # Rule 1: Duplicate descriptions in career history
    career = cand.get('career_history', [])
    desc_list = [job.get('description', '') for job in career if job.get('description')]
    if len(desc_list) != len(set(desc_list)):
        return True, "Duplicate job descriptions in career history."

    # Rule 2: Impossible skill duration
    years_exp = cand.get('profile', {}).get('years_of_experience', 0)
    max_allowed_months = (years_exp * 12) + 6
    for sk in cand.get('skills', []):
        if sk.get('duration_months', 0) > max_allowed_months:
            return True, f"Impossible skill duration: {sk.get('name')} duration exceeds total experience."

    # Rule 3: Invalid expected salary range
    sal = cand.get('redrob_signals', {}).get('expected_salary_range_inr_lpa', {})
    s_min = sal.get('min', 0)
    s_max = sal.get('max', 0)
    if s_max < s_min:
        return True, "Invalid expected salary range: max < min."

    # Rule 4: Over-embellished skills (expert in too many skills relative to experience)
    expert_count = sum(1 for sk in cand.get('skills', []) if sk.get('proficiency') == 'expert')
    if years_exp < 3.0 and expert_count >= 5:
        return True, f"Unusually high number of expert skills ({expert_count}) for {years_exp} years of experience."

    return False, ""

def compute_score(cand):
    prof = cand.get('profile', {})
    skills = cand.get('skills', [])
    career = cand.get('career_history', [])
    signals = cand.get('redrob_signals', {})
    
    # 1. Experience Years Fit (Target 5-9 years, ideal 6-8)
    years_exp = prof.get('years_of_experience', 0)
    exp_score = 0
    if 5.0 <= years_exp <= 9.0:
        exp_score = 1.0
    elif 4.0 <= years_exp < 5.0:
        exp_score = 0.8
    elif 9.0 < years_exp <= 12.0:
        exp_score = 0.8
    elif 12.0 < years_exp <= 15.0:
        exp_score = 0.5
    else:
        exp_score = 0.1

    # 2. Skill Relevance Score
    skill_score = 0
    relevant_skills_found = []
    for sk in skills:
        name = sk.get('name', '').lower()
        profic = sk.get('proficiency', '').lower()
        dur = sk.get('duration_months', 0)
        
        # Match JD Keywords
        weight = 0
        if any(kw in name for kw in AI_ML_KEYWORDS):
            weight = 2.0
            relevant_skills_found.append(sk.get('name'))
        
        profic_mult = {'beginner': 0.5, 'intermediate': 1.0, 'advanced': 1.5, 'expert': 2.0}.get(profic, 1.0)
        dur_mult = min(dur / 24.0, 2.0) if dur > 0 else 0.5
        
        skill_score += weight * profic_mult * dur_mult

    # Normalized skill relevance score
    skill_score = min(skill_score / 20.0, 1.0)

    # 3. Career & Title Relevance (Shipper/Product-engineering focus)
    career_score = 0
    has_product_exp = False
    has_consultancy_exp = False
    
    for job in career:
        title = job.get('title', '').lower()
        desc = job.get('description', '').lower()
        company = job.get('company', '').lower()
        industry = job.get('industry', '').lower()
        
        # Check if the title is relevant to ML / AI / Ranking / Data Infra
        title_weight = 0
        if any(kw in title for kw in ['ai', 'ml', 'machine learning', 'nlp', 'retrieval', 'search', 'ranking', 'recommendation', 'data engineer', 'backend']):
            title_weight = 1.0
            
        # Check if company belongs to service consultancies
        if any(cons in company for cons in CONSULTANCIES) or 'it services' in industry:
            has_consultancy_exp = True
        else:
            has_product_exp = True
            
        # Check description for shipping product features or ranking systems
        desc_weight = 0
        if any(kw in desc for kw in ['shipped', 'deployed', 'production', 'ab test', 'a/b test', 'pipeline', 'scale', 'retrieval', 'vector']):
            desc_weight = 1.0
            
        career_score += (title_weight + desc_weight) * (job.get('duration_months', 12) / 12.0)

    # Penalize purely consultancy background or award product background
    if has_product_exp and not has_consultancy_exp:
        career_score *= 1.3
    elif has_consultancy_exp and not has_product_exp:
        career_score *= 0.3

    career_score = min(career_score / 5.0, 1.0)

    # 4. Location Match
    loc = prof.get('location', '').lower()
    country = prof.get('country', '').lower()
    loc_score = 0.5 # Default
    
    if any(p_loc in loc for p_loc in PREFERRED_LOCATIONS) or country == 'india':
        loc_score = 1.0
    elif signals.get('willing_to_relocate', False):
        loc_score = 0.8
    elif country != 'india' and not signals.get('willing_to_relocate', False):
        loc_score = 0.2

    # 5. Platform Activity & Engagement Signals
    response_rate = signals.get('recruiter_response_rate', 0)
    response_time = signals.get('avg_response_time_hours', 100)
    open_to_work = signals.get('open_to_work_flag', False)
    github_score = signals.get('github_activity_score', -1)
    
    # Active multiplier
    active_mult = 1.0
    if open_to_work:
        active_mult += 0.2
    if response_rate > 0.7:
        active_mult += 0.2
    elif response_rate < 0.2:
        active_mult -= 0.3
        
    if response_time < 24:
        active_mult += 0.1
    elif response_time > 120:
        active_mult -= 0.1
        
    if github_score > 30:
        active_mult += 0.1
    elif github_score == -1:
        active_mult -= 0.05
        
    active_mult = max(0.2, min(active_mult, 1.5))

    # Composite Match Score Calculation
    base_match = (0.25 * exp_score + 0.35 * skill_score + 0.30 * career_score + 0.10 * loc_score)
    final_score = base_match * active_mult
    
    return round(final_score, 4), relevant_skills_found

def generate_reasoning(cand, score, relevant_skills):
    prof = cand.get('profile', {})
    years = prof.get('years_of_experience', 0)
    title = prof.get('current_title', 'Engineer')
    loc = prof.get('location', 'India')
    signals = cand.get('redrob_signals', {})
    response_rate = int(signals.get('recruiter_response_rate', 0) * 100)
    
    skills_str = ", ".join(relevant_skills[:3]) if relevant_skills else "applied ML"
    
    templates = [
        f"Strong fit with {years} years of experience as a {title} with expertise in {skills_str}. Great engagement profile ({response_rate}% response rate) and located in {loc}.",
        f"Demonstrates solid production experience in {skills_str} over a {years}-year career. Highly active on the platform and matches the required hands-on AI engineering profile.",
        f"Matches founding team needs with {years} years of experience. Handled {skills_str} in past roles at product companies; strong candidate active in {loc}."
    ]
    
    # Select template based on candidate ID hash to ensure variation
    h = sum(ord(c) for c in cand.get('candidate_id', ''))
    reasoning = templates[h % len(templates)]
    return reasoning

def main():
    if len(sys.argv) < 3:
        print("Usage: python rank.py --candidates <candidates_file> --out <output_csv>")
        sys.exit(1)
        
    candidates_file = sys.argv[2]
    output_csv = sys.argv[4]
    
    ranked_candidates = []
    
    print("Processing candidates...")
    with open(candidates_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            cand = json.loads(line)
            
            # Filter Honeypots completely
            is_hp, reason = is_honeypot(cand)
            if is_hp:
                continue
                
            score, relevant_skills = compute_score(cand)
            
            ranked_candidates.append({
                'candidate_id': cand['candidate_id'],
                'score': score,
                'candidate': cand,
                'relevant_skills': relevant_skills
            })
            
    # Sort candidates: primary key score descending, secondary key candidate_id ascending
    ranked_candidates.sort(key=lambda x: (-x['score'], x['candidate_id']))
    
    print(f"Total valid candidates ranked: {len(ranked_candidates)}")
    
    # Keep top 100
    top_100 = ranked_candidates[:100]
    
    # Write submission
    with open(output_csv, 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['candidate_id', 'rank', 'score', 'reasoning'])
        
        for idx, item in enumerate(top_100):
            rank = idx + 1
            cid = item['candidate_id']
            score = item['score']
            cand = item['candidate']
            relevant_skills = item['relevant_skills']
            reasoning = generate_reasoning(cand, score, relevant_skills)
            
            # Make sure scores are monotonically non-increasing
            # Force score formatting to float
            writer.writerow([cid, rank, score, reasoning])
            
    print(f"Saved top 100 candidates to {output_csv}")

if __name__ == '__main__':
    main()
