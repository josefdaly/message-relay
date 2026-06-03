from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import redis
import os
import uuid

app = Flask(__name__)
CORS(app)
r = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=6379, decode_responses=True)


def _queue_key(queue_id):
    return f"queue:{queue_id}"


@app.route("/health")
def health():
    r.ping()
    return {"status": "ok"}


@app.route("/queue", methods=["POST"])
def create_queue():
    queue_id = str(uuid.uuid4())
    sender_id = str(uuid.uuid4())
    recipient_id = str(uuid.uuid4())

    r.set(f"sender:{sender_id}", queue_id)
    r.set(f"recipient:{recipient_id}", queue_id)

    return jsonify({"sender_id": sender_id, "recipient_id": recipient_id}), 201


@app.route("/send/<sender_id>", methods=["POST"])
def send_message(sender_id):
    queue_id = r.get(f"sender:{sender_id}")
    if not queue_id:
        return jsonify({"error": "invalid sender_id"}), 404

    body = request.get_json(silent=True)
    if not body or "message" not in body:
        return jsonify({"error": "missing message field"}), 400

    r.rpush(_queue_key(queue_id), body["message"])
    return jsonify({"status": "sent"}), 200


@app.route("/receive/<recipient_id>", methods=["GET"])
def receive_message(recipient_id):
    queue_id = r.get(f"recipient:{recipient_id}")
    if not queue_id:
        return jsonify({"error": "invalid recipient_id"}), 404

    message = r.lpop(_queue_key(queue_id))
    return jsonify({"message": message}), 200


@app.route("/receive/<recipient_id>/drain", methods=["GET"])
def drain_messages(recipient_id):
    queue_id = r.get(f"recipient:{recipient_id}")
    if not queue_id:
        return jsonify({"error": "invalid recipient_id"}), 404

    messages = []
    while True:
        msg = r.lpop(_queue_key(queue_id))
        if msg is None:
            break
        messages.append(msg)

    return jsonify({"messages": messages}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
