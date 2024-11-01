import streamlit as st
import requests
import os
from PIL import Image

# Define the queries
QUERIES = {
    "Simple Queries": [
        "What genes are associated with the GO term 'apoptosis'?",
        "Which proteins are part of the 'cell cycle' pathway?",
        "What are the child terms of 'neuron' in the Cell Ontology?",
        "Which genes are expressed in the liver?",
        "What SNPs are associated with the BRCA1 gene?",
        "Which transcripts are produced by the TP53 gene?",
        "What are the protein products of the insulin gene?",
        "Which enhancers are active in stem cells?",
        "What are the target genes of the miRNA let-7?",
        "Which proteins interact with the epidermal growth factor receptor?"
    ],
    "Medium Queries": [
        "What are the shared GO terms between the proteins TP53 and MDM2?",
        "Which genes are both regulated by the transcription factor FOXP3 and involved in the immune response pathway?",
        "What are the tissue-specific expressions of genes in the insulin signaling pathway?",
        "Which SNPs are associated with changes in gene expression (eQTLs) in both liver and muscle tissues?",
        "What are the conserved non-coding elements within 50kb of the FOXP2 gene?",
        "Which genes are in the same topologically associating domain (TAD) as the MYC gene?",
        "What are the differentially expressed genes between normal and cancerous lung tissue?",
        "Which transcription factors have binding sites that overlap with DNase I hypersensitive sites in neural progenitor cells?",
        "What are the protein-protein interactions among genes involved in both DNA repair and cell cycle regulation?",
        "Which long non-coding RNAs are expressed in the same tissues as their neighboring protein-coding genes?"
    ],
    "Complex Queries": [
        "What are the key driver genes in the regulatory network of pancreatic beta cells?",
        "Which genes show evolutionary conservation across humans, mice, and zebrafish in heart development?",
        "What are the potential off-target effects of a CRISPR-Cas9 guide RNA?",
        "Which enhancer-promoter interactions are altered in breast cancer?",
        "What is the predicted impact of rare variants on protein structure and function?",
        "How does 3D chromatin structure change during stem cell differentiation?",
        "What are the key pathways involved in epithelial-to-mesenchymal transition?",
        "Which genetic variants are associated with changes in gene expression across multiple tissues?",
        "What is the predicted cellular response to a novel drug compound?",
        "How does alternative splicing differ between normal and cancer stem cells?"
    ]
}

def load_image(query_category, query_index):
    """Load and return an image if it exists"""
    # Convert category to lowercase and get first word
    category_prefix = query_category.lower().split()[0]
    
    # Construct possible image paths
    image_paths = [
        f"images/{category_prefix}_{query_index + 1}.png",
        f"images/{category_prefix}_{query_index + 1}.jpg",
        f"images/{category_prefix}_{query_index + 1}.jpeg"
    ]
    
    for path in image_paths:
        if os.path.exists(path):
            try:
                return Image.open(path)
            except:
                continue
    
    return None

def main():
    st.title('Biological Query Interface')
    
    # Create tabs for different query types
    tab1, tab2, tab3, tab4 = st.tabs(["Simple Queries", "Medium Queries", "Complex Queries", "Custom Query"])
    
    # Function to handle query selection and display
    def process_query(queries, tab):
        with tab:
            # Create columns for layout
            cols = st.columns(2)
            
            # Display queries in two columns
            for i, query in enumerate(queries):
                col = cols[i % 2]
                if col.button(f"Q{i+1}", key=f"query_{id(queries)}_{i}"):
                    # Send query to backend
                    try:
                        response = requests.post('http://localhost:5001/query', json={'query': query})
                        result = response.json()
                        
                        # Display query results
                        st.subheader("Query Result")
                        st.json(result)
                        
                        # Try to load and display corresponding image
                        image = load_image(tab.label, i)
                        if image:
                            st.subheader("Related Visualization")
                            st.image(image, caption=f"Visualization for {tab.label} Query {i+1}")
                    
                    except Exception as e:
                        st.error(f"Error executing query: {e}")
                
                # Display query text
                col.write(query)
    
    # Process queries for each tab
    process_query(QUERIES["Simple Queries"], tab1)
    process_query(QUERIES["Medium Queries"], tab2)
    process_query(QUERIES["Complex Queries"], tab3)
    
    # Custom query tab
    with tab4:
        st.subheader("Enter Your Own Query")
        custom_query = st.text_input("Type your biological query here:")
        
        if st.button("Submit Custom Query"):
            if custom_query:
                try:
                    # Send custom query to backend
                    response = requests.post('http://localhost:5001/query', json={'query': custom_query})
                    result = response.json()
                    
                    # Display query results
                    st.subheader("Custom Query Result")
                    st.json(result)
                
                except Exception as e:
                    st.error(f"Error executing custom query: {e}")
            else:
                st.warning("Please enter a query.")

if __name__ == "__main__":
    main()