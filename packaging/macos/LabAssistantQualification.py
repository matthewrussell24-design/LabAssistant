"""Non-release py2app entry point for local bundle qualification."""

from __future__ import annotations

import os


if os.environ.get("LABASSISTANT_QUALIFICATION_SMOKE") == "1":
    from labassistant.packaging_smoke import main

    raise SystemExit(main())

from labassistant.desktop import main

raise SystemExit(main())
