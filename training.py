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

# --- Helper: Debug Console Manager ---
def log_api_call(method, url, response):
    """Stores the last API response in session state for the sidebar console."""
    log_entry = {
        "Method": method,
        "URL": url,
        "Status": response.status_code,
        "Body": response.text  # Plain text response
    }
    st.session_state["api_debug_log"] = log_entry

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
                    log_api_call("POST", api_url, response) # Log to console
                    
                    if response.status_code == 200:
                        token = response.json().get("access_token")
                        st.session_state["api_token"] = token
                        st.success("Successfully authenticated!")
                        st.rerun() 
                    else:
                        st.error(f"Login failed: {response.status_code}")
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
        # 1. Main Carousel
        url1 = f"{base_url}/accounts/customer?instance=carousel&limit=500"
        res1 = requests.get(url1, headers=headers)
        log_api_call("GET", url1, res1)
        
        for item in res1.json():
            info = item.get("accountInfo", {})
            customer_list.append({
                "companyName": info.get("accountInfo.companyname"),
                "accountId": info.get("accountInfo.accountId"),
                "resellerId": ""
            })

        # 2. Resellers
        for r_id in ['4', '2', '1']:
            url_r = f"{base_url}/site/resellerId/{r_id}?instance=carousel&limit=500"
            res_r = requests.get(url_r, headers=headers)
            log_api_call("GET", url_r, res_r)
            
            data = res_r.json()
            for item in data.get("customers", []):
                customer_list.append({
                    "companyName": item.get("customerName"),
                    "accountId": item.get("customerId"),
                    "resellerId": r_id
                })

        unique_customers = {}
        for cust in customer_list:
            acc_id = cust["accountId"]
            if acc_id and acc_id not in unique_customers:
                unique_customers[acc_id] = cust

        return sorted(unique_customers.values(), key=lambda x: (x['companyName'] or "").lower())
    except Exception as e:
        st.error(f"Error building customer cache: {e}")
        return []

# --- Sidebar Content ---
with st.sidebar:
    st.header("Upload & Tools")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    
    st.divider()
    st.header("🪟 API Debug Console")
    if "api_debug_log" in st.session_state:
        log = st.session_state["api_debug_log"]
        st.write(f"**Last Method:** {log['Method']}")
        st.write(f"**Status:** {log['Status']}")
        st.text_area("Plain Text Response:", value=log['Body'], height=300)
    else:
        st.info("No API calls made yet.")

# --- Main App Logic ---
st.title("NWN Collaboration Team iPilot & Teams Provisioning")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
    
    if set(EXPECTED_COLUMNS).issubset(df.columns):
        # Validation Logic
        errors = []
        for _, row in df.iterrows():
            row_errs = []
            if not is_valid_uuid(row['civicAddressId']): row_errs.append("Invalid GUID")
            if not is_valid_email(row['UserPrincipalName']): row_errs.append("Invalid Email")
            if not is_valid_phone(row['TeamsVoicePhoneNumber']): row_errs.append("Phone < 10 digits")
            if not is_valid_account(row['TypeofAccount']): row_errs.append("Must be 'User' or 'Resource'")
            errors.append(", ".join(row_errs) if row_errs else "Valid")
        
        df['ValidationStatus'] = errors
        st.dataframe(df.style.applymap(lambda v: f'color: {"red" if v != "Valid" else "green"}', subset=['ValidationStatus']), use_container_width=True)
        
        all_valid = (df['ValidationStatus'] == 'Valid').all()

        if all_valid:
            if "api_token" not in st.session_state:
                if st.button("Connect to iPilot"):
                    login_dialog()
            else:
                if "customer_cache" not in st.session_state:
                    with st.spinner("Building Customer Cache..."):
                        st.session_state["customer_cache"] = get_all_customers()
                
                customers = st.session_state.get("customer_cache", [])
                selected_customer = st.selectbox(
                    "Select the iPilot Account:",
                    options=customers,
                    format_func=lambda x: f"{x['companyName']} (ID: {x['accountId']})"
                )
                
                if selected_customer:
                    # Fetch Domains Logic
                    target_id = selected_customer['accountId']
                    if st.session_state.get("current_customer_id") != target_id:
                        token = st.session_state.get("api_token")
                        headers = {"x-access-token": token, "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs", "accept": "application/json"}
                        d_url = f"https://api.nuwave.com/v1/msteams?instance=carousel&customerId={target_id}"
                        
                        d_res = requests.get(d_url, headers=headers)
                        log_api_call("GET", d_url, d_res) # Log domain call
                        
                        # Handle list vs dict response
                        resp_json = d_res.json()
                        st.session_state["raw_domains"] = resp_json if isinstance(resp_json, list) else resp_json.get("domains", [])
                        st.session_state["current_customer_id"] = target_id

                    # Domain Selection
                    domain_mapping = {}
                    for d in st.session_state.get("raw_domains", []):
                        if is_valid_uuid(d): domain_mapping["Operator Connect"] = d
                        elif str(d).startswith("NWNMS"): domain_mapping["DRaaS"] = d

                    if domain_mapping:
                        conn_type = st.selectbox("Select Connection Type:", options=list(domain_mapping.keys()))
                        if st.button("Start Sync"):
                            st.write(f"Syncing {len(df)} users to {domain_mapping[conn_type]}...")
    else:
        st.error(f"Columns missing: {EXPECTED_COLUMNS}")