import streamlit as st

def add_sidebar_logo(logo_path="assets/NWN-Logo_No-Tagline_Horizonal_RGB_Orange-and-Navy.png"):
    """
    Adds a logo to the top of the sidebar and 
    adjusts padding so it doesn't look cramped.
    """
    # 1. Display the image in the sidebar
    st.logo(image=logo_path, icon_image=None, size="large")

def inject_custom_nwn_css():
    st.markdown(
        """
        <style>
        /* Global Font Adjustments */
        html, body, [class*="css"] {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        /* Standardize Text Area for Logs */
        div[data-baseweb="textarea"] textarea {
            font-size: 14px !important;
            font-family: 'Courier New', Courier, monospace !important;
        }

        /* Custom Sidebar Styling */
        section[data-testid="stSidebar"] {
            border-right: 1px solid #31333f;
        }
        
        /* Make Metric Labels Pop */
        [data-testid="stMetricLabel"] {
            font-weight: bold;
            text-transform: uppercase;
            color: #888;
        }
        </style>
        """,
        unsafe_allow_html=True
    )