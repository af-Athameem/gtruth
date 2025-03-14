import streamlit as st
import time

from utils.auth import authenticate_user, check_session_timeout

st.set_page_config(
    page_title="Ground Truth Benchmark",
    layout="wide",  
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
        /* Hide the sidebar completely */
        [data-testid="stSidebar"] {
            display: none !important;
        }
        
        /* Remove sidebar collapse control */
        .st-emotion-cache-1b32qsx {
            display: none !important;
        }
        
        }
        
        /* Navigation style adjustments */
        [data-testid="stSidebarNav"] {
            display: none;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Login")

# Initialize session state for authentication
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
    st.session_state["username"] = None
    st.session_state["last_activity"] = time.time()

if check_session_timeout():
    st.warning("Your session has expired due to inactivity. Please log in again.")

if st.session_state["authenticated"]:
    st.switch_page("pages/login.py")
    
else:
    # Login Form
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")            
        submit_login = st.form_submit_button("Login")
    
    if submit_login:
        if not username or not password:
            st.error("Please enter both username and password.")
        else:
            if authenticate_user(username, password):
                st.session_state["authenticated"] = True
                st.session_state["username"] = username
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Invalid username or password.")
    
# Logout button
if st.session_state["authenticated"]:
    st.sidebar.header(f"Welcome, {st.session_state['username']}!")
    
    if st.sidebar.button("Logout"):
        st.session_state["authenticated"] = False
        st.session_state["username"] = None
        
        # Also clear SharePoint auth tokens
        if "token" in st.session_state:
            del st.session_state["token"]
        if "site_id" in st.session_state:
            del st.session_state["site_id"]
        
        st.rerun()
