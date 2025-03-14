import streamlit as st
import pandas as pd
import uuid

from streamlit_option_menu import option_menu
from utils import (
    logout, get_document_libraries, 
    get_files_from_storage, upload_to_storage, get_unique_filename,
    add_partial_answer, remove_partial_answer, 
    add_reference_to_partial, remove_reference_from_partial,
    handle_new_tag
)
from utils.s3 import read_json_from_s3, write_json_to_s3, get_all_tags_from_list

# Page configuration
st.set_page_config(page_title="Ground Truth Benchmark", layout="wide", initial_sidebar_state="expanded")

# Load questions from S3
try:
    QUESTIONS = read_json_from_s3("submitted_questions.json")
    if QUESTIONS is None or not isinstance(QUESTIONS, dict):
        QUESTIONS = {}
        write_json_to_s3("submitted_questions.json", {})
except Exception:
    QUESTIONS = {}
    write_json_to_s3("submitted_questions.json", {})

# Authentication check
if "authenticated" not in st.session_state or not st.session_state["authenticated"]:
    st.warning("Please log in first.")
    st.switch_page("pages/login.py")

# CSS
# Add this CSS styling to your existing st.markdown section
st.markdown("""
    <style>
        .main { background-color: #f4f4f9; }
        .stButton>button {
            width: 100%;
            margin-bottom: 10px;
            background-color: #4CAF50;
            color: white;
        }
        .stButton>button:hover { background-color: #45a049; }
        .dataframe th, .dataframe td { padding: 10px; text-align: left; }
        .dataframe thead th { background-color: #4CAF50; color: white; }
        .dataframe tbody tr:nth-child(odd) { background-color: #f9f9f9; }
        .dataframe tbody tr:hover { background-color: #f1f1f1; }
        h1, h2, h3, h4 { color: #333; }
        [data-testid="stSidebarNav"] { display: none; }
        .partial-answer-section {
            background-color: #f0f0f0;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
            border-left: 5px solid #4CAF50;
        }
        
        /* Target remove reference buttons */
        [data-testid="stButton"] button[data-testid*="remove_ref_"] {
            background-color: #dc3545;
            color: white;
            padding: 0.25rem 0.5rem;
            font-size: 0.8rem;
            min-height: unset;
            height: auto;
            width: auto;
        }
        
        [data-testid="stButton"] button[data-testid*="remove_ref_"]:hover {
            background-color: #c82333;
            color: white;
        }
    </style>
""", unsafe_allow_html=True)


# Initialize session state for partial answers
if 'partial_answers' not in st.session_state:
    st.session_state['partial_answers'] = [{
        "id": str(uuid.uuid4()),
        "answer": "",
        "references": [{
            "id": str(uuid.uuid4()),
            "document": "",
            "pages": ""
        }]
    }]

# Sidebar navigation
with st.sidebar:
    if st.button("Add New Question"):
        st.session_state['option'] = "Add New Question"
    if st.button("View Questions"):
        st.session_state['option'] = "View Questions"
    if st.button("View and Upload Documents"):
        st.session_state['option'] = "View and Upload Documents"    
    if st.sidebar.button("Logout"):
        logout()
           
# Set default page           
option = st.session_state.get('option', "Add New Question")

# Get authentication tokens from session
TOKEN = st.session_state.get("token")
SITE_ID = st.session_state.get("site_id")

if not TOKEN or not SITE_ID:
    st.error("Authentication required. Please log in.")
