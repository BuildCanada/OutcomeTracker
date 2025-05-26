#!/usr/bin/env python3
"""
Script to replace temporary flat structure files with main files during deployment.
This automates the transition from development files to production files.
"""

import os
import shutil
import sys
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# File replacement mappings
FILE_REPLACEMENTS = {
    # Frontend files
    'lib/data-flat.ts': 'lib/data.ts',
    
    # Backend files  
    'scripts/common_utils_flat.py': 'scripts/common_utils.py',
}

# Function name replacements within files
FUNCTION_NAME_REPLACEMENTS = {
    'lib/data.ts': {
        'fetchPromisesForDepartmentFlat': 'fetchPromisesForDepartment',
        'getPromiseCountsByParty': 'getPromiseCountsByParty',  # No change needed
        'fetchPromisesForMultipleDepartments': 'fetchPromisesForMultipleDepartments',  # No change
        'searchPromisesByText': 'searchPromisesByText',  # No change
        'getMigrationStatus': 'getMigrationStatus',  # No change
    }
}

def backup_original_files():
    """Create backups of original files before replacement."""
    logger.info("Creating backups of original files...")
    
    backup_mappings = {
        'lib/data.ts': 'lib/data-legacy-backup.ts',
        'scripts/common_utils.py': 'scripts/common_utils-legacy-backup.py'
    }
    
    for original, backup in backup_mappings.items():
        if os.path.exists(original):
            shutil.copy2(original, backup)
            logger.info(f"Backed up {original} to {backup}")
        else:
            logger.warning(f"Original file not found: {original}")

def replace_files():
    """Replace original files with flat structure versions."""
    logger.info("Replacing files with flat structure versions...")
    
    for source, target in FILE_REPLACEMENTS.items():
        if os.path.exists(source):
            # Create backup if target exists
            if os.path.exists(target):
                backup_target = f"{target}.pre-migration-backup"
                shutil.copy2(target, backup_target)
                logger.info(f"Backed up existing {target} to {backup_target}")
            
            # Replace the file
            shutil.move(source, target)
            logger.info(f"Replaced {target} with {source}")
        else:
            logger.error(f"Source file not found: {source}")
            return False
    
    return True

def update_function_names():
    """Update function names in replaced files to remove 'Flat' suffixes."""
    logger.info("Updating function names to remove 'Flat' suffixes...")
    
    for file_path, replacements in FUNCTION_NAME_REPLACEMENTS.items():
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                for old_name, new_name in replacements.items():
                    if old_name != new_name:  # Only replace if names are different
                        content = content.replace(old_name, new_name)
                
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"Updated function names in {file_path}")
                else:
                    logger.info(f"No function name changes needed in {file_path}")
                    
            except Exception as e:
                logger.error(f"Error updating function names in {file_path}: {e}")
                return False
        else:
            logger.warning(f"File not found for function name updates: {file_path}")
    
    return True

def update_import_references():
    """Update import references throughout the codebase."""
    logger.info("Updating import references...")
    
    # Find all TypeScript and Python files that might import the old files
    import_updates = []
    
    # Look for files importing from data-flat.ts
    for root, dirs, files in os.walk('.'):
        # Skip node_modules, .git, etc.
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != 'node_modules']
        
        for file in files:
            if file.endswith(('.ts', '.tsx', '.js', '.jsx', '.py')):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    original_content = content
                    
                    # Update import statements
                    if 'data-flat' in content:
                        content = content.replace('from "./data-flat"', 'from "./data"')
                        content = content.replace('from "../lib/data-flat"', 'from "../lib/data"')
                        content = content.replace('from "../../lib/data-flat"', 'from "../../lib/data"')
                        content = content.replace('import { } from "./data-flat"', 'import { } from "./data"')
                    
                    if 'common_utils_flat' in content:
                        content = content.replace('from common_utils_flat import', 'from common_utils import')
                        content = content.replace('import common_utils_flat', 'import common_utils')
                    
                    if content != original_content:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        import_updates.append(file_path)
                        
                except Exception as e:
                    logger.error(f"Error updating imports in {file_path}: {e}")
    
    if import_updates:
        logger.info(f"Updated imports in {len(import_updates)} files:")
        for file_path in import_updates:
            logger.info(f"  - {file_path}")
    else:
        logger.info("No import updates needed")
    
    return True

def verify_replacement():
    """Verify that all files have been replaced correctly."""
    logger.info("Verifying file replacement...")
    
    success = True
    
    # Check that target files exist
    for source, target in FILE_REPLACEMENTS.items():
        if not os.path.exists(target):
            logger.error(f"Target file missing after replacement: {target}")
            success = False
        
        if os.path.exists(source):
            logger.error(f"Source file still exists after replacement: {source}")
            success = False
    
    # Check that backup files exist
    backup_files = ['lib/data-legacy-backup.ts', 'scripts/common_utils-legacy-backup.py']
    for backup_file in backup_files:
        if not os.path.exists(backup_file):
            logger.warning(f"Backup file not found: {backup_file}")
    
    return success

def main():
    """Main execution function."""
    logger.info("Starting file replacement for production deployment...")
    
    try:
        # Step 1: Backup original files
        backup_original_files()
        
        # Step 2: Replace files
        if not replace_files():
            logger.error("File replacement failed")
            return False
        
        # Step 3: Update function names
        if not update_function_names():
            logger.error("Function name updates failed")
            return False
        
        # Step 4: Update import references
        if not update_import_references():
            logger.error("Import reference updates failed")
            return False
        
        # Step 5: Verify replacement
        if not verify_replacement():
            logger.error("File replacement verification failed")
            return False
        
        logger.info("✅ File replacement completed successfully!")
        logger.info("Next steps:")
        logger.info("1. Test the application thoroughly")
        logger.info("2. Run migration validation")
        logger.info("3. Deploy to production")
        
        return True
        
    except Exception as e:
        logger.critical(f"File replacement failed with critical error: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 