#!/usr/bin/env bash
set -euo pipefail

# Modern visual diff tool for printer label regression tests
# Uses iTerm2's imgcat for inline image display with rich terminal formatting

# Colors and formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly BLUE='\033[0;34m'
readonly YELLOW='\033[1;33m'
readonly CYAN='\033[0;36m'
readonly PURPLE='\033[0;35m'
readonly BOLD='\033[1m'
readonly DIM='\033[2m'
readonly RESET='\033[0m'

# Unicode symbols for modern terminal experience
readonly ARROW="→"
readonly CHECK="✓"
readonly CROSS="✗"
readonly DIFF_SYMBOL="⚡"
readonly BASELINE_SYMBOL="📋"
readonly NEW_SYMBOL="🆕"

BASELINES_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../tests/baselines" && pwd)"
IMGCAT_PATH="/Applications/iTerm.app/Contents/Resources/utilities/imgcat"

usage() {
    cat << EOF
${BOLD}Visual Diff Tool for Printer Labels${RESET}

${CYAN}USAGE:${RESET}
    $(basename "$0") [OPTIONS] [PATTERN]

${CYAN}OPTIONS:${RESET}
    -h, --help          Show this help message
    -l, --list          List all available diffs
    -a, --all           Show all diffs (default: interactive mode)
    -c, --clean         Remove all DIFF_*.png files
    -s, --summary       Show summary of differences only
    -g, --grid          Show thumbnail grid overview (requires imgcat)
    --no-images         Skip image display (text summary only)

${CYAN}PATTERN:${RESET}
    Optional pattern to filter diff files (e.g., "receipt" or "best_by")

${CYAN}EXAMPLES:${RESET}
    $(basename "$0")                    # Interactive mode for all diffs
    $(basename "$0") receipt            # Show only receipt-related diffs
    $(basename "$0") --all              # Show all diffs non-interactively
    $(basename "$0") --clean            # Remove all diff files
    $(basename "$0") --summary          # Quick summary of all diffs
    $(basename "$0") --grid             # Thumbnail grid overview

${DIM}This tool leverages iTerm2's inline image capabilities for a modern
terminal-based visual diff experience.${RESET}
EOF
}

check_requirements() {
    if [[ ! -d "$BASELINES_DIR" ]]; then
        echo -e "${RED}${CROSS} Baselines directory not found: $BASELINES_DIR${RESET}" >&2
        exit 1
    fi

    if [[ ! -x "$IMGCAT_PATH" ]]; then
        echo -e "${YELLOW}⚠️  imgcat not found at $IMGCAT_PATH${RESET}" >&2
        echo -e "${DIM}   Image display will be disabled. Install iTerm2 for full functionality.${RESET}" >&2
        IMGCAT_PATH=""
    fi
}

