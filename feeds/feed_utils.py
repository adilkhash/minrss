import logging
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

import feedparser
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from .models import Feed, FeedItem

logger = logging.getLogger(__name__)

# Constants
FEED_TIMEOUT = getattr(settings, 'FEED_FETCH_TIMEOUT', 10)  # seconds
MAX_REDIRECTS = getattr(settings, 'FEED_MAX_REDIRECTS', 5)
VALID_SCHEMES = {'http', 'https'}


def validate_feed_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    Validates if the provided URL is a valid RSS feed.
    
    Args:
        url: The URL to validate
        
    Returns:
        Tuple of (is_valid: bool, error_message: Optional[str])
    """
    try:
        # Basic URL validation
        parsed = urlparse(url)
        if not parsed.scheme or parsed.scheme not in VALID_SCHEMES:
            return False, "URL must start with http:// or https://"
        
        if not parsed.netloc:
            return False, "Invalid URL format"
        
        # Attempt to fetch and parse the feed
        feed = feedparser.parse(url, timeout=FEED_TIMEOUT)
        
        # Check for feed parsing errors
        if hasattr(feed, 'bozo') and feed.bozo:
            return False, f"Feed parsing error: {feed.bozo_exception}"
        
        # Check if feed has entries
        if not feed.entries:
            return False, "Feed contains no entries"
        
        return True, None
        
    except feedparser.FeedParserHTTPError as e:
        logger.error(f"HTTP error while validating feed {url}: {str(e)}")
        return False, f"HTTP error: {str(e)}"
    except feedparser.FeedParserHTTPRedirect as e:
        logger.error(f"Too many redirects for feed {url}: {str(e)}")
        return False, f"Too many redirects (max {MAX_REDIRECTS})"
    except Exception as e:
        logger.error(f"Unexpected error while validating feed {url}: {str(e)}")
        return False, f"Unexpected error: {str(e)}"


def extract_feed_title(feed: feedparser.FeedParserDict) -> Optional[str]:
    """Extract feed title from various possible locations in the feed."""
    if hasattr(feed, 'title'):
        return feed.title
    elif hasattr(feed, 'feed') and hasattr(feed.feed, 'title'):
        return feed.feed.title
    return None


def extract_entry_guid(entry: feedparser.FeedParserDict) -> str:
    """Extract unique identifier for a feed entry."""
    if hasattr(entry, 'id'):
        return entry.id
    elif hasattr(entry, 'guid'):
        return entry.guid
    # Fallback to link if no guid/id is available
    return entry.get('link', '')


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various date formats into datetime object."""
    if not date_str:
        return None
    
    try:
        # Try parsing with feedparser's date parser
        parsed_date = feedparser._parse_date(date_str)
        if parsed_date:
            return timezone.make_aware(parsed_date)
    except Exception:
        pass
    
    # Fallback to current time if parsing fails
    return timezone.now()


def fetch_feed_content(feed_obj: Feed) -> Tuple[List[Dict], Optional[str]]:
    """
    Fetches and parses content from a feed URL.
    
    Args:
        feed_obj: Feed model instance
        
    Returns:
        Tuple of (list of feed items, error message if any)
    """
    try:
        # Fetch and parse the feed
        feed = feedparser.parse(feed_obj.url, timeout=FEED_TIMEOUT)
        
        if hasattr(feed, 'bozo') and feed.bozo:
            error_msg = f"Feed parsing error: {feed.bozo_exception}"
            logger.error(f"Error parsing feed {feed_obj.url}: {error_msg}")
            return [], error_msg
        
        # Update feed title if not set
        if not feed_obj.title:
            feed_title = extract_feed_title(feed)
            if feed_title:
                feed_obj.title = feed_title
                feed_obj.save()
        
        # Process entries
        items = []
        for entry in feed.entries:
            try:
                # Extract required fields
                guid = extract_entry_guid(entry)
                if not guid:
                    logger.warning(f"Skipping entry from {feed_obj.url}: No GUID found")
                    continue
                
                # Check for duplicate entry
                if FeedItem.objects.filter(feed=feed_obj, guid=guid).exists():
                    continue
                
                # Extract content
                content = entry.get('summary', entry.get('description', ''))
                if not content and hasattr(entry, 'content'):
                    content = entry.content[0].value if entry.content else ''
                
                # Create item dictionary
                item = {
                    'title': entry.get('title', 'Untitled'),
                    'content': content,
                    'published_at': parse_date(entry.get('published', entry.get('updated'))),
                    'guid': guid,
                }
                items.append(item)
                
            except Exception as e:
                logger.error(f"Error processing entry from {feed_obj.url}: {str(e)}")
                continue
        
        if not items:
            return [], "No new items found in feed"
        
        return items, None
        
    except feedparser.FeedParserHTTPError as e:
        error_msg = f"HTTP error while fetching feed: {str(e)}"
        logger.error(f"Error fetching feed {feed_obj.url}: {error_msg}")
        return [], error_msg
    except feedparser.FeedParserHTTPRedirect as e:
        error_msg = f"Too many redirects: {str(e)}"
        logger.error(f"Error fetching feed {feed_obj.url}: {error_msg}")
        return [], error_msg
    except Exception as e:
        error_msg = f"Unexpected error while fetching feed: {str(e)}"
        logger.error(f"Error fetching feed {feed_obj.url}: {error_msg}")
        return [], error_msg


def create_feed_items(feed_obj: Feed, items: List[Dict]) -> int:
    """
    Creates FeedItem objects from the parsed feed items.
    
    Args:
        feed_obj: Feed model instance
        items: List of parsed feed items
        
    Returns:
        Number of items created
    """
    created_count = 0
    for item in items:
        try:
            FeedItem.objects.create(
                feed=feed_obj,
                title=item['title'],
                content=item['content'],
                published_at=item['published_at'],
                guid=item['guid']
            )
            created_count += 1
        except Exception as e:
            logger.error(f"Error creating feed item for {feed_obj.url}: {str(e)}")
            continue
    
    return created_count 