"""
OpenReview API interaction for finding missing reviews and pulling reviews.
"""

import os
import re

import openreview
from openreview.api import OpenReviewClient


def get_client():
    """Authenticate with OpenReview using environment variables (loads .env if present)."""
    from dotenv import load_dotenv

    load_dotenv()
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


def _get_note_invitations(note):
    """Get all invitation strings from a note (handles API v1 and v2)."""
    inv = getattr(note, "invitation", None) or ""
    invs = getattr(note, "invitations", None) or []
    return invs + ([inv] if inv else [])


def _extract_content_value(field):
    """Extract the value from a content field (handles dict with 'value' key or plain string)."""
    if isinstance(field, dict):
        return field.get("value", "")
    return field


def _classify_note(note):
    """Classify a note by its invitation type. Returns a category string or None."""
    all_invs = _get_note_invitations(note)
    patterns = [
        (r"/-/Official_Review$", "review"),
        (r"/-/Meta_Review$", "meta_review"),
        (r"/-/Decision$", "decision"),
        (r"/-/Official_Comment$", "comment"),
    ]
    for pattern, category in patterns:
        if any(re.search(pattern, i) for i in all_invs):
            return category
    return None


def get_paper_reviews(client, venue_id, paper_ids):
    """
    Fetch the full discussion thread for each paper.

    Returns list of dicts with keys:
        paper_id, paper_number, title, authors, abstract,
        reviews, meta_reviews, decisions, comments
    """
    results = []

    for paper_id in paper_ids:
        note = client.get_note(paper_id)
        title = _extract_content_value(note.content.get("title", "Unknown"))
        authors = _extract_content_value(note.content.get("authors", []))
        if isinstance(authors, list):
            authors = ", ".join(authors)
        abstract = _extract_content_value(note.content.get("abstract", ""))
        number = note.number

        all_notes = client.get_all_notes(forum=paper_id)

        # Build anonymous-to-signature label mapping
        anon_groups = client.get_groups(
            prefix=f"{venue_id}/Submission{number}/Reviewer_"
        )
        # Map anon group ID to a short label like "Reviewer 1"
        anon_label = {}
        for i, ag in enumerate(anon_groups, 1):
            anon_label[ag.id] = f"Reviewer {i}"

        ac_anon_groups = client.get_groups(
            prefix=f"{venue_id}/Submission{number}/Area_Chair_"
        )
        for ag in ac_anon_groups:
            anon_label[ag.id] = "Area Chair"

        sac_anon_groups = client.get_groups(
            prefix=f"{venue_id}/Submission{number}/Senior_Area_Chair_"
        )
        for ag in sac_anon_groups:
            anon_label[ag.id] = "Senior Area Chair"

        # Classify notes
        reviews = []
        meta_reviews = []
        decisions = []
        comments = []

        for n in all_notes:
            if n.id == paper_id:
                continue  # skip the submission itself
            category = _classify_note(n)
            if category is None:
                continue

            # Extract all content fields
            content = {}
            if hasattr(n, "content") and isinstance(n.content, dict):
                for key, val in n.content.items():
                    content[key] = _extract_content_value(val)

            # Resolve signature label
            sig_labels = []
            for sig in (n.signatures or []):
                sig_labels.append(anon_label.get(sig, sig.rsplit("/", 1)[-1]))

            entry = {
                "id": n.id,
                "content": content,
                "signatures": sig_labels,
                "replyto": n.replyto,
            }

            if category == "review":
                reviews.append(entry)
            elif category == "meta_review":
                meta_reviews.append(entry)
            elif category == "decision":
                decisions.append(entry)
            elif category == "comment":
                comments.append(entry)

        results.append({
            "paper_id": paper_id,
            "paper_number": number,
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "reviews": reviews,
            "meta_reviews": meta_reviews,
            "decisions": decisions,
            "comments": comments,
        })

    return results


