"""
OpenReview API interaction for finding missing reviews.
"""

import os
import re

import openreview
from openreview.api import OpenReviewClient


def get_client():
    """Authenticate with OpenReview using environment variables."""
    username = os.environ.get("OPENREVIEW_USERNAME")
    password = os.environ.get("OPENREVIEW_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD environment variables must be set"
        )
    return OpenReviewClient(
        baseurl="https://api2.openreview.net",
        username=username,
        password=password,
    )


def get_area_chair_venues(client, user_id):
    """
    Discover all venues where user_id is an Area Chair.

    Returns list of dicts: {venue_id, group_id}
    """
    groups = client.get_groups(member=user_id)
    seen = set()
    venues = []
    for g in groups:
        if g.id.endswith("/Area_Chairs"):
            venue_id = g.id.rsplit("/Area_Chairs", 1)[0]
            # Skip paper-level AC groups (e.g. .../Submission1234/Area_Chairs)
            last_segment = venue_id.rsplit("/", 1)[-1]
            if re.match(r"(Paper|Submission)\d+", last_segment):
                continue
            if venue_id not in seen:
                seen.add(venue_id)
                venues.append({"venue_id": venue_id, "group_id": g.id})
    return list(reversed(venues))


def get_ac_paper_assignments(client, venue_id, user_id):
    """
    Get paper IDs assigned to user_id as AC in the given venue.

    Returns list of paper note IDs.
    """
    edges = client.get_all_edges(
        invitation=f"{venue_id}/Area_Chairs/-/Assignment",
        tail=user_id,
    )
    return [edge.head for edge in edges]


def get_missing_reviews(client, venue_id, paper_ids):
    """
    For each paper, find reviewers who haven't submitted reviews.

    Returns list of dicts:
        {paper_title, paper_number, paper_id, reviewer_email, reviewer_id}
    """
    results = []
    all_missing_reviewer_ids = []

    paper_missing = []
    for paper_id in paper_ids:
        note = client.get_note(paper_id)
        title = note.content.get("title", {})
        if isinstance(title, dict):
            title = title.get("value", "Unknown")
        number = note.number

        # Get reviewer assignments
        reviewer_edges = client.get_all_edges(
            invitation=f"{venue_id}/Reviewers/-/Assignment",
            head=paper_id,
        )
        assigned_reviewer_ids = [edge.tail for edge in reviewer_edges]

        # Get submitted reviews — fetch all notes for the forum and filter
        # API v2 uses 'invitations' (list) instead of 'invitation' (string)
        all_notes = client.get_all_notes(forum=paper_id)
        review_notes = []
        for n in all_notes:
            inv = getattr(n, "invitation", None) or ""
            invs = getattr(n, "invitations", None) or []
            all_invs = invs + ([inv] if inv else [])
            if any(
                re.search(r"/-/Official_Review$", i) for i in all_invs
            ):
                review_notes.append(n)

        # Map anonymous reviewer IDs to profile IDs
        # Reviews are signed with anonymous IDs like venue/Submission123/Reviewer_abc
        anon_groups = client.get_groups(
            prefix=f"{venue_id}/Submission{number}/Reviewer_"
        )
        anon_to_profile = {}
        for ag in anon_groups:
            if ag.members:
                anon_to_profile[ag.id] = ag.members[0]

        # Find emergency declarations
        emergency_profiles = set()
        for n in all_notes:
            inv = getattr(n, "invitation", None) or ""
            invs = getattr(n, "invitations", None) or []
            all_invs = invs + ([inv] if inv else [])
            if any(
                re.search(r"/-/Emergency_Declaration$", i) for i in all_invs
            ):
                for sig in n.signatures:
                    if sig in anon_to_profile:
                        emergency_profiles.add(anon_to_profile[sig])

        # Find which profile IDs have submitted reviews
        reviewed_profiles = set()
        for review in review_notes:
            for sig in review.signatures:
                if sig in anon_to_profile:
                    reviewed_profiles.add(anon_to_profile[sig])

        # Find missing reviewers
        missing_ids = [
            rid for rid in assigned_reviewer_ids if rid not in reviewed_profiles
        ]

        for rid in missing_ids:
            paper_missing.append(
                {
                    "paper_title": title,
                    "paper_number": number,
                    "paper_id": paper_id,
                    "reviewer_id": rid,
                    "flag": "Emergency" if rid in emergency_profiles else "",
                }
            )
            all_missing_reviewer_ids.append(rid)

    # Batch-fetch profiles for all missing reviewer IDs
    email_map = {}
    name_map = {}
    if all_missing_reviewer_ids:
        unique_ids = list(set(all_missing_reviewer_ids))
        profiles = openreview.tools.get_profiles(client, unique_ids)
        for profile in profiles:
            email = None
            name = None
            if hasattr(profile, "content"):
                content = profile.content
                if isinstance(content, dict):
                    email = content.get("preferredEmail")
                    if not email:
                        emails = content.get("emails", [])
                        if emails:
                            email = emails[0]
                    names = content.get("names", [])
                    if names:
                        n = names[0]
                        if isinstance(n, dict):
                            first = n.get("first", "")
                            last = n.get("last", "")
                            name = f"{first} {last}".strip()
            if not email:
                email = profile.id
            email_map[profile.id] = email
            name_map[profile.id] = name or profile.id

    for entry in paper_missing:
        rid = entry["reviewer_id"]
        entry["reviewer_email"] = email_map.get(rid, rid)
        entry["reviewer_name"] = name_map.get(rid, rid)
        results.append(entry)

    return results


