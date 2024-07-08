import json
import re
from src.config import settings

def get_all(type = None):
    f= open(settings.TRACKERS_CONFIG_FILEPATH)
    data=json.load(f)
    
    if type!=None and type == "link":
        return [i["url"] for i in data["trackers"]]
    elif type!=None and type == "parser":
        return list(set([i["parser"] for i in data["trackers"]]))
    else:
        return data

def add_link(link :str,parser :str):
    pattern =r'^(https?:\/\/)?(www\.)?([a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+)(\/[^\s]*)?$'
    if re.match(pattern,link) and parser != None:

        tracker_data = get_all()
        if len(filter(link=link))==0:            
            tracker_data["trackers"].append({"url":f"{link}","parser":f"{parser}"})
            with open(settings.TRACKERS_CONFIG_FILEPATH,'w') as file:
                json.dump(tracker_data,file,indent=4)
                return "Add new link successful!"
        else:
            return "The link has existing at list below."
    else:
        return "The link is not correct format."
    

def remove_link(link :str):
    tracker_data = get_all()
    data = {"trackers":[i for i in tracker_data["trackers"] if i["url"] != link]}
    with open(settings.TRACKERS_CONFIG_FILEPATH,'w') as file:
        json.dump(data,file,indent=4)

def filter(parser=None,link=None):
    f= open(settings.TRACKERS_CONFIG_FILEPATH)
    data=json.load(f)
    if link:
        return [i for i in data["trackers"] if i["url"].replace("https://","").replace("www.","") ==link.replace("https://","").replace("www.","")]
    elif parser:
        return [i for i in data["trackers"] if i["parser"] == parser]



