from sqlalchemy import Engine
from sqlalchemy.sql import text
import re

from src.db import utils

engine = utils.get_engine(
        url="sqlite:///data/sqlite/shopify_links.db"
    )
utils.LocalSession.configure(bind = engine)
session=utils.LocalSession()

def select_link_by_type (type = None):
    
    condition = f"where link_type = '{type}'" if type != None else ""
    result = utils.execute_select_statement(session=session,statement=f"SELECT link,link_type FROM sh_links {condition};")
    return result

def insert_link(link:str,type: str):
    try:
        pattern =r'^[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
        if re.match(pattern,link) and (type != None or type != ""):
            query = text("INSERT INTO sh_links VALUES (:link,:type)")
            session.execute(query,{"link":link,"type":type})
            session.commit()

            return "Insert success"
        else:
            print("You not enter link")
            return "You not enter link"
    except Exception:
        return "Have some trouble when insert link"

def remove_link(link: str):
    if link != None:
        query = text('DELETE FROM sh_links WHERE link = :link')
        session.execute(query,{'link':link})
        session.commit()
        return "Delete link success"
    else:
        return "not selected link"
