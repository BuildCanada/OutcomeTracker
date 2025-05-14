# Ensure the 'requests' library is installed in your Python environment:
# pip install requests

import requests
import xml.etree.ElementTree as ET

def fetch_parliament_bills_xml(parliament_number_target):
    """
    Fetches XML data for bills and extracts detailed information for a specific parliament,
    including the URL to the bill's detail page on LEGISinfo.

    Args:
        parliament_number_target (str): The parliament number to filter for (e.g., "44").

    Returns:
        list: A list of dictionaries, where each dictionary contains details of a bill.
              Returns an empty list if an error occurs or no bills are found.
    """
    bills_url = "https://www.parl.ca/legisinfo/en/bills/xml"
    all_bills_data = []
    base_bill_page_url = "https://www.parl.ca/legisinfo/en/bill"

    print(f"Attempting to fetch bills from: {bills_url}")
    try:
        response = requests.get(bills_url, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        
        xml_data = response.content
        root = ET.fromstring(xml_data)
        
        print(f"Successfully fetched and parsed XML data. Processing bills for Parliament {parliament_number_target}...")

        for bill_node in root.findall('.//Bill'):
            parliament_number_node = bill_node.find('ParliamentNumber')
            
            if parliament_number_node is not None and parliament_number_node.text == parliament_number_target:
                bill_details = {}
                details_to_extract = [
                    'BillId', 'BillNumberFormatted', 'LongTitleEn', 'LongTitleFr',
                    'ShortTitleEn', 'ShortTitleFr', 'ParlSessionEn', 'ParlSessionFr',
                    'ParliamentNumber', 'SessionNumber', 'OriginatingChamberId', 
                    'BillTypeEn', 'BillTypeFr', 'CurrentStatusEn', 'CurrentStatusFr',
                    'SponsorEn', 'SponsorFr', 'LatestActivityEn', 'LatestActivityFr',
                    'LatestActivityDateTime', 'IntroducedHouseOfCommonsDateTime',
                    'PassedHouseOfCommonsFirstReadingDateTime', 
                    'PassedHouseOfCommonsSecondReadingDateTime',
                    'PassedHouseOfCommonsThirdReadingDateTime',
                    'IntroducedSenateDateTime',
                    'PassedSenateFirstReadingDateTime',
                    'PassedSenateSecondReadingDateTime',
                    'PassedSenateThirdReadingDateTime',
                    'ReceivedRoyalAssentDateTime'
                ]
                
                for detail_tag in details_to_extract:
                    node = bill_node.find(detail_tag)
                    bill_details[detail_tag] = node.text if node is not None and node.text is not None else None
                
                # Construct the bill detail page URL
                parl_num = bill_details.get('ParliamentNumber')
                sess_num = bill_details.get('SessionNumber')
                bill_num_formatted = bill_details.get('BillNumberFormatted')

                if parl_num and sess_num and bill_num_formatted:
                    # Ensure bill_num_formatted is not None before calling .lower()
                    bill_identifier_for_url = bill_num_formatted.lower()
                    bill_details['BillDetailPageUrl'] = f"{base_bill_page_url}/{parl_num}-{sess_num}/{bill_identifier_for_url}"
                else:
                    bill_details['BillDetailPageUrl'] = None
                
                all_bills_data.append(bill_details)
        
        if not all_bills_data:
            print(f"No bills found for Parliament {parliament_number_target} in the feed, or the feed structure is unexpected.")
        else:
            print(f"Found {len(all_bills_data)} bills for Parliament {parliament_number_target}.")
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
    return all_bills_data

if __name__ == "__main__":
    target_parliament = "44"
    
    print("Python script to fetch Parliamentary bill data.")
    print(f"Targeting Parliament: {target_parliament}")
    # print("Ensure the 'requests' library is installed ('pip install requests').") # Assuming it's installed now
    
    bills_from_44th = fetch_parliament_bills_xml(target_parliament)
    bills_to_process = 10 # Set the number of bills to process (as per your script)

    if bills_from_44th:
        print(f"\nDetailed Information for Bills from the {target_parliament}th Parliament:")
        for i, bill in enumerate(bills_from_44th[:bills_to_process]): 
            print(f"\n--- Bill {i+1} ({bill.get('BillNumberFormatted', 'N/A')}) ---")
            print(f"  Long Title (En): {bill.get('LongTitleEn', 'N/A')}")
            print(f"  Current Status (En): {bill.get('CurrentStatusEn', 'N/A')}")
            print(f"  Sponsor (En): {bill.get('SponsorEn', 'N/A')}")
            print(f"  Latest Activity (En): {bill.get('LatestActivityEn', 'N/A')}")
            print(f"  Latest Activity Date: {bill.get('LatestActivityDateTime', 'N/A')}")
            print(f"  LEGISinfo Detail Page: {bill.get('BillDetailPageUrl', 'N/A')}") # Added this line
            
            # To print all extracted details for each bill:
            # if i < 2: # Example: Print all details for the first two bills
            #     print("  Full extracted details:")
            #     for key, value in bill.items():
            #         if value is not None: # Only print if there's data
            #             print(f"    {key}: {value}")

        if len(bills_from_44th) > bills_to_process:
            print(f"\n... and {len(bills_from_44th) - bills_to_process} more bills (details not printed here for brevity).")
    else:
        print("No bill information was retrieved.")

    print("\nScript execution complete.")