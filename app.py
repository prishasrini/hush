from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from database import get_db, init_db
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.secret_key = "hush-secret-key"
init_db()

# ---------- AUTH HELPER ----------

def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated

# ---------- AUTH ROUTES ----------

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

        # log them in — store their anonymous ID in session
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

        # generate anonymous ID — this is what we use for all data
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

        # log them in immediately
        session["user_id"] = anon_id
        session["username"] = username
        return redirect(url_for("dashboard"))

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ---------- PROTECTED ROUTES ----------

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

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
    user_id = session.get("user_id")
    data = request.get_json()
    messages = data.get("messages", [])

    conn = get_db()
    if messages:
        last = messages[-1]
        conn.execute(
            "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
            (user_id, last["role"], last["content"])
        )
        conn.commit()
    conn.close()

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
Respond with warmth first, then gently say: "please reach out to iCall right now — 9152987821. they're free, confidential, and made for students. i'm right here too 🤍"

You are NOT a therapist. You are the safe first step.
Respond in the same language the user writes or speaks in."""

    clean_messages = []
    for m in messages:
        if m.get("role") in ["user", "assistant"] and m.get("content"):
            clean_messages.append({
                "role": m["role"],
                "content": str(m["content"])
            })

    payload = json.dumps({
        "model": "openrouter/free",
        "messages": [
            {"role": "system", "content": system_prompt}
        ] + clean_messages
    }).encode("utf-8")

    import os
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

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            reply = result["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print("API ERROR DETAIL:", error_body)
        reply = "i'm here with you. i had a little trouble connecting just now — can you say that again? 🤍"
    except Exception as e:
        print("API ERROR:", str(e))
        reply = "i'm here with you. i had a little trouble connecting just now — can you say that again? 🤍"

    return jsonify({"reply": reply})

@app.route("/sos")
@login_required
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
        "SELECT user_id, content, created_at FROM room_messages WHERE room = ? ORDER BY created_at ASC LIMIT 100",
        (room_name,)
    ).fetchall()
    conn.close()
    return jsonify([dict(m) for m in messages])

@app.route("/api/rooms/<room_name>/send", methods=["POST"])
@login_required
def send_room_message(room_name):
    user_id = session.get("user_id")
    data = request.get_json()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "empty"}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO room_messages (room, user_id, content) VALUES (?, ?, ?)",
        (room_name, user_id, content)
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "sent"})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)