import logging
import re
from typing import Dict
from urllib.parse import urlparse
import aiohttp
from bs4 import BeautifulSoup
import html2text
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebContentExtractor:
    def __init__(self):
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = True
        self.h2t.ignore_images = True
        
    async def extract_content(self, url: str, session: aiohttp.ClientSession) -> Dict:
        """
        Extract relevant content from scientific articles and papers
        """
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None
                    
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Extract metadata
                metadata = self._extract_metadata(soup)
                
                # Extract main content based on domain-specific rules
                domain = urlparse(url).netloc
                content = self._extract_domain_specific_content(soup, domain)
                
                return {
                    "metadata": metadata,
                    "content": content,
                    "url": url
                }
        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e}")
            return None
            
    def _extract_metadata(self, soup: BeautifulSoup) -> Dict:
        """
        Extract article metadata including authors, date, doi, etc.
        """
        metadata = {}
        
        # Extract publication date
        date_meta = soup.find('meta', {'name': ['publication_date', 'article:published_time']})
        if date_meta:
            metadata['pub_date'] = date_meta.get('content')
            
        # Extract DOI
        doi_meta = soup.find('meta', {'name': 'citation_doi'})
        if doi_meta:
            metadata['doi'] = doi_meta.get('content')
            
        # Extract authors
        author_meta = soup.find_all('meta', {'name': 'citation_author'})
        if author_meta:
            metadata['authors'] = [author.get('content') for author in author_meta]
            
        return metadata
        
    def _extract_domain_specific_content(self, soup: BeautifulSoup, domain: str) -> str:
        """
        Extract main content from scientific articles based on domain-specific rules.
        
        Args:
            soup (BeautifulSoup): Parsed HTML content
            domain (str): Website domain (e.g., 'nature.com', 'science.org')
            
        Returns:
            str: Extracted article content with preserved formatting
        """
        content = ""
        
        # Common article content selectors for different domains
        domain_selectors = {
            'nature.com': {
                'content': ['div.c-article-body', 'article.main-content'],
                'exclude': ['div.c-article-references', 'div.c-article-footer']
            },
            'science.org': {
                'content': ['div.article-content', 'div.fulltext-view'],
                'exclude': ['div.references', 'div.article-footer']
            },
            'arxiv.org': {
                'content': ['div.abstract', 'div.full-text'],
                'exclude': ['div.bibliography']
            },
            'biorxiv.org': {
                'content': ['div.article-content', 'div.content-block'],
                'exclude': ['div.ref-list', 'div.section.ref-list']
            }
        }
        
        # Get domain-specific selectors or use generic ones
        selectors = domain_selectors.get(domain, {
            'content': ['article', 'div.content', 'div.article-content'],
            'exclude': ['div.references', 'div.footer', 'div.header']
        })
        
        # Try domain-specific content extraction
        for selector in selectors['content']:
            content_element = soup.select_one(selector)
            if content_element:
                # Remove elements to exclude
                for exclude_selector in selectors['exclude']:
                    for element in content_element.select(exclude_selector):
                        element.decompose()
                
                # Extract text while preserving some structure
                for element in content_element.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                    if element.name.startswith('h'):
                        content += f"\n\n{element.get_text().strip()}\n"
                    else:
                        content += f"{element.get_text().strip()}\n\n"
                
                break
        
        # Fallback to generic extraction if no content found
        if not content:
            # Look for the largest text block
            text_blocks = []
            for element in soup.find_all(['div', 'article', 'section']):
                text = element.get_text(strip=True)
                if len(text) > 500:  # Minimum length threshold
                    text_blocks.append((len(text), text))
            
            if text_blocks:
                # Use the largest text block
                content = max(text_blocks, key=lambda x: x[0])[1]
        
        # Clean up the extracted content
        content = re.sub(r'\n{3,}', '\n\n', content)  # Remove excessive newlines
        content = content.strip()
        
        return content

class WebSearchHandler:
    def __init__(self, api_key: str, custom_search_id: str):
        self.api_key = api_key
        self.custom_search_id = custom_search_id
        self.base_url = "https://www.googleapis.com/customsearch/v1"
        self.h2t = html2text.HTML2Text()
        self.h2t.ignore_links = True
        self.h2t.ignore_images = True

    
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
                link = item.get('link')
                # content = self._extract_content(link)
                results.append({
                    'title': item.get('item'),
                    'snippet': item.get('snippet'),
                    'link': item.get('link')
                    # 'content': content
                })
            return results
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return []
    
    def _extract_content(self, url: str) -> str:
        """
        Extract the main content from a web page.
        """
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract the main content
            main_content = soup.find('article') or soup.find('main') or soup.find('div', {'class': 'content'})
            if main_content:
                return self.h2t.handle(str(main_content)).strip()
            else:
                return ''
        except Exception as e:
            logger.error(f"Failed to extract content from {url}: {e}")
            return ''