import streamlit as st
import pandas as pd
import re
import uuid
import requests

# https://python-v7byjeughqnzi69czd3tve.streamlit.app/

# Set the page configuration for a better user experience
st.set_page_config(
    page_title="iPilot Sync Tool",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. Create a label/header
st.title("NWN Collaboration Team iPilot and Teams Bulk Provision Tool")
st.write("Click the button in the sidebar to upload and view an import file.")

# 2. Create the file uploader (the "button" that opens a file)
uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type="csv")

# Define what we EXPECT the file to look like
EXPECTED_COLUMNS = ['SiteName', 'civicAddressId', 'UserPrincipalName', 'TeamsVoicePhoneNumber', 'TypeofAccount']

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

def is_valid_email(email):
    # Simple regex for email validation
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, str(email)))

def is_valid_phone(phone):
    # Removes non-digits and checks if length is at least 10
    digits = re.sub(r'\D', '', str(phone))
    return len(digits) >= 10

def is_valid_account(acc_type):
    return str(acc_type).strip().lower() in ['user', 'resource']

# 1. Define the Dialog (The Pop-up)
@st.dialog("Connect to iPilot")
def login_dialog():
    st.write("Please enter your iPilot credentials to authenticate.")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username and password:
            with st.spinner("Authenticating..."):
                # 2. The REST API Call for the Token
                # Replace the URL with your actual iPilot token endpoint
                api_url = "https://api.nuwave.com/v1/oauth2/authorize?instance=carousel" 
                payload = {
                    "username": username, 
                    "password": password
                    }
                headers = {
                    "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "accept": "application/json"
                }
                
                try:
                # Use 'data=' if the API expects form-encoded, or 'json=' if it expects JSON
                # Based on your "Content-Type" key, 'data=' is likely what it wants
                    response = requests.post(api_url, data=payload, headers=headers,timeout=10)
                
                    if response.status_code == 200:
                        response_data = response.json()
                        token = response_data.get("access_token")
                        
                        # Store information in session state
                        st.session_state["api_token"] = token
                        
                        # Update payload for your debug view
                        headers["Content-Type"] = "application/json" 
                        st.session_state["last_payload"] = payload # Save it to show on main page
                        st.session_state["last_headers"] = headers # Save it to show on main page

                        st.success("Successfully authenticated!")
                        st.rerun() 
                    else:
                        st.error(f"Login failed: {response.status_code} - {response.text}")
                        
                except Exception as e:
                    st.error(f"Connection error: {e}")
        else:
            st.warning("Please enter both username and password.")

def get_ipilot_accounts():
    # 1. Grab token from session state
    token = st.session_state.get("api_token")
    if not token:
        st.error("No token found. Please log in.")
        return []

    # 2. Prepare the request
    url = "https://api.nuwave.com/v1/accounts/customer?instance=carousel&limit=500"
    headers = {
        "x-access-token": token,
        "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs",
        "accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # 3. Handle Errors based on Status Code
        if response.status_code == 200:
            data = response.json()
            # Assuming the API returns a list of accounts
            # Adjust 'accountName' to match the actual key from iPilot
            return data 
            
        elif response.status_code == 400:
            st.error(f"400 Bad Request: Check your parameters. Server says: {response.text}")
        elif response.status_code == 401:
            st.error("401 Unauthorized: Your token might be expired.")
        else:
            st.error(f"Error {response.status_code}: {response.text}")
            
    except Exception as e:
        st.error(f"Connection Failed: {str(e)}")
    
    return []

# 3. Logic to handle the file once it is uploaded
if uploaded_file is not None:

    # Read the file using Pandas
    df = pd.read_csv(uploaded_file)
    
    # 1. Check if all columns exist
    if set(EXPECTED_COLUMNS).issubset(df.columns):
        
        # 2. Row-by-row validation
        errors = []
        
        for index, row in df.iterrows():
            row_errors = []
            
            if not is_valid_uuid(row['civicAddressId']):
                row_errors.append("Invalid GUID")
            
            if not is_valid_email(row['UserPrincipalName']):
                row_errors.append("Invalid Email")
                
            if not is_valid_phone(row['TeamsVoicePhoneNumber']):
                row_errors.append("Phone < 10 digits")
                
            if not is_valid_account(row['TypeofAccount']):
                row_errors.append("Must be 'User' or 'Resource'")
            
            errors.append(", ".join(row_errors) if row_errors else "Valid")

        # Add the status column to our view
        df['ValidationStatus'] = errors
        
        # 3. Display Results
        st.subheader("Validation Results")
        
        # Color coding the rows (Green for Valid, Red for Errors)
        def highlight_errors(val):
            color = 'red' if val != 'Valid' else 'green'
            return f'color: {color}'

        st.dataframe(df.style.applymap(highlight_errors, subset=['ValidationStatus']))
        
        

        # Summary Stats
        valid_count = (df['ValidationStatus'] == 'Valid').sum()
        st.metric("Clean Rows", f"{valid_count} / {len(df)}")
        
    else:
        st.error(f"Missing Columns! Requirements: {EXPECTED_COLUMNS}")

    all_valid = (df['ValidationStatus'] == 'Valid').all()

    if all_valid:
        st.success("🎉 All rows are valid! You can now proceed to iPilot.")
        # 3. Only show the connect button if validation passed
        if "api_token" not in st.session_state:
            if st.button("Connect to iPilot"):
                login_dialog()
        else:
            st.success("Authenticated with iPilot")
            
            # --- DEBUG SECTION ---
            with st.expander("Developer Debug: View Payload & Token"):
                st.write("### Last Auth Payload")
                st.json(st.session_state.get("last_payload"))
                st.json(st.session_state.get("last_headers"))
                st.write("### Active Token")
                st.code(st.session_state["api_token"])
            # ---------------------

        # Proceed with showing the account selection dropdown here
            with st.spinner("Fetching accounts from iPilot..."):
                accounts = get_ipilot_accounts()
                
                # Store accounts in "Session State" so they don't disappear on next click
                st.session_state['ipilot_accounts'] = accounts

        # If accounts have been fetched, show the selection box
        # --- In your main logic where the dropdown is displayed ---
        if 'ipilot_accounts' in st.session_state and st.session_state['ipilot_accounts']:
            # Create a list of names for the dropdown
            # If data is list of dicts: [{'accountName': 'ACME', 'accountId': '123'}, ...]
            account_list = st.session_state['ipilot_accounts']
            
            # This allows the user to see names, but you can access the full object
            selected_account = st.selectbox(
                "Select the iPilot Account:",
                options=account_list,
                format_func=lambda x: x.get('accountName', 'Unknown Account')
            )
            
            if selected_account:
                st.info(f"Target Account ID: {selected_account.get('accountId')}")
                st.info(f"Ready to sync data to: **{selected_account}**")
            
            if st.button("Start Sync"):
                st.write("Syncing to API... (Logic goes here)")
                
    else:
        invalid_count = (df['ValidationStatus'] != 'Valid').sum()
        st.error(f"Cannot proceed. {invalid_count} rows contain errors. Please fix the CSV and re-upload.")
        st.dataframe(df[df['ValidationStatus'] != 'Valid']) # Show only the broken rows