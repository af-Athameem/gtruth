import streamlit as st
import requests


# Const
GRAPH_API_BASE_URL = "https://graph.microsoft.com/v1.0"
EVAL_BENCHMARK_PATH = "/Eval Benchmark"
SHAREPOINT_FOLDER = "/sites/qlytics.sharepoint.com:/sites/AmpliforceHQ"

def get_access_token(tenant_id, client_id, client_secret):
    """Get OAuth Token from Microsoft"""
    token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default"
    }
    response = requests.post(token_url, data=data)
    token_json = response.json()

    if "access_token" not in token_json:
        return None

    return token_json["access_token"]

def get_site_id(token):
    """Get SharePoint Site ID"""
    headers = {"Authorization": f"Bearer {token}"}
    site_url = f"{GRAPH_API_BASE_URL}/sites/qlytics.sharepoint.com:/sites/AmpliforceHQ"

    response = requests.get(site_url, headers=headers)
    site_info = response.json()

    if "id" not in site_info:
        return None

    return site_info["id"]

def get_document_libraries(token, site_id):
    """Returns a list of document libraries from SharePoint"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_API_BASE_URL}/sites/{site_id}/drives"
    response = requests.get(url, headers=headers)
    libraries = response.json()

    if "value" not in libraries:
        return None

    return libraries["value"]

def get_files_in_eval_benchmark(token, drive_id):
    """Returns a list of files in the Eval Benchmark folder"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/root:{EVAL_BENCHMARK_PATH}:/children"
    
    try:
        with st.spinner("Loading files..."):
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                files = response.json()
                if "value" in files:
                    return files["value"]
                else:
                    return []
            else:
                root_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/root/children"
                root_response = requests.get(root_url, headers=headers)
                
                if root_response.status_code == 200:
                    root_items = root_response.json()
                    
                    if "value" in root_items:
                        for item in root_items["value"]:
                            if item.get("name") == "Eval Benchmark" and "folder" in item:
                                eval_id = item.get("id")
                                
                                eval_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/items/{eval_id}/children"
                                eval_response = requests.get(eval_url, headers=headers)
                                
                                if eval_response.status_code == 200:
                                    eval_items = eval_response.json()
                                    if "value" in eval_items:
                                        return eval_items["value"]
        return []
    except Exception:
        return []

def get_file_item(token, drive_id, file_name):
    """Gets a specific file from the Eval Benchmark folder"""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/root:{EVAL_BENCHMARK_PATH}/{file_name}"
    
    try:
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        
        files = get_files_in_eval_benchmark(token, drive_id)
        
        if files:
            for file in files:
                if file.get("name") == file_name:
                    return file
        
        return None
    except Exception:
        return None

def upload_to_eval_benchmark(token, site_id, file_name, file_content):
    """Uploads a file to the Eval Benchmark folder in SharePoint"""
    headers = {"Authorization": f"Bearer {token}"}
    
    libraries = get_document_libraries(token, site_id)
    if not libraries:
        return None

    drive_id = None
    for lib in libraries:
        if "document" in lib["name"].lower():  
            drive_id = lib["id"]
            break

    if not drive_id:
        return None
        
    existing_file = get_file_item(token, drive_id, file_name)
    
    upload_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream"
    }
    
    if existing_file and "id" in existing_file:
        upload_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/items/{existing_file['id']}/content"
        response = requests.put(upload_url, headers=upload_headers, data=file_content)
        
        if response.status_code in (200, 201):
            return True
        else:
            return False
    else:
        upload_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/root:{EVAL_BENCHMARK_PATH}/{file_name}:/content"
        
        response = requests.put(upload_url, headers=upload_headers, data=file_content)

        if response.status_code in (200, 201):
            return True
        else:
            try:
                root_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/root/children"
                root_response = requests.get(root_url, headers=headers)
                
                if root_response.status_code == 200:
                    root_items = root_response.json()
                    
                    if "value" in root_items:
                        eval_benchmark_id = None
                        for item in root_items["value"]:
                            if item.get("name") == "Eval Benchmark" and "folder" in item:
                                eval_benchmark_id = item.get("id")
                                break
                        
                        if not eval_benchmark_id:
                            create_folder_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/root/children"
                            create_folder_data = {
                                "name": "Eval Benchmark",
                                "folder": {},
                                "@microsoft.graph.conflictBehavior": "rename"
                            }
                            create_folder_response = requests.post(
                                create_folder_url, 
                                headers={**headers, "Content-Type": "application/json"},
                                json=create_folder_data
                            )
                            
                            if create_folder_response.status_code in (200, 201):
                                eval_benchmark_id = create_folder_response.json().get("id")
                            else:
                                return False
                        
                        if eval_benchmark_id:
                            alt_upload_url = f"{GRAPH_API_BASE_URL}/drives/{drive_id}/items/{eval_benchmark_id}:/{file_name}:/content"
                            alt_response = requests.put(alt_upload_url, headers=upload_headers, data=file_content)
                            
                            if alt_response.status_code in (200, 201):
                                return True
            except Exception:
                pass
                
            return False
def get_all_documents_from_list(questions_list):
    """Get all unique document names from the questions list."""
    if questions_list is None or not isinstance(questions_list, list):
        return []
        
    all_documents = set()
    
    for question in questions_list:
        if "Reference Documents" in question:
            for doc in question["Reference Documents"]:
                if "name" in doc and doc["name"]:
                    all_documents.add(doc["name"])
                
    return sorted(list(all_documents))
