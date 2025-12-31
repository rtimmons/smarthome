# Visual Diff System for Printer Labels

A modern, iTerm2-enhanced visual diff system for reviewing visual regression test failures in printer label templates.

## Overview

The visual diff system provides multiple ways to review and manage visual differences when printer label tests fail:

- **Interactive Review**: Step through differences one by one with inline images
- **Grid Overview**: Thumbnail grid showing all differences at once
- **Text Summary**: Quick text-based overview of all differences
- **Integrated Testing**: Automatic diff display when tests fail

## Quick Start

```bash
# Show help with all available commands
just visual-diff-help

# Quick overview of any differences
just visual-diff-summary

# Modern grid view (requires iTerm2)
just visual-diff-grid

# Interactive review with full-size images
just visual-diff

# Run tests and automatically show diffs if any fail
just test-visual
```

## Commands Reference

### Review Commands

| Command | Description | Best For |
|---------|-------------|----------|
| `just visual-diff [pattern]` | Interactive review with full-size images | Detailed analysis of specific differences |
| `just visual-diff-grid [pattern]` | Thumbnail grid overview | Quick visual scanning of multiple differences |
| `just visual-diff-all [pattern]` | Show all differences non-interactively | Batch review or documentation |
| `just visual-diff-summary [pattern]` | Text summary only | Quick status check, CI/CD integration |

### Management Commands

| Command | Description |
|---------|-------------|
| `just visual-diff-clean [pattern]` | Remove diff files with confirmation |
| `just test-visual` | Run tests and show diffs if any fail |
| `just test-visual-update` | Run tests and update baselines |

### Pattern Filtering

All commands support optional pattern filtering:

```bash
just visual-diff-grid best_by   # Only best_by template diffs
just visual-diff-clean qr       # Only QR code related diffs
```

## Features

### 🖼️ iTerm2 Integration

- **Inline Images**: Images display directly in the terminal
- **Side-by-Side Comparison**: Expected vs. actual images shown together
- **Thumbnail Grid**: Compact overview of multiple differences
- **Automatic Scaling**: Images sized appropriately for terminal viewing

### 🎨 Modern Terminal UI

- **Rich Colors**: Color-coded output for different types of information
- **Unicode Symbols**: Modern symbols for visual clarity (⚡ 📋 🆕 ✓ ✗)
- **Progress Indicators**: Clear indication of current position in review
- **Interactive Controls**: Simple keyboard navigation

### 🔧 Developer Workflow Integration

- **Test Integration**: Automatic diff display when visual tests fail
- **Pattern Matching**: Filter diffs by template type or feature
- **Batch Operations**: Clean up multiple diff files at once
- **Help System**: Comprehensive help and examples

## Interactive Review Controls

When using `just visual-diff`:

- **Enter**: Continue to next difference
- **q**: Quit review
- **d**: Delete current diff file

## File Organization

```
printer/tests/baselines/
├── baseline_image.png          # Expected result
├── DIFF_baseline_image.png     # Actual result (when test fails)
└── ...
```

## Requirements

- **iTerm2**: Required for inline image display
- **macOS**: Uses iTerm2's imgcat utility
- **Terminal**: Works in other terminals with reduced functionality

## Troubleshooting

### Images Not Displaying

If images don't display inline:
1. Ensure you're using iTerm2
2. Check that imgcat is available: `/Applications/iTerm.app/Contents/Resources/utilities/imgcat`
3. Use `--no-images` flag for text-only mode

### No Differences Found

If no differences are shown but tests are failing:
1. Run tests manually: `just test`
2. Check that visual regression tests are included
3. Verify baseline files exist in `tests/baselines/`

## Integration with CI/CD

For automated environments, use the summary mode:

```bash
# Exit code 0 if no diffs, non-zero if diffs found
just visual-diff-summary

# Text-only output suitable for logs
just visual-diff-summary --no-images
```
