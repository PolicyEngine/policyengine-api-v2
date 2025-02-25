import streamlit as st
import requests

EXAMPLE_PARAMS = {
    "scope": "household",
    "country": "uk",
    "data": {
        "employment_income": {
            2025: 30_000,
        }
    },
}

st.json(EXAMPLE_PARAMS)
if st.button("Submit"):
    requests.post("http://localhost:8000/job", json=EXAMPLE_PARAMS)


if st.button("Get first job"):
    st.json(requests.get("http://localhost:8000/job/1").json())
