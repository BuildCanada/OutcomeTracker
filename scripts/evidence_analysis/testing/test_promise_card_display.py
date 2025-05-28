#!/usr/bin/env python3
"""
PromiseCard Component Testing Script
Task 2.1: PromiseCard Component Testing

This script tests the PromiseCard component functionality and performance,
verifying evidence count accuracy, date calculations, and load times.
"""

import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Any, Tuple
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Initialize Firebase Admin if not already done
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

class PromiseCardTester:
    """Tests PromiseCard component functionality and performance."""
    
    def __init__(self, base_url: str = "http://localhost:3000"):
        self.base_url = base_url
        self.db = db
        self.test_results = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'performance_metrics': {},
            'functionality_tests': {},
            'edge_case_tests': {},
            'data_consistency_tests': {},
            'summary': {}
        }
        self.driver = None
        
    async def run_complete_test_suite(self) -> Dict[str, Any]:
        """Run the complete PromiseCard test suite."""
        print("🧪 Starting PromiseCard Component Testing...")
        print("=" * 60)
        
        # Step 1: Setup test environment
        print("🔧 Step 1: Setting up test environment...")
        await self.setup_test_environment()
        
        # Step 2: Fetch test data
        print("📊 Step 2: Fetching test data...")
        test_promises = await self.fetch_test_promises()
        
        # Step 3: Test evidence count accuracy
        print("🔢 Step 3: Testing evidence count accuracy...")
        await self.test_evidence_count_accuracy(test_promises)
        
        # Step 4: Test last update date calculation
        print("📅 Step 4: Testing last update date calculation...")
        await self.test_last_update_date_calculation(test_promises)
        
        # Step 5: Test performance with different evidence counts
        print("⚡ Step 5: Testing performance with different evidence counts...")
        await self.test_performance_by_evidence_count(test_promises)
        
        # Step 6: Test edge cases
        print("🎯 Step 6: Testing edge cases...")
        await self.test_edge_cases(test_promises)
        
        # Step 7: Test data consistency
        print("🔗 Step 7: Testing data consistency...")
        await self.test_data_consistency(test_promises)
        
        # Step 8: Generate performance benchmarks
        print("📈 Step 8: Generating performance benchmarks...")
        await self.generate_performance_benchmarks()
        
        # Step 9: Export results
        print("💾 Step 9: Exporting test results...")
        await self.export_results()
        
        # Step 10: Cleanup
        print("🧹 Step 10: Cleaning up...")
        await self.cleanup()
        
        print("✅ PromiseCard testing complete!")
        return self.test_results
    
    async def setup_test_environment(self):
        """Setup Selenium WebDriver and test environment."""
        print("  🔧 Setting up Selenium WebDriver...")
        
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            print("  ✅ WebDriver initialized successfully")
        except Exception as e:
            print(f"  ❌ Failed to initialize WebDriver: {e}")
            print("  💡 Make sure ChromeDriver is installed and in PATH")
            raise
        
        # Test if the application is running
        try:
            self.driver.get(self.base_url)
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            print(f"  ✅ Application accessible at {self.base_url}")
        except Exception as e:
            print(f"  ❌ Application not accessible: {e}")
            print("  💡 Make sure the Next.js application is running")
            raise
    
    async def fetch_test_promises(self) -> List[Dict[str, Any]]:
        """Fetch a diverse set of promises for testing."""
        print("  📊 Fetching test promises...")
        
        # Get promises with different evidence counts
        promises_ref = self.db.collection('promises')
        all_promises = []
        
        for doc in promises_ref.stream():
            data = doc.to_dict()
            data['id'] = doc.id
            all_promises.append(data)
        
        # Categorize promises by evidence count
        categorized_promises = {
            'no_evidence': [],
            'low_evidence': [],    # 1-5 evidence items
            'medium_evidence': [], # 6-20 evidence items
            'high_evidence': []    # 20+ evidence items
        }
        
        for promise in all_promises:
            evidence_count = 0
            
            # Count evidence from both possible sources
            if 'linked_evidence_ids' in promise:
                evidence_count = len(promise['linked_evidence_ids'])
            elif 'evidence' in promise:
                evidence_count = len(promise['evidence'])
            
            if evidence_count == 0:
                categorized_promises['no_evidence'].append(promise)
            elif evidence_count <= 5:
                categorized_promises['low_evidence'].append(promise)
            elif evidence_count <= 20:
                categorized_promises['medium_evidence'].append(promise)
            else:
                categorized_promises['high_evidence'].append(promise)
        
        # Select test samples from each category
        test_promises = []
        for category, promises in categorized_promises.items():
            sample_size = min(5, len(promises))  # Max 5 from each category
            test_promises.extend(promises[:sample_size])
        
        print(f"  ✅ Selected {len(test_promises)} test promises")
        print(f"    📊 No evidence: {len(categorized_promises['no_evidence'])}")
        print(f"    📊 Low evidence: {len(categorized_promises['low_evidence'])}")
        print(f"    📊 Medium evidence: {len(categorized_promises['medium_evidence'])}")
        print(f"    📊 High evidence: {len(categorized_promises['high_evidence'])}")
        
        return test_promises
    
    async def test_evidence_count_accuracy(self, test_promises: List[Dict[str, Any]]):
        """Test that evidence counts displayed match actual data."""
        print("  🔢 Testing evidence count accuracy...")
        
        accuracy_results = []
        
        for promise in test_promises:
            promise_id = promise['id']
            
            # Calculate expected evidence count
            expected_count = 0
            if 'linked_evidence_ids' in promise:
                expected_count = len(promise['linked_evidence_ids'])
            elif 'evidence' in promise:
                expected_count = len(promise['evidence'])
            
            # Navigate to promise page and check displayed count
            try:
                start_time = time.time()
                
                # Navigate to promise detail page
                promise_url = f"{self.base_url}/promise/{promise_id}"
                self.driver.get(promise_url)
                
                # Wait for PromiseCard to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='promise-card']"))
                )
                
                load_time = time.time() - start_time
                
                # Find evidence count element
                try:
                    evidence_count_element = self.driver.find_element(
                        By.CSS_SELECTOR, "[data-testid='evidence-count']"
                    )
                    displayed_count = int(evidence_count_element.text.strip())
                except (NoSuchElementException, ValueError):
                    # Try alternative selectors
                    try:
                        evidence_count_element = self.driver.find_element(
                            By.CSS_SELECTOR, ".evidence-count"
                        )
                        displayed_count = int(evidence_count_element.text.strip())
                    except:
                        displayed_count = None
                
                accuracy_results.append({
                    'promise_id': promise_id,
                    'expected_count': expected_count,
                    'displayed_count': displayed_count,
                    'accurate': displayed_count == expected_count if displayed_count is not None else False,
                    'load_time': load_time,
                    'error': None if displayed_count is not None else "Could not find evidence count element"
                })
                
            except TimeoutException:
                accuracy_results.append({
                    'promise_id': promise_id,
                    'expected_count': expected_count,
                    'displayed_count': None,
                    'accurate': False,
                    'load_time': None,
                    'error': "Page load timeout"
                })
            except Exception as e:
                accuracy_results.append({
                    'promise_id': promise_id,
                    'expected_count': expected_count,
                    'displayed_count': None,
                    'accurate': False,
                    'load_time': None,
                    'error': str(e)
                })
        
        # Calculate accuracy metrics
        total_tests = len(accuracy_results)
        accurate_tests = sum(1 for result in accuracy_results if result['accurate'])
        accuracy_rate = accurate_tests / total_tests if total_tests > 0 else 0
        
        avg_load_time = sum(
            result['load_time'] for result in accuracy_results 
            if result['load_time'] is not None
        ) / len([r for r in accuracy_results if r['load_time'] is not None])
        
        self.test_results['functionality_tests']['evidence_count_accuracy'] = {
            'total_tests': total_tests,
            'accurate_tests': accurate_tests,
            'accuracy_rate': accuracy_rate,
            'average_load_time': avg_load_time,
            'results': accuracy_results
        }
        
        print(f"    📊 Accuracy rate: {accuracy_rate:.1%}")
        print(f"    ⚡ Average load time: {avg_load_time:.2f}s")
    
    async def test_last_update_date_calculation(self, test_promises: List[Dict[str, Any]]):
        """Test that last update dates are calculated correctly."""
        print("  📅 Testing last update date calculation...")
        
        date_results = []
        
        for promise in test_promises:
            promise_id = promise['id']
            
            # Calculate expected last update date
            expected_date = await self.calculate_expected_last_update_date(promise)
            
            try:
                start_time = time.time()
                
                # Navigate to promise page
                promise_url = f"{self.base_url}/promise/{promise_id}"
                self.driver.get(promise_url)
                
                # Wait for PromiseCard to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='promise-card']"))
                )
                
                load_time = time.time() - start_time
                
                # Find last update date element
                try:
                    last_update_element = self.driver.find_element(
                        By.CSS_SELECTOR, "[data-testid='last-update-date']"
                    )
                    displayed_date_text = last_update_element.text.strip()
                    
                    # Parse displayed date (this might need adjustment based on actual format)
                    displayed_date = self.parse_displayed_date(displayed_date_text)
                    
                except (NoSuchElementException, ValueError):
                    displayed_date = None
                
                # Compare dates (allowing for some tolerance due to formatting)
                date_match = self.dates_match(expected_date, displayed_date)
                
                date_results.append({
                    'promise_id': promise_id,
                    'expected_date': expected_date.isoformat() if expected_date else None,
                    'displayed_date': displayed_date.isoformat() if displayed_date else None,
                    'displayed_text': displayed_date_text if 'displayed_date_text' in locals() else None,
                    'accurate': date_match,
                    'load_time': load_time,
                    'error': None if displayed_date is not None else "Could not find or parse date element"
                })
                
            except Exception as e:
                date_results.append({
                    'promise_id': promise_id,
                    'expected_date': expected_date.isoformat() if expected_date else None,
                    'displayed_date': None,
                    'displayed_text': None,
                    'accurate': False,
                    'load_time': None,
                    'error': str(e)
                })
        
        # Calculate date accuracy metrics
        total_tests = len(date_results)
        accurate_tests = sum(1 for result in date_results if result['accurate'])
        date_accuracy_rate = accurate_tests / total_tests if total_tests > 0 else 0
        
        self.test_results['functionality_tests']['last_update_date_accuracy'] = {
            'total_tests': total_tests,
            'accurate_tests': accurate_tests,
            'accuracy_rate': date_accuracy_rate,
            'results': date_results
        }
        
        print(f"    📊 Date accuracy rate: {date_accuracy_rate:.1%}")
    
    async def calculate_expected_last_update_date(self, promise: Dict[str, Any]) -> datetime:
        """Calculate the expected last update date for a promise."""
        latest_date = None
        
        # Check promise's own dates
        for date_field in ['date_updated', 'date_issued']:
            if date_field in promise and promise[date_field]:
                date_value = promise[date_field]
                if hasattr(date_value, 'timestamp'):
                    date_obj = datetime.fromtimestamp(date_value.timestamp(), tz=timezone.utc)
                elif isinstance(date_value, str):
                    date_obj = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                else:
                    continue
                
                if latest_date is None or date_obj > latest_date:
                    latest_date = date_obj
        
        # Check evidence dates if evidence exists
        if 'linked_evidence_ids' in promise:
            evidence_ids = promise['linked_evidence_ids']
            for evidence_id in evidence_ids:
                try:
                    evidence_doc = self.db.collection('evidence_items').document(evidence_id).get()
                    if evidence_doc.exists:
                        evidence_data = evidence_doc.to_dict()
                        evidence_date = evidence_data.get('evidence_date')
                        
                        if evidence_date:
                            if hasattr(evidence_date, 'timestamp'):
                                date_obj = datetime.fromtimestamp(evidence_date.timestamp(), tz=timezone.utc)
                            elif isinstance(evidence_date, str):
                                date_obj = datetime.fromisoformat(evidence_date.replace('Z', '+00:00'))
                            else:
                                continue
                            
                            if latest_date is None or date_obj > latest_date:
                                latest_date = date_obj
                except Exception:
                    continue
        
        return latest_date
    
    def parse_displayed_date(self, date_text: str) -> datetime:
        """Parse displayed date text into datetime object."""
        # This will need to be adjusted based on the actual date format used in the UI
        # Common formats to try:
        formats = [
            "%Y-%m-%d",
            "%B %d, %Y",
            "%b %d, %Y",
            "%m/%d/%Y",
            "%d/%m/%Y"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        # If no format works, try to extract date from text
        import re
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        match = re.search(date_pattern, date_text)
        if match:
            return datetime.strptime(match.group(1), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        
        raise ValueError(f"Could not parse date: {date_text}")
    
    def dates_match(self, expected: datetime, displayed: datetime, tolerance_days: int = 1) -> bool:
        """Check if two dates match within tolerance."""
        if expected is None or displayed is None:
            return False
        
        diff = abs((expected - displayed).days)
        return diff <= tolerance_days
    
    async def test_performance_by_evidence_count(self, test_promises: List[Dict[str, Any]]):
        """Test performance with different evidence counts."""
        print("  ⚡ Testing performance by evidence count...")
        
        performance_results = []
        
        # Group promises by evidence count ranges
        evidence_ranges = {
            '0': [],
            '1-10': [],
            '11-50': [],
            '50+': []
        }
        
        for promise in test_promises:
            evidence_count = 0
            if 'linked_evidence_ids' in promise:
                evidence_count = len(promise['linked_evidence_ids'])
            elif 'evidence' in promise:
                evidence_count = len(promise['evidence'])
            
            if evidence_count == 0:
                evidence_ranges['0'].append(promise)
            elif evidence_count <= 10:
                evidence_ranges['1-10'].append(promise)
            elif evidence_count <= 50:
                evidence_ranges['11-50'].append(promise)
            else:
                evidence_ranges['50+'].append(promise)
        
        # Test performance for each range
        for range_name, promises in evidence_ranges.items():
            if not promises:
                continue
            
            range_times = []
            
            for promise in promises[:3]:  # Test max 3 from each range
                promise_id = promise['id']
                
                try:
                    # Measure multiple load times for consistency
                    load_times = []
                    for _ in range(3):
                        start_time = time.time()
                        
                        promise_url = f"{self.base_url}/promise/{promise_id}"
                        self.driver.get(promise_url)
                        
                        # Wait for PromiseCard to be fully loaded
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='promise-card']"))
                        )
                        
                        # Additional wait for evidence count to be calculated
                        time.sleep(0.5)
                        
                        load_time = time.time() - start_time
                        load_times.append(load_time)
                    
                    avg_load_time = sum(load_times) / len(load_times)
                    range_times.append(avg_load_time)
                    
                    performance_results.append({
                        'promise_id': promise_id,
                        'evidence_range': range_name,
                        'evidence_count': len(promise.get('linked_evidence_ids', promise.get('evidence', []))),
                        'average_load_time': avg_load_time,
                        'load_times': load_times,
                        'meets_target': avg_load_time < 0.5  # 500ms target
                    })
                    
                except Exception as e:
                    performance_results.append({
                        'promise_id': promise_id,
                        'evidence_range': range_name,
                        'evidence_count': len(promise.get('linked_evidence_ids', promise.get('evidence', []))),
                        'average_load_time': None,
                        'load_times': [],
                        'meets_target': False,
                        'error': str(e)
                    })
            
            # Calculate range statistics
            if range_times:
                avg_range_time = sum(range_times) / len(range_times)
                print(f"    📊 {range_name} evidence items: {avg_range_time:.2f}s average")
        
        self.test_results['performance_metrics']['load_time_by_evidence_count'] = performance_results
    
    async def test_edge_cases(self, test_promises: List[Dict[str, Any]]):
        """Test edge cases and error handling."""
        print("  🎯 Testing edge cases...")
        
        edge_case_results = []
        
        # Test 1: Promise with no evidence
        promises_no_evidence = [p for p in test_promises 
                               if not p.get('linked_evidence_ids') and not p.get('evidence')]
        
        if promises_no_evidence:
            promise = promises_no_evidence[0]
            result = await self.test_single_edge_case(
                promise['id'], 
                "no_evidence", 
                "Promise with no evidence should display 0 count"
            )
            edge_case_results.append(result)
        
        # Test 2: Promise with malformed evidence data
        # (This would require creating test data or finding existing malformed data)
        
        # Test 3: Very long promise titles
        long_title_promises = [p for p in test_promises if len(p.get('title', '')) > 100]
        if long_title_promises:
            promise = long_title_promises[0]
            result = await self.test_single_edge_case(
                promise['id'],
                "long_title",
                "Promise with long title should display properly"
            )
            edge_case_results.append(result)
        
        self.test_results['edge_case_tests'] = edge_case_results
    
    async def test_single_edge_case(self, promise_id: str, case_type: str, description: str) -> Dict[str, Any]:
        """Test a single edge case."""
        try:
            start_time = time.time()
            
            promise_url = f"{self.base_url}/promise/{promise_id}"
            self.driver.get(promise_url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='promise-card']"))
            )
            
            load_time = time.time() - start_time
            
            # Check for any JavaScript errors
            logs = self.driver.get_log('browser')
            js_errors = [log for log in logs if log['level'] == 'SEVERE']
            
            return {
                'promise_id': promise_id,
                'case_type': case_type,
                'description': description,
                'load_time': load_time,
                'success': True,
                'js_errors': js_errors,
                'error': None
            }
            
        except Exception as e:
            return {
                'promise_id': promise_id,
                'case_type': case_type,
                'description': description,
                'load_time': None,
                'success': False,
                'js_errors': [],
                'error': str(e)
            }
    
    async def test_data_consistency(self, test_promises: List[Dict[str, Any]]):
        """Test data consistency between database and display."""
        print("  🔗 Testing data consistency...")
        
        consistency_results = []
        
        for promise in test_promises[:5]:  # Test first 5 promises
            promise_id = promise['id']
            
            try:
                # Navigate to promise page
                promise_url = f"{self.base_url}/promise/{promise_id}"
                self.driver.get(promise_url)
                
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='promise-card']"))
                )
                
                # Extract displayed data
                displayed_data = {}
                
                try:
                    title_element = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='promise-title']")
                    displayed_data['title'] = title_element.text.strip()
                except:
                    displayed_data['title'] = None
                
                try:
                    description_element = self.driver.find_element(By.CSS_SELECTOR, "[data-testid='promise-description']")
                    displayed_data['description'] = description_element.text.strip()
                except:
                    displayed_data['description'] = None
                
                # Compare with database data
                consistency_check = {
                    'title_match': displayed_data['title'] == promise.get('title') if displayed_data['title'] else False,
                    'description_match': displayed_data['description'] == promise.get('description') if displayed_data['description'] else False
                }
                
                consistency_results.append({
                    'promise_id': promise_id,
                    'displayed_data': displayed_data,
                    'database_data': {
                        'title': promise.get('title'),
                        'description': promise.get('description')
                    },
                    'consistency_check': consistency_check,
                    'overall_consistent': all(consistency_check.values())
                })
                
            except Exception as e:
                consistency_results.append({
                    'promise_id': promise_id,
                    'displayed_data': {},
                    'database_data': {},
                    'consistency_check': {},
                    'overall_consistent': False,
                    'error': str(e)
                })
        
        self.test_results['data_consistency_tests'] = consistency_results
    
    async def generate_performance_benchmarks(self):
        """Generate performance benchmarks and targets."""
        print("  📈 Generating performance benchmarks...")
        
        performance_data = self.test_results['performance_metrics'].get('load_time_by_evidence_count', [])
        
        if not performance_data:
            return
        
        # Calculate benchmarks by evidence range
        benchmarks = {}
        
        for range_name in ['0', '1-10', '11-50', '50+']:
            range_data = [p for p in performance_data if p['evidence_range'] == range_name and p['average_load_time']]
            
            if range_data:
                load_times = [p['average_load_time'] for p in range_data]
                benchmarks[range_name] = {
                    'count': len(load_times),
                    'average': sum(load_times) / len(load_times),
                    'min': min(load_times),
                    'max': max(load_times),
                    'meets_target_rate': sum(1 for p in range_data if p['meets_target']) / len(range_data)
                }
        
        # Overall performance summary
        all_load_times = [p['average_load_time'] for p in performance_data if p['average_load_time']]
        overall_performance = {
            'total_tests': len(all_load_times),
            'average_load_time': sum(all_load_times) / len(all_load_times) if all_load_times else 0,
            'target_met_rate': sum(1 for p in performance_data if p['meets_target']) / len(performance_data) if performance_data else 0,
            'benchmarks_by_range': benchmarks
        }
        
        self.test_results['performance_metrics']['benchmarks'] = overall_performance
        
        print(f"    📊 Overall average load time: {overall_performance['average_load_time']:.2f}s")
        print(f"    🎯 Target met rate: {overall_performance['target_met_rate']:.1%}")
    
    async def export_results(self):
        """Export test results to files."""
        print("  💾 Exporting test results...")
        
        # Create output directory
        os.makedirs('testing_results/promise_card', exist_ok=True)
        
        # 1. JSON export
        with open('testing_results/promise_card/test_results.json', 'w') as f:
            json.dump(self.test_results, f, indent=2, default=str)
        
        # 2. CSV exports for analysis
        if 'functionality_tests' in self.test_results:
            # Evidence count accuracy
            if 'evidence_count_accuracy' in self.test_results['functionality_tests']:
                accuracy_data = self.test_results['functionality_tests']['evidence_count_accuracy']['results']
                df = pd.DataFrame(accuracy_data)
                df.to_csv('testing_results/promise_card/evidence_count_accuracy.csv', index=False)
            
            # Date accuracy
            if 'last_update_date_accuracy' in self.test_results['functionality_tests']:
                date_data = self.test_results['functionality_tests']['last_update_date_accuracy']['results']
                df = pd.DataFrame(date_data)
                df.to_csv('testing_results/promise_card/date_accuracy.csv', index=False)
        
        # 3. Performance data
        if 'performance_metrics' in self.test_results:
            performance_data = self.test_results['performance_metrics'].get('load_time_by_evidence_count', [])
            if performance_data:
                df = pd.DataFrame(performance_data)
                df.to_csv('testing_results/promise_card/performance_metrics.csv', index=False)
        
        # 4. Generate test report
        await self.generate_test_report()
        
        print("    ✅ Results exported to testing_results/promise_card/")
    
    async def generate_test_report(self):
        """Generate comprehensive test report."""
        functionality = self.test_results.get('functionality_tests', {})
        performance = self.test_results.get('performance_metrics', {})
        
        # Calculate summary statistics
        evidence_accuracy = functionality.get('evidence_count_accuracy', {})
        date_accuracy = functionality.get('last_update_date_accuracy', {})
        benchmarks = performance.get('benchmarks', {})
        
        report = f"""
# PromiseCard Component Test Report
Generated: {self.test_results['timestamp']}

## Executive Summary

### Functionality Test Results
- **Evidence Count Accuracy**: {evidence_accuracy.get('accuracy_rate', 0):.1%} ({evidence_accuracy.get('accurate_tests', 0)}/{evidence_accuracy.get('total_tests', 0)} tests passed)
- **Date Calculation Accuracy**: {date_accuracy.get('accuracy_rate', 0):.1%} ({date_accuracy.get('accurate_tests', 0)}/{date_accuracy.get('total_tests', 0)} tests passed)

### Performance Test Results
- **Average Load Time**: {benchmarks.get('average_load_time', 0):.2f}s
- **Target Met Rate**: {benchmarks.get('target_met_rate', 0):.1%} (target: <500ms)
- **Total Performance Tests**: {benchmarks.get('total_tests', 0)}

## Detailed Results

### Evidence Count Accuracy
The PromiseCard component should display accurate evidence counts based on the promise's linked evidence.

**Results**: {evidence_accuracy.get('accuracy_rate', 0):.1%} accuracy rate
**Average Load Time**: {evidence_accuracy.get('average_load_time', 0):.2f}s

### Last Update Date Calculation
The component should calculate and display the most recent date from promise and evidence data.

**Results**: {date_accuracy.get('accuracy_rate', 0):.1%} accuracy rate

### Performance by Evidence Count
Load time performance across different evidence count ranges:

"""
        
        # Add performance breakdown by range
        if 'benchmarks_by_range' in benchmarks:
            for range_name, stats in benchmarks['benchmarks_by_range'].items():
                report += f"""
**{range_name} Evidence Items**:
- Average Load Time: {stats['average']:.2f}s
- Target Met Rate: {stats['meets_target_rate']:.1%}
- Tests: {stats['count']}
"""
        
        report += f"""

## Recommendations

### Performance Optimization
"""
        
        if benchmarks.get('target_met_rate', 0) < 0.9:
            report += """
1. **Improve Load Times**: Current performance below 90% target achievement
2. **Optimize Evidence Loading**: Consider lazy loading for high evidence count promises
3. **Implement Caching**: Cache evidence counts to reduce calculation time
"""
        else:
            report += """
1. **Performance Acceptable**: Current load times meet targets
2. **Monitor Regression**: Set up continuous performance monitoring
"""
        
        if evidence_accuracy.get('accuracy_rate', 0) < 0.95:
            report += """

### Data Accuracy Issues
1. **Fix Evidence Count Calculation**: Some promises show incorrect evidence counts
2. **Review Data Loading Logic**: Ensure both legacy and current evidence fields are handled
3. **Add Error Handling**: Improve graceful degradation for missing data
"""
        
        report += """

## Next Steps
1. Address any failing tests identified in this report
2. Implement performance optimizations if needed
3. Set up automated testing for regression prevention
4. Monitor performance metrics in production
"""
        
        with open('testing_results/promise_card/test_report.md', 'w') as f:
            f.write(report)
        
        print("    📄 Test report saved to testing_results/promise_card/test_report.md")
    
    async def cleanup(self):
        """Clean up test environment."""
        if self.driver:
            self.driver.quit()
            print("  🧹 WebDriver closed")

