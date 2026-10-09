# Acquisition package map

```text
acquisition/
├── shared/                  # Platform-neutral helpers
└── platforms/
    ├── jobwant_104/
    │   ├── client/          # 104 transport and pagination
    │   ├── capture/         # Capture flows, category catalog, immutable batches
    │   ├── distributed/     # Coordinator, worker, pacing, queue, summaries
    │   ├── persistence/     # 104 Bronze/Silver PostgreSQL operations
    │   └── reporting/       # Read-only coverage and browser viewer
    └── yes123/              # yes123 API, catalog, capture, loader, and diagnostic modules
```

## Boundaries

- Put platform-neutral address, salary, SQL parsing, and schema helpers in `shared/`.
- Put API contracts, parsing, native identifiers, and source-specific persistence under that platform's folder.
- Keep each platform's capture formats and database contracts independent. Shared helpers must not assume a platform's API fields or pagination rules.
- Use package-relative imports inside `acquisition`; command wrappers under `tools/` remain the stable operator entry points.
- Keep raw capture data under `data/<platform>/`, outside this source-code tree.

## JobWant 104 groups

| Package | Responsibility |
| --- | --- |
| `platforms/jobwant_104/client/` | Existing 104 transport and pagination contracts |
| `platforms/jobwant_104/capture/` | Search/category capture workflows, category catalog, and immutable local batches |
| `platforms/jobwant_104/distributed/` | Distributed run coordination, worker pacing, queue, and summaries |
| `platforms/jobwant_104/persistence/` | 104-specific Bronze/Silver PostgreSQL writes and local batch synchronization |
| `platforms/jobwant_104/reporting/` | Read-only coverage output and local browser viewer |

The `yes123/` package stays flat while its files remain small and single-purpose: client and parser, catalog/capture/batch runner, loader, adaptive pacing, and probe. Keep each source contract in this platform package; bulk capture remains blocked until rights and code mappings are evidenced.
