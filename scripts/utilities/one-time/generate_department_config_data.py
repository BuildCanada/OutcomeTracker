import json
import re
# from datetime import datetime # Not strictly needed for server timestamp which is handled by Firestore

# --- PASTE YOUR DEPARTMENT_MAP HERE ---
# Make sure this is the most up-to-date version from your common_utils.py
DEPARTMENT_MAP = {
    # Standard Titles
    "deputy prime minister and minister of finance": {"full": "Finance Canada", "short": "Finance"},
    "minister of environment and climate change": {"full": "Environment and Climate Change Canada", "short": "Environment"},
    "president of the treasury board": {"full": "Treasury Board of Canada Secretariat", "short": "Treasury Board"},
    "minister of natural resources": {"full": "Natural Resources Canada", "short": "Natural Resources"},
    "minister of innovation, science and industry": {"full": "Innovation, Science and Economic Development Canada", "short": "Innovation"},
    "minister of health": {"full": "Health Canada", "short": "Health"},
    "minister of public safety": {"full": "Public Safety Canada", "short": "Public Safety"},
    "minister of employment, workforce development and disability inclusion": {"full": "Employment and Social Development Canada", "short": "Employment"},
    "minister of intergovernmental affairs, infrastructure and communities": {"full": "Infrastructure Canada", "short": "Housing"},
    "minister of national defence": {"full": "National Defence", "short": "Defence"},
    "minister of housing and diversity and inclusion": {"full": "Infrastructure Canada", "short": "Housing"},
    "minister of foreign affairs": {"full": "Global Affairs Canada", "short": "Foreign Affairs"},
    "minister of international trade, export promotion, small business and economic development": {"full": "Global Affairs Canada", "short": "Foreign Affairs"},
    "minister of canadian heritage and quebec lieutenant": {"full": "Canadian Heritage", "short": "Heritage"},
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario": {"full": "Indigenous Services Canada", "short": "Indigenous Services"},
    "minister of justice and attorney general of canada": {"full": "Justice Canada", "short": "Justice"},
    "minister of crown-indigenous relations": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Crown-Indigenous Relations"},
    "president of the queen's privy council for canada and minister of emergency preparedness": {"full": "Public Safety Canada", "short": "Public Safety"},
    "president of the queen\'s privy council and minister of emergency preparedness": {"full": "Public Safety Canada", "short": "Public Safety"},
    "minister of transport": {"full": "Transport Canada", "short": "Transport"},
    "minister of international development and minister responsible for the pacific economic development agency of canada": {"full": "Global Affairs Canada", "short": "Foreign Affairs"},
    "minister of families, children and social development": {"full": "Employment and Social Development Canada", "short": "Employment"},
    "minister of fisheries, oceans and the canadian coast guard": {"full": "Fisheries and Oceans Canada", "short": "Fisheries"},
    "minister of fisheries, oceans and canadian coast guard": {"full": "Fisheries and Oceans Canada", "short": "Fisheries"},
    "minister of labour": {"full": "Employment and Social Development Canada", "short": "Employment"},
    "minister of immigration, refugees and citizenship": {"full": "Immigration, Refugees and Citizenship Canada", "short": "Immigration"},
    "minister of public services and procurement": {"full": "Public Services and Procurement Canada", "short": "Procurement"},
    "minister for women and gender equality and youth": {"full": "Women and Gender Equality Canada", "short": "Gender Equality"},
    "minister of national revenue": {"full": "Canada Revenue Agency", "short": "Revenue Agency"},
    "minister of mental health and addictions and associate minister of health": {"full": "Health Canada", "short": "Health"},
    "minister of agriculture and agri-food": {"full": "Agriculture and Agri-Food Canada", "short": "Agriculture"},
    "minister of northern affairs, minister responsible for prairies economic development canada, and minister responsible for the canadian northern economic development agency": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Crown-Indigenous Relations"},
    "leader of the government in the house of commons": {"full": "Privy Council Office", "short": "Privy Council"},
    "minister of veterans affairs and associate minister of national defence": {"full": "Veterans Affairs Canada", "short": "Veterans Affairs"},
    "minister of veteran\'s affairs": {"full": "Veterans Affairs Canada", "short": "Veterans Affairs"},
    "minister of sport and minister responsible for the economic development agency of canada for the regions of quebec": {"full": "Canadian Heritage", "short": "Heritage"},
    "minister of official languages and minister responsible for the atlantic canada opportunities agency": {"full": "Canadian Heritage", "short": "Heritage"},
    "minister of official languages": {"full": "Canadian Heritage", "short": "Heritage"},
    "minister of seniors": {"full": "Employment and Social Development Canada", "short": "Employment"},
    "minister responsible for the federal economic development agency for southern ontario": {"full": "Federal Economic Development Agency for Southern Ontario", "short": "FedDev Ontario"},
    "minister of tourism and associate minister of finance": {"full": "Innovation, Science and Economic Development Canada", "short": "Innovation"},
    "minister of rural economic development": {"full": "Innovation, Science and Economic Development Canada", "short": "Innovation"},
    "minister of finance": {"full": "Finance Canada", "short": "Finance"},
    "minister of indigenous services": {"full": "Indigenous Services Canada", "short": "Indigenous Services"},
    # "minister of crown-indigenous relations": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Crown-Indigenous Relations"}, # Duplicate key, handled by logic below
    "minister of canadian heritage": {"full": "Canadian Heritage", "short": "Heritage"},
    "natural resources canada": {"full": "Natural Resources Canada", "short": "Natural Resources"},
    "public services and procurement canada": {"full": "Public Services and Procurement Canada", "short": "Procurement"},
    "minister of sport and physical activity": {"full": "Canadian Heritage", "short": "Heritage"},
    "minister of citizens\' services": {"full": "Treasury Board of Canada Secretariat", "short": "Treasury Board"},
    "president of the queen\'s privy council for canada and minister of emergency preparedness president of the treasury board": {"full": "Multiple Departments - Needs Review", "short": "Multiple"},
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario and minister responsible for the federal economic development agency for northern ontario": {"full": "Indigenous Services Canada", "short": "Indigenous Services"},
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario canada": {"full": "Indigenous Services Canada", "short": "Indigenous Services"},
    "ministre of foreign affairs": {"full": "Global Affairs Canada", "short": "Foreign Affairs"},
    "public safety canada": {"full": "Public Safety Canada", "short": "Public Safety"},
    "transport canada": {"full": "Transport Canada", "short": "Transport"},
    "treasury board of canada secretariat": {"full": "Treasury Board of Canada Secretariat", "short": "Treasury Board"},
    "veterans affairs canada": {"full": "Veterans Affairs Canada", "short": "Veterans Affairs"},
    "women and gender equality canada": {"full": "Women and Gender Equality Canada", "short": "WAGE"},
    "minister of public safety, democratic institutions and intergovernmental affairs": {"full": "Public Safety Canada", "short": "Public Safety"},
    # "president of the treasury board": {"full": "Treasury Board of Canada Secretariat", "short": "Treasury Board"}, # Duplicate key, handled by logic
    "president of the king\'s privy council for canada and minister of emergency preparedness": {"full": "Emergency Preparedness Canada", "short": "Emergency Preparedness"},
    "minister of northern affairs, minister responsible for prairies economic development canada and minister responsible for the canadian northern economic development agency": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Northern Affairs"},
}
# --- END OF DEPARTMENT_MAP ---

