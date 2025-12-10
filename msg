feat: Complete deployment system cleanup and documentation updates

## Summary
Comprehensive cleanup of the deployment infrastructure to ensure consistency,
accuracy, and production readiness. All documentation updated to reflect the
enhanced deployment system, old function remnants removed, and test coverage
verified.

## Changes Made

### 🧹 Code Cleanup
- **Removed unused `run_deploy` wrapper function** from `addon_builder.py`
- **Verified CLI consistency** - both single and batch deployment commands have `--verbose` flags
- **Eliminated old deployment paradigms** - no vestigial references to outdated patterns

### 📚 Documentation Updates
- **Updated `talos/docs/USAGE.md`** - Enhanced batch deployment section with new CLI commands
- **Updated `talos/README.md`** - Added `talos addons deploy` to batch operations
- **Updated `talos/docs/ARCHITECTURE.md`** - Corrected deployment workflow to use enhanced system
- **Enhanced deployment guide** remains accurate and comprehensive

### ✅ Quality Assurance
- **All tests passing** - 42 fast tests + 11 slow tests (53 total)
- **Full deployment test coverage** - 16 deployment-specific tests verified
- **Container build tests** - All add-ons build successfully
- **CLI functionality verified** - Both single and batch deployment commands working

### 🎯 Key Improvements
1. **Consistent API** - All deployment functions use same signature with `verbose` parameter
2. **Clean documentation** - No references to old `talos addons run deploy` pattern
3. **Enhanced user experience** - Rich progress tracking and comprehensive error handling
4. **Production reliability** - Robust error handling with detailed troubleshooting steps

## Verification
- ✅ `just test` - All 42 fast tests pass in ~50 seconds
- ✅ `just test-slow` - All 11 slow tests pass in ~84 seconds  
- ✅ CLI commands work: `talos addon deploy --help` and `talos addons deploy --help`
- ✅ Documentation consistency verified across all files
- ✅ No old deployment function references remain

## Impact
The deployment system is now **production-ready** with:
- Comprehensive error handling and recovery mechanisms
- Rich user experience with progress tracking and detailed output
- Clean, maintainable codebase with no technical debt
- Thorough test coverage ensuring reliability
- Accurate documentation reflecting current implementation

Ready for deployment to production environments.
