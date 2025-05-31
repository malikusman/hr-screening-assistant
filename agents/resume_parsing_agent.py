from flask import Flask, jsonify, request
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
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
    temperature=0.3  # Lower temperature for structured output
)

# Define prompt for resume parsing
prompt = PromptTemplate(
    input_variables=["resume"],
    template="""
    Parse the following resume and extract the following fields in JSON format:
    - name
    - skills (list of strings)
    - experience_years (integer)
    - education (string)
    Resume: {resume}
    Return only the JSON object, no additional text.
    """
)
chain = prompt | llm

# A2A Agent Card
@app.route("/.well-known/agent.json")
def agent_card():
    return jsonify({
        "agent_id": "resume-parsing-agent",
        "endpoint": "http://localhost:8001/resume",
        "capabilities": ["resume_parsing", "data_extraction"],
        "authentication": "none",  # Simplified for POC
        "input_formats": ["json"],
        "output_formats": ["json"],
        "description": "Parses resumes to extract structured data (name, skills, experience, education)."
    })

# A2A Parse Endpoint
@app.route("/resume", methods=["POST"])
def parse_resume():
    task = request.json
    if not task or "data" not in task or "resume" not in task["data"]:
        return jsonify({"error": "Invalid task format, 'data.resume' required"}), 400

    try:
        resume = task["data"]["resume"]
        # Convert resume dict to string
        # for LLM
        resume_str = json.dumps(resume)
        # Run LangChain to parse resume
        result = chain.invoke({"resume": resume_str})
        # Parse LLM output (expecting JSON)
        parsed_data = json.loads(result.content)
        return jsonify({
            "task_id": task.get("task_id"),
            "result": parsed_data
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=True)  # Use port 8001 to avoid conflict with Host Agent