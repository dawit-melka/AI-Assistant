import json
from flask import Blueprint, request, jsonify, current_app,Response
from dotenv import load_dotenv
from .llm_handle.llm_models import GeminiModel, OpenAIModel

import requests
import os
from .main import AiAssistance

main_bp = Blueprint('main', __name__) 
def get_llm_model(config):
    model_type = config['llm_model']

    if model_type == 'openai':
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            raise ValueError("OpenAI API key not found")
        return OpenAIModel(openai_api_key)
    elif model_type == 'gemini':
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("Gemini API key not found")
        return GeminiModel(gemini_api_key)
    else:
        raise ValueError("Invalid model type in configuration")


@main_bp.route('/query', methods=['POST'])
def process_query():
    '''
    This API accepts a query request and returns a response containing content 
    and an optional graph (if the query is graph-related), or just content for queries 
    without any graph-related information.
    '''
    data = request.json
    query = data.get('query', '')
    graph = data.get('graph', None)
    user = data.get('user')

    if not query:
        return jsonify({"error": "No query provided"}), 400

    config = current_app.config
    schema_text = open(config['schema_path'], 'r').read()
    llm = get_llm_model(config)   
    
    try:
        response = AiAssistance(llm,schema_text).assistant_response(query,graph,user)
        return response
    except:
        return "empty page", 400
  