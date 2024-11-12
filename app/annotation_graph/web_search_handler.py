import logging
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)



class WebSearchHandler:
    def __init__(self, api_key: str, custom_search_id: str):
        self.api_key = api_key
        self.custom_search_id = custom_search_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
    
    def search(self, query: str, num_results: int = 5):
        """
        Perfom a Google Custom Search
        """
        try:
            params = {
                'key': self.api_key,
                'cx': self.custom_search_id,
                'q': query,
                'num': num_results
            }
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()

            results = []
            for item in response.json().get('items', []):
                results.append({
                    'title': item.get('item'),
                    'snippet': item.get('snippet'),
                    'link': item.get('link'),
                })
            return results
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []