#!/usr/bin/env python3
"""TrackFlow incident analysis CLI wrapper.

Run after installing or syncing the Python project in services/incident-processor.
"""

from incident_processor.cli import entrypoint


if __name__ == "__main__":
    entrypoint()

