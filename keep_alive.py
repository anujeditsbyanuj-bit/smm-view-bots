"""
Keep-alive Flask server.
Replit aur Render dono pe bot ko alive rakhta hai.
UptimeRobot se ping karo — bot kabhi nahi soyega.
"""

from flask import Flask
from threading import Thread

app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>✅ Views Bot is Running!</h1><p>Bot is alive and working.</p>"

@app.route('/health')
def health():
    return {"status": "ok", "bot": "running"}, 200

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()
