from __future__ import annotations

from typing import Any

import streamlit as st

from hike_journal.domain.longitudinal import build_hike_comparison, build_place_profile
from hike_journal.services.repositories import HikeJournalRepository


LIFE_GROUP_ICONS = {
    "plantae": "🌿",
    "aves": "🪶",
    "mammalia": "🐾",
    "fungi": "🍄",
    "insecta": "🦋",
    "arachnida": "🕸️",
    "reptilia": "🦎",
    "amphibia": "🐸",
    "actinopterygii": "🐟",
}


def render_places_view(
    repository: HikeJournalRepository,
    hikes: list[dict[str, Any]],
    confirmed_observations: list[dict[str, Any]],
) -> None:
    st.markdown("<div class='section-kicker'>Longitudinal field record</div>", unsafe_allow_html=True)
    st.title("Places over time")
    st.caption(
        "Explore what your own journal has accumulated at familiar places. "
        "These are personal records, not claims about a species’ full ecology."
    )

    locations = repository.list_hike_locations()
    tagged_location_ids = {
        str(tag.get("id") or "")
        for hike in hikes
        for tag in hike.get("location_tags") or []
        if tag.get("id")
    }
    choices = [location for location in locations if str(location.get("id") or "") in tagged_location_ids]
    if not choices:
        st.info("Tag hikes with a saved location to begin a Place Profile.")
        return

    selected_name = st.selectbox(
        "Place",
        [str(location.get("name") or "Unknown place") for location in choices],
        key="longitudinal_place_name",
    )
    location = next(item for item in choices if str(item.get("name") or "") == selected_name)
    location_id = str(location.get("id") or "")
    place_hikes = [
        hike
        for hike in hikes
        if not hike.get("is_archived")
        and any(str(tag.get("id") or "") == location_id for tag in hike.get("location_tags") or [])
    ]
    for hike in place_hikes:
        photos = repository.list_photos(str(hike.get("id") or ""))
        cover_id = str(hike.get("cover_photo_id") or "")
        cover = next((photo for photo in photos if str(photo.get("id") or "") == cover_id), None)
        if cover is None:
            cover = next(
                (
                    photo
                    for photo in reversed(photos)
                    if not str(photo.get("content_type") or "").lower().startswith("video/")
                ),
                None,
            )
        hike["cover_url"] = str((cover or {}).get("public_url") or "")
    profile = build_place_profile(location, place_hikes, confirmed_observations)
    summary = profile["summary"]
    columns = st.columns(5)
    columns[0].metric("Recorded visits", summary["outing_count"])
    columns[1].metric("Distance", f"{summary['total_distance_miles']:.1f} mi")
    columns[2].metric("Species", summary["species_count"])
    columns[3].metric("Observations", summary["observation_count"])
    columns[4].metric("First visit", summary["first_visit"] or "—")

    season, progression = st.columns([0.48, 0.52], gap="large")
    with season:
        st.subheader("Your seasonal record")
        month_rows = profile["seasonal_history"]["months"]
        st.bar_chart(
            month_rows,
            x="label",
            y="count",
            x_label="Month",
            y_label="Recorded observations",
        )
    with progression:
        st.subheader("Biodiversity by visit")
        chronological = list(reversed(profile["visits"]))
        st.line_chart(
            chronological,
            x="hike_date",
            y="cumulative_species_count",
            x_label="Visit",
            y_label="Cumulative species",
        )

    st.subheader("Life recorded")
    st.caption("Open a life group to browse every distinct confirmed species you have recorded here.")
    for group in profile["taxon_groups"]:
        icon = LIFE_GROUP_ICONS.get(str(group["name"]).lower(), "◌")
        with st.expander(f"{icon} {group['name']} · {group['count']}"):
            for species in group["species"]:
                st.markdown(
                    f"**{species['common_name']}**  \n"
                    f"*{species['scientific_name']}* · {species['encounter_count']} encounter"
                    f"{'s' if species['encounter_count'] != 1 else ''}"
                )

    st.subheader("Visit history")
    for visit in profile["visits"]:
        image, detail = st.columns([0.2, 0.8], vertical_alignment="center")
        if visit["cover_url"]:
            image.image(visit["cover_url"], width="stretch")
        else:
            image.caption("No cover photo")
        detail.markdown(f"**{visit['hike_date']} · {visit['title']}**")
        detail.caption(
            f"{visit['species_count']} species · {visit['observation_count']} observations · "
            f"{visit['new_species_count']} new then · {visit['cumulative_species_count']} cumulative"
        )
        st.divider()

    st.divider()
    st.subheader("Compare two field journals")
    st.caption("Species comparisons use confirmed records from each outing.")
    if len(hikes) < 2:
        st.info("Record another hike to compare visits.")
        return
    labels = {
        f"{hike.get('hike_date', '')} · {hike.get('title', 'Untitled hike')}": hike
        for hike in hikes
        if not hike.get("is_archived")
    }
    comparison_columns = st.columns(2)
    label_a = comparison_columns[0].selectbox("First journal", list(labels), key="comparison_hike_a")
    remaining = [label for label in labels if label != label_a]
    label_b = comparison_columns[1].selectbox("Second journal", remaining, key="comparison_hike_b")
    comparison = build_hike_comparison(labels[label_a], labels[label_b], confirmed_observations)
    groups = st.columns(3, gap="large")
    for column, title, key in (
        (groups[0], "Recorded on both", "shared"),
        (groups[1], f"Only {comparison['hike_a']['hike_date']}", "only_a"),
        (groups[2], f"Only {comparison['hike_b']['hike_date']}", "only_b"),
    ):
        column.markdown(f"**{title}**")
        species = comparison["species"][key]
        if not species:
            column.caption("No confirmed species in this group.")
        for item in species:
            column.markdown(
                f"{item['common_name']}  \n*{item['scientific_name']}*"
            )
