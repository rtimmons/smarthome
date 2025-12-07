# Operations - Maintenance & Planning

This directory contains documentation for system maintenance, verification procedures, and strategic planning.

## 🔍 Operations & Maintenance

**System maintenance and planning:**

1. **[system-verification.md](system-verification.md)** — System consistency verification procedures
2. **[improvements.md](improvements.md)** — Comprehensive improvements roadmap

## Files

- **[system-verification.md](system-verification.md)** — Verification procedures for configuration files, documentation, and build tools
- **[improvements.md](improvements.md)** — **Strategic roadmap** consolidating all improvement plans and priorities

## Common Operations

### System Verification
```bash
# Verify system consistency after changes
just --list  # Check all Justfiles parse correctly
just addons  # Verify add-on discovery
just setup   # Verify environment setup
```

### Planning & Improvements
- Review **[improvements.md](improvements.md)** for current priorities
- Update roadmap after completing major initiatives
- Use verification procedures before major releases

## Audience

- **Maintainers** — System consistency and health
- **Project leads** — Strategic planning and roadmap management
- **Contributors** — Understanding project direction and priorities

## See Also

- **[../README.md](../README.md)** — Main documentation index
- **[../../AGENTS.md](../../AGENTS.md)** — Operational procedures and workflows
