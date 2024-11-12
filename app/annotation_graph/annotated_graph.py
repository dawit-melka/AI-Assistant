import copy
import json
import logging
from flask import app, current_app
import requests
import os
from dotenv import load_dotenv
from app.annotation_graph.neo4j_handler import Neo4jConnection
from app.annotation_graph.schema_handler import SchemaHandler
from app.annotation_graph.web_search_handler import WebSearchHandler
from app.llm_handle.llm_models import LLMInterface
from app.prompts.annotation_prompts import EXTRACT_RELEVANT_INFORMATION_PROMPT, FINAL_RESPONSE_PROMPT, JSON_CONVERSION_PROMPT, REASONING_GENERATOR_PROMPT, SELECT_PROPERTY_VALUE_PROMPT
from app.prompts.web_search_prompts import SYTHESIS_PROMPT
from .dfs_handler import *
from .llm_handler import *

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Graph:
    def __init__(self, llm: LLMInterface, schema: str, schema_handler:SchemaHandler) -> None:
        self.llm = llm
        self.schema = schema # Enhanced or preprocessed schema
        self.neo4j = Neo4jConnection(uri=os.getenv('NEO4J_URI'), 
                                            username=os.getenv('NEO4J_USERNAME'), 
                                            password=os.getenv('NEO4J_PASSWORD'))
        self.schema_handler = schema_handler
        self.web_search = WebSearchHandler(
            api_key=os.getenv('GOOGLE_API_KEY'),
            custom_search_id=os.getenv('GOOGLE_CUSTOM_SEARCH_ID')
        )
        self.trusted_domains = [
            'ncbi.nlm.nih.gov',
            'uniprot.org',
            'genecards.org',
            'ensembl.org',
            'genome.gov',
            'ebi.ac.uk',
            'proteinatlas.org',
            'nature.com',
            'sciencedirect.com',
            'cell.com',
            'pubmed.ncbi.nlm.nih.gov',
            'rejuve.bio'
        ]

    def query_knowledge_graph(self, json_query):
        """
        Query the knowledge graph service.

        Args:
            json_query (dict): The JSON query to be sent.

        Returns:
            dict: The JSON response from the knowledge graph service or an error message.
        """
        logger.info("Starting knowledge graph query...")

        payload = {"requests": json_query}
        kg_service_url = current_app.config['ANNOTATION_SERVICE_URL']
        auth_token = current_app.config['ANNOTATION_AUTH_TOKEN']
        
        try:
            logger.debug(f"Sending request to {kg_service_url} with payload: {payload}")
            response = requests.post(
                kg_service_url,
                json=payload,
                headers={"Authorization": f"Bearer {auth_token}"}
            )
            response.raise_for_status()
            json_response = response.json()
            logger.info(f"Successfully queried the knowledge graph. 'nodes count': {len(json_response.get('nodes'))} 'edges count': {len(json_response.get('edges', []))}")
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error querying knowledge graph: {e}")
            if e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return {"error": f"Failed to query knowledge graph: {str(e)}"}

    def generate_graph(self, query, user_id):
        intermediate_steps = {
            "relevant_information": "",
            "initial_json": "",
            "validation_report": "",
            "validated_json": {},
            "reasoning": "",
            "queried_graph": None,
            "web_search_results": None,
            "answer": "No result found",
            "source": "knowledge_graph"
        }
        try:
            logger.info(f"Starting annotation query processing for question: '{query}'")

            relevant_information = self._extract_relevant_information(query)
            intermediate_steps["relevant_information"] = relevant_information
            
            initial_json = self._convert_to_annotation_json(relevant_information, query)
            intermediate_steps["initial_json"] = copy.deepcopy(initial_json)
            
            validation = self._validate_and_update(initial_json)
            intermediate_steps["validation_report"] = validation['validation_report']
            if validation["validation_report"]["validation_status"] == "failed":
                logger.warning("Knowledge graph validation failed, falling back to web search")
                web_results = self._get_web_search_results(query)
                web_search_results = web_results.get("web_search_results")
                intermediate_steps["web_search_results"] = web_results["web_search_results"]
                if web_search_results and web_results["answer"] != "No result found.":
                    intermediate_steps["answer"] = web_results["answer"]
                    intermediate_steps["source"] = "web"
                    logger.info("Returning answer from web search.")
                    return intermediate_steps
                else: 
                    logger.warning("Web search failed, falling back to LLM  response")
                    intermediate_steps["answer"] = self.llm.generate(query)
                    intermediate_steps["source"] = "llm"
                    logger.info("Returning answer from LLM.")
                    return intermediate_steps
            intermediate_steps["validated_json"] = validation["updated_json"]
            graph = self.query_knowledge_graph(validation["updated_json"])
            reasoning = self._generate_reasoning(query, validation["updated_json"])
            intermediate_steps["reasoning"] = reasoning
            intermediate_steps["queried_graph"] = graph
            if "error" in graph or len(graph['nodes']) == 0:
                logger.warning("Knowledge graph returned empty result, falling back to web search")
                web_results = self._get_web_search_results(query)
                web_search_results = web_results.get("web_search_results")
                intermediate_steps["web_search_results"] = web_results["web_search_results"]
                if web_search_results and web_results["answer"] != "No result found.":
                    intermediate_steps["answer"] = web_results["answer"]
                    intermediate_steps["source"] = "web"
                    logger.info("Returning answer from web search.")
                    return intermediate_steps
                else: 
                    logger.warning("Web search failed, falling back to LLM  response")
                    intermediate_steps["answer"] = self.llm.generate(query)
                    intermediate_steps["source"] = "llm"
                    logger.info("Returning answer from LLM.")
                    return intermediate_steps
    
            final_answer = self._provide_text_response(query,validation, graph)
            intermediate_steps["answer"] = final_answer
            
            logger.info("Completed query processing.")
            return intermediate_steps
        except Exception as e:
            logger.error(f"An error occurred during graph generation: {e}")
            return intermediate_steps

    def _extract_relevant_information(self, query):
        try:
            logger.info("Extracting relevant information from the query.")
            prompt = EXTRACT_RELEVANT_INFORMATION_PROMPT.format(schema=self.schema, query=query)
            extracted_info =  self.llm.generate(prompt)
            logger.info(f"Extracted data: \n{extracted_info}")
            return extracted_info
        except Exception as e:
            logger.error(f"Failed to extract relevant information: {e}")
            raise

    def _convert_to_annotation_json(self, relevant_information, query):
        try:
            logger.info("Converting relevant information to annotation JSON format.")
            prompt = JSON_CONVERSION_PROMPT.format(query=query, extracted_information=relevant_information, schema=self.schema)
            json_data = self.llm.generate(prompt)
            logger.info(f"Converted JSON:\n{json.dumps(json_data, indent=2)}")
            return json_data
        except Exception as e:
            logger.error(f"Failed to convert information to annotation JSON: {e}")
            raise

    def _validate_and_update(self, initial_json):
        try:
            logger.info("Validating and updating the JSON structure.")
            node_types = {}
            validation_report = {
                "property_changes": [],
                "direction_changes": [],
                "removed_properties": [],
                "validation_status": "success"
            }
            
            # Create a deep copy to track changes
            updated_json = copy.deepcopy(initial_json)
            
            # Validate node properties
            if "nodes" not in updated_json:
                raise ValueError("The input JSON must contain a 'nodes' key.")
                
            for node in updated_json.get("nodes"):
                node_type = node.get('type')
                properties = node.get('properties', {})
                node_id = node.get('node_id')
                node_types[node_id] = node_type
                
                # Track removed properties
                for property_key in list(properties.keys()):
                    property_value = properties[property_key]
                    
                    if not property_value and property_value != 0:
                        del properties[property_key]
                        validation_report["removed_properties"].append({
                            "node_type": node_type,
                            "node_id": node_id,
                            "property": property_key,
                            "original_value": property_value
                        })
                    elif isinstance(property_value, str):
                        similar_values = self.neo4j.get_similar_property_values(
                            node_type, property_key, property_value
                        )
                        
                        if similar_values:
                            selected_property = self._select_best_matching_property_value(
                                property_value, similar_values
                            )
                            
                            if selected_property.get("selected_value"):
                                new_value = selected_property.get("selected_value")
                                if new_value != property_value:
                                    validation_report["property_changes"].append({
                                        "node_type": node_type,
                                        "node_id": node_id,
                                        "property": property_key,
                                        "original_value": property_value,
                                        "new_value": new_value,
                                        "similar_values": similar_values
                                    })
                                properties[property_key] = new_value
                            else:
                                raise ValueError(
                                    f"No suitable property found for {node_type} with key {property_key} "
                                    f"and value {property_value}."
                                )
                        else:
                            raise ValueError(
                                f"No suitable property found for {node_type} with key {property_key} "
                                f"and value {property_value}."
                            )
            
            # Validate edge direction
            for edge in updated_json.get("predicates", []):
                s = node_types.get(edge['source'])
                t = node_types.get(edge['target'])
                rel = edge['type']
                conn = f'{s}-{rel}-{t}'
                
                if conn not in self.schema_handler.processed_schema:
                    rev = f'{t}-{rel}-{s}'
                    if rev not in self.schema_handler.processed_schema:
                        raise ValueError(
                            f"Invalid source {s} and target {t} for predicate {rel}"
                        )
                    # Track direction changes
                    validation_report["direction_changes"].append({
                        "relation_type": rel,
                        "original": f"({s})-[{rel}]→({t})",
                        "corrected": f"({t})-[{rel}]→({s})"
                    })
                    # Swap source and target
                    temp_s = edge['source']
                    edge['source'] = edge['target']
                    edge['target'] = temp_s

            logger.info(f"Validated and updated JSON: \n{json.dumps(updated_json, indent=2)}")
            
            return {
                "updated_json": updated_json,
                "validation_report": validation_report
            }
            
        except Exception as e:
            logger.error(f"Validation and update of JSON failed: {e}")
            validation_report["validation_status"] = "failed"
            validation_report["error_message"] = str(e)
            return {
                "updated_json": initial_json,
                "validation_report": validation_report
            }

    def _select_best_matching_property_value(self, user_input_value, possible_values):
        try:
            prompt = SELECT_PROPERTY_VALUE_PROMPT.format(search_query = user_input_value, possible_values=possible_values)
            selected_value = self.llm.generate(prompt)
            logger.info(f"Selected value: {selected_value}")
            return selected_value
        except Exception as e:
            logger.error(f"Failed to select property value: {e}")
            raise
    
    def _provide_text_response(self, query, json_query, kg_response):
        try:
            prompt = FINAL_RESPONSE_PROMPT.format(query=query, json_query=json_query, kg_response=kg_response)
            text_response = self.llm.generate(prompt)
            logger.info(f"Final Answer:\n{text_response[:100]} ...")
            return text_response
        except Exception as e:
            logger.error(f"Failed to provide final response: {e}")

    def _generate_reasoning(self, query, json_query):
        try:
            prompt = REASONING_GENERATOR_PROMPT.format(query=query, json_query=json_query)
            response = self.llm.generate(prompt)
            logger.info(f"Reasoning: \n{response}")
            return response
        except Exception as e:
            logger.error(f"Failed to provide reasoning response: {e}")

    def _get_web_search_results(self, query):
        try:
            # query = f"{query} site:({' OR '.join(self.trusted_domains)})"
            search_results = self.web_search.search(query)

            if not search_results:
                raise ValueError("No relevant web search result found")
            
            search_context = "\n".join([
                f"Title: {result['title']}\nDescription: {result['snippet']}\nSource: {result['link']}\n"
                for result in search_results
            ])

            prompt = SYTHESIS_PROMPT.format(query=query, search_context=search_context)
            synthesized_answer = self.llm.generate(prompt)
            return {
                "answer": synthesized_answer,
                "web_search_results": search_results
            }
        except Exception as e:
            logger.error(f"Failed to synthesize web search results: {e}")
            return {"answer": f"Failed to process web search: {e}", "web_search_results": []}
