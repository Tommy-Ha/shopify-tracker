from flask import Flask
from src.auth.auth import requires_auth,requires_role

server = Flask(__name__)

@server.route("/users")
@requires_auth
@requires_role("admin")
def admin_page():
    return "welcome admin page!"