import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Nutrigenomics GraphRAG", layout="wide")

st.title("Nutrigenomics GraphRAG MVP")
st.caption("SNP → Gene → Trait → Nutrient → Food graph reasoning demo")

DEMO_QUESTIONS = [
    "What foods may support rs1801133 related folate metabolism risk?",
    "Which nutrients are connected to glucose metabolism?",
    "What is the graph path between MTHFR and cardiovascular risk?",
    "Which biomarkers are connected to folate metabolism?",
    "Which foods contain nutrients linked with lipid metabolism?",
    "What does CYP1A2 affect and what food is connected to it?",
]

with st.sidebar:
    st.subheader("Demo Questions")
    for q in DEMO_QUESTIONS:
        if st.button(q, key=q):
            st.session_state["question"] = q

    st.divider()
    st.subheader("Graph Health")
    try:
        health = requests.get(f"{API_URL}/health", timeout=3).json()
        st.json(health)
    except Exception:
        st.warning("API not reachable. Start the FastAPI server first.")

if "question" not in st.session_state:
    st.session_state["question"] = DEMO_QUESTIONS[0]

question = st.text_area(
    "Ask a question",
    value=st.session_state["question"],
    height=100,
)

col1, col2 = st.columns([1, 5])
with col1:
    ask_btn = st.button("Ask", type="primary")

if ask_btn and question.strip():
    with st.spinner("Retrieving from graph and vector store..."):
        try:
            response = requests.post(
                f"{API_URL}/ask",
                json={"question": question},
                timeout=30
            )
            response.raise_for_status()
            data = response.json()

            st.subheader("Answer")
            st.markdown(data.get("answer", "No answer returned."))

            evidence = data.get("evidence", [])
            if evidence:
                with st.expander(f"Retrieved Evidence ({len(evidence)} items)"):
                    for item in evidence:
                        st.write("- " + str(item))
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to API. Run: `uvicorn src.api.main:app --reload --port 8000`")
        except Exception as e:
            st.error(f"Error: {e}")
