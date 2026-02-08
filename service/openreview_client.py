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


def _get_profile_email(profile):
    """Get the best available unmasked email from a profile, or None."""
    if not hasattr(profile, "content") or not isinstance(profile.content, dict):
        return None
    content = profile.content

    # 1. preferredEmail (populated by with_preferred_emails edges, or set directly)
    pref = content.get("preferredEmail")
    if pref and "*" not in pref and "@" in pref:
        return pref

    # 2. emailsConfirmed — unmasked confirmed emails available in API v2
    for e in content.get("emailsConfirmed", []):
        if isinstance(e, str) and "*" not in e and "@" in e:
            return e

    # 3. emails list — pick the first unmasked one
    for e in content.get("emails", []):
        if isinstance(e, str) and "*" not in e and "@" in e:
            return e

    return None


def post_ac_comment(client, venue_id, paper_id, paper_number, user_id):
    """
    Post a private comment on a paper's forum as the AC, visible only to
    Program Chairs, Senior Area Chairs, and Area Chairs.

    Returns (paper_number, True) on success or (paper_number, False, error_msg)
    on failure.
    """
    try:
        # Look up AC's anonymous group for this paper
        anon_groups = client.get_groups(
            prefix=f"{venue_id}/Submission{paper_number}/Area_Chair_"
        )
        ac_anon_id = None
        for ag in anon_groups:
            if ag.members and user_id in ag.members:
                ac_anon_id = ag.id
                break

        if not ac_anon_id:
            return (paper_number, False, "Could not find AC anonymous ID for this paper")

        from pathlib import Path
        template_path = Path(__file__).parent / "templates" / "ac_comment.txt"
        comment_text = template_path.read_text().strip()

        client.post_note_edit(
            invitation=f"{venue_id}/Submission{paper_number}/-/Official_Comment",
            signatures=[ac_anon_id],
            note=openreview.api.Note(
                forum=paper_id,
                replyto=paper_id,
                readers=[
                    f"{venue_id}/Program_Chairs",
                    f"{venue_id}/Submission{paper_number}/Senior_Area_Chairs",
                    f"{venue_id}/Submission{paper_number}/Area_Chairs",
                ],
                writers=[venue_id, ac_anon_id],
                signatures=[ac_anon_id],
                content={
                    "comment": {"value": comment_text},
                },
            ),
        )
        return (paper_number, True)
    except Exception as e:
        return (paper_number, False, str(e))


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

        # Try fetching profiles with preferred emails from venue edges
        try:
            profiles = openreview.tools.get_profiles(
                client, unique_ids,
                with_preferred_emails=f"{venue_id}/-/Preferred_Emails",
            )
        except Exception:
            profiles = openreview.tools.get_profiles(client, unique_ids)

        needs_individual_fetch = []
        for profile in profiles:
            email = _get_profile_email(profile)
            name = None
            if hasattr(profile, "content") and isinstance(profile.content, dict):
                names = profile.content.get("names", [])
                if names:
                    n = names[0]
                    if isinstance(n, dict):
                        first = n.get("first", "")
                        last = n.get("last", "")
                        name = f"{first} {last}".strip()
            if not email:
                needs_individual_fetch.append(profile.id)
            email_map[profile.id] = email or profile.id
            name_map[profile.id] = name or profile.id

        # For profiles without emails, try individual fetch (may return
        # fuller data for authenticated ACs)
        for pid in needs_individual_fetch:
            try:
                full_profile = client.get_profile(pid)
                email = _get_profile_email(full_profile)
                if email:
                    email_map[pid] = email
            except Exception:
                pass

        # Map original input IDs that are emails (keys above are tilde IDs)
        for uid in unique_ids:
            if uid not in email_map and "@" in uid:
                email_map[uid] = uid
                name_map[uid] = uid

    for entry in paper_missing:
        rid = entry["reviewer_id"]
        entry["reviewer_email"] = email_map.get(rid, rid)
        entry["reviewer_name"] = name_map.get(rid, rid)
        results.append(entry)

    return results