find_diff_files() {
    local pattern="${1:-}"
    local files=()
    
    while IFS= read -r -d '' file; do
        if [[ -z "$pattern" ]] || [[ "$(basename "$file")" == *"$pattern"* ]]; then
            files+=("$file")
        fi
    done < <(find "$BASELINES_DIR" -name "DIFF_*.png" -print0 2>/dev/null)
    
    if [[ ${#files[@]} -gt 0 ]]; then
        printf '%s\n' "${files[@]}"
    fi
}

get_baseline_path() {
    local diff_file="$1"
    local basename_file
    basename_file="$(basename "$diff_file")"
    basename_file="${basename_file#DIFF_}"
    echo "$BASELINES_DIR/$basename_file"
}

generate_enhanced_diff() {
    local baseline="$1"
    local diff_file="$2"
    local output_dir="$3"

    local basename_file=$(basename "$baseline" .png)
    local enhanced_diff="${output_dir}/ENHANCED_${basename_file}.png"

    # Generate enhanced visual diff if it doesn't exist or is older than source files
    if [[ ! -f "$enhanced_diff" ]] || [[ "$baseline" -nt "$enhanced_diff" ]] || [[ "$diff_file" -nt "$enhanced_diff" ]]; then
        echo -e "${DIM}🔄 Generating enhanced visual diff...${RESET}"
        local output
        local python_cmd="python3"
        local script_dir
        script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

        # Try to use virtual environment if available
        if [[ -f "$script_dir/../.venv/bin/python" ]]; then
            python_cmd="$script_dir/../.venv/bin/python"
        fi
        if output=$($python_cmd "$script_dir/generate-visual-diff.py" "$baseline" "$diff_file" "$enhanced_diff" 2>&1); then
            if [[ "$output" == *"no enhanced diff needed"* ]]; then
                echo -e "${DIM}✓ Images are identical - no enhanced diff needed${RESET}"
                return 2  # Special return code for identical images
            else
                echo -e "${DIM}✓ Enhanced diff generated${RESET}"
            fi
        else
            echo -e "${DIM}✗ Failed to generate enhanced diff: $output${RESET}"
            return 1
        fi
    fi

    echo "$enhanced_diff"
}

get_template_info() {
    local filename="$1"
    local template_name=""
    local parameters=""

    # Extract template type and parameters from filename
    case "$filename" in
        best_by_*)
            template_name="Best By Label"
            case "$filename" in
                *qr*) parameters="with QR code" ;;
                *custom*) parameters="custom text" ;;
                *offset*) parameters="with date offset" ;;
                *prefix*) parameters="with prefix" ;;
                *) parameters="simple date" ;;
            esac
            ;;
        kitchen_label_*)
            template_name="Kitchen Label"
            case "$filename" in
                *three_lines*) parameters="3 lines" ;;
                *two_lines*) parameters="2 lines" ;;
                *single_line*) parameters="1 line" ;;
                *long_text*) parameters="long text" ;;
                *) parameters="" ;;
            esac
            ;;
        bluey_*)
            template_name="Bluey Label"
            case "$filename" in
                *bluey_2*) template_name="Bluey Label 2" ;;
            esac
            case "$filename" in
                *repeated*) parameters="repeated titles" ;;
                *long_text*) parameters="long text" ;;
                *missing_symbol*) parameters="missing symbol" ;;
                *alt_symbol*) parameters="alt symbol" ;;
                *full_fields*) parameters="full fields" ;;
                *initials*) parameters="initials only" ;;
                *default*) parameters="default" ;;
                *) parameters="" ;;
            esac
            ;;
        *)
            template_name="Unknown Template"
            parameters=""
            ;;
    esac

    if [[ -n "$parameters" ]]; then
        echo "$template_name ($parameters)"
    else
        echo "$template_name"
    fi
}

display_image_pair() {
    local baseline_path="$1"
    local diff_path="$2"
    local label="$3"

    local template_info
    template_info="$(get_template_info "$label")"

    echo -e "\n${BOLD}${DIFF_SYMBOL} Comparing: ${CYAN}$label${RESET}"
    echo -e "${DIM}Template: $template_info${RESET}"
    echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"

    if [[ -n "$IMGCAT_PATH" ]]; then
        # Try to generate and show enhanced diff first
        local enhanced_diff
        if [[ -f "$baseline_path" ]]; then
            enhanced_diff=$(generate_enhanced_diff "$baseline_path" "$diff_path" "$(dirname "$diff_path")")
            local enhanced_result=$?

            if [[ $enhanced_result -eq 2 ]]; then
                echo -e "\n${GREEN}✓ Images are identical (0 pixels changed) - skipping display${RESET}"
                return 0
            elif [[ -f "$enhanced_diff" ]]; then
                echo -e "\n${PURPLE}🎯 ENHANCED VISUAL DIFF (with difference highlighting):${RESET}"
                "$IMGCAT_PATH" --width 80 "$enhanced_diff" 2>/dev/null || echo -e "${DIM}[Enhanced diff display failed]${RESET}"
                echo -e "\n${DIM}━━━ Original Images ━━━${RESET}"
            fi
        fi

        echo -e "\n${GREEN}${BASELINE_SYMBOL} BASELINE (Expected)${RESET}"
        if [[ -f "$baseline_path" ]]; then
            "$IMGCAT_PATH" --width 60 "$baseline_path"
        else
            echo -e "${RED}${CROSS} Baseline file not found: $baseline_path${RESET}"
        fi

        echo -e "\n${RED}${NEW_SYMBOL} CURRENT (Actual)${RESET}"
        "$IMGCAT_PATH" --width 60 "$diff_path"
    else
        echo -e "${YELLOW}Image display disabled (imgcat not available)${RESET}"
        echo -e "${GREEN}${BASELINE_SYMBOL} Baseline: ${RESET}$baseline_path"
        echo -e "${RED}${NEW_SYMBOL} Current:  ${RESET}$diff_path"
    fi
}

