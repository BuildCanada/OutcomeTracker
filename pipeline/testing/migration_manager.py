"""
Migration Manager

Handles the safe transition from old scripts to the new pipeline system.
Provides rollback capabilities and gradual migration features.
"""

import logging
import json
import shutil
import os
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

from .migration_tester import MigrationTester


@dataclass
class MigrationStep:
    """Represents a single migration step"""
    name: str
    description: str
    old_files: List[str]
    new_components: List[str]
    dependencies: List[str] = None
    rollback_data: Dict[str, Any] = None
    completed: bool = False


class MigrationManager:
    """
    Manages the migration from old scripts to new pipeline.
    
    Provides safe migration with testing, rollback capabilities,
    and gradual transition features.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """Initialize the migration manager"""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Paths
        self.project_root = Path(__file__).parent.parent.parent
        self.scripts_dir = self.project_root / "scripts"
        self.pipeline_dir = self.project_root / "pipeline"
        self.backup_dir = self.project_root / "migration_backups"
        
        # Migration state
        self.migration_state_file = self.project_root / "migration_state.json"
        self.migration_steps = self._define_migration_steps()
        self.current_state = self._load_migration_state()
        
        # Testing framework
        self.tester = MigrationTester(config.get('testing', {}))
        
        # Safety settings
        self.require_tests = config.get('require_tests', True)
        self.create_backups = config.get('create_backups', True)
        self.dry_run = config.get('dry_run', False)
    
    def _define_migration_steps(self) -> List[MigrationStep]:
        """Define the migration steps in order"""
        return [
            MigrationStep(
                name="backup_existing_system",
                description="Create backup of existing scripts and configuration",
                old_files=[
                    "scripts/ingestion_jobs/",
                    "scripts/processing_jobs/",
                    "cloud_run_main.py",
                    "cloudbuild.yaml"
                ],
                new_components=[],
                dependencies=[]
            ),
            MigrationStep(
                name="test_ingestion_jobs",
                description="Test new ingestion jobs against old scripts",
                old_files=[
                    "scripts/ingestion_jobs/ingest_canada_news.py",
                    "scripts/ingestion_jobs/ingest_legisinfo_bills.py",
                    "scripts/ingestion_jobs/ingest_oic.py",
                    "scripts/ingestion_jobs/ingest_canada_gazette_p2.py"
                ],
                new_components=[
                    "pipeline/stages/ingestion/canada_news.py",
                    "pipeline/stages/ingestion/legisinfo_bills.py",
                    "pipeline/stages/ingestion/orders_in_council.py",
                    "pipeline/stages/ingestion/canada_gazette.py"
                ],
                dependencies=["backup_existing_system"]
            ),
            MigrationStep(
                name="migrate_ingestion_jobs",
                description="Replace old ingestion scripts with new pipeline jobs",
                old_files=[
                    "scripts/ingestion_jobs/ingest_canada_news.py",
                    "scripts/ingestion_jobs/ingest_legisinfo_bills.py",
                    "scripts/ingestion_jobs/ingest_oic.py",
                    "scripts/ingestion_jobs/ingest_canada_gazette_p2.py"
                ],
                new_components=[
                    "pipeline/stages/ingestion/"
                ],
                dependencies=["test_ingestion_jobs"]
            ),
            MigrationStep(
                name="test_processing_jobs",
                description="Test new processing jobs against old scripts",
                old_files=[
                    "scripts/processing_jobs/process_news_to_evidence.py",
                    "scripts/processing_jobs/process_legisinfo_to_evidence.py",
                    "scripts/processing_jobs/process_oic_to_evidence.py",
                    "scripts/processing_jobs/process_gazette_p2_to_evidence.py"
                ],
                new_components=[
                    "pipeline/stages/processing/canada_news_processor.py",
                    "pipeline/stages/processing/legisinfo_processor.py",
                    "pipeline/stages/processing/orders_in_council_processor.py",
                    "pipeline/stages/processing/canada_gazette_processor.py"
                ],
                dependencies=["migrate_ingestion_jobs"]
            ),
            MigrationStep(
                name="migrate_processing_jobs",
                description="Replace old processing scripts with new pipeline jobs",
                old_files=[
                    "scripts/processing_jobs/"
                ],
                new_components=[
                    "pipeline/stages/processing/"
                ],
                dependencies=["test_processing_jobs"]
            ),
            MigrationStep(
                name="migrate_orchestration",
                description="Replace cloud_run_main.py with new orchestrator",
                old_files=[
                    "cloud_run_main.py"
                ],
                new_components=[
                    "pipeline/orchestrator.py"
                ],
                dependencies=["migrate_processing_jobs"]
            ),
            MigrationStep(
                name="test_linking_jobs",
                description="Test new linking jobs against old scripts",
                old_files=[
                    "scripts/run_evidence_linking_with_progress_update.py",
                    "scripts/consolidated_evidence_linking.py"
                ],
                new_components=[
                    "pipeline/stages/linking/evidence_linker.py",
                    "pipeline/stages/linking/progress_scorer.py"
                ],
                dependencies=["migrate_orchestration"]
            ),
            MigrationStep(
                name="migrate_linking_jobs",
                description="Replace old linking scripts with new pipeline jobs",
                old_files=[
                    "scripts/run_evidence_linking_with_progress_update.py",
                    "scripts/consolidated_evidence_linking.py",
                    "scripts/update_promise_progress_scores.py"
                ],
                new_components=[
                    "pipeline/stages/linking/"
                ],
                dependencies=["test_linking_jobs"]
            ),
            MigrationStep(
                name="cleanup_deprecated_scripts",
                description="Remove deprecated scripts and clean up",
                old_files=[
                    "scripts/processing_jobs/",
                    "scripts/ingestion_jobs/",
                    "scripts/linking_jobs/"
                ],
                new_components=[],
                dependencies=["migrate_linking_jobs"]
            )
        ]
    
    def _load_migration_state(self) -> Dict[str, Any]:
        """Load migration state from file"""
        if self.migration_state_file.exists():
            try:
                with open(self.migration_state_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.warning(f"Could not load migration state: {e}")
        
        return {
            'current_step': 0,
            'completed_steps': [],
            'failed_steps': [],
            'started_at': None,
            'last_updated': None
        }
    
    def _save_migration_state(self):
        """Save migration state to file"""
        self.current_state['last_updated'] = datetime.now(timezone.utc).isoformat()
        
        try:
            with open(self.migration_state_file, 'w') as f:
                json.dump(self.current_state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Could not save migration state: {e}")
    
    def start_migration(self) -> Dict[str, Any]:
        """
        Start the migration process.
        
        Returns:
            Migration status and results
        """
        self.logger.info("Starting migration from old scripts to new pipeline")
        
        if not self.current_state.get('started_at'):
            self.current_state['started_at'] = datetime.now(timezone.utc).isoformat()
        
        results = {
            'migration_started': True,
            'steps_completed': [],
            'steps_failed': [],
            'current_step': None,
            'overall_success': False
        }
        
        try:
            # Execute migration steps
            for i, step in enumerate(self.migration_steps):
                if i < self.current_state.get('current_step', 0):
                    # Skip already completed steps
                    continue
                
                self.logger.info(f"Executing migration step {i+1}/{len(self.migration_steps)}: {step.name}")
                results['current_step'] = step.name
                
                # Check dependencies
                if not self._check_dependencies(step):
                    error_msg = f"Dependencies not met for step: {step.name}"
                    self.logger.error(error_msg)
                    results['steps_failed'].append({
                        'step': step.name,
                        'error': error_msg
                    })
                    break
                
                # Execute step
                step_result = self._execute_migration_step(step)
                
                if step_result['success']:
                    self.logger.info(f"Migration step completed: {step.name}")
                    results['steps_completed'].append(step.name)
                    self.current_state['completed_steps'].append(step.name)
                    self.current_state['current_step'] = i + 1
                    step.completed = True
                else:
                    self.logger.error(f"Migration step failed: {step.name}")
                    results['steps_failed'].append({
                        'step': step.name,
                        'error': step_result.get('error', 'Unknown error')
                    })
                    self.current_state['failed_steps'].append(step.name)
                    break
                
                self._save_migration_state()
            
            # Check if migration completed successfully
            if len(results['steps_completed']) == len(self.migration_steps):
                results['overall_success'] = True
                self.logger.info("Migration completed successfully!")
            
        except Exception as e:
            self.logger.error(f"Migration failed with error: {e}", exc_info=True)
            results['error'] = str(e)
        
        self._save_migration_state()
        return results
    
    def _check_dependencies(self, step: MigrationStep) -> bool:
        """Check if step dependencies are met"""
        if not step.dependencies:
            return True
        
        completed_steps = self.current_state.get('completed_steps', [])
        
        for dependency in step.dependencies:
            if dependency not in completed_steps:
                return False
        
        return True
    
    def _execute_migration_step(self, step: MigrationStep) -> Dict[str, Any]:
        """Execute a single migration step"""
        try:
            if step.name == "backup_existing_system":
                return self._backup_existing_system(step)
            elif step.name.startswith("test_"):
                return self._run_migration_tests(step)
            elif step.name.startswith("migrate_"):
                return self._migrate_components(step)
            elif step.name == "cleanup_deprecated_scripts":
                return self._cleanup_deprecated_scripts(step)
            else:
                return {'success': False, 'error': f'Unknown step type: {step.name}'}
                
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _backup_existing_system(self, step: MigrationStep) -> Dict[str, Any]:
        """Create backup of existing system"""
        if not self.create_backups:
            return {'success': True, 'message': 'Backups disabled'}
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = self.backup_dir / f"migration_backup_{timestamp}"
        
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
            
            # Backup files and directories
            for file_path in step.old_files:
                source = self.project_root / file_path
                if source.exists():
                    if source.is_dir():
                        dest = backup_path / file_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copytree(source, dest)
                    else:
                        dest = backup_path / file_path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, dest)
            
            # Save backup metadata
            backup_metadata = {
                'timestamp': timestamp,
                'backed_up_files': step.old_files,
                'backup_path': str(backup_path)
            }
            
            with open(backup_path / "backup_metadata.json", 'w') as f:
                json.dump(backup_metadata, f, indent=2)
            
            step.rollback_data = backup_metadata
            
            return {
                'success': True,
                'backup_path': str(backup_path),
                'files_backed_up': len(step.old_files)
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Backup failed: {e}'}
    
    def _run_migration_tests(self, step: MigrationStep) -> Dict[str, Any]:
        """Run migration tests for a step"""
        if not self.require_tests:
            return {'success': True, 'message': 'Tests disabled'}
        
        try:
            # Run specific tests based on step name
            if "ingestion" in step.name:
                test_results = self.tester._test_ingestion_jobs()
            elif "processing" in step.name:
                test_results = self.tester._test_processing_jobs()
            elif "linking" in step.name:
                test_results = self.tester._test_linking_jobs()
            else:
                return {'success': False, 'error': f'Unknown test type for step: {step.name}'}
            
            # Check test results
            passed_tests = sum(1 for result in test_results if result.passed)
            total_tests = len(test_results)
            
            if total_tests == 0:
                return {'success': True, 'message': 'No tests to run'}
            
            success_rate = passed_tests / total_tests
            
            # Require 80% success rate to proceed
            if success_rate >= 0.8:
                return {
                    'success': True,
                    'tests_passed': passed_tests,
                    'total_tests': total_tests,
                    'success_rate': success_rate
                }
            else:
                return {
                    'success': False,
                    'error': f'Tests failed: {passed_tests}/{total_tests} passed (need 80%)',
                    'tests_passed': passed_tests,
                    'total_tests': total_tests,
                    'success_rate': success_rate
                }
                
        except Exception as e:
            return {'success': False, 'error': f'Testing failed: {e}'}
    
    def _migrate_components(self, step: MigrationStep) -> Dict[str, Any]:
        """Migrate components for a step"""
        if self.dry_run:
            return {'success': True, 'message': 'Dry run - no actual migration performed'}
        
        try:
            migrated_files = []
            
            # For now, we'll just mark old files as deprecated
            # In a real migration, you might move or rename files
            for file_path in step.old_files:
                source = self.project_root / file_path
                if source.exists():
                    if source.is_file():
                        # Rename to .deprecated
                        deprecated_path = source.with_suffix(source.suffix + '.deprecated')
                        source.rename(deprecated_path)
                        migrated_files.append(str(deprecated_path))
                    else:
                        # For directories, create a .deprecated marker
                        marker_file = source / ".deprecated"
                        marker_file.write_text(f"Deprecated on {datetime.now().isoformat()}")
                        migrated_files.append(str(marker_file))
            
            return {
                'success': True,
                'migrated_files': migrated_files,
                'new_components': step.new_components
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Migration failed: {e}'}
    
    def _cleanup_deprecated_scripts(self, step: MigrationStep) -> Dict[str, Any]:
        """Clean up deprecated scripts"""
        if self.dry_run:
            return {'success': True, 'message': 'Dry run - no cleanup performed'}
        
        try:
            cleaned_files = []
            
            for file_path in step.old_files:
                source = self.project_root / file_path
                deprecated_source = source.with_suffix(source.suffix + '.deprecated')
                
                # Remove deprecated files
                if deprecated_source.exists():
                    if deprecated_source.is_file():
                        deprecated_source.unlink()
                        cleaned_files.append(str(deprecated_source))
                    else:
                        shutil.rmtree(deprecated_source)
                        cleaned_files.append(str(deprecated_source))
                
                # Remove deprecated directories
                if source.exists() and source.is_dir():
                    marker_file = source / ".deprecated"
                    if marker_file.exists():
                        shutil.rmtree(source)
                        cleaned_files.append(str(source))
            
            return {
                'success': True,
                'cleaned_files': cleaned_files
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Cleanup failed: {e}'}
    
    def rollback_migration(self, to_step: str = None) -> Dict[str, Any]:
        """
        Rollback migration to a previous state.
        
        Args:
            to_step: Step name to rollback to (default: beginning)
            
        Returns:
            Rollback status and results
        """
        self.logger.info(f"Rolling back migration to step: {to_step or 'beginning'}")
        
        try:
            # Find the most recent backup
            if not self.backup_dir.exists():
                return {'success': False, 'error': 'No backups found'}
            
            backup_dirs = [d for d in self.backup_dir.iterdir() if d.is_dir() and d.name.startswith('migration_backup_')]
            if not backup_dirs:
                return {'success': False, 'error': 'No migration backups found'}
            
            # Use the most recent backup
            latest_backup = max(backup_dirs, key=lambda d: d.name)
            
            # Load backup metadata
            metadata_file = latest_backup / "backup_metadata.json"
            if not metadata_file.exists():
                return {'success': False, 'error': 'Backup metadata not found'}
            
            with open(metadata_file, 'r') as f:
                backup_metadata = json.load(f)
            
            # Restore files
            restored_files = []
            for file_path in backup_metadata['backed_up_files']:
                backup_source = latest_backup / file_path
                restore_dest = self.project_root / file_path
                
                if backup_source.exists():
                    # Remove current version if it exists
                    if restore_dest.exists():
                        if restore_dest.is_dir():
                            shutil.rmtree(restore_dest)
                        else:
                            restore_dest.unlink()
                    
                    # Restore from backup
                    restore_dest.parent.mkdir(parents=True, exist_ok=True)
                    if backup_source.is_dir():
                        shutil.copytree(backup_source, restore_dest)
                    else:
                        shutil.copy2(backup_source, restore_dest)
                    
                    restored_files.append(file_path)
            
            # Reset migration state
            self.current_state = {
                'current_step': 0,
                'completed_steps': [],
                'failed_steps': [],
                'started_at': None,
                'last_updated': datetime.now(timezone.utc).isoformat()
            }
            self._save_migration_state()
            
            return {
                'success': True,
                'restored_files': restored_files,
                'backup_used': str(latest_backup)
            }
            
        except Exception as e:
            return {'success': False, 'error': f'Rollback failed: {e}'}
    
    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status"""
        total_steps = len(self.migration_steps)
        completed_steps = len(self.current_state.get('completed_steps', []))
        
        return {
            'total_steps': total_steps,
            'completed_steps': completed_steps,
            'progress_percentage': (completed_steps / total_steps) * 100 if total_steps > 0 else 0,
            'current_step': self.current_state.get('current_step', 0),
            'started_at': self.current_state.get('started_at'),
            'last_updated': self.current_state.get('last_updated'),
            'failed_steps': self.current_state.get('failed_steps', []),
            'migration_steps': [
                {
                    'name': step.name,
                    'description': step.description,
                    'completed': step.name in self.current_state.get('completed_steps', [])
                }
                for step in self.migration_steps
            ]
        } 