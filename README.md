# Redrob Candidate Ranker - Team Idea Architects

This repository contains the candidate ranking engine developed by **Team Idea Architects** for the Intelligent Candidate Discovery & Ranking Challenge.

The solution ranks a pool of 100,000 candidates for a founding **Senior AI Engineer** role at Redrob, running fully on CPU in under 20 seconds.

## Project Structure
* `rank.py`: Core ranking script including honeypot filtration and candidate scoring.
* `team_antigravity.csv`: Top 100 ranked candidates matching the JD.
* `submission_metadata.yaml`: Team details and submission declarations.
* `requirements.txt`: Python dependencies.

## Setup and Reproduction

### Prerequisites
* Python 3.8+ (tested on Python 3.11)

### Installation
Clone this repository and run:
```bash
pip install -r requirements.txt
```

### Run Ranking Code
To run the ranker and generate the submission CSV:
```bash
python rank.py --candidates ./candidates.jsonl --out ./team_antigravity.csv
```

## Methodology

### 1. Trap / Honeypot Filtration
We filter out synthetically generated honeypots using three deterministic checks before performing scoring:
* **Duplicate Career Descriptions**: Candidates with identical job descriptions in their `career_history`.
* **Impossible Skill Duration**: Skill usage durations (`duration_months`) exceeding the candidate's total professional experience.
* **Invalid Salary Range**: Stated expectations where `max < min`.

### 2. Candidate Matching & Relevance
Remaining candidates are scored dynamically on:
* **Experience Fit**: Prioritizes 5–9 years of experience.
* **Skill Match**: Assigns weights to AI, ML, NLP, embeddings, RAG, and vector search skills.
* **Product vs. Consultancy**: Awards a multiplier for product company backgrounds while penalizing pure-service consultancy histories.
* **Location Fit**: Favors Pune, Noida, Bangalore, or candidates willing to relocate to India.
* **Engagement Signals**: Weighs recruiter response rate, response speed, open-to-work flags, and platform activity.
