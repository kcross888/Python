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

def parse_ipilot_response(resp_text):
    """Parses raw response text using validated nested logic for iPilot responses."""
    try:
        if not resp_text:
            return 500, "Empty response from API"

        # Ensure we are working with a dictionary
        data = json.loads(resp_text) if isinstance(resp_text, str) else resp_text
        
        # 1. Get the nested status (statusCode), defaulting to 200
        inner_status = data.get("statusCode", 200) 
        
        # 2. Extract the message from errors or status key
        msg = data.get("errors", {}).get("message") or data.get("status", "Operation Successful")
        
        # 3. Handle the 'invalid_numbers' map if present
        invalid_map = data.get("data", {}).get("invalid_numbers", {})
        if invalid_map:
            details = " | ".join([f"{num}: {reason}" for num, reason in invalid_map.items()])
            msg = f"{msg} ({details})"
            
        # 4. Return the status as an int and the formatted message
        # Added a safe-guard just in case 'inner_status' isn't a clean number
        try:
            return int(inner_status), msg
        except (ValueError, TypeError):
            return 400, f"{inner_status} | {msg}"
            
    except json.JSONDecodeError:
        return 200, "Response received, but body was not in JSON format."
    except Exception as e:
        return 500, f"Parsing Error: {str(e)}"

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
    
    if st.button("Login", width="stretch"):
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
    
    # Domains
    d_url = f"https://api.nuwave.com/v1/msteams?instance=carousel&customerId={target_id}"
    try:
        d_res = requests.get(d_url, headers=headers, timeout=10)
        log_api_call("GET", d_url, d_res)
        resp_json = d_res.json()
        st.session_state["raw_domains"] = resp_json[0].get("domains", []) if isinstance(resp_json, list) and resp_json else []
    except:
        st.session_state["raw_domains"] = []

    # Addresses
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
    st.title("Engineer Dashboard")
    st.header("📍 Session Context")
    
    # Context Labels
    ipilot_cust = st.session_state.get("selected_customer_name", "None Selected")
    ipilot_dom = st.session_state.get("active_conn_type", "None Selected")
    teams_tenant = st.session_state.get("connected_tenant", "Disconnected")
    
    st.markdown(f"**iPilot Customer:** `{ipilot_cust}`")
    st.markdown(f"**iPilot Domain:** `{ipilot_dom}`")
    st.markdown(f"**Teams Tenant:** `{teams_tenant}`")
    st.divider()

    st.header("Upload & Tools")
    uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
    if st.button("🔄 Clear All Caches", width="stretch"):
        for key in ["customer_cache", "raw_domains", "current_customer_id", "api_token", "api_debug_log", 
                    "address_data", "teams_authenticated", "connected_tenant", "selected_customer_name", 
                    "active_conn_type", "active_domain_val"]:
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

top_pane = st.container()
st.divider()
bottom_pane = st.container()

