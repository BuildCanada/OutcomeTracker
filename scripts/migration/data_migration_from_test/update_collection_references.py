#!/usr/bin/env python3
"""
Update Collection References Script

This script automatically updates hardcoded collection references in Python scripts
from test collections (promises_test, evidence_items_test) to production collections
(promises, evidence_items).

Usage:
    python update_collection_references.py [--dry-run] [--target-dir PATH]
"""

import os
import sys
import re
import argparse
from datetime import datetime
from typing import Dict, List, Tuple
import shutil


class CollectionReferenceUpdater:
    """Updates collection references in Python scripts."""
    
    def __init__(self, target_directory: str = None):
        """Initialize the updater."""
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Default to the scripts directory
        if target_directory is None:
            self.target_directory = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.target_directory = target_directory
        
        # Define the replacements to make
        self.replacements = {
            # Direct string replacements
            '"promises_test"': '"promises"',
            "'promises_test'": "'promises'",
            '"evidence_items_test"': '"evidence_items"',
            "'evidence_items_test'": "'evidence_items'",
            
            # Variable assignments
            'EVIDENCE_ITEMS_COLLECTION = "evidence_items_test"': 'EVIDENCE_ITEMS_COLLECTION = "evidence_items"',
            "EVIDENCE_ITEMS_COLLECTION = 'evidence_items_test'": "EVIDENCE_ITEMS_COLLECTION = 'evidence_items'",
            
            # Environment variable defaults
            'os.getenv("TARGET_PROMISES_COLLECTION", "promises_test")': 'os.getenv("TARGET_PROMISES_COLLECTION", "promises")',
            'os.getenv("TARGET_EVIDENCE_COLLECTION", "evidence_items_test")': 'os.getenv("TARGET_EVIDENCE_COLLECTION", "evidence_items")',
            
            # Function parameter defaults
            'collection_name="promises_test"': 'collection_name="promises"',
            "collection_name='promises_test'": "collection_name='promises'",
        }
        
        # Files to exclude from updates
        self.excluded_files = {
            'backup_production_collections.py',
            'migrate_test_to_production.py',
            'update_collection_references.py',
            'validate_migration.py'
        }
        
        # Track changes made
        self.update_report = {
            'timestamp': self.timestamp,
            'target_directory': self.target_directory,
            'files_processed': [],
            'files_updated': [],
            'total_replacements': 0,
            'errors': []
        }
    
    def find_python_files(self) -> List[str]:
        """Find all Python files in the target directory and subdirectories."""
        python_files = []
        
        for root, dirs, files in os.walk(self.target_directory):
            # Skip certain directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
            
            for file in files:
                if file.endswith('.py') and file not in self.excluded_files:
                    python_files.append(os.path.join(root, file))
        
        return python_files
    
    def analyze_file(self, file_path: str) -> Tuple[bool, List[str], str]:
        """
        Analyze a file for collection references that need updating.
        
        Args:
            file_path: Path to the file to analyze
            
        Returns:
            Tuple of (needs_update, list_of_changes, updated_content)
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            updated_content = content
            changes_made = []
            
            # Apply each replacement
            for old_pattern, new_pattern in self.replacements.items():
                if old_pattern in updated_content:
                    # Count occurrences
                    count = updated_content.count(old_pattern)
                    if count > 0:
                        updated_content = updated_content.replace(old_pattern, new_pattern)
                        changes_made.append(f"Replaced '{old_pattern}' with '{new_pattern}' ({count} times)")
            
            # Check for any remaining test collection references that might need manual review
            test_patterns = [
                r'promises_test',
                r'evidence_items_test'
            ]
            
            remaining_refs = []
            for pattern in test_patterns:
                matches = re.findall(pattern, updated_content)
                if matches:
                    remaining_refs.extend(matches)
            
            if remaining_refs:
                changes_made.append(f"WARNING: Found remaining test collection references: {set(remaining_refs)}")
            
            needs_update = len(changes_made) > 0 and not all(change.startswith("WARNING") for change in changes_made)
            
            return needs_update, changes_made, updated_content
            
        except Exception as e:
            error_msg = f"Error analyzing {file_path}: {str(e)}"
            self.update_report['errors'].append(error_msg)
            return False, [], ""
    
    def update_file(self, file_path: str, new_content: str, dry_run: bool = False) -> bool:
        """
        Update a file with new content.
        
        Args:
            file_path: Path to the file to update
            new_content: New content for the file
            dry_run: If True, don't actually write the file
            
        Returns:
            True if successful, False otherwise
        """
        if dry_run:
            print(f"  [DRY RUN] Would update file: {file_path}")
            return True
        
        try:
            # Create backup
            backup_path = f"{file_path}.backup_{self.timestamp}"
            shutil.copy2(file_path, backup_path)
            
            # Write new content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"  ✓ Updated file: {file_path}")
            print(f"    Backup created: {backup_path}")
            return True
            
        except Exception as e:
            error_msg = f"Error updating {file_path}: {str(e)}"
            print(f"  ✗ {error_msg}")
            self.update_report['errors'].append(error_msg)
            return False
    
    def process_files(self, dry_run: bool = False) -> bool:
        """
        Process all Python files and update collection references.
        
        Args:
            dry_run: If True, only simulate the updates
            
        Returns:
            True if all updates successful, False otherwise
        """
        print(f"{'='*60}")
        print(f"{'DRY RUN - ' if dry_run else ''}UPDATING COLLECTION REFERENCES")
        print(f"Target Directory: {self.target_directory}")
        print(f"Timestamp: {self.timestamp}")
        print(f"{'='*60}")
        
        # Find all Python files
        python_files = self.find_python_files()
        print(f"\nFound {len(python_files)} Python files to process")
        
        all_successful = True
        total_replacements = 0
        
        for file_path in python_files:
            relative_path = os.path.relpath(file_path, self.target_directory)
            print(f"\nProcessing: {relative_path}")
            
            self.update_report['files_processed'].append(relative_path)
            
            # Analyze the file
            needs_update, changes, new_content = self.analyze_file(file_path)
            
            if not changes:
                print(f"  No collection references found")
                continue
            
            # Show what changes would be made
            for change in changes:
                if change.startswith("WARNING"):
                    print(f"  ⚠ {change}")
                else:
                    print(f"  • {change}")
                    total_replacements += 1
            
            if needs_update:
                # Update the file
                success = self.update_file(file_path, new_content, dry_run)
                if success:
                    self.update_report['files_updated'].append(relative_path)
                else:
                    all_successful = False
            else:
                print(f"  ⚠ File has warnings but no updates needed")
        
        self.update_report['total_replacements'] = total_replacements
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"UPDATE SUMMARY")
        print(f"{'='*60}")
        print(f"Files processed: {len(self.update_report['files_processed'])}")
        print(f"Files updated: {len(self.update_report['files_updated'])}")
        print(f"Total replacements: {total_replacements}")
        
        if self.update_report['errors']:
            print(f"Errors encountered: {len(self.update_report['errors'])}")
            for error in self.update_report['errors']:
                print(f"  ✗ {error}")
        
        if self.update_report['files_updated']:
            print(f"\nUpdated files:")
            for file_path in self.update_report['files_updated']:
                print(f"  ✓ {file_path}")
        
        print(f"\nOverall Status: {'SUCCESS' if all_successful else 'FAILED'}")
        
        return all_successful
    
    def save_report(self, dry_run: bool = False):
        """Save the update report to a JSON file."""
        import json
        
        report_filename = f"update_report_{self.timestamp}.json"
        report_path = os.path.join(
            os.path.dirname(__file__), 
            report_filename
        )
        
        if not dry_run:
            try:
                with open(report_path, 'w') as f:
                    json.dump(self.update_report, f, indent=2)
                print(f"\n✓ Update report saved to: {report_path}")
            except Exception as e:
                print(f"\n✗ Error saving update report: {e}")
        else:
            print(f"\n[DRY RUN] Would save update report to: {report_path}")
    
    def run_updates(self, dry_run: bool = False) -> bool:
        """
        Run the complete update process.
        
        Args:
            dry_run: If True, only simulate the updates
            
        Returns:
            True if all updates successful, False otherwise
        """
        success = self.process_files(dry_run)
        self.save_report(dry_run)
        
        if not dry_run and success:
            print(f"\n✓ Collection references updated successfully!")
            print("All scripts now default to production collections.")
            print("Environment variables can still override for testing.")
        
        return success


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Update collection references in Python scripts')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Simulate the updates without actually modifying files')
    parser.add_argument('--target-dir', type=str,
                       help='Target directory to process (default: scripts directory)')
    
    args = parser.parse_args()
    
    try:
        updater = CollectionReferenceUpdater(target_directory=args.target_dir)
        success = updater.run_updates(dry_run=args.dry_run)
        
        if success:
            print(f"\n🎉 Update {'simulation' if args.dry_run else 'process'} completed successfully!")
            if not args.dry_run:
                print("Scripts have been updated to use production collections.")
                print("Backup files have been created for all modified files.")
        else:
            print(f"\n❌ Update {'simulation' if args.dry_run else 'process'} failed!")
            print("Please review the errors above before proceeding.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\n⚠ Update process interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 