show_diff_summary() {
    local diff_files
    diff_files="$(find_diff_files "$@")"

    if [[ -z "$diff_files" ]]; then
        echo -e "${GREEN}${CHECK} No visual differences found!${RESET}"
        echo -e "${DIM}All visual regression tests are passing.${RESET}"
        return 0
    fi

    local count=0
    while IFS= read -r diff_file; do
        [[ -n "$diff_file" ]] && count=$((count + 1))
    done <<< "$diff_files"

    echo -e "${BOLD}${DIFF_SYMBOL} Visual Regression Summary${RESET}"
    echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${RED}Found ${count} visual difference(s):${RESET}\n"

    while IFS= read -r diff_file; do
        [[ -z "$diff_file" ]] && continue
        local basename_file
        basename_file="$(basename "$diff_file")"
        basename_file="${basename_file#DIFF_}"
        basename_file="${basename_file%.png}"

        local baseline_path
        baseline_path="$(get_baseline_path "$diff_file")"

        local status_icon="${CROSS}"
        local status_color="${RED}"
        if [[ -f "$baseline_path" ]]; then
            status_icon="${DIFF_SYMBOL}"
            status_color="${YELLOW}"
        fi

        echo -e "  ${status_color}${status_icon} ${basename_file}${RESET}"
        echo -e "    ${DIM}Baseline: $(basename "$baseline_path")${RESET}"
        echo -e "    ${DIM}Current:  $(basename "$diff_file")${RESET}"
        echo
    done <<< "$diff_files"

    echo -e "${CYAN}${ARROW} Run '$(basename "$0")' to review differences interactively${RESET}"
    echo -e "${CYAN}${ARROW} Run '$(basename "$0") --grid' for thumbnail overview${RESET}"
    echo -e "${CYAN}${ARROW} Run '$(basename "$0") --clean' to remove all diff files${RESET}"
}

show_grid_overview() {
    local pattern="${1:-}"
    local diff_files
    diff_files="$(find_diff_files "$pattern")"

    if [[ -z "$diff_files" ]]; then
        echo -e "${GREEN}${CHECK} No visual differences found!${RESET}"
        echo -e "${DIM}All visual regression tests are passing.${RESET}"
        return 0
    fi

    if [[ -z "$IMGCAT_PATH" ]]; then
        echo -e "${YELLOW}⚠️  Grid overview requires imgcat (iTerm2)${RESET}"
        echo -e "${DIM}   Falling back to summary view...${RESET}\n"
        show_diff_summary "$pattern"
        return 0
    fi

    local count=0
    while IFS= read -r diff_file; do
        [[ -n "$diff_file" ]] && count=$((count + 1))
    done <<< "$diff_files"

    echo -e "${BOLD}${DIFF_SYMBOL} Visual Diff Grid Overview${RESET}"
    echo -e "${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${RED}Found ${count} visual difference(s):${RESET}\n"

    local current=0
    while IFS= read -r diff_file; do
        [[ -z "$diff_file" ]] && continue
        current=$((current + 1))

        local basename_file
        basename_file="$(basename "$diff_file")"
        basename_file="${basename_file#DIFF_}"
        basename_file="${basename_file%.png}"

        local baseline_path
        baseline_path="$(get_baseline_path "$diff_file")"

        echo -e "${BOLD}[${current}/${count}] ${CYAN}${basename_file}${RESET}"

        # Show baseline and diff side by side with smaller size
        if [[ -f "$baseline_path" ]]; then
            echo -e "${GREEN}${BASELINE_SYMBOL} Expected${RESET}                    ${RED}${NEW_SYMBOL} Actual${RESET}"
            # Use a smaller width for grid view - iTerm2 will scale appropriately
            "$IMGCAT_PATH" --width 40 "$baseline_path" &
            "$IMGCAT_PATH" --width 40 "$diff_file" &
            wait
        else
            echo -e "${RED}${CROSS} Baseline missing: $baseline_path${RESET}"
            "$IMGCAT_PATH" --width 40 "$diff_file"
        fi

        if [[ $current -lt $count ]]; then
            echo -e "\n${DIM}────────────────────────────────────────────────────────────────────────────────${RESET}\n"
        fi
    done <<< "$diff_files"

    echo -e "\n${CYAN}${ARROW} Run '$(basename "$0")' for interactive review${RESET}"
    echo -e "${CYAN}${ARROW} Run '$(basename "$0") --clean' to remove all diff files${RESET}"
}

