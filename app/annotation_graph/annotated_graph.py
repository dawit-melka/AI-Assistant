import copy
import json
import logging
from flask import app, current_app
import requests
import os
from dotenv import load_dotenv
from app.annotation_graph.neo4j_handler import Neo4jConnection
from app.llm_handle.llm_models import LLMInterface
from app.prompts.annotation_prompts import EXTRACT_RELEVANT_INFORMATION_PROMPT, FINAL_RESPONSE_PROMPT, JSON_CONVERSION_PROMPT, REASONING_GENERATOR_PROMPT, SELECT_PROPERTY_VALUE_PROMPT
from .dfs_handler import *
from .llm_handler import *

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Graph:
    def __init__(self, llm: LLMInterface, schema: str) -> None:
        self.llm = llm
        self.schema = schema # Enhanced or preprocessed schema
        self.neo4j = Neo4jConnection(uri=os.getenv('NEO4J_URI'), 
                                            username=os.getenv('NEO4J_USERNAME'), 
                                            password=os.getenv('NEO4J_PASSWORD'))

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

    def generate_graph(self, query):
        intermediate_steps = {
            "relevant_information": "",
            "initial_json": "",
            "validated_json": "",
            "reasoning": "",
            "queried_graph": "",
            "final_answer": "No result found"
        }
        try:
            logger.info(f"Starting annotation query processing for question: '{query}'")

            relevant_information = self._extract_relevant_information(query)
            intermediate_steps["relevant_information"] = relevant_information
            
            initial_json = self._convert_to_annotation_json(relevant_information, query)
            intermediate_steps["initial_json"] = copy.deepcopy(initial_json)
            
            validated_json = self._validate_and_update(initial_json)
            intermediate_steps["validated_json"] = validated_json
            
            reasoning = self._generate_reasoning(query, validated_json)
            intermediate_steps["reasoning"] = reasoning

            graph = self.query_knowledge_graph(validated_json)
            intermediate_steps["queried_graph"] = graph
    
            final_answer = self._provide_text_response(query,validated_json, graph)
            intermediate_steps["final_answer"] = final_answer
            
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
            # Validate node properties
            if "nodes" not in initial_json:
                raise ValueError("The input JSON must contain a 'nodes' key.")
            for node in initial_json.get("nodes"):
                node_type = node.get('type')
                properties = node.get('properties', {})
                node_id = node.get('node_id')
                node_type[node_id] = node_type
                for property_key in list(properties.keys()):
                    property_value = properties[property_key]

                    if not property_value and property_value != 0:
                        del properties[property_key]
                    elif isinstance(property_value, str):
                        similar_values = self.neo4j.get_similar_property_values(node_type, property_key, property_value)
                        if similar_values:
                            selected_property_value = self._select_best_matching_property_value(property_value, similar_values)
                            if selected_property_value.get("selected_value"):
                                properties[property_key] = selected_property_value.get("selected_value")
                            else:
                                logger.debug(f"No suitable property found for {node_type} with key {property_key} and value {property_value}.")
                                raise ValueError(f"No suitable property found for {node_type} with key {property_key} and value {property_value}.") 
                        else:
                            logger.debug(f"No suitable property found for {node_type} with key {property_key} and value {property_value}.")
                            raise ValueError(f"No suitable property found for {node_type} with key {property_key} and value {property_value}.")
            # VAlidate edge direction
            for edge in initial_json.get("predicates", []):
                s = node_types.get(edge['source'])
                t = node_types.get(edge['target'])
                rel = edge['type']

            logger.info(f"Validated and updated JSON: \n{json.dumps(initial_json, indent=2)}")
            return initial_json
        except Exception as e:
            logger.error(f"Validation and update of JSON failed: {e}")
            raise

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
            logger.info(f"Final Answer:\n{text_response}")
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
