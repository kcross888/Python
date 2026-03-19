import streamlit as st
from style_utils import add_sidebar_logo, inject_custom_nwn_css

# This must be the first Streamlit command on the page
st.set_page_config(page_title="NWN Portal", layout="wide")

add_sidebar_logo()
inject_custom_nwn_css()

st.title("🛠️ NWN Collaboration Engineer Portal")
st.write("Centralized access for Teams Voice and iPilot automation tools.")

col1, col2, col3 = st.columns(3)

with col1:
    st.info("### Project Task List Generator")
    st.write("Generate task lists for project management.")
    if st.button("Launch Task List Generator", key="btn_tasklist"):
        st.switch_page("pages/01_Project_Task_List_Generator.py")

with col2:
    st.info("### Bulk Provisioning")
    st.write("Bulk provisioning for Operator Connect and DRaaS.")
    if st.button("Launch Bulk Provisioning", key="btn_bulkprovisioning"):
        st.switch_page("pages/02_Bulk_Voice_Activation.py")

with col3:
    st.warning("### E911 Manager")
    st.write("Verify Kari's Law / Ray Baum compliance.")
    st.link_button("Open Tool", "http://localhost:8504")