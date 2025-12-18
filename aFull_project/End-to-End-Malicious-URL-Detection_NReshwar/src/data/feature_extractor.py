
import re
from urllib.parse import urlparse
import tldextract

class FeatureExtractor:
    def __init__(self, url):
        self.url = url if url.startswith(('http://', 'https://')) else 'http://' + url
        self.parsed_url = urlparse(self.url)
        self.domain = self.parsed_url.netloc
        self.path = self.parsed_url.path
        self.extracted_tld = tldextract.extract(self.url)
        self.tld = self.extracted_tld.suffix

    def extract_all_features(self):
        """
        Extracts all 40 features required by the model.
        The feature names are taken directly from the url_engine.py file.
        """
        features = {
            # URL-based features
            'qty_dot_url': self.url.count('.'),
            'qty_hyphen_url': self.url.count('-'),
            'qty_underline_url': self.url.count('_'),
            'qty_slash_url': self.url.count('/'),
            'qty_questionmark_url': self.url.count('?'),
            'qty_equal_url': self.url.count('='),
            'qty_at_url': self.url.count('@'),
            'qty_and_url': self.url.count('&'),
            'qty_exclamation_url': self.url.count('!'),
            'qty_space_url': self.url.count(' '),
            'qty_tilde_url': self.url.count('~'),
            'qty_comma_url': self.url.count(','),
            'qty_plus_url': self.url.count('+'),
            'qty_asterisk_url': self.url.count('*'),
            'qty_hashtag_url': self.url.count('#'),
            'qty_dollar_url': self.url.count('$'),
            'qty_percent_url': self.url.count('%'),
            'qty_tld_url': len(self.tld),
            'length_url': len(self.url),

            # Domain-based features
            'qty_dot_domain': self.domain.count('.'),
            'qty_hyphen_domain': self.domain.count('-'),
            'qty_underline_domain': self.domain.count('_'),
            'qty_slash_domain': self.domain.count('/'),
            'qty_questionmark_domain': self.domain.count('?'),
            'qty_equal_domain': self.domain.count('='),
            'qty_at_domain': self.domain.count('@'),
            'qty_and_domain': self.domain.count('&'),
            'qty_exclamation_domain': self.domain.count('!'),
            'qty_space_domain': self.domain.count(' '),
            'qty_tilde_domain': self.domain.count('~'),
            'qty_comma_domain': self.domain.count(','),
            'qty_plus_domain': self.domain.count('+'),
            'qty_asterisk_domain': self.domain.count('*'),
            'qty_hashtag_domain': self.domain.count('#'),
            'qty_dollar_domain': self.domain.count('$'),
            'qty_percent_domain': self.domain.count('%'),
            'qty_vowels_domain': sum(1 for char in self.domain if char in 'aeiouAEIOU'),
            'domain_length': len(self.domain),
            'domain_in_ip': 1 if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", self.domain) else 0,
            
            # A simple check for 'server' or 'client' in the domain name
            'server_client_domain': 1 if 'server' in self.domain.lower() or 'client' in self.domain.lower() else 0
        }
        return features