interactive_diff_review() {
    local pattern="${1:-}"
    local diff_files
    diff_files="$(find_diff_files "$pattern")"

    if [[ -z "$diff_files" ]]; then
        echo -e "${GREEN}${CHECK} No visual differences found!${RESET}"
        return 0
    fi

    # Pre-filter to find files with actual differences
    local actual_diff_files=""
    local total_count=0
    local python_cmd="python3"
    if [[ -f "$(dirname "$0")/../.venv/bin/python" ]]; then
        python_cmd="$(dirname "$0")/../.venv/bin/python"
    fi

    echo -e "${DIM}🔍 Checking for actual visual differences...${RESET}"

    while IFS= read -r diff_file; do
        [[ -z "$diff_file" ]] && continue

        local baseline_path
        baseline_path="$(get_baseline_path "$diff_file")"

        if [[ -f "$baseline_path" ]]; then
            # Quick check if images are actually different
            local output
            if output=$($python_cmd "$(dirname "$0")/generate-visual-diff.py" "$baseline_path" "$diff_file" "/tmp/dummy.png" 2>&1); then
                if [[ "$output" != *"no enhanced diff needed"* ]]; then
                    if [[ -n "$actual_diff_files" ]]; then
                        actual_diff_files="${actual_diff_files}"$'\n'"${diff_file}"
                    else
                        actual_diff_files="${diff_file}"
                    fi
                    total_count=$((total_count + 1))
                fi
            fi
        fi
    done <<< "$diff_files"

    if [[ $total_count -eq 0 ]]; then
        echo -e "${GREEN}${CHECK} All images are identical - no visual differences to review!${RESET}"
        return 0
    fi

    echo -e "${BOLD}${DIFF_SYMBOL} Interactive Visual Diff Review${RESET}"
    echo -e "${DIM}Found ${total_count} actual difference(s). Press 'q' to quit, 'Enter' to continue.${RESET}\n"

    local count=0
    while IFS= read -r diff_file; do
        [[ -z "$diff_file" ]] && continue
        count=$((count + 1))
        local basename_file
        basename_file="$(basename "$diff_file")"
        basename_file="${basename_file#DIFF_}"
        basename_file="${basename_file%.png}"

        local baseline_path
        baseline_path="$(get_baseline_path "$diff_file")"

        echo -e "${DIM}[${count}/${total_count}]${RESET}"
        display_image_pair "$baseline_path" "$diff_file" "$basename_file"

        if [[ $count -lt $total_count ]]; then
            echo -e "\n${DIM}Press Enter to continue, 'q' to quit, 'd' to delete this diff: ${RESET}"
            read -r response
            case "$response" in
                q|Q)
                    echo -e "${YELLOW}Exiting...${RESET}"
                    break
                    ;;
                d|D)
                    rm -f "$diff_file"
                    echo -e "${GREEN}${CHECK} Deleted $diff_file${RESET}"
                    ;;
            esac
        fi
    done <<< "$actual_diff_files"
}

