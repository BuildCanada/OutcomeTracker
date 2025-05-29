#!/usr/bin/env python3
"""
Migration Runner Script

Command-line interface for running the migration from old scripts to new pipeline.
Provides options for testing, dry-run, and rollback.
"""

import argparse
import logging
import json
import sys
from pathlib import Path

# Add pipeline to path
pipeline_dir = Path(__file__).parent.parent
sys.path.insert(0, str(pipeline_dir))

from testing.migration_manager import MigrationManager
from testing.migration_tester import MigrationTester


def setup_logging(verbose: bool = False):
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('migration.log')
        ]
    )


def run_tests_only(config: dict):
    """Run migration tests without performing migration"""
    print("🧪 Running migration tests...")
    
    tester = MigrationTester(config.get('testing', {}))
    results = tester.run_full_migration_test()
    
    # Save test results
    output_file = tester.save_test_results()
    
    # Print summary
    print(f"\n📊 Test Results Summary:")
    print(f"   Total Tests: {results['total_tests']}")
    print(f"   Passed: {results['passed_tests']}")
    print(f"   Failed: {results['failed_tests']}")
    print(f"   Success Rate: {results['success_rate']:.1%}")
    print(f"   Results saved to: {output_file}")
    
    if results['failed_tests'] > 0:
        print(f"\n❌ Failed Tests:")
        for failed_test in results['failed_test_details']:
            print(f"   - {failed_test['name']}: {failed_test.get('notes', 'No details')}")
        return False
    
    print(f"\n✅ All tests passed!")
    return True


def run_migration(config: dict):
    """Run the full migration process"""
    print("🚀 Starting migration from old scripts to new pipeline...")
    
    manager = MigrationManager(config)
    
    # Show current status
    status = manager.get_migration_status()
    print(f"📈 Migration Progress: {status['progress_percentage']:.1f}% complete")
    
    if status['completed_steps'] > 0:
        completed_step_names = [step['name'] for step in status['migration_steps'][:status['completed_steps']]]
        print(f"   Completed steps: {', '.join(completed_step_names)}")
    
    # Run migration
    results = manager.start_migration()
    
    # Print results
    print(f"\n📊 Migration Results:")
    print(f"   Overall Success: {'✅' if results['overall_success'] else '❌'}")
    print(f"   Steps Completed: {len(results['steps_completed'])}")
    print(f"   Steps Failed: {len(results['steps_failed'])}")
    
    if results['steps_completed']:
        print(f"   ✅ Completed: {', '.join(results['steps_completed'])}")
    
    if results['steps_failed']:
        print(f"   ❌ Failed:")
        for failed_step in results['steps_failed']:
            print(f"      - {failed_step['step']}: {failed_step['error']}")
    
    return results['overall_success']


def rollback_migration(config: dict, to_step: str = None):
    """Rollback migration to previous state"""
    print(f"🔄 Rolling back migration{f' to step: {to_step}' if to_step else ''}...")
    
    manager = MigrationManager(config)
    results = manager.rollback_migration(to_step)
    
    if results['success']:
        print(f"✅ Rollback successful!")
        print(f"   Restored files: {len(results['restored_files'])}")
        print(f"   Backup used: {results['backup_used']}")
    else:
        print(f"❌ Rollback failed: {results['error']}")
    
    return results['success']


def show_status(config: dict):
    """Show current migration status"""
    manager = MigrationManager(config)
    status = manager.get_migration_status()
    
    print(f"📊 Migration Status:")
    print(f"   Progress: {status['progress_percentage']:.1f}% complete")
    print(f"   Steps: {status['completed_steps']}/{status['total_steps']}")
    
    if status['started_at']:
        print(f"   Started: {status['started_at']}")
    if status['last_updated']:
        print(f"   Last Updated: {status['last_updated']}")
    
    print(f"\n📋 Migration Steps:")
    for i, step in enumerate(status['migration_steps'], 1):
        status_icon = "✅" if step['completed'] else "⏳"
        print(f"   {i:2d}. {status_icon} {step['name']}")
        print(f"       {step['description']}")
    
    if status['failed_steps']:
        print(f"\n❌ Failed Steps: {', '.join(status['failed_steps'])}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Promise Tracker Pipeline Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run tests only
  python run_migration.py --test-only
  
  # Run migration with dry-run
  python run_migration.py --migrate --dry-run
  
  # Run full migration
  python run_migration.py --migrate
  
  # Show current status
  python run_migration.py --status
  
  # Rollback migration
  python run_migration.py --rollback
        """
    )
    
    # Action arguments
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument('--test-only', action='store_true',
                             help='Run migration tests without performing migration')
    action_group.add_argument('--migrate', action='store_true',
                             help='Run the migration process')
    action_group.add_argument('--rollback', action='store_true',
                             help='Rollback migration to previous state')
    action_group.add_argument('--status', action='store_true',
                             help='Show current migration status')
    
    # Configuration arguments
    parser.add_argument('--dry-run', action='store_true',
                       help='Perform dry run without making actual changes')
    parser.add_argument('--no-tests', action='store_true',
                       help='Skip testing requirements during migration')
    parser.add_argument('--no-backups', action='store_true',
                       help='Skip creating backups during migration')
    parser.add_argument('--max-test-items', type=int, default=5,
                       help='Maximum items to process during testing (default: 5)')
    parser.add_argument('--rollback-to', type=str,
                       help='Specific step to rollback to')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    parser.add_argument('--config', type=str,
                       help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Load configuration
    config = {}
    if args.config and Path(args.config).exists():
        with open(args.config, 'r') as f:
            config = json.load(f)
    
    # Override config with command line arguments
    config.update({
        'dry_run': args.dry_run,
        'require_tests': not args.no_tests,
        'create_backups': not args.no_backups,
        'testing': {
            'dry_run': True,  # Always dry run for tests
            'max_items_per_test': args.max_test_items
        }
    })
    
    # Execute requested action
    success = False
    
    try:
        if args.test_only:
            success = run_tests_only(config)
        elif args.migrate:
            success = run_migration(config)
        elif args.rollback:
            success = rollback_migration(config, args.rollback_to)
        elif args.status:
            show_status(config)
            success = True
        
    except KeyboardInterrupt:
        print("\n⚠️  Migration interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Migration failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    # Exit with appropriate code
    if success:
        print("\n🎉 Operation completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Operation failed")
        sys.exit(1)


if __name__ == '__main__':
    main() 