# common_utils.py
import logging

logger = logging.getLogger(__name__) 

PROMISE_CATEGORIES = [
    "Economy", "Healthcare", "Immigration", "Defence", "Housing", 
    "Cost of Living", "Environment", "Social Programs", "Governance", 
    "Indigenous Relations", "Foreign Affairs", "Infrastructure", "Other" 
]

# --- Updated DEPARTMENT_MAP with 'full' and 'short' names (No Acronyms) ---
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
    "minister of intergovernmental affairs, infrastructure and communities": {"full": "Infrastructure Canada", "short": "Infrastructure"},
    "minister of national defence": {"full": "National Defence", "short": "Defence"},
    "minister of housing and diversity and inclusion": {"full": "Infrastructure Canada", "short": "Infrastructure"}, # Note: Still mapped to Infrastructure full/short
    "minister of foreign affairs": {"full": "Global Affairs Canada", "short": "Foreign Affairs"}, # Changed from GAC
    "minister of international trade, export promotion, small business and economic development": {"full": "Global Affairs Canada", "short": "Foreign Affairs"}, # Also Foreign Affairs
    "minister of canadian heritage and quebec lieutenant": {"full": "Canadian Heritage", "short": "Heritage"},
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario": {"full": "Indigenous Services Canada", "short": "Indigenous Services"},
    "minister of justice and attorney general of canada": {"full": "Justice Canada", "short": "Justice"},
    "minister of crown-indigenous relations": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Crown-Indigenous Relations"}, # Changed from CIRNAC
    "president of the queen's privy council for canada and minister of emergency preparedness": {"full": "Public Safety Canada", "short": "Public Safety"}, # Maps to Public Safety
    "president of the queen\'s privy council and minister of emergency preparedness": {"full": "Public Safety Canada", "short": "Public Safety"}, # Shorter variant
    "minister of transport": {"full": "Transport Canada", "short": "Transport"},
    "minister of international development and minister responsible for the pacific economic development agency of canada": {"full": "Global Affairs Canada", "short": "Foreign Affairs"}, # Also Foreign Affairs
    "minister of families, children and social development": {"full": "Employment and Social Development Canada", "short": "Employment"}, # Also Employment
    "minister of fisheries, oceans and the canadian coast guard": {"full": "Fisheries and Oceans Canada", "short": "Fisheries"}, # Changed from DFO
    "minister of fisheries, oceans and canadian coast guard": {"full": "Fisheries and Oceans Canada", "short": "Fisheries"}, # Variant without 'the'
    "minister of labour": {"full": "Employment and Social Development Canada", "short": "Employment"}, # Also Employment
    "minister of immigration, refugees and citizenship": {"full": "Immigration, Refugees and Citizenship Canada", "short": "Immigration"}, # Changed from IRCC
    "minister of public services and procurement": {"full": "Public Services and Procurement Canada", "short": "Procurement"}, # Changed from PSPC
    "minister for women and gender equality and youth": {"full": "Women and Gender Equality Canada", "short": "Gender Equality"}, # Changed from WAGE
    "minister of national revenue": {"full": "Canada Revenue Agency", "short": "Revenue Agency"}, # Changed from CRA
    "minister of mental health and addictions and associate minister of health": {"full": "Health Canada", "short": "Health"}, # Also Health
    "minister of agriculture and agri-food": {"full": "Agriculture and Agri-Food Canada", "short": "Agriculture"}, # Changed from AAFC
    "minister of northern affairs, minister responsible for prairies economic development canada, and minister responsible for the canadian northern economic development agency": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Crown-Indigenous Relations"}, # Also Crown-Indigenous Relations
    "leader of the government in the house of commons": {"full": "Privy Council Office", "short": "Privy Council"}, # Changed from PCO
    "minister of veterans affairs and associate minister of national defence": {"full": "Veterans Affairs Canada", "short": "Veterans Affairs"}, # Changed from VAC
    "minister of veteran\'s affairs": {"full": "Veterans Affairs Canada", "short": "Veterans Affairs"}, # Shorter variant
    "minister of sport and minister responsible for the economic development agency of canada for the regions of quebec": {"full": "Canadian Heritage", "short": "Heritage"}, # Also Heritage
    "minister of official languages and minister responsible for the atlantic canada opportunities agency": {"full": "Canadian Heritage", "short": "Heritage"}, # Also Heritage
    "minister of seniors": {"full": "Employment and Social Development Canada", "short": "Employment"}, # Also Employment
    "minister responsible for the federal economic development agency for southern ontario": {"full": "Federal Economic Development Agency for Southern Ontario", "short": "FedDev Ontario"}, # Kept as is, fairly common
    "minister of tourism and associate minister of finance": {"full": "Innovation, Science and Economic Development Canada", "short": "Innovation"}, # Also Innovation
    "minister of rural economic development": {"full": "Innovation, Science and Economic Development Canada", "short": "Innovation"}, # Also Innovation

    # Simple/Common Variants
    "minister of finance": {"full": "Finance Canada", "short": "Finance"},
    "minister of indigenous services": {"full": "Indigenous Services Canada", "short": "Indigenous Services"},
    "minister of crown-indigenous relations": {"full": "Crown-Indigenous Relations and Northern Affairs Canada", "short": "Crown-Indigenous Relations"}, 
    "minister of canadian heritage": {"full": "Canadian Heritage", "short": "Heritage"}, 

    # Malformed Variants (Handle special case)
    "president of the queen's privy council for canada and minister of emergency preparedness president of the treasury board": {"full": "Multiple Departments - Needs Review", "short": "Multiple"}, 
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario and minister responsible for the federal economic development agency for northern ontario": {"full": "Indigenous Services Canada", "short": "Indigenous Services"}, 
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario canada": {"full": "Indigenous Services Canada", "short": "Indigenous Services"} ,
    
    # Typo from original map
    "ministre of foreign affairs": {"full": "Global Affairs Canada", "short": "Foreign Affairs"} 
}

