import json
import re
from src.config import settings
import gspread
import pathlib

def initial_gspread():
    client = gspread.service_account(
        filename=pathlib.Path("src/config/creds.json").absolute(),
    )
    return client

def creat_new_spreadsheet(title:str):
    client = initial_gspread()
    response = client.create(title=title)
    for i in settings.CUSTOME_MAIL:
        response.share(email_address=i,perm_type='user',role='writer')
    
    sheet_id= response.id
    with open(pathlib.Path("src/config/sheetId.txt").absolute(),"+a") as f:
        f.write(sheet_id+"|#|#|"+title+"\n")
    return sheet_id

def get_all_sheet_id():
    with open(pathlib.Path("src/config/sheetId.txt").absolute(),"r") as f:
        sheet_id= f.readlines()
    return sheet_id
    
def insert_new_link_to_sheet():
    all_links = get_all("link")
    all_shet_id = get_all_sheet_id()
    sheetJson = {"spreadsheets":[
        
    ]}
    
    index_tracker_url = 0
    for i in all_shet_id:
        if(index_tracker_url+2<len(all_links)):
            sheetJson["spreadsheets"].append({
                "key_id": "{}".format(i.split("|#|#|")[0]),
                "tracker_urls": [
                    all_links[index_tracker_url],                
                    all_links[index_tracker_url+1],                
                    all_links[index_tracker_url+2],                
                ]
            })    
        elif(index_tracker_url+1<len(all_links)):
            sheetJson["spreadsheets"].append({
                "key_id": "{}".format(i.split("|#|#|")[0]),
                "tracker_urls": [
                    all_links[index_tracker_url],                
                    all_links[index_tracker_url+1],                            
                ]
            })
        elif(index_tracker_url<len(all_links)):
            sheetJson["spreadsheets"].append({
                "key_id": "{}".format(i.split("|#|#|")[0]),
                "tracker_urls": [
                    all_links[index_tracker_url],             
                ]
            })
        index_tracker_url +=3
                                                                        
    with open(pathlib.Path("src/config/sheets.json").absolute(),'w') as f:
        json.dump(sheetJson,f,indent=4)
    
def get_all(type = None):
    f= open(settings.TRACKERS_CONFIG_FILEPATH)
    data=json.load(f)
    
    f_sheet = open(settings.SHEETS_CONFIG_FILEPATH)
    data_sheet = json.load(f_sheet)
                    
    if type!=None and type == "link":
        return [i["url"] for i in data["trackers"]]
    elif type!=None and type == "parser":            
        return list(set([i["parser"] for i in data["trackers"]]))
    
    else:
        data_sheet_response = {"trackers":[]}
        for i in data["trackers"]:
            for j in data_sheet["spreadsheets"]:
                for k in j["tracker_urls"]:
                    if i["url"] == k:
                        data_sheet_response["trackers"].append({
                            "url":i["url"],
                            "parser":i["parser"],
                            "sheet_link":"https://docs.google.com/spreadsheets/d/"+j["key_id"]
                        })
                        break
        return data_sheet_response

def add_link(link :str,parser :str):
    pattern =r'^(https?:\/\/)?(www\.)?([a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)+)(\/[^\s]*)?$'
    if re.match(pattern,link) and parser != None:

        tracker_data = get_all()
        if len(filter(link=link))==0:            
            number_sheet_created=get_all_sheet_id()
            distance_links = len(tracker_data["trackers"])+1-len(number_sheet_created)*3
            if(distance_links-1>3):
                for i in range(0,distance_links-1,3):
                    
                    link1= tracker_data["trackers"][i]["url"].replace("https://","").replace("www.","").replace("/","")
                    link2= tracker_data["trackers"][i+1]["url"].replace("https://","").replace("www.","").replace("/","") if i+1<distance_links else ""
                    link3=   tracker_data["trackers"][i+2]["url"].replace("https://","").replace("www.","").replace("/","") if i+2 <distance_links else ""
                    title_sheet= "|".join([link1,link2,link3])
                    creat_new_spreadsheet(title=title_sheet)
                if(distance_links%3>0):
                    title=tracker_data["trackers"][distance_links%3]["url"].replace("https://","").replace("www.","")
                    sheet_id = creat_new_spreadsheet(title=title)
                    tracker_data["trackers"].append({"url":f"{link}","parser":f"{parser}", "sheet_link":sheet_id})
            elif(distance_links<=3 and distance_links>0):
                title = link.replace("https://","").replace("www.","").replace("/","")
                sheet_id = creat_new_spreadsheet(title=title)
                tracker_data["trackers"].append({"url":f"{link}","parser":f"{parser}", "sheet_link":sheet_id})
            elif(distance_links<=0):
                sheet_id = tracker_data["trackers"][len(tracker_data["trackers"])-1]["sheet_link"]
                tracker_data["trackers"].append({"url":f"{link}","parser":f"{parser}", "sheet_link":sheet_id})
                
            with open(settings.TRACKERS_CONFIG_FILEPATH,'w') as file:
                json.dump(tracker_data,file,indent=4)
                
            insert_new_link_to_sheet()
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



