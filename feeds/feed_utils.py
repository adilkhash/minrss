"""
Utility module for validating and fetching RSS feeds.
"""
import logging
import requests
import feedparser
from urllib.parse import urlparse
from typing import List, Dict, Any, Optional
from datetime import datetime
from requests.exceptions import RequestException, Timeout, ConnectionError

# Configure logging
logger = logging.getLogger(__name__)

# Constants
REQUEST_TIMEOUT = 10  # seconds
USER_AGENT = "RSS Feed Reader/1.0"


def validate_feed_url(url: str) -> bool:
    """
    Validates if the provided URL is a valid RSS feed.

    Args:
        url: The URL to validate

    Returns:
        bool: True if the URL is a valid RSS feed, False otherwise
    """
    # Check if URL format is valid
    if not url or not isinstance(url, str):
        logger.error(f"Invalid URL type: {type(url)}")
        return False

    # Check URL has proper scheme
    parsed_url = urlparse(url)
    if not parsed_url.scheme or parsed_url.scheme not in ["http", "https"]:
        logger.error(f"Invalid URL scheme: {url}")
        return False

    # Try to fetch and parse the feed
    try:
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses

        # Try to parse the content as an RSS feed
        feed = feedparser.parse(response.content)

        # Check if the feed has entries or a title (basic validation)
        if feed.get("bozo", 1) == 1 and feed.get("bozo_exception"):
            logger.warning(
                f"Feed parsing warning for {url}: {feed.get('bozo_exception')}"
            )
            # Some feeds may have warnings but still be valid, check if it has entries
            if not feed.get("entries") and not feed.get("feed", {}).get("title"):
                logger.error(f"URL does not appear to be a valid feed: {url}")
                return False

        # Additional validation: check for essential feed elements
        if not feed.get("feed", {}).get("title") and not feed.get("entries"):
            logger.error(f"URL does not contain required RSS elements: {url}")
            return False

        logger.info(f"Successfully validated feed: {url}")
        return True

    except Timeout:
        logger.error(f"Timeout while fetching URL: {url}")
        return False
    except ConnectionError:
        logger.error(f"Connection error while fetching URL: {url}")
        return False
    except RequestException as e:
        logger.error(f"Request error while validating URL {url}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error while validating URL {url}: {str(e)}")
        return False


def fetch_feed_content(url) -> List[Dict[str, Any]]:
    """
    Fetches the latest content from a feed URL.

    Args:
        feed_obj: A Feed model object with at least a 'url' attribute

    Returns:
        List of dictionaries containing feed items with:
            - title: The item title
            - content: The item content/description
            - published_date: The publication date
            - guid: Globally unique identifier for the item
    """
    feed_items = []

    try:
        logger.info(f"Fetching feed content from: {url}")
        headers = {"User-Agent": USER_AGENT}
        response = requests.get(
            url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True
        )
        response.raise_for_status()

        # Parse the feed content
        feed = feedparser.parse(response.content)

        # Process each entry in the feed
        for entry in feed.get("entries", []):
            item = {
                "title": entry.get("title", "No Title"),
                "guid": entry.get("id", entry.get("link", None)),
                "published_date": _parse_date(entry),
                "content": _extract_content(entry),
                "link": entry.get("link", None),
                "author": entry.get("author", None),
            }

            # Skip items without a guid as we can't uniquely identify them
            if not item["guid"]:
                logger.warning(f"Skipping feed item without guid: {item['title']}")
                continue

            feed_items.append(item)

        logger.info(f"Successfully fetched {len(feed_items)} items from {url}")
        return feed_items

    except Timeout:
        logger.error(f"Timeout while fetching feed: {url}")
        return feed_items
    except ConnectionError:
        logger.error(f"Connection error while fetching feed: {url}")
        return feed_items
    except RequestException as e:
        logger.error(f"Request error while fetching feed {url}: {str(e)}")
        return feed_items
    except Exception as e:
        logger.error(f"Unexpected error while fetching feed {url}: {str(e)}")
        return feed_items


def _extract_content(entry: Dict[str, Any]) -> str:
    """
    Extracts the content from a feed entry, handling different content formats.

    Args:
        entry: A feed entry dictionary

    Returns:
        str: The content of the entry
    """
    # Try different possible content fields in order of preference
    if "content" in entry and entry["content"]:
        # Some feeds use a list of content items
        if isinstance(entry["content"], list) and entry["content"]:
            return entry["content"][0].get("value", "")
        return entry["content"]

    if "summary" in entry:
        return entry["summary"]

    if "description" in entry:
        return entry["description"]

    return ""


def _parse_date(entry: Dict[str, Any]) -> Optional[datetime]:
    """
    Parses the publication date from a feed entry.

    Args:
        entry: A feed entry dictionary

    Returns:
        datetime or None: The parsed publication date or None if not available
    """
    # Try different date fields in order of preference
    date_fields = ["published_parsed", "updated_parsed", "created_parsed"]

    for field in date_fields:
        if field in entry and entry[field]:
            try:
                # Convert struct_time to datetime
                return datetime(*entry[field][:6])
            except (ValueError, TypeError):
                continue

    # If no parsed date is available, try string date fields
    string_date_fields = ["published", "updated", "created"]

    for field in string_date_fields:
        if field in entry and entry[field]:
            try:
                return feedparser._parse_date(entry[field])
            except (ValueError, TypeError):
                continue

    return None
