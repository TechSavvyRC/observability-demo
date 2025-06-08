#!/bin/bash

#==============================================================================
# Docker Environment Reset Script
# 
# Purpose: Completely reset Docker environment by removing all containers,
#          images, volumes, networks, and system resources
# Author: System Administrator
# Version: 1.0
# Created: $(date +%Y-%m-%d)
#
# WARNING: This script will permanently delete ALL Docker resources!
#          Use with extreme caution in production environments.
#==============================================================================

# Configuration
readonly SCRIPT_NAME="docker-reset"
readonly LOG_LEVEL="INFO"
readonly TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Color codes for output formatting
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
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

log_separator() {
    echo "================================================================================"
}

#==============================================================================
# Utility Functions
#==============================================================================

# Check if Docker is running
check_docker_status() {
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running. Please start Docker and try again."
        exit 1
    fi
    log_info "Docker daemon is running and accessible"
}

# Get count of resources before cleanup
get_resource_counts() {
    CONTAINER_COUNT=$(docker ps -aq 2>/dev/null | wc -l)
    IMAGE_COUNT=$(docker images -aq 2>/dev/null | wc -l)
    VOLUME_COUNT=$(docker volume ls -q 2>/dev/null | wc -l)
    NETWORK_COUNT=$(docker network ls -q --filter type=custom 2>/dev/null | wc -l)
    
    log_info "Current resource counts - Containers: $CONTAINER_COUNT, Images: $IMAGE_COUNT, Volumes: $VOLUME_COUNT, Custom Networks: $NETWORK_COUNT"
}

# Confirmation prompt for destructive operation
confirm_reset() {
    log_warning "This operation will PERMANENTLY DELETE all Docker resources!"
    log_warning "This includes all containers, images, volumes, and networks."
    echo
    read -p "Are you sure you want to continue? (type 'YES' to confirm): " confirmation
    
    if [[ "$confirmation" != "YES" ]]; then
        log_info "Operation cancelled by user"
        exit 0
    fi
    log_info "User confirmed reset operation"
}

#==============================================================================
# Cleanup Functions
#==============================================================================

# Stop all running containers
stop_containers() {
    log_info "Stopping all running containers..."
    
    local containers=$(docker ps -q 2>/dev/null)
    if [[ -n "$containers" ]]; then
        if docker stop $containers >/dev/null 2>&1; then
            local stopped_count=$(echo "$containers" | wc -w)
            log_success "Successfully stopped $stopped_count container(s)"
        else
            log_error "Failed to stop some containers"
            return 1
        fi
    else
        log_info "No running containers found"
    fi
    return 0
}

# Remove all containers (running and stopped)
remove_containers() {
    log_info "Removing all containers..."
    
    local containers=$(docker ps -aq 2>/dev/null)
    if [[ -n "$containers" ]]; then
        if docker rm -f $containers >/dev/null 2>&1; then
            local removed_count=$(echo "$containers" | wc -w)
            log_success "Successfully removed $removed_count container(s)"
        else
            log_error "Failed to remove some containers"
            return 1
        fi
    else
        log_info "No containers found to remove"
    fi
    return 0
}

# Remove all Docker images
remove_images() {
    log_info "Removing all Docker images..."
    
    local images=$(docker images -aq 2>/dev/null)
    if [[ -n "$images" ]]; then
        if docker rmi -f $images >/dev/null 2>&1; then
            local removed_count=$(echo "$images" | wc -w)
            log_success "Successfully removed $removed_count image(s)"
        else
            log_warning "Some images may still be in use or have dependencies"
            # Force remove any remaining images
            docker image prune -a -f >/dev/null 2>&1
        fi
    else
        log_info "No images found to remove"
    fi
    return 0
}

# Remove all Docker volumes
remove_volumes() {
    log_info "Removing all Docker volumes..."
    
    local volumes=$(docker volume ls -q 2>/dev/null)
    if [[ -n "$volumes" ]]; then
        if docker volume rm $volumes >/dev/null 2>&1; then
            local removed_count=$(echo "$volumes" | wc -w)
            log_success "Successfully removed $removed_count volume(s)"
        else
            log_warning "Some volumes may still be in use"
            # Force remove dangling volumes
            docker volume prune -f >/dev/null 2>&1
        fi
    else
        log_info "No volumes found to remove"
    fi
    return 0
}

# Remove custom Docker networks
remove_networks() {
    log_info "Removing custom Docker networks..."
    
    local networks=$(docker network ls -q --filter type=custom 2>/dev/null)
    if [[ -n "$networks" ]]; then
        if docker network rm $networks >/dev/null 2>&1; then
            local removed_count=$(echo "$networks" | wc -w)
            log_success "Successfully removed $removed_count custom network(s)"
        else
            log_warning "Some networks may still be in use"
            # Clean up unused networks
            docker network prune -f >/dev/null 2>&1
        fi
    else
        log_info "No custom networks found to remove"
    fi
    return 0
}

# Perform comprehensive system cleanup
system_prune() {
    log_info "Performing comprehensive system cleanup..."
    
    if docker system prune -a -f --volumes >/dev/null 2>&1; then
        log_success "System prune completed successfully"
    else
        log_error "System prune encountered errors"
        return 1
    fi
    return 0
}

# Display remaining resources after cleanup
show_remaining_resources() {
    log_separator
    log_info "Docker environment reset completed. Displaying remaining resources:"
    log_separator
    
    echo
    echo "Remaining Containers:"
    docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "No containers found"
    
    echo
    echo "Remaining Images:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}" 2>/dev/null || echo "No images found"
    
    echo
    echo "Remaining Volumes:"
    docker volume ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>/dev/null || echo "No volumes found"
    
    echo
    echo "Remaining Networks:"
    docker network ls --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" 2>/dev/null || echo "No custom networks found"
    
    log_separator
}

#==============================================================================
# Main Execution
#==============================================================================

main() {
    log_separator
    log_info "Starting Docker Environment Reset Script"
    log_info "Script: $SCRIPT_NAME | Timestamp: $TIMESTAMP"
    log_separator
    
    # Pre-flight checks
    check_docker_status
    get_resource_counts
    
    # Safety confirmation
    confirm_reset
    
    log_separator
    log_info "Beginning Docker environment reset process..."
    log_separator
    
    # Execute cleanup operations in sequence
    local cleanup_failed=false
    
    stop_containers || cleanup_failed=true
    remove_containers || cleanup_failed=true
    remove_images || cleanup_failed=true
    remove_volumes || cleanup_failed=true
    remove_networks || cleanup_failed=true
    system_prune || cleanup_failed=true
    
    # Final status and resource display
    if [[ "$cleanup_failed" == "true" ]]; then
        log_warning "Docker reset completed with some warnings or errors"
    else
        log_success "Docker environment reset completed successfully!"
    fi
    
    show_remaining_resources
    
    log_separator
    log_info "Docker Environment Reset Script completed"
    log_separator
}

# Script entry point
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
