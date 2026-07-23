# Code Review Packet

This packet bounds review to the TANTRA Ecosystem Convergence sprint. It does
not copy source files or include unrelated historical modules.

## Review Order

1. `REPOSITORY_TREE.md`
2. `ARCHITECTURE_CHANGE_SUMMARY.md`
3. `DEPENDENCY_GRAPHS.md`
4. `TOP_FILES.md`
5. `FILE_CHANGES.md`
6. `IMPLEMENTATION_AREAS.md`

Primary implementation path:

```text
api.py -> runtime.py -> ecosystem.py -> store.py / depository.py
```

Primary behavioral review:

```text
pratham/tests/test_ecosystem_convergence.py
```

No implementation area names more than three critical files.
