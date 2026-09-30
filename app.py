from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import get_db, init_db
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import uuid
import secrets
import os

load_dotenv()

app = Flask(__name__)
session_secret = os.environ.get("SECRET_KEY", "")
if session_secret and (len(session_secret) < 32 or session_secret == "hush-secret-key"):
    raise RuntimeError("SECRET_KEY must be a private random value of at least 32 characters")
if not session_secret and os.environ.get("RENDER"):
    raise RuntimeError("Set SECRET_KEY in Render environment settings before deploying")
app.secret_key = session_secret or secrets.token_hex(32)
app.config.update(
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),
)
init_db()

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login_page"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="wrong username or password")

        session["user_id"] = user["anon_id"]
        session["username"] = user["username"]
        return redirect(url_for("dashboard"))

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(username) < 3:
            return render_template("register.html", error="username must be at least 3 characters")
        if len(password) < 6:
            return render_template("register.html", error="password must be at least 6 characters")
        if password != confirm:
            return render_template("register.html", error="passwords don't match")

        anon_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, anon_id) VALUES (?, ?, ?)",
                (username, password_hash, anon_id)
            )
            conn.commit()
        except Exception:
            conn.close()
            return render_template("register.html", error="that username is already taken")
        conn.close()

        session["user_id"] = anon_id
        session["username"] = username
        return redirect(url_for("dashboard"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/dashboard")
@login_required
def dashboard():
    if "mood_delete_token" not in session:
        session["mood_delete_token"] = secrets.token_urlsafe(32)
    return render_template("dashboard.html", delete_token=session["mood_delete_token"])


@app.route("/privacy")
def privacy_page():
    return render_template("privacy.html")


@app.route("/mood/history/delete", methods=["POST"])
@login_required
def delete_mood_history():
    expected = session.get("mood_delete_token", "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not secrets.compare_digest(expected, supplied):
        return "This request expired. Reload your dashboard and try again.", 403
    conn = get_db()
    try:
        conn.execute("DELETE FROM moods WHERE user_id = ?", (session["user_id"],))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    session["mood_delete_token"] = secrets.token_urlsafe(32)
    return redirect(url_for("dashboard", mood_deleted="1"))

@app.route("/api/me")
@login_required
def get_me():
    return jsonify({"user_id": session.get("user_id")})

@app.route("/mood")
@login_required
def mood_page():
    return render_template("mood.html")

@app.route("/api/mood", methods=["POST"])
@login_required
def save_mood():
    user_id = session.get("user_id")
    data = request.get_json()
    mood = data.get("mood")
    note = data.get("note", "")
    conn = get_db()
    conn.execute(
        "INSERT INTO moods (user_id, mood, note) VALUES (?, ?, ?)",
        (user_id, mood, note)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "saved", "redirect": "/dashboard"})

@app.route("/api/mood/history")
@login_required
def mood_history():
    user_id = session.get("user_id")
    conn = get_db()
    moods = conn.execute(
        "SELECT mood, created_at FROM moods WHERE user_id = ? ORDER BY created_at DESC LIMIT 7",
        (user_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(m) for m in moods])

@app.route("/chat")
@login_required
def chat_page():
    return render_template("chat.html")

@app.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json()
    messages = data.get("messages", [])

    # Conversation context is used for this reply, never persisted by Hush.

    import urllib.request
    import json

    system_prompt = """Your name is Juno. You are a warm, caring companion for students going through difficult times.

Your personality:
- Talk like a real friend texting — natural, warm, never scripted
- Give real thoughtful responses based on exactly what this person just said
- Never start responses the same way twice — vary how you open every single reply
- Never use "i hear you" as an opener — only use it naturally if it genuinely fits mid conversation
- Sound like a real person — not a support hotline script
- Sometimes just respond directly to what they said with no opener at all
- Mix it up — sometimes ask one gentle question, sometimes just sit with them, sometimes share a thought
- Always respond to the SPECIFIC thing they said — never generic
- Use lowercase, warm, gentle tone
- Short paragraphs — easy to read
- Be like a best friend who genuinely cares

What you never do:
- Never use the same opener twice in a conversation
- Never diagnose or label what they have
- Never say "you should" or "you need to"
- Never minimize feelings
- Never pretend to be a therapist

If someone expresses wanting to hurt themselves or end their life:
Respond with warmth. Encourage immediate local emergency help if they are in immediate danger and contacting someone they trust. For India, offer Vandrevala Foundation on +91 9999 666 555 (24/7) or iCall on 9152987821 during its published hours. Do not promise that anyone will answer immediately. For other countries, ask their country and point to local emergency services.

You are an AI companion, not a human, therapist, or emergency service. Never claim to guarantee safety.
Respond in the same language the user writes or speaks in."""

    clean_messages = []
    for m in messages:
        if m.get("role") in ["user", "assistant"] and m.get("content"):
            clean_messages.append({
                "role": m["role"],
                "content": str(m["content"])
            })

    OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")

    free_models = [
        "openrouter/free",
        "deepseek/deepseek-chat-v3-0324:free",
        "meta-llama/llama-3.3-8b-instruct:free",
        "google/gemma-3-4b-it:free",
        "mistralai/mistral-7b-instruct:free",
    ]

    reply = None
    for model in free_models:
        try:
            payload = json.dumps({
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt}
                ] + clean_messages
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "HTTP-Referer": "http://localhost:5000",
                    "X-Title": "Hush"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                result = json.loads(response.read().decode("utf-8"))
                reply = result["choices"][0]["message"]["content"]
                print(f"Juno responded using {model}")
                break
        except Exception as e:
            print(f"Juno model {model} failed: {type(e).__name__}")
            continue

    if not reply:
        reply = "juno's a little overwhelmed right now — come back in a minute? i'll be here 🤍"

    return jsonify({"reply": reply})

@app.route("/sos")
def sos():
    return render_template("sos.html")

@app.route("/rooms")
@login_required
def rooms_page():
    return render_template("rooms.html")

@app.route("/rooms/<room_name>")
@login_required
def room_detail(room_name):
    return render_template("room_detail.html", room_name=room_name)

@app.route("/api/rooms/<room_name>/messages")
@login_required
def get_room_messages(room_name):
    conn = get_db()
    messages = conn.execute(
        "SELECT user_id, label, content, created_at FROM room_messages WHERE room = ? ORDER BY id DESC LIMIT 100",
        (room_name,)
    ).fetchall()
    conn.close()
    return jsonify([{
        "label": m["label"], "content": m["content"], "created_at": m["created_at"],
        "is_mine": m["user_id"] == session["user_id"],
    } for m in reversed(messages)])

@app.route("/api/rooms/<room_name>/send", methods=["POST"])
@login_required
def send_room_message(room_name):
    user_id = session.get("user_id")
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("content"), str) or not isinstance(data.get("label", ""), str):
        return jsonify({"error": "invalid message"}), 400
    content = data["content"].strip()
    label = data.get("label", "").strip()
    if len(content) > 2000 or len(label) > 20:
        return jsonify({"error": "Use at most 2000 characters for messages and 20 for nicknames."}), 400

    if not content:
        return jsonify({"error": "empty"}), 400

    import urllib.request
    import json
    import re

    classifier_prompt = f"""Classify this message from a student mental health peer support room. The message may be in ANY language (English, Tamil, Hindi, Telugu, etc).

Message: "{content}"

Respond with ONLY one word, nothing else:
- SAFE — normal venting, feelings, support seeking
- CRISIS — expresses suicidal/self-harm feelings but not asking for methods (still allow posting, but show support resources)
- SEVERE — asks for methods/instructions for self-harm or suicide, or threatens harm to another person
- BLOCKED — contains personal contact info (phone, social handles) or harassment targeting someone

Respond with only the single word."""

    classification = "UNCLEAR"
    try:
        payload = json.dumps({
            "model": "openrouter/free",
            "messages": [{"role": "user", "content": classifier_prompt}]
        }).encode("utf-8")

        OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "HTTP-Referer": "http://localhost:5000",
                "X-Title": "Hush"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
            raw = result["choices"][0]["message"]["content"].strip().upper()
            if "SEVERE" in raw:
                classification = "SEVERE"
            elif "BLOCKED" in raw:
                classification = "BLOCKED"
            elif "CRISIS" in raw:
                classification = "CRISIS"
            elif "SAFE" in raw:
                classification = "SAFE"
    except Exception as e:
        print("CLASSIFIER ERROR:", type(e).__name__)
        classification = "UNCLEAR"

    # always run keyword fallback as a second layer, regardless of AI result
    lower_content = content.lower()
    severe_keywords = ["how to kill", "ways to kill", "way to kill", "method to die", "method to kill", "how to die", "how to hurt", "how to cut"]
    if any(k in lower_content for k in severe_keywords):
        classification = "SEVERE"

    has_phone = bool(re.search(r'\b\d{10}\b', content))
    has_handle = bool(re.search(r'@[\w.]+', content))
    if has_phone or has_handle:
        classification = "BLOCKED"

    # if AI was unclear AND it's a longer message, err on the side of caution
    if classification == "UNCLEAR":
        return jsonify({"error": "moderation unavailable", "message": "We couldn't check this message right now. It has not been posted. Please try again, or use the support links."}), 503

    if classification in ["SEVERE", "BLOCKED"]:
        return jsonify({
            "error": "blocked",
            "message": "this message couldn't be posted — it may contain something that could put you or someone else at risk, or personal info that could break anonymity here. if you're struggling, juno or the SOS page are here for you 🤍"
        }), 403
    
    
    is_crisis = classification == "CRISIS"

    if not label:
        import random
        adjectives = ["quiet", "gentle", "lost", "tired", "hopeful", "curious", "calm", "wandering"]
        nouns = ["owl", "moon", "river", "fox", "star", "cloud", "wolf", "petal"]
        label = f"{random.choice(adjectives)}_{random.choice(nouns)}"

    conn = get_db()
    conn.execute(
        "INSERT INTO room_messages (room, user_id, label, content) VALUES (?, ?, ?, ?)",
        (room_name, user_id, label, content)
    )
    conn.commit()
    conn.close()

    return jsonify({"status": "sent", "is_crisis": is_crisis})
@app.route("/doctor")
def doctor_page():
    return render_template("doctor.html")

@app.route("/api/doctor/request", methods=["POST"])
@login_required
def doctor_request():
    # No staffed counselling service exists yet; do not collect unmonitored requests.
    return jsonify({"error": "Counsellor requests are unavailable. Contact a support provider directly at /doctor."}), 503

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