with top_pane:
    left_col, right_col = st.columns(2)

    # --- TOP LEFT: iPilot Pane ---
    with left_col:
        st.subheader("🌐 iPilot Connection")
        if "api_token" not in st.session_state:
            if st.button("🔑 Connect to iPilot", width="stretch"): login_dialog()
        else:
            if "customer_cache" not in st.session_state:
                with st.spinner("Building Customer Cache..."):
                    st.session_state["customer_cache"] = get_all_customers()
            
            customers = st.session_state.get("customer_cache", [])
            selected_customer = st.selectbox("Select Customer:", options=customers, format_func=lambda x: f"{x['companyName']} (ID: {x['accountId']})")
            
            if selected_customer:
                target_id = selected_customer['accountId']
                
                # Metadata Fetch & Context Update
                if st.session_state.get("current_customer_id") != target_id:
                    with st.spinner("Fetching Metadata..."):
                        fetch_customer_metadata(target_id)
                        st.session_state["current_customer_id"] = target_id
                        st.session_state["selected_customer_name"] = selected_customer['companyName']
                        
                        domain_mapping = {}
                        for d in st.session_state.get("raw_domains", []):
                            if is_valid_uuid(d): domain_mapping["Operator Connect"] = d
                            else: domain_mapping["DRaaS"] = d
                        
                        if len(domain_mapping) == 1:
                            conn_type = list(domain_mapping.keys())[0]
                            st.session_state["active_conn_type"] = conn_type
                            st.session_state["active_domain_val"] = domain_mapping[conn_type]
                        
                        st.rerun()
                
                domain_mapping = {}
                for d in st.session_state.get("raw_domains", []):
                    if is_valid_uuid(d): domain_mapping["Operator Connect"] = d
                    else: domain_mapping["DRaaS"] = d
                
                if domain_mapping:
                    options = list(domain_mapping.keys())
                    if len(options) > 1:
                        choice = st.selectbox("Connection Type:", options=options)
                        if st.session_state.get("active_conn_type") != choice:
                            st.session_state["active_conn_type"] = choice
                            st.session_state["active_domain_val"] = domain_mapping[choice]
                            st.rerun()
                    else:
                        st.info(f"Using Domain: **{st.session_state.get('active_conn_type')}**")
                else:
                    st.warning("No compatible domains found.")

                # Downloads
                d_col1, d_col2 = st.columns(2)
                template_df = pd.DataFrame(columns=EXPECTED_COLUMNS)
                d_col1.download_button(label="📥 Blank Template", data=template_df.to_csv(index=False).encode('utf-8'), file_name="Template.csv", width="stretch")
                addr_list = st.session_state.get("address_data", [])
                if addr_list:
                    d_col2.download_button(label="📖 Address Ref", data=pd.DataFrame(addr_list).to_csv(index=False).encode('utf-8'), file_name="Addresses.csv", width="stretch")
                else:
                    d_col2.button("📖 No Addresses", disabled=True, width="stretch")

    # --- TOP RIGHT: Teams Pane ---
    with right_col:
        st.subheader("🖥️ Teams Management")
        if "teams_module_installed" not in st.session_state:
            has_mod, _ = check_teams_module()
            st.session_state["teams_module_installed"] = has_mod
        
        if st.session_state.get("teams_module_installed"):
            if "teams_authenticated" not in st.session_state:
                if st.button("🔑 Connect to Microsoft Teams", width="stretch"):
                    code, log = execute_embedded_ps(None, action="Login")
                    if "SUCCESS" in log:
                        st.session_state["teams_authenticated"] = True
                        match = re.search(r"TENANT_DOMAIN:\s+(\S+)", log)
                        st.session_state["connected_tenant"] = match.group(1) if match else "Unknown Domain"
                        st.rerun()
                    else: st.error("Auth Failed")
            else:
                st.success(f"✅ Connected to: **{st.session_state.get('connected_tenant')}**")
                if st.button("🔌 Disconnect", width="stretch"):
                    execute_embedded_ps(None, action="Logout")
                    for key in ["teams_authenticated", "connected_tenant"]:
                        if key in st.session_state: del st.session_state[key]
                    st.rerun()
        else: st.error("Teams Module not found.")

