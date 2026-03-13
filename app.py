import streamlit as st
import pandas as pd
from io import BytesIO

# https://673szt68ypq4sugnzq8vbr.streamlit.app/

# 1. THE INTERNAL MASTER DATA
# PHASE | ITEM | CATEGORY | TASK | OWNER
raw_task_data = [
    ["Initiation", "Project Onboading", "Standard", "Engineer Review of SOW", "Lead Engineer"],
    ["Initiation", "Project Onboarding", "Standard", "Internal Kickoff Call", "PM"],
    ["Initiation", "Project Onboarding", "Standard", "Client Kickoff Call", "PM"],
    ["Initiation", "Customer Onboarding", "Operator Connect", "Enable NWN as Operator Connect provider", "Customer"],
    ["Initiation", "Customer Onboarding", "DRaaS", "NWN Integration through App Auth", "Customer"],
    ["Discovery, Planning, Design", "Discovery", "Standard", "Initial Discovery Meeting with Customer", "PM"],
    ["Discovery, Planning, Design", "Discovery", "Voice Config", "NWN Access", "Customer"],
    ["Discovery, Planning, Design", "Discovery", "Voice Config", "Phone Number Migration - High Level", "Lead Engineer"],
    ["Discovery, Planning, Design", "Discovery", "Voice Config", "Dialing Pattern Requirements", "Lead Engineer"],
    ["Discovery, Planning, Design", "Discovery", "Voice Config", "Routing Requirements (Intl, Domestic, etc)", "Lead Engineer"],
    ["Discovery, Planning, Design", "Discovery", "Paging", "Paging - OHP", "Lead Engineer"],
    ["Discovery, Planning, Design", "Discovery", "Paging", "Paging - Phone Paging", "Lead Engineer"],
    ["Discovery, Planning, Design", "Discovery", "Faxing", "Faxing (ATA vs Cloud vs other)", "Lead Engineer"],
    ["Discovery, Planning, Design", "Discovery", "Analog", "Call buttons, POTS lines, PLARs", "Lead Engineer"],
    ["Discovery, Planning, Design", "Data Collection", "Voice Config", "User Template (DIDs and UPNs, Shared Lines, etc)", "Lead Engineer"],
    ["Discovery, Planning, Design", "Data Collection", "Voice Config", "E911 Template", "Lead Engineer"],
    ["Discovery, Planning, Design", "Data Collection", "Voice Config", "AA/CQ Template", "Lead Engineer"],
    ["Discovery, Planning, Design", "Data Collection", "Analog", "ATA Zero Touch Config Template", "Lead Engineer"],
    ["Discovery, Planning, Design", "Planning", "Voice Config", "Migration Waves & Port Events", "SOW"],
    ["Discovery, Planning, Design", "Planning", "Voice Config", "Licensing Procurement", "Customer"],
    ["Discovery, Planning, Design", "Planning", "Voice Config", "Handset Procurement", "Customer"],
    ["Discovery, Planning, Design", "Planning", "Analog", "ATA Procurement", "Customer"],
    ["Discovery, Planning, Design", "Planning", "Direct Routing", "SBC Procurement", "Customer"],
    ["Discovery, Planning, Design", "Planning", "Paging", "Paging Adapter Procurement", "Customer"],
    ["Discovery, Planning, Design", "Design", "Paging", "Paging - OHP", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Paging", "Paging - Phone Paging", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Faxing", "Faxing (ATA vs Cloud vs other)", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Analog", "Call buttons, POTS lines, PLARs", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Voice Config", "E911 Finalization", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Voice Config", "AA/CQ Finalization", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Voice Config", "Shared Lines Finalization", "Lead Engineer"],
    ["Discovery, Planning, Design", "Design", "Voice Config", "User and Shared Device Finalization", "Lead Engineer"],
    ["Staging and Configuration", "Staging", "Licensing", "User Licenses Procured", "Customer"],
    ["Staging and Configuration", "Staging", "Licensing", "Shared Device Licenses Procured", "Customer"],
    ["Staging and Configuration", "Staging", "Licensing", "Resource Account Licenses Procured", "Customer"],
    ["Staging and Configuration", "Staging", "Licensing", "Teams Premium Licenses Procured", "Customer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "Shared Device Accounts Created", "Lead Engineer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "Resource Accounts Created", "Lead Engineer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "M365 Groups Created (CQ's, VM, etc)", "Lead Engineer"],
    ["Staging and Configuration", "Staging", "Analog", "ATA Connected", "Customer"],
    ["Staging and Configuration", "Staging", "Operator Connect", "iPilot Test Numbers provisioned", "Lead Engineer"],
    ["Staging and Configuration", "Staging", "DRaaS", "iPilot Test Numbers provisioned", "Lead Engineer"],
    ["Staging and Configuration", "Staging", "Voice Config", "Pilot group identified", "Customer"],
    ["Staging and Configuration", "Staging", "Direct Routing", "SBC Connected", "Customer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "Pilot group configured with Teams Voice", "Lead Engineer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "E911 Configured", "Lead Engineer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "Auto attendants configured", "Lead Engineer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "Call queues configured", "Lead Engineer"],
    ["Staging and Configuration", "Configuration", "Voice Config", "Dial Plans configured (if required)", "Lead Engineer"],
    ["Testing and Validation (Operational Readiness)", "Testing", "Standard", "Test Plan Executed", "Voice Eng"],
    ["Testing and Validation (Operational Readiness)", "Testing", "Standard", "Test Failures Remediated or identified and communicated", "Voice Eng"],
    ["Implementation", "User Readiness", "Standard", "User Communication and Training has been delivered or scheduled", "Customer"],
]

# Function to transform the flat list into the nested format
def get_nested_data(data_list):
    nested = {}
    for phase, item, cat, task, owner in data_list:
        if phase not in nested:
            nested[phase] = {}
        if item not in nested[phase]:
            nested[phase][item] = []
        nested[phase][item].append({"Task": task, "Owner": owner, "Category": cat})
    return nested

master_data = get_nested_data(raw_task_data)

# --- STREAMLIT UI ---
st.set_page_config(page_title="Teams Voice Scoper", layout="wide")
st.title("📞 Teams Voice Project Scoper")

# 2. GLOBAL CATEGORY FILTERS
st.sidebar.header("🌍 Global Category Filter")
unique_cats = sorted(list(set(row[2] for row in raw_task_data)))
enabled_categories = {}

for cat in unique_cats:
    enabled_categories[cat] = st.sidebar.toggle(f"Include {cat}", value=True)

st.sidebar.divider()

# 3. PHASE & ITEM FILTERS
st.sidebar.header("📂 Phase & Item Detail")
selected_tasks = []

for phase, items in master_data.items():
    with st.sidebar.expander(f"{phase}", expanded=True):
        for item_name, tasks in items.items():
            # Check if any tasks in this item belong to an enabled category
            item_cats = set(t['Category'] for t in tasks)
            if any(enabled_categories.get(c) for c in item_cats):
                is_item_in_scope = st.checkbox(item_name, value=True, key=f"chk_{phase}_{item_name}")
                
                if is_item_in_scope:
                    for task in tasks:
                        if enabled_categories.get(task['Category']):
                            new_task = task.copy()
                            new_task.update({"Phase": phase, "Item": item_name})
                            selected_tasks.append(new_task)

# --- 4. PORTING EVENTS LOGIC (Re-added) ---
# Only show if 'Voice Config' is enabled, as porting is a core voice function
if enabled_categories.get("Voice Config", True):
    st.sidebar.divider()
    st.sidebar.header("🚛 Porting Logistics")
    port_count = st.sidebar.number_input("Number of Porting Events", min_value=0, max_value=20, value=1)
    
    if port_count > 0:
        for i in range(1, port_count + 1):
            event_name = f"Porting Event {i}"
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Voice Config", "Task": f"Submit LOA/FOC for {event_name}", "Owner": "Carrier Lead"})
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Voice Config", "Task": f"Execution/Cutover for {event_name}", "Owner": "Voice Eng"})
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Voice Config", "Task": f"Execution/Cutover for {event_name}", "Owner": "Voice Eng"})
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Voice Config", "Task": f"iPilot Call Path Update for {event_name}", "Owner": "Voice Eng"})
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Voice Config", "Task": f"FreeCallerRegistry Update for {event_name}", "Owner": "Voice Eng"})
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Voice Config", "Task": f"D911 iPilot Update for {event_name}", "Owner": "Voice Eng"})

# --- 5. PREVIEW & EXPORT ---
df = pd.DataFrame(selected_tasks)

if not df.empty:
    # Column ordering for the final output
    df = df[["Phase", "Item", "Category", "Task", "Owner"]]
    st.subheader("Project Scope Preview")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Excel Generation
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='ProjectPlan', index=False, startrow=1, header=False)
        workbook, worksheet = writer.book, writer.sheets['ProjectPlan']
        
        # Formatting
        hdr_fmt = workbook.add_format({'bold': True, 'fg_color': '#4472C4', 'font_color': 'white', 'border': 1})
        (max_row, max_col) = df.shape
        
        # Create Table
        worksheet.add_table(0, 0, max_row, max_col - 1, {
            'columns': [{'header': col, 'header_format': hdr_fmt} for col in df.columns],
            'style': 'Table Style Medium 9'
        })
        
        # Add Status Column for the end user
        worksheet.write(0, max_col, "Status", hdr_fmt)
        worksheet.data_validation(1, max_col, max_row, max_col, {
            'validate': 'list', 
            'source': ['To Do', 'In Progress', 'Done', 'Blocked', 'N/A']
        })
        
        # Final formatting
        worksheet.autofit()
        worksheet.set_column(3, 3, 50) # Extra width for Task description
        worksheet.freeze_panes(1, 0)

    st.download_button(
        label="📥 Download Excel Checklist",
        data=output.getvalue(),
        file_name="Teams_Voice_Migration_Plan.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.warning("No tasks match the current filters. Check your sidebar toggles.")