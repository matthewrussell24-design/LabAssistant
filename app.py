import pandas as pd
import streamlit as st


def load_csv(uploaded_file) -> pd.DataFrame:
    """Read an uploaded CSV file into a pandas DataFrame."""
    return pd.read_csv(uploaded_file)


def main() -> None:
    st.title("LabAssistant")
    st.subheader("DLS Data Explorer")

    uploaded_file = st.file_uploader("Upload a CSV file", type=["csv"])

    if uploaded_file is None:
        st.info("Upload a CSV file to preview its contents.")
        return

    try:
        data = load_csv(uploaded_file)
    except pd.errors.EmptyDataError:
        st.error("This CSV appears to be empty. Please upload a file with data.")
        return
    except pd.errors.ParserError:
        st.error("Pandas could not parse this CSV. Please check the file format.")
        return

    st.write("Uploaded data preview")
    st.dataframe(data, use_container_width=True)


if __name__ == "__main__":
    main()

