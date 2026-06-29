"""
演示爬虫 — 生成模拟数据用于本地开发和测试
"""
from typing import List
from spiders.base import BaseSpider, ResourceItem

DEMO_DATA = [
    {
        "title": "流浪地球2",
        "title_en": "The Wandering Earth II",
        "year": 2023,
        "category": "movie",
        "genre": "科幻/冒险/灾难",
        "country": "中国",
        "rating": 8.3,
        "directors": ["郭帆"],
        "actors": ["吴京", "刘德华", "李雪健"],
        "synopsis": "太阳即将毁灭，人类在地球表面建造了巨大的推进器，寻找新家园。",
        "poster_url": "https://img2.doubanio.com/view/photo/s_ratio_poster/public/p2885955777.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO1", "link_type": "magnet", "quality": "4K", "format": "MKV", "subtitle": "中字"},
            {"url": "https://pan.quark.cn/s/demo1", "link_type": "pan_quark", "quality": "1080P"},
        ],
    },
    {
        "title": "满江红",
        "title_en": "Full River Red",
        "year": 2023,
        "category": "movie",
        "genre": "悬疑/古装/喜剧",
        "country": "中国",
        "rating": 7.8,
        "directors": ["张艺谋"],
        "actors": ["沈腾", "易烊千玺", "张译"],
        "synopsis": "南宋绍兴年间，岳飞死后，一个小兵和捕快联手揭露阴谋的故事。",
        "poster_url": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2884409543.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO2", "link_type": "magnet", "quality": "1080P", "format": "MP4", "subtitle": "中字"},
            {"url": "https://pan.baidu.com/s/demo2", "link_type": "pan_baidu", "quality": "HD", "password": "1234"},
        ],
    },
    {
        "title": "狂飙",
        "title_en": "The Knockout",
        "year": 2023,
        "category": "tv",
        "genre": "犯罪/剧情",
        "country": "中国",
        "rating": 9.0,
        "directors": ["徐纪周"],
        "actors": ["张译", "李一桐", "张颂文"],
        "synopsis": "从2000年到2021年，一个警察和黑帮老大之间跨越二十年的纠缠。",
        "poster_url": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2880668440.jpg",
        "links": [
            {"url": "https://pan.aliyundrive.com/s/demo3", "link_type": "pan_aliyun", "quality": "1080P", "episode_info": "全39集"},
        ],
    },
    {
        "title": "宇宙探索编辑部",
        "title_en": "Journey to the West",
        "year": 2023,
        "category": "movie",
        "genre": "科幻/喜剧/剧情",
        "country": "中国",
        "rating": 7.8,
        "directors": ["孔大山"],
        "actors": ["杨皓宇", "艾丽娅", "王一通"],
        "synopsis": "一本濒临倒闭的科幻杂志编辑部意外踏上寻找外星人的旅程。",
        "poster_url": "https://img2.doubanio.com/view/photo/s_ratio_poster/public/p2869396325.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO4", "link_type": "magnet", "quality": "1080P", "format": "MKV"},
        ],
    },
    {
        "title": "奥本海默",
        "title_en": "Oppenheimer",
        "year": 2023,
        "category": "movie",
        "genre": "传记/历史/剧情",
        "country": "美国/英国",
        "rating": 9.0,
        "directors": ["克里斯托弗·诺兰"],
        "actors": ["基里安·墨菲", "艾米莉·布朗特", "马特·达蒙"],
        "synopsis": "原子弹之父罗伯特·奥本海默的传记，记录他领导曼哈顿计划的故事。",
        "poster_url": "https://img2.doubanio.com/view/photo/s_ratio_poster/public/p2884402049.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO5", "link_type": "magnet", "quality": "4K", "format": "MKV", "subtitle": "中英字幕"},
            {"url": "https://pan.quark.cn/s/demo5", "link_type": "pan_quark", "quality": "1080P", "subtitle": "中字"},
        ],
    },
    {
        "title": "芭比",
        "title_en": "Barbie",
        "year": 2023,
        "category": "movie",
        "genre": "喜剧/奇幻/冒险",
        "country": "美国/英国",
        "rating": 7.7,
        "directors": ["格蕾塔·葛韦格"],
        "actors": ["玛格特·罗比", "瑞恩·高斯林", "艾梅里卡·费雷拉"],
        "synopsis": "芭比从完美的芭比乐园来到人类世界，踏上自我发现之旅。",
        "poster_url": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2879498170.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO6", "link_type": "magnet", "quality": "1080P", "format": "MP4"},
        ],
    },
    {
        "title": "蜘蛛侠：纵横宇宙",
        "title_en": "Spider-Man: Across the Spider-Verse",
        "year": 2023,
        "category": "movie",
        "genre": "动画/动作/科幻",
        "country": "美国",
        "rating": 9.1,
        "directors": ["凯姆·斯密斯·麦可"],
        "actors": ["沙美克·摩尔", "海利·斯坦菲尔德", "奥斯卡·伊萨克"],
        "synopsis": "迈尔斯·莫拉莱斯踏上了穿越蜘蛛侠多元宇宙的旅程。",
        "poster_url": "https://img9.doubanio.com/view/photo/s_ratio_poster/public/p2884534286.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO7", "link_type": "magnet", "quality": "1080P", "subtitle": "中英字幕"},
        ],
    },
    {
        "title": "鬼灭之刃：刀匠村篇",
        "title_en": "Demon Slayer: Kimetsu no Yaiba - Swordsmith Village Arc",
        "year": 2023,
        "category": "anime",
        "genre": "动画/动作/奇幻",
        "country": "日本",
        "rating": 9.0,
        "directors": ["外崎春雄"],
        "actors": ["花江夏树", "鬼头明里"],
        "synopsis": "炭治郎来到刀匠村，与上弦之鬼展开激烈战斗。",
        "poster_url": "https://img2.doubanio.com/view/photo/s_ratio_poster/public/p2885726026.jpg",
        "links": [
            {"url": "https://pan.aliyundrive.com/s/demo8", "link_type": "pan_aliyun", "quality": "1080P", "subtitle": "简繁中字", "episode_info": "全11集"},
        ],
    },
    {
        "title": "繁花",
        "title_en": "Blossoms Shanghai",
        "year": 2023,
        "category": "tv",
        "genre": "剧情/历史",
        "country": "中国",
        "rating": 8.6,
        "directors": ["王家卫"],
        "actors": ["胡歌", "马伊琍", "唐嫣"],
        "synopsis": "上海1990年代，一个从贫困中崛起的商人在繁华都市中沉浮。",
        "poster_url": "https://img2.doubanio.com/view/photo/s_ratio_poster/public/p2887166100.jpg",
        "links": [
            {"url": "https://pan.quark.cn/s/demo9", "link_type": "pan_quark", "quality": "4K", "episode_info": "全30集"},
            {"url": "magnet:?xt=urn:btih:DEMO9", "link_type": "magnet", "quality": "1080P"},
        ],
    },
    {
        "title": "三体",
        "title_en": "The Three-Body Problem",
        "year": 2023,
        "category": "tv",
        "genre": "科幻/剧情",
        "country": "中国",
        "rating": 8.0,
        "directors": ["杨磊"],
        "actors": ["张鲁一", "于和伟", "陈瑾"],
        "synopsis": "基于刘慈欣同名科幻小说改编，讲述人类与外星文明的第一次接触。",
        "poster_url": "https://img2.doubanio.com/view/photo/s_ratio_poster/public/p2880659869.jpg",
        "links": [
            {"url": "https://pan.aliyundrive.com/s/demo10", "link_type": "pan_aliyun", "quality": "1080P", "episode_info": "全30集"},
        ],
    },
    {
        "title": "好东西",
        "title_en": "Her Story",
        "year": 2024,
        "category": "movie",
        "genre": "剧情/喜剧",
        "country": "中国",
        "rating": 9.1,
        "directors": ["邵艺辉"],
        "actors": ["宋佳", "钟楚曦", "赵又廷"],
        "synopsis": "两个女人和一个孩子，关于独立、友谊与生活的温柔故事。",
        "poster_url": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2909760376.jpg",
        "links": [
            {"url": "magnet:?xt=urn:btih:DEMO11", "link_type": "magnet", "quality": "4K", "format": "MKV", "subtitle": "中字"},
            {"url": "https://pan.quark.cn/s/demo11", "link_type": "pan_quark", "quality": "1080P"},
        ],
    },
    {
        "title": "只此青绿",
        "title_en": "A Voyage Through Green",
        "year": 2024,
        "category": "movie",
        "genre": "歌舞/剧情/历史",
        "country": "中国",
        "rating": 8.0,
        "directors": ["周莉亚", "韩真"],
        "actors": ["张翰", "孟庆旸"],
        "synopsis": "一幅传世名画背后，一位匠人的故事与现代舞蹈的完美结合。",
        "poster_url": "https://img1.doubanio.com/view/photo/s_ratio_poster/public/p2900001000.jpg",
        "links": [
            {"url": "https://pan.baidu.com/s/demo12", "link_type": "pan_baidu", "quality": "1080P", "password": "abcd"},
        ],
    },
]


class DemoSpider(BaseSpider):
    name = "demo"
    base_url = "https://demo.local"

    async def crawl(self, page: int = 1) -> List[ResourceItem]:
        if page > 1:
            return []
        items = []
        for d in DEMO_DATA:
            item = ResourceItem(
                title=d["title"],
                year=d["year"],
                category=d["category"],
                genre=d["genre"],
                country=d.get("country"),
                rating=d.get("rating"),
                synopsis=d.get("synopsis"),
                poster_url=d.get("poster_url"),
                directors=d.get("directors", []),
                actors=d.get("actors", []),
            )
            for link in d.get("links", []):
                item.add_link(**link)
            items.append(item)
        return items

    async def search(self, keyword: str) -> List[ResourceItem]:
        return [
            item for item in await self.crawl(1)
            if keyword.lower() in item.title.lower()
        ]