def get_reviewers_without_response(client, venue_id, paper_ids):
    """
    For each paper, find reviewers who submitted a review, received an author
    response to that review, but have not yet replied to it.

    Author responses are detected as Official_Comment notes signed by the
    Authors group that reply directly to a review note (venues may not use a
    dedicated Rebuttal invitation).

    Returns list of dicts:
        {paper_title, paper_number, paper_id, reviewer_id, reviewer_anon_id}
    """
    results = []

    for paper_id in paper_ids:
        note = client.get_note(paper_id)
        title = note.content.get("title", {})
        if isinstance(title, dict):
            title = title.get("value", "Unknown")
        number = note.number

        all_notes = client.get_all_notes(forum=paper_id)

        # Build a parent -> [children] map for thread traversal
        children_of = {}
        for n in all_notes:
            parent = getattr(n, "replyto", None)
            if parent:
                children_of.setdefault(parent, []).append(n)

        # Map anonymous reviewer IDs <-> profile IDs
        anon_groups = client.get_groups(
            prefix=f"{venue_id}/Submission{number}/Reviewer_"
        )
        anon_to_profile = {}
        profile_to_anon = {}
        for ag in anon_groups:
            if ag.members:
                anon_to_profile[ag.id] = ag.members[0]
                profile_to_anon[ag.members[0]] = ag.id

        def _is_official_comment(n):
            inv = getattr(n, "invitation", None) or ""
            invs = getattr(n, "invitations", None) or []
            return any(re.search(r"/-/Official_Comment$", i) for i in invs + ([inv] if inv else []))

        def _is_official_review(n):
            inv = getattr(n, "invitation", None) or ""
            invs = getattr(n, "invitations", None) or []
            return any(re.search(r"/-/Official_Review$", i) for i in invs + ([inv] if inv else []))

        def _signed_by_authors(n):
            return any(re.search(r"(/|^)Authors$", sig) for sig in (n.signatures or []))

        def _subtree_notes(root_id):
            """All notes in the subtree rooted at root_id (children, grandchildren, …)."""
            found = []
            queue = [root_id]
            while queue:
                current = queue.pop()
                for child in children_of.get(current, []):
                    found.append(child)
                    queue.append(child.id)
            return found

        # For each reviewer anon ID: find their review note
        review_note_by_anon = {}
        for n in all_notes:
            if not _is_official_review(n):
                continue
            for sig in (n.signatures or []):
                if sig in anon_to_profile:
                    review_note_by_anon[sig] = n

        if not review_note_by_anon:
            continue  # no reviews submitted yet

        # For each review, find the direct author-response comment (if any)
        # An author response is an Official_Comment by Authors replying to the review note.
        author_response_id_for_review = {}  # review_note_id -> author response note id
        for n in all_notes:
            if not _is_official_comment(n):
                continue
            if not _signed_by_authors(n):
                continue
            replyto = getattr(n, "replyto", None)
            review_note_ids = {rn.id for rn in review_note_by_anon.values()}
            if replyto in review_note_ids:
                author_response_id_for_review[replyto] = n.id

        if not author_response_id_for_review:
            continue  # no author responses posted yet

        # For each reviewer whose review got an author response, check whether
        # the reviewer posted any Official_Comment in that response's subtree.
        reviewer_edges = client.get_all_edges(
            invitation=f"{venue_id}/Reviewers/-/Assignment",
            head=paper_id,
        )
        assigned_reviewer_ids = [edge.tail for edge in reviewer_edges]

        for rid in assigned_reviewer_ids:
            anon_id = profile_to_anon.get(rid)
            if not anon_id:
                continue
            review_note = review_note_by_anon.get(anon_id)
            if not review_note:
                continue  # reviewer has no review yet
            author_response_id = author_response_id_for_review.get(review_note.id)
            if not author_response_id:
                continue  # no author response to this reviewer's review

            # Check whether the reviewer replied anywhere in the author-response thread
            replied = any(
                anon_id in (n.signatures or []) and _is_official_comment(n)
                for n in _subtree_notes(author_response_id)
            )
            if not replied:
                results.append({
                    "paper_title": title,
                    "paper_number": number,
                    "paper_id": paper_id,
                    "reviewer_id": rid,
                    "reviewer_anon_id": anon_id,
                })

    return results


def post_reviewer_rebuttal_comment(client, venue_id, paper_id, paper_number, user_id, reviewer_anon_ids):
    """
    Post a single private forum comment visible to all specified reviewers and
    the AC/SAC/PC hierarchy, asking them to respond to the author rebuttal.

    reviewer_anon_ids: list of anonymous reviewer group IDs for this paper.

    Returns (paper_number, True) on success or
            (paper_number, False, error_msg) on failure.
    """
    try:
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
        template_path = Path(__file__).parent / "templates" / "reviewer_rebuttal_nudge.txt"
        comment_text = template_path.read_text().strip()

        readers = [
            f"{venue_id}/Program_Chairs",
            f"{venue_id}/Submission{paper_number}/Senior_Area_Chairs",
            f"{venue_id}/Submission{paper_number}/Area_Chairs",
        ] + list(reviewer_anon_ids)

        client.post_note_edit(
            invitation=f"{venue_id}/Submission{paper_number}/-/Official_Comment",
            signatures=[ac_anon_id],
            note=openreview.api.Note(
                forum=paper_id,
                replyto=paper_id,
                readers=readers,
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


