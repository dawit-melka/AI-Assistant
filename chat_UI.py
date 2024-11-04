import streamlit as st
import requests
import asyncio
import aiohttp

st.title('Annotation Query Processor')

# Define the correct order of steps
STEP_ORDER = [
    "relevant_information",
    "initial_json",
    "validated_json",
    "reasoning",
    "queried_graph",
    "final_answer"
]

# Create a clean layout
st.markdown("### Enter your query below:")
user_query = st.text_input("Query:", placeholder="Type your query here...")

if st.button('Process Query'):
    if user_query:
        async def get_result():
            async with aiohttp.ClientSession() as session:
                async with session.post('http://localhost:5001/query', 
                                      json={'query': user_query}) as response:
                    result = await response.json()
                    
                    # Display steps in the defined order
                    for step in STEP_ORDER:
                        if step in result:
                            step_title = step.replace('_', ' ').title()
                            with st.expander(f"📍 {step_title}"):
                                content = result[step]
                                if isinstance(content, dict):
                                    st.json(content)
                                else:
                                    st.write(content)
                    
                    # Display final answer prominently
                    if "final_answer" in result:
                        st.markdown("### 🎯 Final Answer")
                        st.success(result["final_answer"])

        asyncio.run(get_result())
    else:
        st.warning("⚠️ Please enter a query before submitting.")

# Add some helpful information
with st.sidebar:
    st.markdown("### Process Steps")
    st.markdown("""
    1. Extract Relevant Information
    2. Convert to Annotation JSON
    3. Validate and Update
    4. Generate Reasoning
    5. Query Knowledge Graph
    6. Provide Final Response
    """)