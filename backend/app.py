from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory log of requests
request_logs = []

@app.route("/", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
def catch_all():
    log_entry = {
        "method": request.method,
        "headers": dict(request.headers),
        "body": request.get_data(as_text=True),
    }
    request_logs.append(log_entry)
    print("\n--- [ Request Received at Backend ] ---")
    print(log_entry)
    print("----------------------------------------\n")
    return "OK", 200

@app.route("/_logs", methods=["GET"])
def get_logs():
    return jsonify(request_logs)

@app.route("/_clear_logs", methods=["POST"])
def clear_logs():
    request_logs.clear()
    return "Logs cleared", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)


