#!/usr/bin/env python3
"""
Quick Production Backup Script

Creates a comprehensive backup of all critical production collections
in a single command before running hybrid evidence linking.

Usage:
    python scripts/utilities/quick_production_backup.py
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_backup_command(collections, description):
    """Run backup command and return success status."""
    print(f"\n🚀 {description}")
    print(f"📦 Collections: {', '.join(collections)}")
    
    cmd = [
        sys.executable, 
        "scripts/utilities/backup_production_collections.py",
        "--collections"
    ] + collections + ["--verify"]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed with exit code {e.returncode}")
        return False

def main():
    """Create comprehensive production backup."""
    print("🛡️  COMPREHENSIVE PRODUCTION BACKUP")
    print("=" * 50)
    print(f"🕐 Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Core collections that must be backed up
    backup_sets = [
        (["evidence_items"], "Evidence Items Backup"),
        (["promises"], "Promises Backup"),
        (["evidence_promise_links"], "Evidence-Promise Links Backup (if exists)"),
        (["promise_progress_scores"], "Progress Scores Backup (if exists)"),
    ]
    
    success_count = 0
    total_sets = len(backup_sets)
    
    for collections, description in backup_sets:
        success = run_backup_command(collections, description)
        if success:
            success_count += 1
    
    print("\n" + "=" * 50)
    print("📊 BACKUP SUMMARY")
    print("=" * 50)
    print(f"✅ Successful: {success_count}/{total_sets}")
    print(f"❌ Failed: {total_sets - success_count}/{total_sets}")
    
    if success_count == total_sets:
        print("\n🎉 ALL BACKUPS COMPLETED SUCCESSFULLY!")
        print("✅ Your production data is safely backed up")
        print("🚀 You can now run the hybrid evidence linking system")
        
        # Show restore instructions
        print("\n💡 RESTORATION INSTRUCTIONS:")
        print("If you need to restore any backup, use:")
        print("  python scripts/utilities/backup_production_collections.py --list-backups")
        print("  python scripts/utilities/backup_production_collections.py \\")
        print("    --restore BACKUP_TIMESTAMP \\")
        print("    --collections evidence_items promises \\")
        print("    --confirm-restore")
        
    else:
        print("\n⚠️  SOME BACKUPS FAILED!")
        print("❌ Please review the errors above and retry failed backups")
        print("🛑 Do not run hybrid evidence linking until all backups succeed")
        sys.exit(1)

if __name__ == "__main__":
    main() 