PRIORITY_DEPARTMENTS_MAP = {
    "Finance Canada": "Finance",
    "Natural Resources Canada": "Energy",
    "Treasury Board of Canada Secretariat": "Government Transformation",
    "National Defence": "Defence",
    "Immigration, Refugees and Citizenship Canada": "Immigration",
    "Health Canada": "Health",
    "Infrastructure Canada": "Housing",
    "Innovation, Science and Economic Development Canada": "Innovation"
}

def generate_slug(name):
    s = name.lower()
    s = re.sub(r'[\'"&]', '', s)  # Remove apostrophes, quotes, ampersands
    s = re.sub(r'[^\w\s-]', '', s)  # Remove remaining non-alphanumeric, non-space, non-hyphen
    s = re.sub(r'[-\s]+', '-', s)    # Replace spaces and multiple hyphens with single hyphen
    s = s.strip('-')
    return s if s else "unknown-department"


# Group variants by full department name
grouped_by_full_name = {}
for variant, details in DEPARTMENT_MAP.items():
    full_name = details.get("full")
    short_name_original = details.get("short")

    if not full_name or not short_name_original:
        print(f"Warning: Skipping variant '{variant}' due to missing 'full' or 'short' name.")
        continue

    if full_name not in grouped_by_full_name:
        grouped_by_full_name[full_name] = {
            "official_full_name": full_name,
            "display_short_name_original": short_name_original,
            "name_variants": set(),
            "bc_priority": 2,
            "notes": None,
            "last_updated_by": "System Migration Script - Initial Population",
        }
    grouped_by_full_name[full_name]["name_variants"].add(variant.lower())