async def main():
    """Main execution function."""
    # Check if application is running
    try:
        response = requests.get("http://localhost:3000", timeout=5)
        if response.status_code != 200:
            print("❌ Application not accessible at http://localhost:3000")
            print("💡 Please start the Next.js application first:")
            print("   cd PromiseTracker && npm run dev")
            return
    except requests.exceptions.RequestException:
        print("❌ Application not running at http://localhost:3000")
        print("💡 Please start the Next.js application first:")
        print("   cd PromiseTracker && npm run dev")
        return
    
    tester = PromiseCardTester()
    results = await tester.run_complete_test_suite()
    
    print("\n" + "=" * 60)
    print("🎉 PROMISECARD TESTING COMPLETE!")
    print("=" * 60)
    
    functionality = results.get('functionality_tests', {})
    performance = results.get('performance_metrics', {})
    
    evidence_accuracy = functionality.get('evidence_count_accuracy', {})
    benchmarks = performance.get('benchmarks', {})
    
    print(f"📊 Evidence Count Accuracy: {evidence_accuracy.get('accuracy_rate', 0):.1%}")
    print(f"⚡ Average Load Time: {benchmarks.get('average_load_time', 0):.2f}s")
    print(f"🎯 Performance Target Met: {benchmarks.get('target_met_rate', 0):.1%}")
    print("\n📁 Results saved to: testing_results/promise_card/")
    print("📄 Full report: testing_results/promise_card/test_report.md")

if __name__ == "__main__":
    asyncio.run(main()) 