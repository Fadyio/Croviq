# Engineering Principles

## Core Principles

- **Decoupled components**
- **Reusable modules**
- **Idempotent operations**
- **Explicit interfaces/contracts**
- **Structured observability**
- **Least-privilege security**
- **Configuration separated from code**
- **No hidden environment assumptions**
- **One feature at a time**
- **Local test before commit**
- **Push to main only after local verification**
- **Verify deployment/logs before declaring work complete**

## Definition of Done

For all future features:

1. **CODED**
2. **TESTED LOCALLY**
3. **COMMITTED**
4. **PUSHED**
5. **DEPLOYED** (when applicable)
6. **LOGS VERIFIED** (when applicable)
7. **BROWSER VERIFIED** (when applicable)

## Promotion Workflow

```
LOCAL
→ COMMIT
→ PUSH
→ CI
→ DEPLOY
→ LOG VERIFY
→ BROWSER VERIFY
```

Production infrastructure changes are never applied manually from application code.

