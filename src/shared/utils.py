from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def normalize_url(url: str) -> str:
    """
    Cleans a URL by removing common tracking parameters and normalizes the scheme/host.
    This ensures that the same article from different sources or with tracking 
    is treated as the same URL.
    """
    if not url:
        return ""
        
    parsed = urlparse(url.strip())
    
    # Lowercase scheme and netloc
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # Remove common tracking parameters
    blacklist = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'ref', 'referrer', 'gclid', 'fbclid', 'mc_cid', 'mc_eid', 'ncid',
        'ref_src', 'ref_url', '_hsenc', '_hsmi', 'mkt_tok'
    }
    
    query_params = parse_qsl(parsed.query)
    filtered_params = [(k, v) for k, v in query_params if k.lower() not in blacklist]
    
    # Sort params to ensure consistency
    filtered_params.sort()
    
    new_query = urlencode(filtered_params)
    
    # Reconstruct URL without fragment and with filtered query
    normalized = urlunparse((
        scheme,
        netloc,
        parsed.path,
        parsed.params,
        new_query,
        "" # Remove fragment
    ))
    
    return normalized
