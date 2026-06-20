"""Discovery sub-package: multiple backends for URL discovery."""

from .ddgs import DDGSDiscovery
from .gdelt import GDELTDiscovery
from .google_news import GoogleNewsDiscovery
from .mediacloud import MediaCloudDiscovery
from .rss import RSSDiscovery
from .search_api import SearchAPIDiscovery
from .seed_loader import SeedLoader

__all__ = [
    "DDGSDiscovery",
    "GDELTDiscovery",
    "GoogleNewsDiscovery",
    "MediaCloudDiscovery",
    "RSSDiscovery",
    "SearchAPIDiscovery",
    "SeedLoader",
]
