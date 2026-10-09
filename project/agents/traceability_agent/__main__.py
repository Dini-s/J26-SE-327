"""Allows ``python -m agents.traceability_agent <command>``."""

import sys

from agents.traceability_agent.cli import main

sys.exit(main())
