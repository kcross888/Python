import streamlit as st
import pandas as pd
import re
import uuid
import requests

# https://python-v7byjeughqnzi69czd3tve.streamlit.app/

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

def get_ipilot_accounts():
    """
    In a real scenario, you'd use:
    response = requests.get("https://api.ipilot.io/v1/accounts", headers=headers)
    return response.json()
    """
    # Mock data for learning:
    return ["Enterprise_Main_Tenant", "Testing_Lab_01", "Region_West_Voice"]

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
        
        # --- NEW: Conditional UI for API Interaction ---
        if st.button("Connect to iPilot"):
            # When clicked, fetch the accounts
            with st.spinner("Fetching accounts from iPilot..."):
                accounts = get_ipilot_accounts()
                
                # Store accounts in "Session State" so they don't disappear on next click
                st.session_state['ipilot_accounts'] = accounts

        # If accounts have been fetched, show the selection box
        if 'ipilot_accounts' in st.session_state:
            selected_account = st.selectbox(
                "Select the iPilot Account to target:",
                options=st.session_state['ipilot_accounts']
            )
            st.info(f"Ready to sync data to: **{selected_account}**")
            
            if st.button("Start Sync"):
                st.write("Syncing to API... (Logic goes here)")
                
    else:
        invalid_count = (df['ValidationStatus'] != 'Valid').sum()
        st.error(f"Cannot proceed. {invalid_count} rows contain errors. Please fix the CSV and re-upload.")
        st.dataframe(df[df['ValidationStatus'] != 'Valid']) # Show only the broken rows