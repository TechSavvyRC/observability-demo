#!/bin/bash

#==============================================================================
# File Configuration Formatter Script
# 
# Purpose: Clean and standardize configuration files by:
#          - Converting tabs to spaces (configurable indentation)
#          - Removing carriage returns (Windows line endings)
#          - Removing Byte Order Mark (BOM) if present
#          - Validating final formatting
# 
# Author: System Administrator
# Version: 1.1
# Created: $(date +%Y-%m-%d)
#
# Usage: ./file_formatter.sh <config_file_path>
#==============================================================================

# Configuration
readonly SCRIPT_NAME="file-formatter"
readonly DEFAULT_SPACES=2
readonly BACKUP_SUFFIX=".backup.$(date +%Y%m%d_%H%M%S)"
readonly TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Color codes for output formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

#==============================================================================
# Logging Functions
#==============================================================================

log_info() {
    echo -e "${BLUE}[INFO]${NC} ${TIMESTAMP} - $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} ${TIMESTAMP} - $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} ${TIMESTAMP} - $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} ${TIMESTAMP} - $1"
}

log_debug() {
    echo -e "${CYAN}[DEBUG]${NC} ${TIMESTAMP} - $1"
}

log_separator() {
    echo "================================================================================"
}

#==============================================================================
# Utility Functions
#==============================================================================

show_usage() {
    cat << EOF
Usage: $0 <FILE_PATH>

This script formats configuration files by:
  - Converting tabs to specified number of spaces (interactive prompt)
  - Removing Windows carriage returns (\\r)
  - Removing UTF-8 Byte Order Mark (BOM)
  - Validating the final formatting

The script will interactively prompt you for:
  - Number of spaces to replace each tab
  - Whether to create a backup file

ARGUMENTS:
  FILE_PATH           Path to the configuration file to format (required)

EXAMPLES:
  $0 /opt/app/config.yml              # Format config file
  $0 docker-compose.yml               # Format Docker Compose file
  $0 /etc/config/app.conf             # Format any config file

EOF
}

