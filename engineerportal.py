import streamlit as st
from style_utils import inject_custom_nwn_css, add_sidebar_logo

# This must be the first Streamlit command on the page
st.set_page_config(page_title="NWN Portal", layout="wide")

# Inject the shared styles
inject_custom_nwn_css()
add_sidebar_logo()

st.title("🛠️ NWN Collaboration Engineer Portal")
st.write("Centralized access for Teams Voice and iPilot automation tools.")

col1, col2, col3 = st.columns(3)

with col1:
    st.info("### Bulk Provisioning")
    st.write("Bulk provisioning for Operator Connect and DRaaS.")
    if st.button("Launch Bulk Provisioning", key="btn_bulkprovisioning"):
        st.switch_page("pages/bulkvoiceactivation.py")

with col2:
    st.success("### Tenant Auditor")
    st.write("Check Teams Voice policies and user licensing.")
    st.link_button("Open Tool", "http://localhost:8503")

with col3:
    st.warning("### E911 Manager")
    st.write("Verify Kari's Law / Ray Baum compliance.")
    st.link_button("Open Tool", "http://localhost:8504")