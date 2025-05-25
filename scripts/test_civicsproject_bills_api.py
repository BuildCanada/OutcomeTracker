import os
import requests
from dotenv import load_dotenv
import argparse
import json
from typing import List, Dict, Any

load_dotenv()
API_TOKEN = os.getenv('CIVICS_PROJECT_API_TOKEN')
BASE_URL = "https://api.civicsproject.org/bills/canada"

def fetch_bill_details(bill_list: List[Dict[str, Any]], headers: Dict[str, str]) -> List[Dict[str, Any]]:
    """Fetch detailed information for all bills in the list."""
    detailed_bills = []
    total_bills = len(bill_list)
    
    print(f"Fetching detailed information for {total_bills} bills...")
    
    for i, bill in enumerate(bill_list, 1):
        bill_id = bill.get('id') or bill.get('bill_id')
        if not bill_id:
            print(f"Warning: Bill {i} has no ID, skipping detailed fetch")
            detailed_bills.append(bill)  # Keep original bill data
            continue
            
        detail_url = f"{BASE_URL}/{bill_id}"
        try:
            print(f"Fetching details for bill {i}/{total_bills} (ID: {bill_id})")
            detail_resp = requests.get(detail_url, headers=headers)
            detail_resp.raise_for_status()
            bill_detail = detail_resp.json()
            detailed_bills.append(bill_detail)
        except Exception as e:
            print(f"Error fetching details for bill {bill_id}: {e}")
            detailed_bills.append(bill)  # Keep original bill data on error
            
    return detailed_bills

def main():
    parser = argparse.ArgumentParser(description="Test Civics Project Bills API and optionally output to JSON.")
    parser.add_argument('--details', action='store_true', help='Fetch detailed information for all bills (default: summary only).')
    parser.add_argument('--json', action='store_true', help='Output results to a JSON file.')
    parser.add_argument('--json_output_path', type=str, default=None, help='Path to output JSON file. Defaults to civicsproject_bills_output.json in script directory.')
    args = parser.parse_args()

    if not API_TOKEN:
        print("Error: CIVICS_PROJECT_API_TOKEN not set in environment.")
        exit(1)

    headers = {"Authorization": f"Bearer {API_TOKEN}"}

    # Fetch the main bills list
    try:
        print("Fetching bills summary...")
        resp = requests.get(BASE_URL, headers=headers)
        resp.raise_for_status()
        bills_response = resp.json()
    except Exception as e:
        print(f"Error fetching bills: {e}") 
        exit(1)

    # Print the raw response for inspection
    print("Raw bills response structure:", type(bills_response))

    # Try to extract the list of bills
    bill_list = None
    if isinstance(bills_response, list):
        bill_list = bills_response
    elif isinstance(bills_response, dict):
        # Try common keys
        for key in ['data', 'results', 'bills']:
            if key in bills_response and isinstance(bills_response[key], list):
                bill_list = bills_response[key]
                break
        if bill_list is None:
            print(f"Could not find a list of bills in the response. Available keys: {list(bills_response.keys())}")
            exit(1)
    else:
        print("Unexpected response type for bills.")
        exit(1)

    print(f"Total bills found: {len(bill_list)}")
    
    if not bill_list:
        print("No bills found in the response.")
        return

    # Show sample bill from summary
    print("\nSample bill (summary):")
    print(json.dumps(bill_list[0], indent=2))
    
    # Fetch detailed information if requested
    detailed_bills = None
    if args.details:
        detailed_bills = fetch_bill_details(bill_list, headers)
        print(f"\nSuccessfully fetched details for {len(detailed_bills)} bills")
        
        # Show sample detailed bill
        if detailed_bills:
            print("\nSample bill (detailed):")
            print(json.dumps(detailed_bills[0], indent=2))
    else:
        print(f"\nShowing summary information only. Use --details flag to fetch detailed information for all {len(bill_list)} bills.")

    # Output to JSON if requested
    if args.json:
        output_path = args.json_output_path or os.path.join(os.path.dirname(__file__), 'civicsproject_bills_output.json')
        output_data = {
            'metadata': {
                'total_bills': len(bill_list),
                'details_fetched': args.details,
                'timestamp': json.dumps(None)  # Could add timestamp here
            },
            'raw_response': bills_response,
            'bills_summary': bill_list
        }
        
        if detailed_bills:
            output_data['bills_detailed'] = detailed_bills
            
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            print(f"\nOutput written to {output_path}")
        except Exception as e:
            print(f"Error writing output to JSON: {e}")

if __name__ == "__main__":
    main()