clean_diff_files() {
    local pattern="${1:-}"
    local diff_files
    diff_files="$(find_diff_files "$pattern")"

    # Also find enhanced diff files
    local enhanced_files=""
    if [[ -n "$pattern" ]]; then
        enhanced_files=$(find "$BASELINES_DIR" -name "ENHANCED_*${pattern}*.png" 2>/dev/null || true)
    else
        enhanced_files=$(find "$BASELINES_DIR" -name "ENHANCED_*.png" 2>/dev/null || true)
    fi

    if [[ -z "$diff_files" && -z "$enhanced_files" ]]; then
        echo -e "${GREEN}${CHECK} No diff files to clean${RESET}"
        return 0
    fi

    local count=0
    while IFS= read -r diff_file; do
        [[ -n "$diff_file" ]] && count=$((count + 1))
    done <<< "$diff_files"

    local enhanced_count=0
    while IFS= read -r enhanced_file; do
        [[ -n "$enhanced_file" ]] && enhanced_count=$((enhanced_count + 1))
    done <<< "$enhanced_files"

    local total_count=$((count + enhanced_count))
    echo -e "${YELLOW}Found ${total_count} file(s) to remove:${RESET}"

    if [[ -n "$diff_files" ]]; then
        echo -e "${DIM}  DIFF files:${RESET}"
        while IFS= read -r diff_file; do
            [[ -z "$diff_file" ]] && continue
            echo -e "    ${DIM}$(basename "$diff_file")${RESET}"
        done <<< "$diff_files"
    fi

    if [[ -n "$enhanced_files" ]]; then
        echo -e "${DIM}  Enhanced diff files:${RESET}"
        while IFS= read -r enhanced_file; do
            [[ -z "$enhanced_file" ]] && continue
            echo -e "    ${DIM}$(basename "$enhanced_file")${RESET}"
        done <<< "$enhanced_files"
    fi

    echo -e "\n${RED}Are you sure you want to delete these files? [y/N]: ${RESET}"
    read -r response
    case "$response" in
        y|Y|yes|YES)
            while IFS= read -r diff_file; do
                [[ -z "$diff_file" ]] && continue
                rm -f "$diff_file"
                echo -e "${GREEN}${CHECK} Deleted $(basename "$diff_file")${RESET}"
            done <<< "$diff_files"

            while IFS= read -r enhanced_file; do
                [[ -z "$enhanced_file" ]] && continue
                rm -f "$enhanced_file"
                echo -e "${GREEN}${CHECK} Deleted $(basename "$enhanced_file")${RESET}"
            done <<< "$enhanced_files"

            echo -e "\n${GREEN}${CHECK} Cleanup complete${RESET}"
            ;;
        *)
            echo -e "${YELLOW}Cancelled${RESET}"
            ;;
    esac
}

main() {
    local mode="interactive"
    local pattern=""
    local show_images=true

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -h|--help)
                usage
                exit 0
                ;;
            -l|--list)
                mode="list"
                shift
                ;;
            -a|--all)
                mode="all"
                shift
                ;;
            -c|--clean)
                mode="clean"
                shift
                ;;
            -s|--summary)
                mode="summary"
                shift
                ;;
            -g|--grid)
                mode="grid"
                shift
                ;;
            --no-images)
                show_images=false
                IMGCAT_PATH=""
                shift
                ;;
            -*)
                echo -e "${RED}${CROSS} Unknown option: $1${RESET}" >&2
                usage >&2
                exit 1
                ;;
            *)
                pattern="$1"
                shift
                ;;
        esac
    done

    check_requirements

    case "$mode" in
        list|summary)
            show_diff_summary "$pattern"
            ;;
        grid)
            show_grid_overview "$pattern"
            ;;
        all)
            local diff_files
            diff_files="$(find_diff_files "$pattern")"

            if [[ -z "$diff_files" ]]; then
                echo -e "${GREEN}${CHECK} No visual differences found!${RESET}"
                return 0
            fi

            local total_count=0
            while IFS= read -r diff_file; do
                [[ -n "$diff_file" ]] && total_count=$((total_count + 1))
            done <<< "$diff_files"

            echo -e "${BOLD}${DIFF_SYMBOL} Showing All Visual Differences${RESET}\n"

            local count=0
            while IFS= read -r diff_file; do
                [[ -z "$diff_file" ]] && continue
                count=$((count + 1))
                local basename_file
                basename_file="$(basename "$diff_file")"
                basename_file="${basename_file#DIFF_}"
                basename_file="${basename_file%.png}"

                local baseline_path
                baseline_path="$(get_baseline_path "$diff_file")"

                echo -e "${DIM}[${count}/${total_count}]${RESET}"
                display_image_pair "$baseline_path" "$diff_file" "$basename_file"

                if [[ $count -lt $total_count ]]; then
                    echo -e "\n${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}\n"
                fi
            done <<< "$diff_files"
            ;;
        clean)
            clean_diff_files "$pattern"
            ;;
        interactive)
            interactive_diff_review "$pattern"
            ;;
    esac
}

# Run main function with all arguments
main "$@"