# --- BOTTOM PANE: Data Validation Grid ---
with bottom_pane:
    st.subheader("📊 Data Validation Grid")
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file)
        if set(EXPECTED_COLUMNS).issubset(df.columns):
            errors = [", ".join(filter(None, [
                "Invalid GUID" if not is_valid_uuid(r['civicAddressId']) else None,
                "Invalid Email" if not is_valid_email(r['UserPrincipalName']) else None,
                "Phone < 10 digits" if not is_valid_phone(r['TeamsVoicePhoneNumber']) else None,
                "Invalid Account Type" if not is_valid_account(r['TypeofAccount']) else None
            ])) or "Valid" for _, r in df.iterrows()]
            
            df['ValidationStatus'] = errors
            st.session_state["current_df"] = df
            st.dataframe(df.style.map(lambda v: f'color: {"red" if v != "Valid" else "green"}', subset=['ValidationStatus']), width="stretch")
            
            if (df['ValidationStatus'] == 'Valid').all():
                st.success(f"🎉 Ready to sync {len(df)} users.")
                exec_col1, exec_col2 = st.columns(2)
                
                with exec_col1:
                    st.write("### iPilot Action")
                    active_domain = st.session_state.get("active_domain_val")
                    active_type = st.session_state.get("active_conn_type")
                    
                    if "api_token" in st.session_state and active_domain:
                        if st.button("🚀 Start iPilot Bulk Sync", width="stretch"):
                            results = []
                            domain_count = len(st.session_state.get("raw_domains", []))
                            
                            status_msg = st.empty()
                            progress_bar = st.progress(0)
                            status_msg.info(f"🚀 Initializing parallel sync for {len(df)} users...")
                            
                            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                                future_to_user = {
                                    executor.submit(
                                        send_sync_request, 
                                        row, 
                                        st.session_state["current_customer_id"], 
                                        active_domain, 
                                        active_type, 
                                        domain_count, 
                                        st.session_state["api_token"]
                                    ): row for _, row in df.iterrows()
                                }

                                for i, future in enumerate(concurrent.futures.as_completed(future_to_user)):
                                    results.append(future.result())
                                    progress_bar.progress((i + 1) / len(df))
                                    status_msg.info(f"Processing... Completed {i+1} of {len(df)}")

                            # Create Log & Review UI
                            results_df = pd.DataFrame(results)
                            log_content = "IPILOT BULK SYNC LOG\n" + "="*30 + "\n"
                            final_success_count = 0
                            final_fail_count = 0

                            # --- Color coding for HTML Log ---
                            log_html = """
                            <div style="background-color: #0e1117; color: #d1d1d1; padding: 10px; border-radius: 5px; 
                                        font-family: 'Courier New', Courier, monospace; font-size: 14px; 
                                        height: 300px; overflow-y: scroll; border: 1px solid #31333f;">
                                <strong style="color: #fafafa;">IPILOT BULK SYNC LOG</strong><br>
                                <hr style="border: 0.5px solid #31333f;">
                            """

                            for _, r in results_df.iterrows():
                                actual_code, clean_msg = parse_ipilot_response(r['Response'])
                                if actual_code in [200, 201, 202]:
                                    display_status = "Success"
                                    color = "#28a745" # Green
                                    final_success_count += 1
                                else:
                                    display_status = "Failed"
                                    color = "#ff4b4b" # Red
                                    final_fail_count += 1
                                log_html += f'<span style="color: {color};">[{display_status}]</span> {r["User"]} | ' \
                                            f'Code: {actual_code} | Reason: {clean_msg}<br>'
                            log_html += "</div>"

                            status_msg.success("✅ Sync Operation Complete")
                            st.divider()
                            st.subheader("📋 Provisioning Results")
                            # Display the custom scrollable HTML log
                            st.markdown(log_html, unsafe_allow_html=True)
                            
                            st.download_button(
                                label="💾 Download Sync Log",
                                data=log_content,
                                file_name=f"SyncLog_{st.session_state.get('selected_customer_name')}.txt",
                                mime='text/plain',
                                width="stretch"
                            )
                            
                            c1, c2 = st.columns(2)
                            c1.metric("Success", final_success_count)
                            c2.metric("Failed/Error", final_fail_count, delta_color="inverse")

                            if final_fail_count == 0:
                                st.balloons()
                    else: st.warning("Connect iPilot and select a domain first.")

                with exec_col2:
                    st.write("### Microsoft Teams Action")
                    if st.session_state.get("teams_authenticated"):
                        if st.button("🚀 Execute Teams Bulk Assignment", type="primary", width="stretch"):
                            execute_embedded_ps(st.session_state["current_df"], action="BulkSync")
                    else: st.warning("Connect to Microsoft Teams first.")
        else: st.error(f"Missing Columns: {EXPECTED_COLUMNS}")
    else: st.info("Upload a CSV file in the sidebar to populate the grid.")