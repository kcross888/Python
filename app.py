import streamlit as st
import pandas as pd
from io import BytesIO

# 1. THE INTERNAL MASTER DATA
# PHASE | ITEM | CATEGORY | TASK | OWNER
raw_task_data = [
    ["Discovery, Planning, Design", "Base Discovery", "Standard", "Identify Network Topology", "Network Eng"],
    ["Discovery, Planning, Design", "Base Discovery", "Standard", "Review M365 Licensing Status", "Admin"],
    ["Discovery, Planning, Design", "Paging Systems", "Paging", "Audit Analog Paging Controllers", "Voice Eng"],
    ["Discovery, Planning, Design", "Contact Center", "Contact Center", "Review Existing Queue Logic", "BA"],
    
    ["Configuration", "Core Voice", "Standard", "Configure Emergency Routing Policies", "Voice Eng"],
    ["Configuration", "Core Voice", "Standard", "Set up Tenant Dial Plans", "Voice Eng"],
    ["Configuration", "Paging Integration", "Paging", "Configure ATA/Gateway in Teams", "Voice Eng"],
    ["Configuration", "Paging Integration", "Paging", "Test Analog Port Paging", "Field Tech"],
    ["Configuration", "Auto Attendants", "Standard", "Build AA Menu Navigation", "Voice Eng"],
    
    ["Implementation", "User Migration", "Standard", "Assign Phone Numbers to Users", "Admin"],
    ["Implementation", "User Migration", "Standard", "Distribute User Training Manuals", "PM"],
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
# Only show if 'Standard' is enabled, as porting is a core voice function
if enabled_categories.get("Standard", True):
    st.sidebar.divider()
    st.sidebar.header("🚛 Porting Logistics")
    port_count = st.sidebar.number_input("Number of Porting Events", min_value=0, max_value=10, value=1)
    
    if port_count > 0:
        for i in range(1, port_count + 1):
            event_name = f"Porting Event {i}"
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Standard", "Task": f"Submit LOA/FOC for {event_name}", "Owner": "Carrier Lead"})
            selected_tasks.append({"Phase": "Implementation", "Item": event_name, "Category": "Standard", "Task": f"Execution/Cutover for {event_name}", "Owner": "Voice Eng"})

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