parse_arguments() {
    CONFIG_FILE=""
    
    if [[ $# -eq 0 ]]; then
        log_error "No file path provided"
        show_usage
        exit 1
    fi
    
    CONFIG_FILE="$1"
    
    if [[ $# -gt 1 ]]; then
        log_error "Too many arguments. Only provide the file path."
        show_usage
        exit 1
    fi
}

get_user_preferences() {
    log_separator
    log_info "Interactive Configuration Setup"
    log_separator
    
    # Prompt for number of spaces
    while true; do
        echo
        read -p "How many spaces should replace each tab? (default: 2): " spaces_input
        
        if [[ -z "$spaces_input" ]]; then
            SPACES_COUNT=$DEFAULT_SPACES
            break
        fi
        
        if [[ "$spaces_input" =~ ^[1-9][0-9]*$ ]]; then
            SPACES_COUNT="$spaces_input"
            break
        else
            log_error "Invalid input: '$spaces_input'. Please enter a positive number (1, 2, 3, etc.)"
        fi
    done
    
    TAB_REPLACEMENT=$(printf "%*s" "$SPACES_COUNT" "")
    log_info "Selected: $SPACES_COUNT spaces per tab"
    
    # Prompt for backup preference
    while true; do
        echo
        read -p "Create backup file before formatting? (Y/n): " backup_input
        
        case "${backup_input,,}" in
            ""|"y"|"yes")
                CREATE_BACKUP=true
                log_info "Selected: Create backup file"
                break
                ;;
            "n"|"no")
                CREATE_BACKUP=false
                log_info "Selected: Skip backup creation"
                break
                ;;
            *)
                log_error "Invalid input: '$backup_input'. Please enter 'y' for yes or 'n' for no"
                ;;
        esac
    done
}

validate_file() {
    local file_path="$1"
    
    if [[ ! -f "$file_path" ]]; then
        log_error "Configuration file does not exist: $file_path"
        return 1
    fi
    
    if [[ ! -r "$file_path" ]]; then
        log_error "Cannot read configuration file: $file_path"
        return 1
    fi
    
    if [[ ! -w "$file_path" ]]; then
        log_error "Cannot write to configuration file: $file_path"
        log_info "Consider running with sudo or changing file permissions"
        return 1
    fi
    
    log_info "File validation passed: $file_path"
    return 0
}

create_backup() {
    local file_path="$1"
    local backup_path="${file_path}${BACKUP_SUFFIX}"
    
    if [[ "$CREATE_BACKUP" == "true" ]]; then
        if cp "$file_path" "$backup_path" 2>/dev/null; then
            log_success "Backup created: $backup_path"
        else
            log_error "Failed to create backup file"
            return 1
        fi
    fi
    return 0
}

analyze_file() {
    local file_path="$1"
    
    log_info "Analyzing file contents..."
    
    # Count tabs
    local tab_count=0
    if grep -q $'\t' "$file_path" 2>/dev/null; then
        tab_count=$(grep -o $'\t' "$file_path" 2>/dev/null | wc -l | tr -d ' ')
    fi
    
    # Count carriage returns
    local cr_count=0
    if grep -q $'\r' "$file_path" 2>/dev/null; then
        cr_count=$(grep -o $'\r' "$file_path" 2>/dev/null | wc -l | tr -d ' ')
    fi
    
    # Check for BOM
    local has_bom=false
    if head -c 3 "$file_path" 2>/dev/null | od -tx1 2>/dev/null | grep -q "ef bb bf"; then
        has_bom=true
    fi
    
    # File size
    local file_size="unknown"
    if command -v stat >/dev/null 2>&1; then
        file_size=$(stat -f%z "$file_path" 2>/dev/null || stat -c%s "$file_path" 2>/dev/null || echo "unknown")
    fi
    
    log_info "File analysis results:"
    log_info "  File size: $file_size bytes"
    log_info "  Tab characters found: $tab_count"
    log_info "  Carriage returns found: $cr_count"
    log_info "  UTF-8 BOM present: $has_bom"
    
    # Return status indicating if changes are needed
    if [[ $tab_count -gt 0 ]] || [[ $cr_count -gt 0 ]] || [[ "$has_bom" == "true" ]]; then
        return 0  # Changes needed
    else
        return 1  # No changes needed
    fi
}

#==============================================================================
# File Processing Functions
#==============================================================================

convert_tabs() {
    local file_path="$1"
    
    log_info "Converting tabs to $SPACES_COUNT-space indentation..."
    
    if sed -i.tmp "s/$(printf '\t')/$TAB_REPLACEMENT/g" "$file_path" 2>/dev/null; then
        rm -f "${file_path}.tmp" 2>/dev/null
        log_success "Tab conversion completed (tabs → $SPACES_COUNT spaces)"
    else
        log_error "Failed to convert tabs to spaces"
        return 1
    fi
    return 0
}

remove_carriage_returns() {
    local file_path="$1"
    
    log_info "Removing carriage returns (Windows line endings)..."
    
    if sed -i.tmp 's/\r$//' "$file_path" 2>/dev/null; then
        rm -f "${file_path}.tmp" 2>/dev/null
        log_success "Carriage return removal completed"
    else
        log_error "Failed to remove carriage returns"
        return 1
    fi
    return 0
}

remove_bom() {
    local file_path="$1"
    
    log_info "Removing UTF-8 Byte Order Mark (BOM) if present..."
    
    if sed -i.tmp '1s/^\xEF\xBB\xBF//' "$file_path" 2>/dev/null; then
        rm -f "${file_path}.tmp" 2>/dev/null
        log_success "BOM removal completed"
    else
        log_error "Failed to remove BOM"
        return 1
    fi
    return 0
}

validate_formatting() {
    local file_path="$1"
    
    log_info "Validating final file formatting..."
    
    # Check for remaining tabs
    local remaining_tabs=0
    if grep -q $'\t' "$file_path" 2>/dev/null; then
        remaining_tabs=$(grep -o $'\t' "$file_path" 2>/dev/null | wc -l | tr -d ' ')
    fi
    
    # Check for remaining carriage returns
    local remaining_cr=0
    if grep -q $'\r' "$file_path" 2>/dev/null; then
        remaining_cr=$(grep -o $'\r' "$file_path" 2>/dev/null | wc -l | tr -d ' ')
    fi
    
    # Check for remaining BOM
    local has_bom=false
    if head -c 3 "$file_path" 2>/dev/null | od -tx1 2>/dev/null | grep -q "ef bb bf"; then
        has_bom=true
    fi
    
    # Report validation results
    if [[ $remaining_tabs -eq 0 ]] && [[ $remaining_cr -eq 0 ]] && [[ "$has_bom" == "false" ]]; then
        log_success "File formatting validation passed - file is clean!"
        return 0
    else
        log_warning "File formatting validation found issues:"
        [[ $remaining_tabs -gt 0 ]] && log_warning "  Remaining tabs: $remaining_tabs"
        [[ $remaining_cr -gt 0 ]] && log_warning "  Remaining carriage returns: $remaining_cr"
        [[ "$has_bom" == "true" ]] && log_warning "  UTF-8 BOM still present"
        return 1
    fi
}

#==============================================================================
# Main Execution
#==============================================================================

main() {
    log_separator
    log_info "Starting File Configuration Formatter"
    log_info "Script: $SCRIPT_NAME | Timestamp: $TIMESTAMP"
    log_separator
    
    # Parse command line arguments
    parse_arguments "$@"
    
    # Validate input file
    if ! validate_file "$CONFIG_FILE"; then
        log_error "File validation failed"
        exit 1
    fi
    
    # Get user preferences interactively
    get_user_preferences
    
    # Display configuration
    log_info "Configuration:"
    log_info "  Target file: $CONFIG_FILE"
    log_info "  Spaces per tab: $SPACES_COUNT"
    log_info "  Create backup: $CREATE_BACKUP"
    
    log_separator
    
    # Analyze file contents
    if analyze_file "$CONFIG_FILE"; then
        log_info "File requires formatting changes"
    else
        log_success "File is already properly formatted - no changes needed"
        exit 0
    fi
    
    log_separator
    
    # Create backup if requested
    if ! create_backup "$CONFIG_FILE"; then
        log_error "Backup creation failed"
        exit 1
    fi
    
    # Perform formatting operations
    local formatting_failed=false
    
    log_info "Beginning file formatting operations..."
    
    convert_tabs "$CONFIG_FILE" || formatting_failed=true
    remove_carriage_returns "$CONFIG_FILE" || formatting_failed=true
    remove_bom "$CONFIG_FILE" || formatting_failed=true
    
    # Validate results
    if validate_formatting "$CONFIG_FILE"; then
        log_success "All formatting operations completed successfully!"
    else
        formatting_failed=true
    fi
    
    log_separator
    
    # Final status report
    if [[ "$formatting_failed" == "true" ]]; then
        log_error "File formatting completed with errors"
        exit 1
    else
        log_success "Configuration file formatting completed successfully!"
        log_info "File is now ready for use with proper formatting"
    fi
    
    log_separator
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
