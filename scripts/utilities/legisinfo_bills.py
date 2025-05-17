import requests
import xml.etree.ElementTree as ET
import time

def fetch_bill_text_versions(detailed_xml_url):
    """
    Fetches and parses a detailed XML record for a single bill to extract
    descriptions and URLs for different XML versions of the bill text.

    Args:
        detailed_xml_url (str): The URL to the detailed XML for the bill.

    Returns:
        list: A list of dictionaries, each containing 'description' and 'xml_url'
              for an English XML version of the bill text. Returns an empty list
              if no versions are found or an error occurs.
    """
    if not detailed_xml_url:
        return [] # Return an empty list if no URL is provided
    
    print(f"    Fetching detailed bill information from: {detailed_xml_url}")
    text_versions = []
    parl_base_url = "https://www.parl.ca"

    try:
        time.sleep(0.5) # Be respectful to the server
        response = requests.get(detailed_xml_url, timeout=30)
        response.raise_for_status()
        
        detailed_xml_data = response.content
        detailed_root = ET.fromstring(detailed_xml_data) # Root of the specific bill's XML

        # Primary way: Look for <BillDocument> elements, common in LEGISinfo detailed XML
        # These should contain the relative paths for bill texts.
        bill_documents_node = detailed_root.find('.//BillDocuments')
        if bill_documents_node is not None:
            for doc_node in bill_documents_node.findall('BillDocument'):
                doc_type_node = doc_node.find('DocumentType') # e.g., "First Reading House of Commons"
                relative_path_node = doc_node.find('RelativePath') # e.g., "/Content/Bills/441/..."
                language_node = doc_node.find('Language') # Should be 'eng' for English

                if doc_type_node is not None and doc_type_node.text and \
                   relative_path_node is not None and relative_path_node.text:
                    
                    relative_path = relative_path_node.text.strip()
                    is_english_xml = False

                    # Check 1: Explicit Language tag
                    if language_node is not None and language_node.text and language_node.text.lower() == 'eng':
                        is_english_xml = True
                    
                    # Check 2: Path convention (like _E.xml), as a strong indicator
                    if not is_english_xml and (relative_path.lower().endswith("_e.xml") or "_e." in relative_path.lower()):
                        is_english_xml = True
                    
                    # If no language node, but path doesn't scream French, assume English if it's XML
                    if language_node is None and not (relative_path.lower().endswith("_f.xml") or "_f." in relative_path.lower()):
                         if relative_path.lower().endswith(".xml"): # Default to including if unclear but looks like an XML path
                            is_english_xml = True


                    if is_english_xml and relative_path.lower().endswith(".xml"):
                        description = doc_type_node.text.strip()
                        # Ensure the URL is correctly formed with the base
                        xml_url = relative_path
                        if not xml_url.startswith(('http://', 'https://')):
                            if xml_url.startswith('/'):
                                xml_url = f"{parl_base_url}{xml_url}"
                            else:
                                xml_url = f"{parl_base_url}/{xml_url}" # Should not happen with /Content/...
                        
                        text_versions.append({'description': description, 'xml_url': xml_url})
        
        # Alternative structure check (less common for bill texts, but good for robustness)
        if not text_versions:
            publications_node = detailed_root.find('.//Publications')
            if publications_node is not None:
                for pub_node in publications_node.findall('Publication'):
                    title_node = pub_node.find('Title')
                    links_node = pub_node.find('Links')
                    if title_node is not None and title_node.text and links_node is not None:
                        for link_node in links_node.findall('Link'):
                            link_type = link_node.get('type')
                            link_href = link_node.get('href')
                            if link_type and link_type.upper() == 'XML' and link_href:
                                # Assuming English if not specified, or if title implies it
                                description = title_node.text.strip()
                                xml_url = link_href
                                if not xml_url.startswith(('http://', 'https://')):
                                    xml_url = f"{parl_base_url}{xml_url}" if xml_url.startswith('/') else f"{parl_base_url}/{xml_url}"
                                
                                # Simple check for English in URL as a heuristic
                                if "_e." in xml_url.lower() or "_f." not in xml_url.lower():
                                    text_versions.append({'description': description, 'xml_url': xml_url})
                                break # Found XML link for this publication

        if not text_versions:
            print(f"    No English XML bill text versions found or structure not recognized in: {detailed_xml_url}")
            
    except requests.exceptions.RequestException as e:
        print(f"    Error fetching detailed bill XML from {detailed_xml_url}: {e}")
    except ET.ParseError as e:
        print(f"    Error parsing detailed bill XML from {detailed_xml_url}: {e}")
    except Exception as e:
        print(f"    An unexpected error occurred while processing detailed bill info: {e}")
    
    return text_versions


