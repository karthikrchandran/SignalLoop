"""Knowledge indexing worker entry point.

The local MVP path indexes synchronously through the API. This worker entry
point exists for the scheduled/nightly worker deployment path and can be wired
to Redis job consumption in the release-hardening slice.
"""

from __future__ import annotations


def main() -> None:
    """Run the knowledge indexing worker."""
    raise SystemExit("knowledge_indexing_worker queue loop is not enabled in this local slice")


if __name__ == "__main__":
    main()
