# Add or remove feeds freely — all free public RSS feeds
SOURCES = [
    # ── Core Tech News ───────────────────────────────────────────
    {"url": "https://hnrss.org/frontpage",                              "source": "HackerNews"},
    {"url": "https://feeds.feedburner.com/TheHackersNews",              "source": "HackersNews"},
    {"url": "https://tldr.tech/api/rss/ai",                            "source": "TLDR-AI"},
    {"url": "https://www.artificialintelligence-news.com/feed/",        "source": "AI-News"},

    # ── Dev.to ───────────────────────────────────────────────────
    {"url": "https://dev.to/feed/tag/ai",                              "source": "DevTo-AI"},
    {"url": "https://dev.to/feed/tag/python",                          "source": "DevTo-Python"},
    {"url": "https://dev.to/feed/tag/machinelearning",                 "source": "DevTo-ML"},

    # ── AI/ML Blogs ──────────────────────────────────────────────
    {"url": "https://huggingface.co/blog/feed.xml",                    "source": "HuggingFace"},
    {"url": "https://openai.com/news/rss.xml",                         "source": "OpenAI"},
    {"url": "https://machinelearningmastery.com/feed/",                "source": "MLMastery"},

    # ── Arxiv Papers ─────────────────────────────────────────────
    {"url": "https://rss.arxiv.org/rss/cs.AI",                         "source": "Arxiv-AI"},
    {"url": "https://rss.arxiv.org/rss/cs.LG",                         "source": "Arxiv-ML"},
    {"url": "https://rss.arxiv.org/rss/cs.CL",                         "source": "Arxiv-NLP"},
]