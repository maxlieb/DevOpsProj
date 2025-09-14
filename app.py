from flask import Flask, jsonify, request, Response
import os, json, random, requests, socket
from datetime import datetime
from uuid import uuid4
from collections import OrderedDict

# ============== Config ==============
# Environment variables (can be overridden when running in Docker/K8s)
NTFY_BASE   = os.getenv("NTFY_BASE", "https://ntfy.sh").rstrip("/")   # base URL of ntfy server
NTFY_TOPIC  = os.getenv("NTFY_TOPIC", "dadjokes-api")                 # topic name for storing messages
NTFY_SINCE  = os.getenv("NTFY_SINCE", "72h")                          # how far back to fetch existing db
NTFY_AUTH   = os.getenv("NTFY_AUTH")                                  # optional Bearer token for ntfy
MAX_RECORDS = int(os.getenv("MAX_RECORDS", "30"))                     # max jokes stored in db

# Joke providers (no OAuth)
JOKES_PROVIDER = os.getenv("JOKES_PROVIDER", "icanhaz")               # icanhaz | jokeapi | official
JOKES_UA       = os.getenv("JOKES_UA", "dadjokes-app/1.0 (eks)")
JOKES_TIMEOUT  = int(os.getenv("JOKES_TIMEOUT", "8"))

DB_TITLE = "dadjokes-db"  # used as a marker to identify database messages in ntfy

app = Flask(__name__)

# ============== Small helpers ==============
now_iso = lambda: datetime.utcnow().isoformat(timespec="seconds") + "Z"  # UTC timestamp in ISO format
pod_name = lambda: socket.gethostname()  # current container/pod hostname

# Build ntfy headers (add auth if needed)
def ntfy_headers(content_type="application/json"):
    h = {"Content-Type": content_type, "Title": DB_TITLE}
    if NTFY_AUTH:
        h["Authorization"] = f"Bearer {NTFY_AUTH}"
    return h

# Helper: build topic URL with optional suffix
def topic_url(suffix=""):
    return f"{NTFY_BASE}/{NTFY_TOPIC}{suffix}"

# Return an empty DB structure
def empty_db():
    return {"version": 0, "updated_at": now_iso(), "items": []}

# Keep only the latest "max_records" items
def prune(items, max_records=MAX_RECORDS):
    items = sorted(items, key=lambda x: x.get("created_at",""), reverse=True)
    return items[:max_records]

# Save database to ntfy topic (publishes as JSON)
def save_db(db):
    db["version"] = int(db.get("version", 0)) + 1
    db["updated_at"] = now_iso()
    db["items"] = prune(db.get("items", []))
    r = requests.post(topic_url(), headers=ntfy_headers(), data=json.dumps(db), timeout=10)
    r.raise_for_status()
    return db

# Load latest db from ntfy topic
def load_db():
    headers = {"Authorization": f"Bearer {NTFY_AUTH}"} if NTFY_AUTH else {}
    r = requests.get(topic_url("/json") + f"?poll=1&since={NTFY_SINCE}", headers=headers, timeout=15, stream=True)
    r.raise_for_status()
    latest = None
    # Stream messages until we find the latest DB entry
    for line in r.iter_lines(decode_unicode=True):
        if not line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if evt.get("event") == "message" and evt.get("title") == DB_TITLE:
            try:
                latest = json.loads(evt.get("message", "{}"))
            except Exception:
                pass
    # Fallback to empty DB if nothing found
    if not latest or not isinstance(latest, dict) or "items" not in latest:
        latest = empty_db()
    if not isinstance(latest.get("items"), list):
        latest["items"] = []
    return latest

# Create a new joke item (OrderedDict for stable field order)
def make_item(title, body, source, created_at=None):
    return OrderedDict([
        ("title", title or "No title"),
        ("body", body or ""),
        ("source", source),
        ("pod_name", pod_name()),
        ("created_at", created_at or now_iso()),
        ("id", str(uuid4())),
    ])

# ============== External joke providers (no OAuth) ==============

def fetch_one_joke_icanhaz():
    """Primary: icanhazdadjoke.com (simple, stable)."""
    r = requests.get(
        "https://icanhazdadjoke.com/",
        headers={"Accept": "application/json", "User-Agent": JOKES_UA},
        timeout=JOKES_TIMEOUT,
    )
    r.raise_for_status()
    j = r.json()
    title = "Dad joke"
    body = j.get("joke", "").strip()
    if not body:
        raise RuntimeError("icanhazdadjoke returned empty")
    return title, body

def fetch_one_joke_jokeapi():
    """Fallback 1: JokeAPI (Sv443)."""
    r = requests.get(
        "https://v2.jokeapi.dev/joke/Programming,Pun?type=single&blacklistFlags=nsfw,sexist,explicit",
        headers={"User-Agent": JOKES_UA},
        timeout=JOKES_TIMEOUT,
    )
    r.raise_for_status()
    j = r.json()
    if j.get("type") == "single":
        return "JokeAPI", j.get("joke", "").strip()
    # two-part fallback
    return "JokeAPI", f'{j.get("setup","").strip()} {j.get("delivery","").strip()}'.strip()

