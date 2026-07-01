import pandas as pd
import plotly.express as px
import streamlit as st


def read_csv(uploaded_file, **read_options) -> pd.DataFrame:
    """Read an uploaded file from the beginning with the given Pandas options."""
    uploaded_file.seek(0)
    return pd.read_csv(uploaded_file, **read_options)


def preview_file(uploaded_file, max_characters: int = 1000) -> str:
    """Return a short text preview without permanently consuming the upload."""
    uploaded_file.seek(0)
    preview = uploaded_file.read(max_characters).decode("utf-8", errors="replace")
    uploaded_file.seek(0)
    return preview


def load_csv(uploaded_file) -> pd.DataFrame:
    """Read an uploaded CSV file into a pandas DataFrame."""
    try:
        return read_csv(uploaded_file)
    except pd.errors.ParserError:
        return read_csv(uploaded_file, engine="python", on_bad_lines="skip")


def get_numeric_columns(data: pd.DataFrame) -> list[str]:
    """Return columns that Pandas recognizes as numeric."""
    return data.select_dtypes(include="number").columns.tolist()


def show_chart_builder(data: pd.DataFrame) -> None:
    """Display controls for building a simple Plotly chart."""
    numeric_columns = get_numeric_columns(data)

    st.write("Graph preview")

    if len(numeric_columns) < 2:
        st.info("At least two numeric columns are needed to create a graph.")
        return

    x_axis = st.selectbox("X-axis", numeric_columns)
    y_axis = st.selectbox(
        "Y-axis",
        numeric_columns,
        index=1 if len(numeric_columns) > 1 else 0,
    )

    chart = px.scatter(
        data,
        x=x_axis,
        y=y_axis,
        title=f"{y_axis} vs {x_axis}",
        template="plotly_white",
    )
    chart.update_traces(marker={"size": 8, "opacity": 0.75})
    chart.update_layout(title_x=0.02)

    st.plotly_chart(chart, use_container_width=True)


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
    except pd.errors.ParserError as error:
        st.error("Pandas could not parse this CSV.")
        st.write("Parser details:")
        st.code(str(error))
        st.write("Raw file preview:")
        st.code(preview_file(uploaded_file))
        st.info(
            "CSV files from lab instruments sometimes contain metadata rows, "
            "multiple tables, or inconsistent columns. The preview above helps "
            "us see what Pandas is trying to read."
        )
        return

    if data.empty:
        st.warning("The CSV loaded, but Pandas did not find any rows to display.")
        return

    st.caption(f"Loaded {data.shape[0]} rows and {data.shape[1]} columns.")
    st.write("Uploaded data preview")
    st.dataframe(data, use_container_width=True)
    show_chart_builder(data)


if __name__ == "__main__":
    main()
