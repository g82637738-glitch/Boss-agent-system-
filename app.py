from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os

load_dotenv()
from boss_agent import chat_with_model, research_agent
import state
from agents.task_agent import get_all_tasks

app = Flask(__name__, static_folder='static')

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/dashboard')
def dashboard():
    return send_from_directory('static', 'dashboard.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'missing message'}), 400
    try:
        reply = chat_with_model(message)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/research', methods=['POST'])
def research():
    data = request.get_json() or {}
    message = data.get('message', '')
    if not message:
        return jsonify({'error': 'missing message'}), 400
    try:
        reply = research_agent(message)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = request.host_url.rstrip('/')
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

@app.route('/approval/status', methods=['GET'])
def approval_status():
    if not state.pending_approval:
        return jsonify({'pending': False})
    return jsonify({
        'pending': state.pending_approval.get('status') == 'waiting',
        'id': state.pending_approval.get('id'),
        'action': state.pending_approval.get('action'),
        'reason': state.pending_approval.get('reason'),
    })

@app.route('/approval/respond', methods=['POST'])
def approval_respond():
    data = request.get_json() or {}
    uid = data.get('id')
    decision = data.get('decision')
    if not uid or decision not in ('approved', 'rejected'):
        return jsonify({'error': 'invalid request'}), 400
    if not state.pending_approval or state.pending_approval.get('id') != uid:
        return jsonify({'error': 'no matching approval request'}), 404
    state.pending_approval['status'] = decision
    return jsonify({'ok': True})

@app.route('/notifications', methods=['GET'])
def get_notifications():
    return jsonify({'messages': list(state.notifications)})

@app.route('/api/tasks', methods=['GET'])
def api_tasks():
    try:
        tasks = get_all_tasks()
        return jsonify({'tasks': tasks})
    except Exception as e:
        return jsonify({'error': str(e), 'tasks': []}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"Server is starting on http://127.0.0.1:{port}")
    print(f"If running in Codespaces, forward port {port} and set visibility to Public.")
    app.run(host='0.0.0.0', port=port)
