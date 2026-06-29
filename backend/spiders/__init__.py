from .base import BaseSpider, ResourceItem
from .sources.demo import DemoSpider
from .sources.rss_spider import RSSSpider
from .sources.tmdb_batch import TMDbBatchSpider
from .sources.pan_search import PanSearchSpider

SPIDER_REGISTRY = {
    "demo":       DemoSpider,
    "rss":        RSSSpider,
    "tmdb_batch": TMDbBatchSpider,
    "pan_search": PanSearchSpider,
}
