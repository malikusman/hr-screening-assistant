from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/.well-known/agent.json")
def agent_card():
    return jsonify({
        "agent_id": "host-agent",
        "endpoint": "http://localhost:5000/task",
        "capabilities": ["coordinate_screening", "task_delegation"],
        "authentication": "none",  # Simplified for POC
        "input_formats": ["json"],
        "output_formats": ["json"],
        "description": "Coordinates resume screening tasks among agents."
    })

@app.route("/task", methods=["POST"])
def task_endpoint():
    return jsonify({"status": "Task received, not implemented yet"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)