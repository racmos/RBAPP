"""
Scraper service for fetching content from external sources.
Falls back to realistic placeholder data when scraping fails.
Sync version using requests (converted from httpx async original in rb_landing).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import random

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# ─── Data models ───

@dataclass
class NewsItem:
    title: str
    url: str
    image: str = ""
    date: str = ""
    source: str = ""

@dataclass
class TournamentItem:
    title: str
    date: str
    slots: str = ""
    price: str = ""
    location: str = ""
    url: str = "#"

@dataclass
class VideoItem:
    title: str
    channel: str
    thumbnail: str = ""
    url: str = "#"
    date: str = ""

@dataclass
class DeckItem:
    title: str
    date: str
    set_initials: str = ""
    domains: list[str] = field(default_factory=list)
    legend_image: str = ""
    url: str = "#"


# ─── Placeholder data ───

def _placeholder_noticias() -> list[NewsItem]:
    """Realistic placeholder Riftbound news."""
    titles = [
        "Patch 2.4: Balance Changes & New Cards",
        "Riftbound World Championship 2026 Announced",
        "New Expansion: Shadows of the Rift",
        "Community Spotlight: Top Decks of the Week",
        "Developer Update: Ranked Season 5",
        "Card Preview: Ahri, Spirit Blossom",
        "Riftbound x Arcane Collaboration Event",
        "Competitive Format Update: Ban System",
        "New Player Guide: Building Your First Deck",
    ]
    return [
        NewsItem(
            title=t,
            url="https://riftbound.leagueoflegends.com/en-us/news/",
            image=f"https://placehold.co/400x225/111111/3b82f6?text=RTB+News+{i+1}",
            date=(datetime.now() - timedelta(days=i * 2)).strftime("%d %b %Y"),
            source="Riftbound Official",
        )
        for i, t in enumerate(titles)
    ]


def _placeholder_discord() -> list[NewsItem]:
    """Realistic placeholder Discord news."""
    titles = [
        "🏆 Tournament Results: Weekly Brawl #47",
        "📢 Server Update: New Roles & Channels",
        "🎨 Fan Art Contest Winners Announced",
        "📋 Community Poll: Favorite Champion",
        "🔥 Meta Report: Week 12 Analysis",
        "📅 Upcoming Events Schedule",
        "🎮 Custom Games Night This Friday",
        "💡 Deck Building Workshop — Saturday",
        "🌟 Member of the Month: February",
    ]
    return [
        NewsItem(
            title=t,
            url="https://discord.com/channels/1352591918646689854/",
            image="",
            date=(datetime.now() - timedelta(days=i)).strftime("%d %b %Y"),
            source="Discord",
        )
        for i, t in enumerate(titles)
    ]


def _placeholder_torneos_online() -> list[TournamentItem]:
    """Realistic placeholder online tournaments."""
    names = [
        "Riftbound Weekly Open #48",
        "Demacia Cup — Season 2",
        "Friday Night Rift",
        "Noxus Invitational",
        "Community Draft Tournament",
        "Ranked Qualifier — March",
        "Spirit Blossom Showdown",
        "Beginner Friendly Bracket",
        "2v2 Tag Team Tournament",
    ]
    return [
        TournamentItem(
            title=n,
            date=(datetime.now() + timedelta(days=i * 3 + 1)).strftime("%d %b %Y — %H:00"),
            slots=f"{random.randint(8, 64)} plazas",
            price=random.choice(["Gratis", "5€", "10€", "Gratis", "3€"]),
        )
        for i, n in enumerate(names)
    ]


def _placeholder_torneos_fisicos() -> list[TournamentItem]:
    """Realistic placeholder physical tournaments."""
    items = [
        ("Riftbound Launch Party", "Madrid, España", "15€"),
        ("TCG Weekend Barcelona", "Barcelona, España", "12€"),
        ("Liga Local — Sevilla", "Sevilla, España", "Gratis"),
        ("Grand Open Valencia", "Valencia, España", "20€"),
        ("Torneo Amistoso Bilbao", "Bilbao, España", "5€"),
        ("Riftbound Meet & Play", "Lisboa, Portugal", "8€"),
        ("Copa del Sur", "Málaga, España", "10€"),
        ("Torneo Nocturno", "Zaragoza, España", "Gratis"),
        ("Regional Qualifier", "París, Francia", "25€"),
    ]
    return [
        TournamentItem(
            title=t,
            date=(datetime.now() + timedelta(days=i * 5 + 2)).strftime("%d %b %Y — 11:00"),
            slots=f"{random.randint(16, 128)} plazas",
            price=p,
            location=loc,
        )
        for i, (t, loc, p) in enumerate(items)
    ]


def _placeholder_videos() -> list[VideoItem]:
    """Realistic placeholder YouTube videos."""
    items = [
        ("Top 5 Decks para Ranked — Febrero 2026", "RiftlabTCG"),
        ("Ahri OTK Combo Guide", "xNavalhaRB"),
        ("PACK OPENING: Shadows of the Rift!", "RUNEBOYS-YT"),
        ("Torneo Semanal Highlights", "PochiPoomRiftbound"),
        ("Guía para Principiantes #3", "TabernaDeDam"),
        ("Meta Analysis: Patch 2.4", "ramekiano"),
        ("Budget Deck Challenge", "MaxTaperaGaming"),
        ("Riftbound vs Other TCGs", "RiftlabTCG"),
        ("Live Coaching Session", "xNavalhaRB"),
    ]
    return [
        VideoItem(
            title=t,
            channel=c,
            thumbnail=f"https://placehold.co/400x225/111111/60a5fa?text={c}",
            url=f"https://www.youtube.com/@{c}/videos",
            date=(datetime.now() - timedelta(days=i)).strftime("%d %b %Y"),
        )
        for i, (t, c) in enumerate(items)
    ]


def _placeholder_decks() -> list[DeckItem]:
    """Realistic placeholder decks."""
    items = [
        ("Ahri Midrange", "SB", ["Spirit", "Ionia"], "ahri"),
        ("Garen Aggro", "BC", ["Demacia", "Noxus"], "garen"),
        ("Lux Control", "SB", ["Demacia", "Targon"], "lux"),
        ("Jinx Burn", "BC", ["Piltover", "Noxus"], "jinx"),
        ("Yasuo Stun Lock", "SB", ["Ionia", "Noxus"], "yasuo"),
        ("Ezreal Combo", "BC", ["Piltover", "Freljord"], "ezreal"),
        ("Darius Rally", "SB", ["Demacia", "Noxus"], "darius"),
        ("Twisted Fate Draw", "BC", ["Bilgewater", "Ionia"], "tf"),
        ("Braum Shield Wall", "SB", ["Freljord", "Demacia"], "braum"),
    ]
    return [
        DeckItem(
            title=t,
            date=(datetime.now() - timedelta(days=i * 2)).strftime("%d %b %Y"),
            set_initials=s,
            domains=d,
            legend_image=f"https://placehold.co/80x80/111111/d4a843?text={leg.upper()}",
            url="https://riftbound.gg/decks/",
        )
        for i, (t, s, d, leg) in enumerate(items)
    ]


# ─── Scraping functions (with fallback) ───

def fetch_noticias() -> list[NewsItem]:
    """Attempt to scrape Riftbound news, fallback to placeholders."""
    try:
        resp = requests.get(
            "https://riftbound.leagueoflegends.com/en-us/news/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for article in soup.select("article, .news-card, .post-card")[:9]:
                title_el = article.select_one("h2, h3, .title, a")
                img_el = article.select_one("img")
                link_el = article.select_one("a[href]")
                if title_el:
                    items.append(NewsItem(
                        title=title_el.get_text(strip=True),
                        url=link_el["href"] if link_el else "#",
                        image=img_el["src"] if img_el else "",
                        source="Riftbound Official",
                    ))
            if items:
                return items[:9]
    except Exception as e:
        logger.warning(f"Scraping noticias failed: {e}")
    return _placeholder_noticias()


def fetch_discord() -> list[NewsItem]:
    """Discord requires bot token for API. Using placeholders."""
    return _placeholder_discord()


def fetch_torneos_online() -> list[TournamentItem]:
    """Placeholder online tournaments."""
    return _placeholder_torneos_online()


def fetch_torneos_fisicos() -> list[TournamentItem]:
    """Attempt to scrape UVS locator, fallback to placeholders."""
    try:
        resp = requests.get(
            "https://locator.riftbound.uvsgames.com/events",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for card in soup.select(".event-card, .event, article")[:9]:
                title_el = card.select_one("h2, h3, .event-name, .title")
                if title_el:
                    items.append(TournamentItem(
                        title=title_el.get_text(strip=True),
                        date="TBD",
                        location=card.select_one(".location, .venue")
                                and card.select_one(".location, .venue").get_text(strip=True)
                                or "TBD",
                    ))
            if items:
                return items[:9]
    except Exception as e:
        logger.warning(f"Scraping torneos fisicos failed: {e}")
    return _placeholder_torneos_fisicos()


def fetch_videos() -> list[VideoItem]:
    """YouTube scraping is heavily rate-limited. Using placeholders."""
    return _placeholder_videos()


def fetch_decks() -> list[DeckItem]:
    """Attempt to scrape riftbound.gg decks, fallback to placeholders."""
    try:
        resp = requests.get(
            "https://riftbound.gg/decks/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10.0,
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            items = []
            for card in soup.select(".deck-card, .deck, article")[:9]:
                title_el = card.select_one("h2, h3, .deck-name, .title")
                if title_el:
                    items.append(DeckItem(
                        title=title_el.get_text(strip=True),
                        date="Reciente",
                    ))
            if items:
                return items[:9]
    except Exception as e:
        logger.warning(f"Scraping decks failed: {e}")
    return _placeholder_decks()
