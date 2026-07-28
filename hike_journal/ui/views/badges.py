from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

from hike_journal.domain.badges import (
    BADGE_CATEGORIES,
    BadgeCategory,
    TrailBadge,
    calculate_trail_badges,
)
from hike_journal.services.repositories import HikeJournalRepository


def _format_value(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"


def _unit_for(badge: TrailBadge) -> str:
    metric = badge.definition.metric
    if metric in {"total_miles", "longest_hike"}:
        return "mile" if badge.current == 1 else "miles"
    if metric == "hike_count":
        return "hike" if badge.current == 1 else "hikes"
    if metric == "completed_quests":
        return "quest" if badge.current == 1 else "quests"
    if metric == "rare_finds":
        return "rare find" if badge.current == 1 else "rare finds"
    return "species"


def _progress_copy(badge: TrailBadge) -> str:
    current = _format_value(badge.current)
    target = _format_value(badge.definition.target)
    unit = _unit_for(badge)
    if badge.earned:
        return f"{current} {unit} recorded"
    return f"{current} of {target} {unit}"


def _seal_markup(badge: TrailBadge, *, large: bool = False, preview: bool = False) -> str:
    definition = badge.definition
    state_class = "is-earned" if badge.earned else "is-locked"
    if preview:
        state_class += " is-preview"
    size_class = " trail-medal-seal--large" if large else ""
    target = _format_value(definition.target)
    return f"""
        <div class="trail-medal-seal trail-medal-seal--{escape(definition.finish)} {state_class}{size_class}" aria-hidden="true">
            <span class="trail-medal-ribbon trail-medal-ribbon--left"></span>
            <span class="trail-medal-ribbon trail-medal-ribbon--right"></span>
            <span class="trail-medal-disc">
                <span class="trail-medal-face">
                    <strong>{escape(definition.mark)}</strong>
                    <small>{escape(target)}</small>
                </span>
            </span>
        </div>
    """


def _medal_markup(badge: TrailBadge, index: int) -> str:
    definition = badge.definition
    state_label = "Earned" if badge.earned else _progress_copy(badge)
    earned_class = " is-earned" if badge.earned else ""
    return f"""
        <details class="trail-medal-item{earned_class}" style="--medal-index:{index}">
            <summary>
                {_seal_markup(badge)}
                <span class="trail-medal-name">{escape(definition.title)}</span>
                <span class="trail-medal-state">{escape(state_label)}</span>
            </summary>
            <div class="trail-medal-detail">
                <p>{escape(definition.requirement)}</p>
                <div class="trail-medal-progress" role="progressbar" aria-label="{escape(definition.title)} progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{round(badge.progress * 100)}">
                    <span style="--progress:{badge.progress:.4f}"></span>
                </div>
                <span>{escape(_progress_copy(badge))}</span>
            </div>
        </details>
    """


def _category_markup(
    category: BadgeCategory,
    badges: list[TrailBadge],
    *,
    start_index: int,
) -> str:
    medals = "".join(
        _medal_markup(badge, start_index + index)
        for index, badge in enumerate(badges)
    )
    earned = sum(1 for badge in badges if badge.earned)
    return f"""
        <section class="trail-medal-section">
            <header class="trail-medal-section-head">
                <div>
                    <p>{escape(category.label)}</p>
                    <h2>{escape(category.description)}</h2>
                </div>
                <span>{earned} / {len(badges)} earned</span>
            </header>
            <div class="trail-medal-grid">{medals}</div>
        </section>
    """


def render_badges_view(
    repository: HikeJournalRepository,
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
    user_context: dict[str, Any],
) -> None:
    quests = repository.list_species_quests(
        owner_subject=user_context.get("subject"),
        owner_email=user_context.get("email"),
    )
    badges = calculate_trail_badges(hikes, confirmed_observations, quests)
    earned_count = sum(1 for badge in badges if badge.earned)
    unearned = [badge for badge in badges if not badge.earned]
    next_badge = max(
        unearned,
        key=lambda badge: (badge.progress, -badge.definition.target),
        default=None,
    )
    collection_progress = earned_count / len(badges) if badges else 0.0
    if next_badge:
        next_medal = f"""
            <div class="trail-medal-next">
                {_seal_markup(next_badge, large=True, preview=True)}
                <div>
                    <span>Closest medal</span>
                    <strong>{escape(next_badge.definition.title)}</strong>
                    <small>{escape(_progress_copy(next_badge))}</small>
                </div>
            </div>
        """
    else:
        next_medal = """
            <div class="trail-medal-next trail-medal-next--complete">
                <div>
                    <span>Collection complete</span>
                    <strong>Every trail medal earned</strong>
                    <small>A field record for the ages.</small>
                </div>
            </div>
        """

    category_sections = []
    index = 0
    for category in BADGE_CATEGORIES:
        category_badges = [
            badge
            for badge in badges
            if badge.definition.category.key == category.key
        ]
        category_sections.append(
            _category_markup(category, category_badges, start_index=index)
        )
        index += len(category_badges)

    st.html(
        f"""
        <main class="trail-medals">
            <section class="trail-medal-hero">
                <div class="trail-medal-hero-copy">
                    <p class="trail-medal-eyebrow">HikeJournal · Trail Medals</p>
                    <h1>Every mile leaves a mark.</h1>
                    <p>Milestones drawn from your hikes, distance, Field Quests, and the living archive you have identified along the way.</p>
                    <div class="trail-medal-total">
                        <strong>{earned_count}</strong>
                        <span>of {len(badges)} earned</span>
                    </div>
                    <div class="trail-medal-overall-progress" role="progressbar" aria-label="Overall medal progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="{round(collection_progress * 100)}">
                        <span style="--progress:{collection_progress:.4f}"></span>
                    </div>
                </div>
                {next_medal}
            </section>
            <div class="trail-medal-note">Progress updates automatically as confirmed observations and completed outings enter your journal. Select any medal for its exact requirement.</div>
            {''.join(category_sections)}
        </main>
        """
    )
