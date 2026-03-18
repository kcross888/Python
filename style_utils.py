import streamlit as st
import base64

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

def add_sidebar_logo(logo_path="assets/NWN-Logo_No-Tagline_Horizonal_RGB_Orange-and-Navy.png"):
    """
    Adds a logo to the top of the sidebar and 
    adjusts padding so it doesn't look cramped.
    """
    # 1. Display the image in the sidebar
    st.sidebar.image(logo_path, use_container_width=True)
    
    # 2. Add some CSS to pull the logo to the very top and 
    # fix the spacing between the logo and the navigation links.
    st.sidebar.markdown(
        """
        <style>
            /* Targets the sidebar content area */
            [data-testid="stSidebarNav"] {
                padding-top: 0rem !important;
            }
            /* Adds a nice divider under the logo */
            [data-testid="stSidebar"] img {
                margin-bottom: 20px;
                border-bottom: 1px solid #31333f;
                padding-bottom: 20px;
            }
        </style>
        """,
        unsafe_allow_html=True
    )