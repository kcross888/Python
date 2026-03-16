import streamlit as st
import pandas as pd
import re
import uuid
import requests

# Set the page configuration
st.set_page_config(
    page_title="iPilot Sync Tool",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Configuration & Helpers ---
EXPECTED_COLUMNS = ['SiteName', 'civicAddressId', 'UserPrincipalName', 'TeamsVoicePhoneNumber', 'TypeofAccount']

def is_valid_uuid(val):
    try:
        uuid.UUID(str(val))
        return True
    except:
        return False

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return bool(re.match(pattern, str(email)))

def is_valid_phone(phone):
    digits = re.sub(r'\D', '', str(phone))
    return len(digits) >= 10

def is_valid_account(acc_type):
    return str(acc_type).strip().lower() in ['user', 'resource']

# --- API Logic ---

@st.dialog("Connect to iPilot")
def login_dialog():
    st.write("Please enter your iPilot credentials to authenticate.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username and password:
            with st.spinner("Authenticating..."):
                api_url = "https://api.nuwave.com/v1/oauth2/authorize?instance=carousel" 
                payload = {"username": username, "password": password}
                headers = {
                    "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "accept": "application/json"
                }
                try:
                    response = requests.post(api_url, data=payload, headers=headers, timeout=10)
                    if response.status_code == 200:
                        token = response.json().get("access_token")
                        st.session_state["api_token"] = token
                        st.session_state["last_payload"] = payload
                        st.session_state["last_headers"] = headers
                        st.success("Successfully authenticated!")
                        st.rerun() 
                    else:
                        st.error(f"Login failed: {response.status_code} - {response.text}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

def get_all_customers():
    token = st.session_state.get("api_token")
    headers = {
        "x-access-token": token,
        "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs",
        "accept": "application/json"
    }
    customer_list = []
    base_url = "https://api.nuwave.com/v1"

    try:
        # 1. Main Carousel Customers
        res = requests.get(f"{base_url}/accounts/customer?instance=carousel&limit=500", headers=headers).json()
        for item in res:
            info = item.get("accountInfo", {})
            customer_list.append({
                "companyName": info.get("accountInfo.companyname"),
                "accountId": info.get("accountInfo.accountId"),
                "resellerId": ""
            })

        # 2. Reseller Customers (4, 2, 1)
        for r_id in ['4', '2', '1']:
            res = requests.get(f"{base_url}/site/resellerId/{r_id}?instance=carousel&limit=500", headers=headers).json()
            for item in res.get("customers", []):
                customer_list.append({
                    "companyName": item.get("customerName"),
                    "accountId": item.get("customerId"),
                    "resellerId": r_id
                })

        # 3. Deduplicate (Keep first occurrence of accountId)
        unique_customers = {}
        for cust in customer_list:
            acc_id = cust["accountId"]
            if acc_id and acc_id not in unique_customers:
                unique_customers[acc_id] = cust

        return sorted(unique_customers.values(), key=lambda x: (x['companyName'] or "").lower())
    except Exception as e:
        st.error(f"Error building customer cache: {e}")
        return []

# --- UI Layout ---
st.title("NWN Collaboration Team iPilot and Teams Bulk Provision Tool")
uploaded_file = st.sidebar.file_uploader("Choose a CSV file", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    if set(EXPECTED_COLUMNS).issubset(df.columns):
        errors = []
        for _, row in df.iterrows():
            row_errs = []
            if not is_valid_uuid(row['civicAddressId']): row_errs.append("Invalid GUID")
            if not is_valid_email(row['UserPrincipalName']): row_errs.append("Invalid Email")
            if not is_valid_phone(row['TeamsVoicePhoneNumber']): row_errs.append("Phone < 10 digits")
            if not is_valid_account(row['TypeofAccount']): row_errs.append("Must be 'User' or 'Resource'")
            errors.append(", ".join(row_errs) if row_errs else "Valid")
        
        df['ValidationStatus'] = errors
        st.subheader("Validation Results")
        
        st.dataframe(df.style.applymap(lambda v: f'color: {"red" if v != "Valid" else "green"}', subset=['ValidationStatus']))
        
        valid_count = (df['ValidationStatus'] == 'Valid').sum()
        st.metric("Clean Rows", f"{valid_count} / {len(df)}")
        
        all_valid = (df['ValidationStatus'] == 'Valid').all()

        if all_valid:
            st.success("🎉 All rows are valid!")
            
            if "api_token" not in st.session_state:
                if st.button("Connect to iPilot"):
                    login_dialog()
            else:
                # Cache customers so we don't fetch on every click
                if "customer_cache" not in st.session_state:
                    with st.spinner("Building Customer Cache..."):
                        st.session_state["customer_cache"] = get_all_customers()
                
                customers = st.session_state.get("customer_cache", [])
                
                if customers:
                    selected_customer = st.selectbox(
                        "Select the iPilot Account to target:",
                        options=customers,
                        format_func=lambda x: f"{x['companyName']} (ID: {x['accountId']})"
                    )
                    
                    if selected_customer:
                        target_id = selected_customer['accountId']
                        target_reseller = selected_customer['reseller_id'] # Note: reseller_id from previous step
                        
                        # 1. Fetch Domains if they aren't already in session state for THIS customer
                        if st.session_state.get("current_customer_id") != target_id:
                            with st.spinner("Fetching Teams Domains..."):
                                token = st.session_state.get("api_token")
                                headers = {
                                    "x-access-token": token,
                                    "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs",
                                    "accept": "application/json"
                                }
                                
                                domain_url = f"https://api.nuwave.com/v1/msteams?instance=carousel&customerId={target_id}"
                                try:
                                    domain_res = requests.get(domain_url, headers=headers).json()
                                    # Extract the list of domains from the 'domains' key
                                    st.session_state["raw_domains"] = domain_res.get("domains", [])
                                    st.session_state["current_customer_id"] = target_id
                                except Exception as e:
                                    st.error(f"Failed to fetch domains: {e}")
                                    st.session_state["raw_domains"] = []

                        # 2. Logic to map "Operator Connect" and "DRaaS"
                        raw_domains = st.session_state.get("raw_domains", [])
                        domain_mapping = {}

                        for d in raw_domains:
                            # Check if it's a GUID (Operator Connect)
                            if is_valid_uuid(d):
                                domain_mapping["Operator Connect"] = d
                            # Check if it starts with NWNMS (DRaaS)
                            elif str(d).startswith("NWNMS"):
                                domain_mapping["DRaaS"] = d

                        # 3. Present the Domain Dropdown if we found matches
                        if domain_mapping:
                            connection_type = st.selectbox(
                                "Select Connection Type:",
                                options=list(domain_mapping.keys())
                            )
                            
                            selected_domain = domain_mapping[connection_type]
                            st.info(f"Selected Domain: `{selected_domain}`")
                            
                            # Now you are ready to Sync
                            if st.button("Start Sync"):
                                st.write(f"Initiating sync for {target_id} using {selected_domain}...")
                        else:
                            st.warning("No compatible Operator Connect or DRaaS domains found for this customer.")
                
                with st.expander("Developer Debug"):
                    st.json(st.session_state.get("last_headers"))
                    st.code(st.session_state.get("api_token"))
    else:
        st.error(f"Missing Columns! Requirements: {EXPECTED_COLUMNS}")