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
                            
                            # Special handling for validated JSON step
                            if step == "validated_json":
                                with st.expander(f"📍 {step_title}"):
                                    validation_data = result[step]
                                    
                                    # Display validation report if available
                                    if isinstance(validation_data, dict) and "validation_report" in validation_data:
                                        report = validation_data["validation_report"]
                                        
                                        # Show validation status
                                        status_color = "green" if report["validation_status"] == "success" else "red"
                                        st.markdown(f"**Status:** :{status_color}[{report['validation_status']}]")
                                        
                                        # Show property changes
                                        if report["property_changes"]:
                                            st.markdown("#### Property Changes")
                                            for change in report["property_changes"]:
                                                st.write(f"""
                                                ```
                                                Node: {change['node_type']} ({change['node_id']})  
                                                Property: `{change['property']}`  
                                                Changed: "{change['original_value']}" → "{change['new_value']}"
                                                ```
                                                Similar values found:
                                                ```
                                                {change['similar_values']}
                                                ```
                                                ***
                                                """)
                                        
                                        # Show direction changes
                                        if report["direction_changes"]:
                                            st.markdown("#### Relation Direction Changes")
                                            for change in report["direction_changes"]:
                                                st.markdown(f"""
                                                ```
                                                Relation: {change['relation_type']}  
                                                Direction changed: {change['corrected']}
                                                ```
                                                ***
                                                """)
                                        
                                        # Show removed properties
                                        if report["removed_properties"]:
                                            st.markdown("#### Removed Empty Properties")
                                            for removed in report["removed_properties"]:
                                                st.markdown(f"""
                                                🗑️ **Node:** {removed['node_type']} ({removed['node_id']})  
                                                Removed empty property: `{removed['property']}`
                                                ---
                                                """)
                                        
                                        # Show error message if validation failed
                                        if report["validation_status"] == "failed":
                                            st.error(f"Validation Error: {report.get('error_message', 'Unknown error')}")
                                        
                                        # Show the updated JSON
                                        st.markdown("#### Updated JSON")
                                        st.json(validation_data["updated_json"])
                                    else:
                                        # Fall back to simple JSON display if no validation report
                                        st.json(validation_data)
                            else:
                                # Handle other steps normally
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

# # Add some helpful information
# with st.sidebar:
#     st.markdown("### Process Steps")
#     st.markdown("""
#     1. Extract Relevant Information
#     2. Convert to Annotation JSON
#     3. Validate and Update
#     4. Generate Reasoning
#     5. Query Knowledge Graph
#     6. Provide Final Response
#     """)