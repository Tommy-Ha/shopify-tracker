from flask import request, Response
from src.auth import user
USERS = user.get_all_users()
def check_auth(username, password):
    user = USERS.get(username)
    if user and user['password'] == password:
        return user
    return None

def authenticate():
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username,auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def requires_role(role):
    def decorator(f):
        def decorated_function(*args,**kwargs):
            auth = request.authorization
            user = check_auth(auth.username,auth.password)
            if not auth or user["role"] != role:
                return Response('401')
            return f(*args,**kwargs)
        return decorated_function
    return decorator