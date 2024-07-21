from sqlalchemy import Engine
from sqlalchemy.sql import text
import re

from src.db import utils

engine = utils.get_engine(
        url="sqlite:///data/sqlite/users.db"
    )
utils.LocalSession.configure(bind = engine)
session=utils.LocalSession()

def add_user(user_name :str, password :str, role :str):
    try:
        query = text("INSERT INTO sh_users VALUES (:user_name,:password,:role)")
        session.execute(query,{"user_name":user_name,"password":password,"role":role})
        session.commit()
    except Exception as e:
        print(e)
def get_all_users():
    try:
        result = utils.execute_select_statement(session=session,statement=f"SELECT user_name,password,role FROM sh_users;")
        return {i["user_name"]: {"password":i["password"],"role":i["role"]} for i in result }
    except Exception as e:
        print(e)
