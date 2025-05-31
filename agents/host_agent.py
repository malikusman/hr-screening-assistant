from flask import Flask, jsonify, request, Response, send_from_directory
from langgraph.graph import StateGraph, END
from typing import Dict, List, Any
import requests
import json
import os
from dotenv import load_dotenv
import time

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='../static')

# Define state for LangGraph
class WorkflowState(Dict):
    resumes: List[Dict]
    parsed_resumes: List[Dict]
    ranked_candidates: List[Dict]
    schedules: List[Dict]
    job_title: str
    status: str

# Define nodes for LangGraph
def parse_resumes(state: WorkflowState) -> WorkflowState:
    state["status"] = "Parsing resumes..."
    parsed_resumes = []
    for resume in state["resumes"]:
        try:
            response = requests.post(
                "http://localhost:8001/resume",
                json={"task_id": f"parse_{resume['id']}", "data": {"resume": resume}},
                timeout=10
            )
            if response.status_code == 200:
                try:
                    result = response.json()
                    parsed_resumes.append(result["result"])
                except json.JSONDecodeError as e:
                    print(f"JSON decode error for resume {resume['id']}: {e}, Response: {response.text}")
                except KeyError as e:
                    print(f"Key error for resume {resume['id']}: {e}, Response: {result}")
            else:
                print(f"Parse error for resume {resume['id']}: Status {response.status_code}, Response: {response.text}")
        except requests.RequestException as e:
            print(f"Request error for resume {resume['id']}: {e}")
    state["parsed_resumes"] = parsed_resumes
    return state

def match_candidates(state: WorkflowState) -> WorkflowState:
    state["status"] = "Matching candidates..."
    response = requests.post(
        "http://localhost:8002/match",
        json={
            "task_id": "match_1",
            "data": {"candidates": state["parsed_resumes"]}
        }
    )
    if response.status_code == 200:
        state["ranked_candidates"] = response.json()["result"]["ranked_candidates"]
    else:
        print(f"Match error: {response.json()}")
    return state

def schedule_interviews(state: WorkflowState) -> WorkflowState:
    state["status"] = "Scheduling interviews..."
    response = requests.post(
        "http://localhost:8004/schedule",
        json={
            "task_id": "schedule_1",
            "data": {
                "job_title": state["job_title"],
                "ranked_candidates": state["ranked_candidates"]
            }
        }
    )
    if response.status_code == 200:
        state["schedules"] = response.json()["result"]["schedules"]
    else:
        print(f"Schedule error: {response.json()}")
    return state

# Define LangGraph workflow
workflow = StateGraph(WorkflowState)
workflow.add_node("parse", parse_resumes)
workflow.add_node("match", match_candidates)
workflow.add_node("schedule", schedule_interviews)
workflow.add_edge("parse", "match")
workflow.add_edge("match", "schedule")
workflow.add_edge("schedule", END)
workflow.set_entry_point("parse")
app_graph = workflow.compile()

# Serve frontend - fix the path here too
@app.route('/')
def serve_frontend():
    return send_from_directory('../static', 'index.html')

# A2A Agent Card
@app.route("/.well-known")
def agent_card():
    return jsonify({
        "agent_id": "host-agent",
        "endpoint": "http://localhost:8080/task",
        "capabilities": ["coordinate_screening", "task_delegation"],
        "authentication": "none",
        "input_formats": ["json"],
        "output_formats": ["json"],
        "description": "Coordinates resume screening tasks among agents."
    })

# SSE for real-time updates
@app.route('/events')
def events():
    def stream():
        state = {"status": "Waiting for task..."}
        while True:
            yield f"data: {state['status']}\n\n"
            time.sleep(1)
            # Update status if workflow is running
            if hasattr(app, 'current_state'):
                state = app.current_state
    return Response(stream(), mimetype='text/event-stream')

# A2A Task Endpoint
@app.route("/task", methods=["POST"])
def run_workflow():
    task = request.json
    if not task or "data" not in task or "resumes" not in task["data"] or "job_title" not in task["data"]:
        return jsonify({"error": "Invalid task format, 'data.resumes' and 'data.job_title' required"}), 400

    try:
        initial_state = {
            "resumes": task["data"]["resumes"],
            "job_title": task["data"]["job_title"],
            "parsed_resumes": [],
            "ranked_candidates": [],
            "schedules": [],
            "status": "Starting workflow..."
        }
        app.current_state = initial_state
        result = app_graph.invoke(initial_state)
        app.current_state = {"status": "Workflow complete."}
        return jsonify({
            "task_id": task.get("task_id"),
            "result": {"schedules": result["schedules"]}
        })
    except Exception as e:
        print(f"Workflow error: {str(e)}")
        app.current_state = {"status": f"Error: {str(e)}"}
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)