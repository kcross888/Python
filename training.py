import streamlit as st
import pandas as pd
import re
import uuid
import requests
import concurrent.futures
import json
import subprocess
import os
import tempfile

# Set the page configuration
st.set_page_config(
    page_title="iPilot Sync Tool",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper: Debug Console Manager ---
def log_api_call(method, url, response):
    log_entry = {
        "Method": method,
        "URL": url,
        "Status": response.status_code,
        "Body": response.text 
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

def parse_ipilot_response(response_text):
    try:
        data = json.loads(response_text)
        inner_status = data.get("statusCode", 200) 
        msg = data.get("errors", {}).get("message") or data.get("status", "Operation Successful")
        invalid_map = data.get("data", {}).get("invalid_numbers", {})
        if invalid_map:
            details = " | ".join([f"{num}: {reason}" for num, reason in invalid_map.items()])
            msg = f"{msg} ({details})"
        return int(inner_status), msg
    except:
        return 200, "Response received, but body was not in JSON format."

# --- API Logic ---
@st.dialog("Connect to iPilot")
def login_dialog():
    st.write("Please enter your iPilot credentials to authenticate.")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login", use_container_width=True):
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
                    log_api_call("POST", api_url, response)
                    if response.status_code == 200:
                        token = response.json().get("access_token")
                        st.session_state["api_token"] = token
                        st.success("Successfully authenticated!")
                        st.rerun() 
                    else:
                        st.error(f"Login failed: {response.status_code}")
                except Exception as e:
                    st.error(f"Connection error: {e}")

def fetch_customer_metadata(target_id):
    token = st.session_state.get("api_token")
    headers = {"x-access-token": token, "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs", "accept": "application/json"}
    
    d_url = f"https://api.nuwave.com/v1/msteams?instance=carousel&customerId={target_id}"
    try:
        d_res = requests.get(d_url, headers=headers, timeout=10)
        log_api_call("GET", d_url, d_res)
        resp_json = d_res.json()
        st.session_state["raw_domains"] = resp_json[0].get("domains", []) if isinstance(resp_json, list) and resp_json else []
    except:
        st.session_state["raw_domains"] = []

    addr_url = f"https://api.nuwave.com/v1/msteams/ocAddress/{target_id}?instance=carousel"
    try:
        addr_res = requests.get(addr_url, headers=headers, timeout=10)
        log_api_call("GET", addr_url, addr_res)
        addr_json = addr_res.json()
        st.session_state["address_data"] = addr_json.get("addresses", []) if isinstance(addr_json, dict) else []
    except:
        st.session_state["address_data"] = []

def get_all_customers():
    token = st.session_state.get("api_token")
    headers = {"x-access-token": token, "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs", "accept": "application/json"}
    customer_list = []
    base_url = "https://api.nuwave.com/v1"
    try:
        url1 = f"{base_url}/accounts/customer?instance=carousel&limit=500"
        res1 = requests.get(url1, headers=headers)
        if res1.status_code == 200:
            for item in res1.json():
                info = item.get("accountInfo", {})
                customer_list.append({"companyName": info.get("companyName"), "accountId": info.get("accountId")})
        unique_customers = {cust["accountId"]: cust for cust in customer_list if cust["accountId"]}
        return sorted(unique_customers.values(), key=lambda x: (x.get('companyName') or "").lower())
    except Exception as e:
        st.error(f"Error building customer cache: {e}")
        return []

def format_phone(phone):
    digits = re.sub(r'\D', '', str(phone))
    return digits[-10:] if len(digits) >= 10 else digits

def get_payload_type(domain_type, account_type, domain_count):
    acc_type_upper = str(account_type).upper()
    if acc_type_upper == "USER":
        if domain_count == 1: return "USER AA & CQ"
        else:
            if domain_type == "Operator Connect": return "OC USER AA & CQ"
            elif domain_type == "DRaaS": return "DR USER"
    return "USER AA & CQ"

def send_sync_request(row, account_id, domain_val, domain_type, domain_count, token):
    api_url = f"https://api.nuwave.com/v1/msteams/{domain_val}/users?instance=carousel"
    headers = {"x-access-token": token, "x-api-key": "sUxNytmtwt5u8uZrwTbtx4qo7Mxy279x88cG0tFs", "Content-Type": "application/json"}
    payload = {
        "user": {
            "telephoneNumber": format_phone(row['TeamsVoicePhoneNumber']),
            "civicAddressId": row['civicAddressId'],
            "type": get_payload_type(domain_type, row['TypeofAccount'], domain_count)
        }
    }
    try:
        res = requests.post(api_url, json=payload, headers=headers, timeout=20)
        return {"User": row['UserPrincipalName'], "Status": "Success" if res.status_code in [200, 201, 202] else "Failed", "Code": res.status_code, "Response": res.text}
    except Exception as e:
        return {"User": row['UserPrincipalName'], "Status": "Error", "Code": "N/A", "Response": str(e)}

def check_teams_module():
    check_script = "Get-Module -ListAvailable MicrosoftTeams"
    try:
        result = subprocess.run(["powershell.exe", "-Command", check_script], capture_output=True, text=True, timeout=10)
        return ("MicrosoftTeams" in result.stdout), "Module check complete."
    except Exception as e:
        return False, f"Environment check failed: {e}"

PS_TEMPLATE = """
param([string]$Action, [string]$JsonData)
if ($Action -eq "Login") {
    try {
        Connect-MicrosoftTeams -ErrorAction Stop
        $firstUser = Get-CsOnlineUser | Select-Object -ExpandProperty UserPrincipalName -First 1
        $tenantDomain = $firstUser.Split('@')[1]
        Write-Host "SUCCESS: Authenticated"
        Write-Host "TENANT_DOMAIN: $tenantDomain"
    } catch { Write-Host "ERROR: $($_.Exception.Message)" }
}
if ($Action -eq "Logout") {
    try {
        Disconnect-MicrosoftTeams -ErrorAction SilentlyContinue
        Write-Host "SUCCESS: Disconnected"
    } catch { Write-Host "ERROR: $($_.Exception.Message)" }
}
if ($Action -eq "BulkSync") {
    $UserData = $JsonData | ConvertFrom-Json
    Connect-MicrosoftTeams 
    Write-Host "Processing $($UserData.Count) records..."
}
"""

def execute_embedded_ps(df, action="BulkSync"):
    json_payload = df[['UserPrincipalName', 'TeamsVoicePhoneNumber']].to_json(orient='records') if (action == "BulkSync" and df is not None) else ""
    with tempfile.NamedTemporaryFile(suffix=".ps1", delete=False, mode='w', encoding='utf-8') as tmp:
        tmp.write(PS_TEMPLATE)
        tmp_path = tmp.name
    try:
        cmd = ["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", tmp_path, "-Action", action, "-JsonData", json_payload]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)
        st.info(f"PowerShell Action '{action}' started...")
        log_area = st.empty()
        full_log = ""
        for line in iter(process.stdout.readline, ""):
            full_log += line
            log_area.code(full_log)
        process.wait()
        return process.returncode, full_log
    except Exception as e:
        st.error(f"Execution Error: {str(e)}")
        return 1, str(e)
    finally:
        if os.path.exists(tmp_path): os.remove(tmp_path)

# --- Sidebar Content ---
with st.sidebar:
    st.header("Upload & Tools")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    if st.button("🔄 Clear All Caches", use_container_width=True):
        for key in ["customer_cache", "raw_domains", "current_customer_id", "api_token", "api_debug_log", "address_data", "teams_authenticated", "connected_tenant"]:
            if key in st.session_state: del st.session_state[key]
        st.rerun()
    st.divider()
    st.header("🪟 API Debug Console")
    if "api_debug_log" in st.session_state:
        log = st.session_state["api_debug_log"]
        st.write(f"**Method:** {log['Method']} | **Status:** {log['Status']}")
        st.text_area("Response Body:", value=log['Body'], height=300)
    else: st.info("No API calls made yet.")

# --- Main Application Layout ---
st.title("NWN Collaboration Team iPilot & Teams Provisioning")

# Define Panes
top_pane = st.container()
st.divider()
bottom_pane = st.container()

with top_pane:
    left_col, right_col = st.columns(2)

    # --- TOP LEFT: iPilot Pane ---
    with left_col:
        st.subheader("🌐 iPilot Connection")
        if "api_token" not in st.session_state:
            if st.button("🔑 Connect to iPilot", use_container_width=True): login_dialog()
        else:
            if "customer_cache" not in st.session_state:
                with st.spinner("Building Customer Cache..."):
                    st.session_state["customer_cache"] = get_all_customers()
            
            customers = st.session_state.get("customer_cache", [])
            selected_customer = st.selectbox("Select Customer:", options=customers, format_func=lambda x: f"{x['companyName']} (ID: {x['accountId']})")
            
            if selected_customer:
                target_id = selected_customer['accountId']
                if st.session_state.get("current_customer_id") != target_id:
                    with st.spinner("Fetching Metadata..."):
                        fetch_customer_metadata(target_id)
                        st.session_state["current_customer_id"] = target_id

                domain_mapping = {}
                for d in st.session_state.get("raw_domains", []):
                    if is_valid_uuid(d): domain_mapping["Operator Connect"] = d
                    else: domain_mapping["DRaaS"] = d
                
                if domain_mapping:
                    conn_type = st.selectbox("Connection Type:", options=list(domain_mapping.keys()))
                    selected_domain = domain_mapping[conn_type]
                else:
                    st.warning("No compatible domains found.")
                    selected_domain = None

                # Downloads
                d_col1, d_col2 = st.columns(2)
                template_df = pd.DataFrame(columns=EXPECTED_COLUMNS)
                d_col1.download_button(label="📥 Blank Template", data=template_df.to_csv(index=False).encode('utf-8'), file_name="Template.csv", use_container_width=True)
                addr_list = st.session_state.get("address_data", [])
                if addr_list:
                    d_col2.download_button(label="📖 Address Ref", data=pd.DataFrame(addr_list).to_csv(index=False).encode('utf-8'), file_name="Addresses.csv", use_container_width=True)
                else:
                    d_col2.button("📖 No Addresses", disabled=True, use_container_width=True)

    # --- TOP RIGHT: Teams Pane ---
    with right_col:
        st.subheader("🖥️ Teams Management")
        if "teams_module_installed" not in st.session_state:
            has_mod, mod_msg = check_teams_module()
            st.session_state["teams_module_installed"] = has_mod
        
        if st.session_state.get("teams_module_installed"):
            if "teams_authenticated" not in st.session_state:
                if st.button("🔑 Connect to Microsoft Teams", use_container_width=True):
                    code, log = execute_embedded_ps(None, action="Login")
                    if "SUCCESS" in log:
                        st.session_state["teams_authenticated"] = True
                        match = re.search(r"TENANT_DOMAIN:\s+(\S+)", log)
                        st.session_state["connected_tenant"] = match.group(1) if match else "Unknown Domain"
                        st.rerun()
                    else: st.error("Auth Failed")
            else:
                tenant_name = st.session_state.get("connected_tenant", "Unknown Tenant")
                st.success(f"✅ Connected to: **{tenant_name}**")
                
                if st.button("🔌 Disconnect", use_container_width=True):
                    execute_embedded_ps(None, action="Logout")
                    for key in ["teams_authenticated", "connected_tenant"]:
                        if key in st.session_state: del st.session_state[key]
                    st.rerun()
                
                st.divider()
                if st.button("🚀 Execute Teams Bulk Assignment", type="primary", use_container_width=True):
                    if "current_df" in st.session_state:
                        execute_embedded_ps(st.session_state["current_df"], action="BulkSync")
                    else: st.error("Please upload and validate a CSV first.")
        else: st.error("Teams Module not found.")

# --- BOTTOM PANE: Data Validation Grid ---
with bottom_pane:
    st.subheader("📊 Data Validation Grid")
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
            st.session_state["current_df"] = df
            st.dataframe(df.style.map(lambda v: f'color: {"red" if v != "Valid" else "green"}', subset=['ValidationStatus']), use_container_width=True)
            
            if (df['ValidationStatus'] == 'Valid').all():
                st.success("CSV Validated. You can now execute Teams or iPilot syncs.")
                if st.button("🚀 Start iPilot Bulk Sync"):
                    # iPilot Sync logic...
                    results = []
                    domain_count = len(st.session_state.get("raw_domains", []))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                        future_to_user = {executor.submit(send_sync_request, row, st.session_state["current_customer_id"], selected_domain, conn_type, domain_count, st.session_state["api_token"]): row for _, row in df.iterrows()}
                        for future in concurrent.futures.as_completed(future_to_user): results.append(future.result())
                    st.write(pd.DataFrame(results))
        else: st.error(f"Missing Columns: {EXPECTED_COLUMNS}")
    else: st.info("Upload a CSV file in the sidebar to populate the grid.")