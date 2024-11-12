# SYTHESIS_PROMPT = """
# The user asked the below question below and as a reference the some web search results are added. but if the search results couldn't answer the question let the user know
# Based on these search results about Query: "{query}"

# Sources:
# {search_context}

# Please provide a comprehensive answer that:
# 1. Synthesizes key findings, prioritizing high-relevance sources
# 2. Explicitly cites sources for major claims
# 3. Distinguishes between established facts and preliminary findings
# 4. Considers the temporal context of the information
# 5. Directly address the Query in an 
# 6. Don't mix the links and the text. 

# Answer:"""

SYTHESIS_PROMPT = """
You are an AI assistant. The user asked the question below and web search results are provided as reference. 
If the search results don't adequately answer the question, please clearly indicate this to the user.

Query: "{query}"

Search Results:
{search_context}

Please provide a comprehensive answer that:
1. Synthesizes key findings, prioritizing high-relevance sources
2. Explicitly cites sources for major claims
3. Distinguishes between established facts and preliminary findings
4. Directly addresses the Query
5. Keeps source citations separate from the main text

If the search results don't contain enough relevant information to answer the query, please state:
"No result found."

Answer:"""