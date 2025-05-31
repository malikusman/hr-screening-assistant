from flask import Flask, jsonify, request
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize Flask app
app = Flask(__name__)

# Initialize LangChain with OpenAI
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    openai_api_key=openai_api_key,
    temperature=0.3
)
embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)

# Load job description for RAG
with open("data/job_description.json", "r") as f:
    job_description = json.load(f)
job_text = f"Job Title: {job_description['title']}\nSkills: {', '.join(job_description['required_skills'])}\nExperience: {job_description['min_experience_years']} years\nEducation: {job_description['education']}"

# Create FAISS index for job skills
job_skills = job_description["required_skills"]
job_index = FAISS.from_texts(job_skills, embeddings)

# Define RAG prompt for job requirement context
rag_prompt = PromptTemplate(
    input_variables=["job_text", "candidate"],
    template="""
    Given the job description: {job_text}
    
    Evaluate the candidate's qualifications: {candidate}
    
    Provide a match score from 0-100 based on skills, experience, and education alignment.
    
    You must respond with ONLY a valid JSON object in this exact format (no other text):
    {{"score": 85, "reason": "Strong Python skills match, adequate experience"}}
    """
)
rag_chain = rag_prompt | llm

# A2A Agent Card
@app.route("/.well-known/agent.json")
def agent_card():
    return jsonify({
        "agent_id": "matching-agent",
        "endpoint": "http://localhost:8002/match",
        "capabilities": ["candidate_matching", "skill_ranking"],
        "authentication": "none",
        "input_formats": ["json"],
        "output_formats": ["json"],
        "description": "Matches candidate resumes to job requirements using FAISS and RAG."
    })

# A2A Match Endpoint
@app.route("/match", methods=["POST"])
def match_candidates():
    task = request.json
    if not task or "data" not in task or "candidates" not in task["data"]:
        return jsonify({"error": "Invalid task format, 'data.candidates' required"}), 400

    try:
        candidates = task["data"]["candidates"]
        ranked_candidates = []

        for candidate in candidates:
            # FAISS: Match candidate skills to job skills
            candidate_skills = candidate.get("skills", [])
            skill_score = 0
            
            if candidate_skills:
                # Calculate average similarity score for all candidate skills
                total_score = 0
                for skill in candidate_skills:
                    # Use LangChain's similarity_search_with_score method
                    results = job_index.similarity_search_with_score(skill, k=1)
                    if results:
                        # FAISS returns distance (lower is better), convert to similarity score
                        distance = results[0][1]
                        # Convert distance to similarity score (0-100)
                        similarity = max(0, 100 - (distance * 100))
                        total_score += similarity
                
                # Average skill match score
                skill_score = int(total_score / len(candidate_skills)) if candidate_skills else 0
            else:
                skill_score = 0

            # RAG: Evaluate overall fit
            candidate_text = f"Name: {candidate['name']}\nSkills: {', '.join(candidate_skills)}\nExperience: {candidate['experience_years']} years\nEducation: {candidate['education']}"
            rag_result = rag_chain.invoke({"job_text": job_text, "candidate": candidate_text})
            
            # Debug: Print what LLM actually returned
            print(f"LLM Response for {candidate['name']}: {rag_result.content}")
            
            try:
                rag_data = json.loads(rag_result.content)
                rag_score = rag_data.get("score", 0)
                reason = rag_data.get("reason", "No reason provided")
            except json.JSONDecodeError as e:
                # Fallback if LLM doesn't return valid JSON
                print(f"JSON parse error for {candidate['name']}: {e}")
                print(f"Raw response: '{rag_result.content}'")
                rag_score = 50  # Default score
                reason = f"Unable to parse LLM response: {rag_result.content[:100]}..."

            # Combine scores (weighted average)
            final_score = int(0.7 * skill_score + 0.3 * rag_score)
            ranked_candidates.append({
                "candidate_id": candidate["name"],
                "score": final_score,
                "skill_score": skill_score,
                "rag_score": rag_score,
                "reason": reason
            })

        # Sort by score (descending)
        ranked_candidates.sort(key=lambda x: x["score"], reverse=True)

        return jsonify({
            "task_id": task.get("task_id"),
            "result": {"ranked_candidates": ranked_candidates}
        })
    except Exception as e:
        print(f"Error in match_candidates: {str(e)}")  # Debug print
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8002, debug=True)  # Added debug=True for better error messages