else:
    # ADD NEW QUESTION PAGE
    if option == "Add New Question":
        st.header("Add a New Question")

        # Reset form after submission
        if st.session_state.get('form_submitted', False):
            st.session_state['question_input'] = ""
            st.session_state['agent_name_input'] = ""
            st.session_state['partial_answers'] = [{
                "id": str(uuid.uuid4()),
                "answer": "",
                "references": [{
                    "id": str(uuid.uuid4()),
                    "document": "",
                    "pages": ""
                }]
            }]
            st.success("Question added successfully!")
            
            st.session_state['selected_tags'] = []
            st.session_state['new_tag_input'] = ""
            st.session_state['form_submitted'] = False

        # Input fields
        question = st.text_area("Question", key="question_input")
        agent_name = st.text_input("Agent Name", key="agent_name_input", placeholder="e.g. SARA, RAFA, TESSA")

        # Document selection section
        libraries = get_document_libraries(TOKEN, SITE_ID)
        drive_id = None
        for lib in libraries:
            if "document" in lib["name"].lower():
                drive_id = lib["id"]
                st.session_state["document_drive_id"] = drive_id
                break
                
        # Get files
        if 'all_files' not in st.session_state or st.session_state.get('refresh_files', False):
            all_files = get_files_from_storage()
            st.session_state['all_files'] = all_files
            st.session_state['refresh_files'] = False
        
        all_files = st.session_state['all_files']
        # Ensure unique filenames in dropdown regardless of storage source
        available_files = list(set(file["name"] for file in all_files))

        if not available_files:
            st.info("No files found. Upload files in the 'View and Upload Documents' section.")
                
        for pa_idx, partial_answer in enumerate(st.session_state['partial_answers']):
            pa_id = partial_answer["id"]
            
            with st.container():
    
                # Answer text area
                answer_key = f"answer_{pa_id}"
                if answer_key not in st.session_state:
                    st.session_state[answer_key] = partial_answer["answer"]
                
                partial_answer["answer"] = st.text_area(
                    "Answer Text", 
                    value=st.session_state[answer_key],
                    key=answer_key
                )
                
                # References for this partial answer
            
                for ref_idx, reference in enumerate(partial_answer["references"]):
                    ref_id = reference["id"]
                    ref_cols = st.columns([3, 2, 1])
                    
                    doc_key = f"doc_{pa_id}_{ref_id}"
                    if doc_key not in st.session_state:
                        st.session_state[doc_key] = reference.get("document", "")
                    
                    with ref_cols[0]:
                        reference["document"] = st.selectbox(
                            "Document", 
                            options=[""] + available_files,
                            index=0 if st.session_state[doc_key] == "" else available_files.index(st.session_state[doc_key]) + 1,
                            key=doc_key
                        )
                    
                    pages_key = f"pages_{pa_id}_{ref_id}"
                    if pages_key not in st.session_state:
                        st.session_state[pages_key] = reference.get("pages", "")
                    
                    with ref_cols[1]:
                        reference["pages"] = st.text_input(
                            "Pages", 
                            value=st.session_state[pages_key],
                            key=pages_key,
                            placeholder="Comma-separated (e.g. 1,2,3)"
                        )
                    
                    with ref_cols[2]:
                        button_id = f"remove_ref_{pa_id}_{ref_id}"
                        if st.button("×", key=button_id, on_click=remove_reference_from_partial,
                             args=(pa_idx, ref_idx), help="Remove this reference"):
                            st.rerun()
                
                ref_cols = st.columns([1, 1])
                with ref_cols[0]:
                    if st.button("Add Reference", key=f"add_ref_{pa_id}"):
                        add_reference_to_partial(pa_idx)
                        st.rerun()
                
                with ref_cols[1]:
                    if len(st.session_state['partial_answers']) > 1:
                        if st.button("Remove Partial Answer", key=f"remove_pa_{pa_id}"):
                            remove_partial_answer(pa_idx)
                            st.rerun()
                
                st.markdown("""</div>""", unsafe_allow_html=True)
        
        if st.button("Add Another Partial Answer"):
            add_partial_answer()
            st.rerun()

        # Tags section
        existing_tags = get_all_tags_from_list(QUESTIONS)

        if 'selected_tags' not in st.session_state:
            st.session_state['selected_tags'] = []

        all_tags = list(existing_tags)
        for tag in st.session_state['selected_tags']:
            if tag not in all_tags:
                all_tags.append(tag)

        selected_tags = st.multiselect(
            "Select Tags", 
            options=all_tags, 
            default=st.session_state['selected_tags'],
            key="tag_multiselect"
        )
        st.session_state['selected_tags'] = selected_tags

        st.text_input(
            "Add New Tag (Optional)", 
            value="",
            help="Enter a new tag name and press Enter",
            key="new_tag_input",
            on_change=handle_new_tag
        )

        # Submit button
        if st.button("Submit", key="submit_btn"):
            if not question.strip():
                st.error("Question is required.")
            elif not agent_name.strip():
                st.error("Agent Name is required.")
            elif not any(pa["answer"].strip() for pa in st.session_state['partial_answers']):
                st.error("At least one partial answer is required.")
            else:
                # Process partial answers
                processed_partial_answers = []
                
                for partial_answer in st.session_state['partial_answers']:
                    if not partial_answer["answer"].strip():
                        continue  # Skip empty answers
                        
                    processed_references = []
                    for ref in partial_answer["references"]:
                        if not ref["document"]:
                            continue  # Skip empty references
                            
                        # Find all sources where this file exists
                        file_sources = []
                        for file in st.session_state['all_files']:
                            if file["name"] == ref["document"]:
                                file_sources.append(file["source"])
                                
                        # Convert to a list of unique sources instead of a comma-separated string
                        file_sources = sorted(set(file_sources)) if file_sources else ["Unknown"]
                        
                        # Convert pages from comma-separated string to a list of strings
                        pages_list = [page.strip() for page in ref["pages"].split(",")] if ref["pages"].strip() else []
                        
                        processed_references.append({
                            "document": ref["document"],
                            "page": pages_list,  # Now a list of page numbers
                            "source": file_sources  # Now a list of source strings
                        })
                    
                    if processed_references:  # Only add if there are valid references
                        processed_partial_answers.append({
                            "answer": partial_answer["answer"],
                            "references": processed_references
                        })
                
                if not processed_partial_answers:
                    st.error("At least one partial answer with references is required.")
                    st.stop()
                
                question_tags = st.session_state['selected_tags'].copy()
                submitted_by = st.session_state.get("username", "Unknown")
                
                # Create new question entry
                question_id = str(uuid.uuid4())
                new_entry = {
                    "question": question,
                    "partial_answers": processed_partial_answers,
                    "agent_name": agent_name,
                    "tags": question_tags,
                    "created_on": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "submitted_by": submitted_by 
                }

                # Add to database
                QUESTIONS[question_id] = new_entry
                write_json_to_s3("submitted_questions.json", QUESTIONS)
                
                st.session_state['form_submitted'] = True
                st.rerun()

    # VIEW QUESTIONS PAGE
    elif option == "View Questions":
        st.header("Ground Truth Library")

        if QUESTIONS:
            # Prepare data for display
            data = []
            
            for question_id, question_data in QUESTIONS.items():
                question_text = question_data.get("question", "")
                agent_name = question_data.get("agent_name", "")
                tags = ", ".join(question_data.get("tags", []))
                created_on = question_data.get("created_on", "")
                submitted_by = question_data.get("submitted_by", "Unknown")
                
                # Process all partial answers
                partial_answers_display = []
                for i, pa in enumerate(question_data.get("partial_answers", [])):
                    answer_text = pa.get("answer", "")
                    
                    # Process references for this partial answer
                    refs_display = []
                    for ref in pa.get("references", []):
                        doc_name = ref.get("document", "")
                        pages = ref.get("page", [])
                        sources = ref.get("source", ["Unknown"])
                        
                        pages_text = ", ".join(ref["page"]) if isinstance(ref["page"], list) else ref["page"]
                        sources_text = ", ".join(ref["source"]) if isinstance(ref["source"], list) else ref["source"]
                        
                        refs_display.append(f"- {doc_name} (Pages: {pages_text}) [Source: {sources_text}]")
                    
                    refs_text = "\n".join(refs_display)
                    partial_answers_display.append(f"Part. {i+1}: {answer_text}\n\nReferences:\n{refs_text}\n")
                
                all_answers = "\n\n".join(partial_answers_display)
                
                data.append({
                    "Question": question_text,
                    "Partial Answers": all_answers,
                    "Agent Name": agent_name,
                    "Tags": tags,
                    "Created On": created_on,
                    "Submitted By": submitted_by
                })
            
            df = pd.DataFrame(data)
            st.dataframe(df, width=3000, height=500)
        else:
            st.info("No questions found. Add new questions in the 'Add New Question' section.")
            
    # DOCUMENT MANAGEMENT PAGE
    elif option == "View and Upload Documents":
        st.header("Document Management")

        selected_page = option_menu(
            menu_title="",
            options=["File List", "Upload New File"],
            default_index=0,
            orientation="horizontal"
        )

        # FILE LIST PAGE
        if selected_page == "File List":
            all_files = get_files_from_storage()

            if all_files:
                unique_files = {}

                for file in all_files:
                    filename = file["name"]
                    modified_date = file.get("lastModified", "").split('T')[0] if "T" in file.get("lastModified", "") else file.get("lastModified", "")
                    created_by = file.get("createdBy", "Unknown")
                    source = file.get("source", "Unknown")

                    # If file already exists, merge storage sources and prioritize SharePoint metadata
                    if filename in unique_files:
                        if file["source"] == "SharePoint":
                            unique_files[filename].update({
                                "Last Modified": modified_date,
                                "Created By": created_by
                            })
                        # Add storage source to the list of sources
                        if source not in unique_files[filename]["Storage"]:
                            unique_files[filename]["Storage"] += f", {source}"
                    else:
                        unique_files[filename] = {
                            "File Name": filename,
                            "Last Modified": modified_date,
                            "Created By": created_by,
                            "Storage": source
                        }

                file_data = list(unique_files.values())
                if file_data:
                    df = pd.DataFrame(file_data)
                    st.table(df)
                else:
                    st.info("No files found. Use the 'Upload New File' tab to add files.")
            else:
                st.info("No files found. Use the 'Upload New File' tab to add files.")

       # UPLOAD FILE PAGE
        elif selected_page == "Upload New File":
            uploaded_files = st.file_uploader("Choose files to upload", type=None, accept_multiple_files=True)

            if uploaded_files:
                files_to_upload = []
                
                # Preview files and show renamed info
                st.subheader("Files Ready to Upload:")
                for uploaded_file in uploaded_files:
                    file_bytes = uploaded_file.getvalue()
                    original_filename = uploaded_file.name
                    upload_filename = get_unique_filename(original_filename)
                    
                    file_info = f"**{upload_filename}**"
                    if upload_filename != original_filename:
                        file_info += f" (renamed from {original_filename})"
                    
                    st.write(file_info)
                    files_to_upload.append((upload_filename, file_bytes))

                if st.button("Upload All Files"):
                    with st.spinner(f"Uploading {len(files_to_upload)} files..."):
                        successful_files = []
                        failed_files = []
                        
                        for filename, file_bytes in files_to_upload:
                            upload_results = upload_to_storage(filename, file_bytes)
                            successful_uploads = [storage for storage, result in upload_results if result]
                            failed_uploads = [storage for storage, result in upload_results if not result]
                            
                            if successful_uploads:
                                successful_files.append((filename, successful_uploads))
                            if failed_uploads:
                                failed_files.append((filename, failed_uploads))
                    
                    # Display upload summary
                    if len(successful_files) == len(files_to_upload):
                        st.success(f"All {len(successful_files)} files uploaded successfully.")
                    elif successful_files:
                        st.warning(f"{len(successful_files)} of {len(files_to_upload)} files uploaded successfully.")
                        
                        # Show successful uploads
                        with st.expander("Successful uploads"):
                            for filename, storages in successful_files:
                                st.write(f"{filename} - Uploaded to: {', '.join(storages)}")
                        
                        # Show failed uploads
                        if failed_files:
                            with st.expander("Failed uploads"):
                                for filename, storages in failed_files:
                                    st.write(f"{filename} - Failed to upload to: {', '.join(storages)}")
                    else:
                        st.error("All uploads failed. Please check your connection and try again.")
                    
                    st.session_state['refresh_files'] = True