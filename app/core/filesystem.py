import os
import stat
import errno

from app.core.config import Settings


def get_filesystem_stats(path: str) -> dict:
    """Get filesystem statistics using os.statvfs.
    
    Uses f_bavail (available to unprivileged users) for available space.
    Does NOT use directory logical size as primary storage measurement.
    """
    try:
        statvfs = os.statvfs(path)
    except FileNotFoundError:
        raise
    except PermissionError:
        raise
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise FileNotFoundError(f"Mount path does not exist: {path}")
        raise

    # Block size and counts
    block_size = statvfs.f_frsize  # Filesystem block size
    total_blocks = statvfs.f_blocks  # Total data blocks in filesystem
    free_blocks = statvfs.f_bfree   # Free blocks
    available_blocks = statvfs.f_bavail  # Available blocks to unprivileged user

    total_bytes = block_size * total_blocks
    free_bytes = block_size * free_blocks
    available_bytes = block_size * available_blocks

    # Inode statistics
    total_inodes = statvfs.f_files
    free_inodes = statvfs.f_ffree
    available_inodes = statvfs.f_favail

    inode_usage_percent = None
    if total_inodes > 0:
        inode_usage_percent = round(
            ((total_inodes - free_inodes) / total_inodes) * 100, 2
        )

    return {
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
        "available_bytes": available_bytes,
        "block_size": block_size,
        "total_blocks": total_blocks,
        "free_blocks": free_blocks,
        "available_blocks": available_blocks,
        "total_inodes": total_inodes,
        "free_inodes": free_inodes,
        "available_inodes": available_inodes,
        "inode_usage_percent": inode_usage_percent,
        "filesystem_identity": path,
    }


def get_filesystem_status(settings: Settings) -> dict:
    """Get filesystem status for the monitored storage path."""
    path = settings.guardarr_storage_path
    
    try:
        stats = get_filesystem_stats(path)
    except FileNotFoundError:
        return {
            "total_bytes": 0,
            "available_bytes": 0,
            "total_inodes": 0,
            "available_inodes": 0,
            "inode_usage_percent": None,
            "filesystem_identity": path,
            "device_identity": "UNKNOWN",
            "ready": False,
            "error": f"Storage path not found: {path}",
        }
    except PermissionError:
        return {
            "total_bytes": 0,
            "available_bytes": 0,
            "total_inodes": 0,
            "available_inodes": 0,
            "inode_usage_percent": None,
            "filesystem_identity": path,
            "device_identity": "UNKNOWN",
            "ready": False,
            "error": f"Permission denied accessing: {path}",
        }

    # Get device identity
    try:
        device_stat = os.stat(path)
        device_identity = hex(getattr(device_stat, 'st_dev', 0))
    except OSError:
        device_identity = "UNKNOWN"

    # Determine readiness (basic check that we can read filesystem)
    ready = stats["total_bytes"] > 0

    stats["device_identity"] = device_identity
    stats["ready"] = ready
    return stats


def check_filesystem_health(settings: Settings) -> dict:
    """Check filesystem health for readiness."""
    path = settings.guardarr_storage_path
    
    if not os.path.exists(path):
        return {
            "ready": False,
            "reason": f"Storage path does not exist: {path}",
        }
    
    try:
        statvfs = os.statvfs(path)
    except (PermissionError, OSError) as e:
        return {
            "ready": False,
            "reason": f"Cannot stat filesystem: {e}",
        }

    return {"ready": True, "reason": None}