# --- standardize_department_name function remains the same ---
# It still returns the FULL name string or None
def standardize_department_name(name_str):
    """
    Standardizes a raw department/ministerial title string to the official FULL department name.
    Returns the full name string or None if no mapping is found.
    """
    original_name_str = str(name_str).strip()
    
    # Normalize apostrophes and spaces, and convert to lowercase
    normalized_name = (original_name_str.lower()
                       .replace("’", "'")  # U+2019
                       .replace("‘", "'")  # U+2018
                       .replace("`", "'")  # U+0060
                       .replace("´", "'")  # U+00B4
                       .replace('\xa0', ' ')) # Non-breaking space

    if not normalized_name or normalized_name == 'nan':
         return None # Return None for empty/NaN input

    # --- Direct Lookup ---
    match_data = DEPARTMENT_MAP.get(normalized_name)
    if match_data:
        # Return ONLY the full name for backward compatibility
        return match_data.get('full') 

    # --- Fallback Substring Search ---
    for key, value_dict in DEPARTMENT_MAP.items():
        if key in normalized_name:
            if "minister of" in normalized_name or "deputy prime minister" in normalized_name or "president of" in normalized_name or "leader of" in normalized_name:
                 # Return ONLY the full name
                 return value_dict.get('full')

    # If no match found after direct and fallback
    logger.warning(f"Could not standardize department: '{original_name_str}' (Normalized: '{normalized_name}')")
    # Return None if no mapping found
    return None 

# --- Updated map for easy lookup of short name FROM full name ---
FULL_NAME_TO_SHORT_NAME_MAP = {}
for mapping_value in DEPARTMENT_MAP.values():
    if isinstance(mapping_value, dict) and 'full' in mapping_value and 'short' in mapping_value:
        full_name = mapping_value['full']
        short_name = mapping_value['short']
        if full_name not in FULL_NAME_TO_SHORT_NAME_MAP:
             FULL_NAME_TO_SHORT_NAME_MAP[full_name] = short_name

# Add check for the special case
if "Multiple Departments - Needs Review" not in FULL_NAME_TO_SHORT_NAME_MAP:
    FULL_NAME_TO_SHORT_NAME_MAP["Multiple Departments - Needs Review"] = "Multiple"

# --- New function to get the short name ---
def get_department_short_name(standardized_full_name):
    """
    Takes a standardized FULL department name and returns its common short name.
    Returns the short name string, or the input full name if no short name is mapped.
    """
    if not standardized_full_name:
        return None 
        
    short_name = FULL_NAME_TO_SHORT_NAME_MAP.get(standardized_full_name)
    
    if short_name:
        return short_name
    else:
        # Fallback if the full name isn't in our derived map
        logger.warning(f"No short name mapping found for full name: '{standardized_full_name}'. Returning full name.")
        return standardized_full_name # Return the full name as fallback