from flask import Flask, jsonify, request
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from dotenv import load_dotenv
import os
import json
import re
from datetime import datetime, timedelta

# Load environment variables
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Initialize Flask app
app = Flask(__name__)

# Initialize LangChain with OpenAI
llm = ChatOpenAI(
    model_name="gpt-4o-mini",
    openai_api_key=openai_api_key,
    temperature=0.3  # Low temperature for structured output
)

# Define prompt for scheduling interviews
# Define prompt for scheduling interviews
prompt = PromptTemplate(
    input_variables=["candidates", "job_title", "start_date"],
    template="""
    You are an HR scheduling assistant for the job: {job_title}.
    Given the following ranked candidates with their match scores:
    {candidates}

    Suggest interview time slots for the top candidates (score >= 80) over the next 3 days, starting from {start_date} at 9 AM. Use 30-minute slots, avoiding overlaps. Return a JSON object with a list of schedules in this format:
    [
        {{"candidate_id": "<name>", "score": <int>, "interview_time": "YYYY-MM-DD HH:MM", "duration": "30 minutes"}},
        ...
    ]
    If no candidates have score >= 80, return an empty list.
    For each candidate, ensure the interview time is at least 1 hour apart from others.
    For each candidate, there will be only one interview slot.
    Only return the JSON object, no additional text or markdown formatting.
    """
)
chain = prompt | llm

def clean_json_response(response_text):
    """Clean LLM response to extract pure JSON"""
    # Remove markdown code blocks
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'```\s*$', '', cleaned)
    
    # Remove any leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned

# A2A Agent Card
@app.route("/.well-known/agent.json")
def agent_card():
    return jsonify({
        "agent_id": "scheduling-agent",
        "endpoint": "http://localhost:8004/schedule",
        "capabilities": ["interview_scheduling", "time_allocation"],
        "authentication": "none",  # Simplified for POC
        "input_formats": ["json"],
        "output_formats": ["json"],
        "description": "Generates interview schedules for ranked candidates."
    })

# A2A Schedule Endpoint
@app.route("/schedule", methods=["POST"])
def schedule_interviews():
    task = request.json
    if not task or "data" not in task or "ranked_candidates" not in task["data"] or "job_title" not in task["data"]:
        return jsonify({"error": "Invalid task format, 'data.ranked_candidates' and 'data.job_title' required"}), 400

    try:
        ranked_candidates = task["data"]["ranked_candidates"]
        job_title = task["data"]["job_title"]
        candidates_text = "\n".join(
            [f"{c['candidate_id']}: Score {c['score']}" for c in ranked_candidates]
        )
        # Calculate tomorrow's date
        start_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

        # Run LangChain to generate schedules
        result = chain.invoke({
            "candidates": candidates_text,
            "job_title": job_title,
            "start_date": start_date
        })
        
        # Clean the response before parsing
        cleaned_response = clean_json_response(result.content)
        print(f"Cleaned response: {cleaned_response}")  # Debug print
        
        try:
            schedules = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}, Raw response: {result.content}")
            print(f"Cleaned response: {cleaned_response}")
            return jsonify({"error": "Invalid LLM response format"}), 500

        return jsonify({
            "task_id": task.get("task_id"),
            "result": {"schedules": schedules}
        })
    except Exception as e:
        print(f"Error in schedule_interviews: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8004, debug=True)  # Use port 5003, debug=True for better errors