def fetch_initial_bill_list(parliament_number_target):
    """
    Fetches the main list of bills and extracts essential info to identify them 
    and construct URLs to their detailed XML records.
    """
    bills_url = "https://www.parl.ca/legisinfo/en/bills/xml"
    bill_identifiers = []
    base_bill_page_url = "https://www.parl.ca/legisinfo/en/bill"

    print(f"Attempting to fetch main bill list from: {bills_url}")
    try:
        response = requests.get(bills_url, timeout=30)
        response.raise_for_status()
        xml_data = response.content
        root = ET.fromstring(xml_data)
        print(f"Successfully fetched and parsed main bill list. Identifying bills for Parliament {parliament_number_target}...")

        for bill_node in root.findall('.//Bill'):
            if bill_node.findtext('ParliamentNumber') == parliament_number_target:
                bill_info = {
                    'BillNumberFormatted': bill_node.findtext('BillNumberFormatted'),
                    'LongTitleEn': bill_node.findtext('LongTitleEn')
                }
                parl_num = bill_node.findtext('ParliamentNumber')
                sess_num = bill_node.findtext('SessionNumber')
                
                if parl_num and sess_num and bill_info.get('BillNumberFormatted'):
                    bill_identifier_for_url = bill_info['BillNumberFormatted'].lower()
                    bill_info['DetailedXmlUrl'] = f"{base_bill_page_url}/{parl_num}-{sess_num}/{bill_identifier_for_url}/xml"
                    bill_identifiers.append(bill_info)
                else:
                    print(f"    Could not form DetailedXmlUrl for a bill (Parl: {parl_num}, Sess: {sess_num}, Num: {bill_info.get('BillNumberFormatted')})")
        
        if not bill_identifiers:
            print(f"No bills found for Parliament {parliament_number_target} in the main feed or couldn't form detailed URLs.")
        else:
            print(f"Identified {len(bill_identifiers)} bills for Parliament {parliament_number_target} from the main feed.")
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching main bill list URL: {e}")
    except ET.ParseError as e:
        print(f"Error parsing main bill list XML: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during initial bill list processing: {e}")
        
    return bill_identifiers

if __name__ == "__main__":
    target_parliament = "44"
    
    print("Python script to fetch Parliamentary bill data and links to bill text XMLs.")
    print(f"Targeting Parliament: {target_parliament}")
    
    initial_bills = fetch_initial_bill_list(target_parliament)
    bills_to_process = 10  # For demonstration, let's process only a few bills. Adjust as needed.

    if initial_bills:
        print(f"\nFetching bill text XML links for up to {bills_to_process} bills from Parliament {target_parliament}:")
        
        for i, bill_info in enumerate(initial_bills[:bills_to_process]): 
            print(f"\n--- Bill {i+1}: {bill_info.get('BillNumberFormatted', 'N/A')} ---")
            print(f"  Long Title (En): {bill_info.get('LongTitleEn', 'N/A')}")
            
            detailed_xml_url = bill_info.get('DetailedXmlUrl')
            if not detailed_xml_url:
                print("    Detailed XML URL not available for this bill. Skipping text version fetch.")
                continue

            text_versions = fetch_bill_text_versions(detailed_xml_url)
            
            if text_versions:
                print("  Available English Bill Text XML Versions:")
                for version in text_versions:
                    print(f"    - Description: {version['description']}")
                    print(f"      XML URL: {version['xml_url']}")
            else:
                # This message is now printed within fetch_bill_text_versions if no versions are found there.
                # We can add a more general one here if the list is empty for other reasons.
                print("    No English XML versions of bill text were extracted.")

        if len(initial_bills) > bills_to_process:
            print(f"\n... Processed {bills_to_process} bills. {len(initial_bills) - bills_to_process} more bills were identified but not processed in this run.")
    else:
        print("No initial bill information was retrieved from the main list.")

    print("\nScript execution complete.")