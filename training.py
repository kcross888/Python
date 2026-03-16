import streamlit as st
import pandas as pd

# 1. Create a label/header
st.title("My First Streamlit App")
st.write("Click the button below to upload and view a file.")

# 2. Create the file uploader (the "button" that opens a file)
uploaded_file = st.file_uploader("Choose a CSV file", type="csv")

# 3. Logic to handle the file once it is uploaded
if uploaded_file is not None:
    # Read the file using Pandas
    df = pd.read_csv(uploaded_file)
    
    # Display a success message
    st.success("File uploaded successfully!")
    
    # Show the data in a table
    st.subheader("Data Preview:")
    st.dataframe(df)