def fetch_one_joke_official():
    """Fallback 2: Official Joke API."""
    r = requests.get("https://official-joke-api.appspot.com/jokes/random", timeout=JOKES_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    return j.get("setup","Joke").strip(), j.get("punchline","").strip()

def fetch_one_joke():
    """
    Unified wrapper used by the app.
    Tries the configured provider, then fallbacks (icanhaz -> jokeapi -> official).
    """
    providers = {
        "icanhaz": fetch_one_joke_icanhaz,
        "jokeapi": fetch_one_joke_jokeapi,
        "official": fetch_one_joke_official,
    }
    order = [JOKES_PROVIDER, "icanhaz", "jokeapi", "official"]
    tried = set()
    for name in order:
        fn = providers.get(name)
        if not fn or name in tried:
            continue
        tried.add(name)
        try:
            return fn()
        except Exception:
            pass
    # If all failed:
    return "No jokes right now", ""

# ============== Routes ==============
# Healthcheck endpoint
@app.get("/health")
def health():
    return jsonify({"ok": True, "topic": NTFY_TOPIC}), 200

# GET / ? Fetch a new joke from providers and store it
@app.get("/")
def external_and_store():
    try:
        title, body = fetch_one_joke()
        db = load_db()
        db["items"].insert(0, make_item(title, body, "external"))
        save_db(db)
        return Response(json.dumps(db["items"][0], indent=2), mimetype="application/json"), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# POST /jokes ? Add custom joke
def add_custom():
    d = request.get_json(silent=True) or {}
    if not d.get("title") or not d.get("body"):
        return jsonify({"error": "title and body are required"}), 400
    db = load_db()
    item = make_item(d["title"], d["body"], "custom")
    db["items"].insert(0, item)
    save_db(db)
    return Response(json.dumps(item, indent=2), mimetype="application/json"), 201

app.add_url_rule("/jokes", view_func=add_custom, methods=["POST"])

# GET /jokes ? List jokes (optionally filter by date range)
@app.get("/jokes")
def list_jokes():
    frm = request.args.get("from")
    to  = request.args.get("to")
    db = load_db()
    items = db.get("items", [])
    if frm: items = [x for x in items if x.get("created_at","") >= frm]
    if to:  items = [x for x in items if x.get("created_at","") <= to]
    return Response(json.dumps(prune(items), indent=2), mimetype="application/json"), 200

# GET /jokes/<id> ? Get joke by ID
@app.get("/jokes/<id_>")
def get_by_id(id_):
    db = load_db()
    for x in db.get("items", []):
        if x.get("id") == id_:
            return Response(json.dumps(x, indent=2), mimetype="application/json"), 200
    return jsonify({"error": "not found"}), 404

# DELETE /jokes/<id> ? Delete joke by ID
@app.delete("/jokes/<id_>")
def delete_by_id(id_):
    db = load_db()
    n_before = len(db["items"])
    db["items"] = [x for x in db.get("items", []) if x.get("id") != id_]
    if len(db["items"]) == n_before:
        return jsonify({"error": "not found"}), 404
    save_db(db)
    return jsonify({"status": "deleted", "id": id_}), 200

# PUT /jokes/<id> ? Update existing joke (replace or update fields)
@app.put("/jokes/<id_>")
def update_joke(id_):
    d = request.get_json(silent=True) or {}
    db = load_db()
    i = next((idx for idx, x in enumerate(db.get("items", [])) if x.get("id") == id_), -1)
    if i == -1:
        return jsonify({"error": "not found"}), 404

    x = db["items"][i]
    if d.get("reddit"):
        # Backward-compatible flag: fetch a fresh external joke (no Reddit).
        title, body = fetch_one_joke()
        x.update({"title": title, "body": body, "source": "external"})
    else:
        # Update with custom values
        if not ("title" in d or "body" in d):
            return jsonify({"error": "provide title/body or set reddit=true"}), 400
        if "title" in d and d["title"] is not None:
            x["title"] = d["title"]
        if "body" in d and d["body"] is not None:
            x["body"]  = d["body"]
        x["source"] = "custom"

    # Always refresh pod name and timestamp
    x["pod_name"] = pod_name()
    x["created_at"] = now_iso()
    db["items"][i] = x
    save_db(db)
    return Response(json.dumps(x, indent=2), mimetype="application/json"), 200

# POST /reset ? Reset the DB (clears all jokes)
@app.post("/reset")
def reset_db():
    db = empty_db()
    save_db(db)
    return jsonify({"status": "reset", "items": 0}), 200

# Run server (Flask)
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
