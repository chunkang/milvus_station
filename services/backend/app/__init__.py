# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

"""milvus_station backend service.

SPEC-INFRA-001 / TASK-006: health & status service.

Scope: health/status only. Embedding and search endpoints
(/api/embed, /api/search) are DEFERRED to SPEC-SEARCH-002 and are
intentionally NOT implemented here (they must 404).
"""

__version__ = "0.1.0"
