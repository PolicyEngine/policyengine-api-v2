#!/usr/bin/env python3
"""
Calls the tagger API cleanup endpoint to remove old traffic tags.

Usage:
    python scripts/cleanup_old_revisions.py <tagger_url> <token> [keep_count]

Arguments:
    tagger_url  - Full URL of the tagger API (e.g., "https://tagger-api-xxx.run.app")
    token       - ID token for authentication
    keep_count  - Number of tags to keep (default: 40)

The cleanup endpoint:
- Gets all existing traffic tags from Cloud Run
- Keeps the newest US and UK tags (safeguards) plus the next N newest
- Updates traffic configuration in one atomic operation
- Does NOT touch metadata files (they enable on-demand tag recreation)
"""

import sys
import json
import urllib.request
import urllib.error


def main():
    if len(sys.argv) < 3:
        print("Usage: cleanup_old_revisions.py <tagger_url> <token> [keep_count]")
        sys.exit(1)

    tagger_url = sys.argv[1]
    token = sys.argv[2]
    keep_count = int(sys.argv[3]) if len(sys.argv) > 3 else 40

    url = f"{tagger_url}/cleanup?keep={keep_count}"
    print("Calling cleanup endpoint on tagger API")
    print(f"  URL: {url}")

    request = urllib.request.Request(
        url,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read().decode("utf-8"))
            http_code = response.status

            print(f"Cleanup successful (HTTP {http_code}):")
            print(json.dumps(body, indent=2))

            # Extract and display summary
            total = body.get("total_tags_found", 0)
            kept = len(body.get("tags_kept", []))
            removed = len(body.get("tags_removed", []))
            newest_us = body.get("newest_us_tag") or "none"
            newest_uk = body.get("newest_uk_tag") or "none"
            errors = body.get("errors", [])

            print()
            print("Summary:")
            print(f"  Total tags found: {total}")
            print(f"  Tags kept: {kept}")
            print(f"  Tags removed: {removed}")
            print(f"  Newest US tag: {newest_us}")
            print(f"  Newest UK tag: {newest_uk}")
            print(f"  Errors: {len(errors)}")

            if errors:
                print()
                print("Warnings during cleanup:")
                for error in errors:
                    print(f"  - {error}")

    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        print(f"Cleanup failed with HTTP {e.code}:")
        print(body)
        # Don't fail the deployment if cleanup fails - it's not critical
        print("::warning::Cleanup failed but deployment succeeded. Review logs for details.")

    except urllib.error.URLError as e:
        print(f"Cleanup failed with network error: {e.reason}")
        print("::warning::Cleanup failed but deployment succeeded. Review logs for details.")


if __name__ == "__main__":
    main()
