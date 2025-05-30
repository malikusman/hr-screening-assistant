import json
with open('data/resumes.json', 'r') as f:
    resumes = json.load(f)
with open('data/job_description.json', 'r') as f:
    job = json.load(f)
print(f"Loaded {len(resumes)} resumes and job: {job['title']}")