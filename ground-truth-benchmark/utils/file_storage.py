import streamlit as st
import pandas as pd
import os
import tempfile
from utils.s3 import upload_file, list_files
from utils.sharepoint import get_files_in_eval_benchmark, upload_to_eval_benchmark

def get_files_from_storage():
    """Get files from both SharePoint and S3 storage."""
    files = []
    
    # Get SharePoint files
    TOKEN = st.session_state.get("token")
    SITE_ID = st.session_state.get("site_id")
    if TOKEN and SITE_ID:
        drive_id = st.session_state.get("document_drive_id")
        if drive_id:
            sharepoint_files = get_files_in_eval_benchmark(TOKEN, drive_id)
            if sharepoint_files:
                for file in sharepoint_files:
                    if "folder" not in file:
                        files.append({
                            "name": file["name"],
                            "source": "SharePoint",
                            "lastModified": file.get("lastModifiedDateTime", ""),
                            "createdBy": file.get("createdBy", {}).get("user", {}).get("displayName", "Unknown")
                        })

    # Get S3 files
    s3_files = list_files()
    for file_name in s3_files:
        files.append({
            "name": file_name,
            "source": "S3",
            "lastModified": pd.Timestamp.now().strftime("%Y-%m-%d"),
            "createdBy": "Unknown"
        })

    return files

def upload_to_storage(file_name, file_bytes):
    results = []
    TOKEN = st.session_state.get("token")
    SITE_ID = st.session_state.get("site_id")
    
    if TOKEN and SITE_ID:
        try:
            sharepoint_result = upload_to_eval_benchmark(TOKEN, SITE_ID, file_name, file_bytes)
            results.append(("SharePoint", sharepoint_result))
        except Exception:
            results.append(("SharePoint", False))

    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            temp_file.write(file_bytes)
        
        s3_result = upload_file(temp_file_path, target_filename=file_name)  
        results.append(("S3", s3_result))
    except Exception:
        results.append(("S3", False))
    finally:
        try:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        except Exception:
            pass

    return results

def get_unique_filename(original_filename):
    """Generate unique filename to avoid overwriting existing files."""
    existing_filenames = {file["name"] for file in get_files_from_storage()}
    
    if original_filename not in existing_filenames:
        return original_filename
        
    name_parts = original_filename.rsplit('.', 1)
    base_name = name_parts[0]
    extension = f".{name_parts[1]}" if len(name_parts) > 1 else ""

    counter = 1
    new_filename = original_filename
    
    while new_filename in existing_filenames:
        new_filename = f"{base_name} copy({counter}){extension}"
        counter += 1
        
    return new_filename