# Prepare final list for Firestore
department_config_list = []
for full_name, data in grouped_by_full_name.items():
    # Generate slug from the official_full_name
    slug = generate_slug(data["official_full_name"])
    
    if not slug: # Handle cases where slug generation might fail for odd names
        print(f"Warning: Could not generate a valid slug for '{data['official_full_name']}'. Using a placeholder.")
        slug = f"dept-{hash(data['official_full_name'])}" # Simple placeholder

    # Determine display_short_name and bc_priority
    if data["official_full_name"] in PRIORITY_DEPARTMENTS_MAP:
        display_short_name = PRIORITY_DEPARTMENTS_MAP[data["official_full_name"]]
        bc_priority = 1
    else:
        display_short_name = data["display_short_name_original"]
        bc_priority = 2

    department_doc = {
        "department_slug": slug, # This will be the document ID in Firestore
        "official_full_name": data["official_full_name"],
        "display_short_name": display_short_name,
        "name_variants": sorted(list(data["name_variants"])),
        "bc_priority": bc_priority,
        "notes": data["notes"],
        "last_updated_by": data["last_updated_by"],
        # "last_updated_at": " Firestore Server Timestamp - set during import "
    }
    department_config_list.append(department_doc)

# Output as JSON
if __name__ == "__main__":
    output_json = json.dumps(department_config_list, indent=2)
    print(output_json)

    # To write to a file:
    # with open("department_config_initial_data.json", "w") as f:
    #     json.dump(department_config_list, f, indent=2)
    # print("\nData written to department_config_initial_data.json")

    # Example of how to use this data to populate Firestore (requires firebase_admin)
    #
    # import firebase_admin
    # from firebase_admin import credentials
    # from firebase_admin import firestore
    #
    # # Initialize Firebase Admin SDK (replace 'path/to/your/serviceAccountKey.json')
    # # cred = credentials.Certificate('path/to/your/serviceAccountKey.json')
    # # firebase_admin.initialize_app(cred)
    # # db = firestore.client()
    #
    # if not firebase_admin._apps:
    #    print("Firebase Admin SDK not initialized. Skipping Firestore population example.")
    #    print("To run this part, uncomment the Firebase init lines and provide your service account key.")
    # else:
    #    db = firestore.client()
    #    print("\nAttempting to populate Firestore...")
    #    for dept_data in department_config_list:
    #        doc_id = dept_data["department_slug"]
    #        # Create a copy to avoid modifying the list element, and add server timestamp
    #        data_to_upload = dept_data.copy()
    #        data_to_upload["last_updated_at"] = firestore.SERVER_TIMESTAMP
    #
    #        try:
    #            db.collection("department_config").document(doc_id).set(data_to_upload)
    #            print(f"Successfully added/updated: {doc_id}")
    #        except Exception as e:
    #            print(f"Error adding/updating {doc_id}: {e}")
    #    print("Firestore population attempt complete.") 