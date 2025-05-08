DEPARTMENT_MAP = {
    # From User's list (keys are lowercased)
    "deputy prime minister and minister of finance": "Finance Canada",
    "minister of environment and climate change": "Environment and Climate Change Canada",
    "president of the treasury board": "Treasury Board of Canada Secretariat",
    "minister of natural resources": "Natural Resources Canada",
    "minister of innovation, science and industry": "Innovation, Science and Economic Development Canada",
    "minister of health": "Health Canada",
    "minister of public safety": "Public Safety Canada",
    "minister of employment, workforce development and disability inclusion": "Employment and Social Development Canada",
    "minister of intergovernmental affairs, infrastructure and communities": "Infrastructure Canada",
    "minister of national defence": "National Defence",
    "minister of housing and diversity and inclusion": "Infrastructure Canada", # Note: Mapped to Infrastructure as per original
    "minister of foreign affairs": "Global Affairs Canada",
    "minister of international trade, export promotion, small business and economic development": "Global Affairs Canada",
    "minister of canadian heritage and quebec lieutenant": "Canadian Heritage",
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario": "Indigenous Services Canada",
    "minister of justice and attorney general of canada": "Justice Canada",
    "minister of crown-indigenous relations": "Crown-Indigenous Relations and Northern Affairs Canada",
    "president of the queen's privy council for canada and minister of emergency preparedness": "Public Safety Canada",
    "president of the queen\'s privy council and minister of emergency preparedness": "Public Safety Canada", # Shorter variant
    "minister of transport": "Transport Canada",
    "minister of international development and minister responsible for the pacific economic development agency of canada": "Global Affairs Canada",
    "minister of families, children and social development": "Employment and Social Development Canada",
    "minister of fisheries, oceans and the canadian coast guard": "Fisheries and Oceans Canada",
    "minister of fisheries, oceans and canadian coast guard": "Fisheries and Oceans Canada", # Variant without 'the'
    "minister of labour": "Employment and Social Development Canada",
    "minister of immigration, refugees and citizenship": "Immigration, Refugees and Citizenship Canada",
    "minister of public services and procurement": "Public Services and Procurement Canada",
    "minister for women and gender equality and youth": "Women and Gender Equality Canada",
    "minister of national revenue": "Canada Revenue Agency",
    "minister of mental health and addictions and associate minister of health": "Health Canada",
    "minister of agriculture and agri-food": "Agriculture and Agri-Food Canada",
    "minister of northern affairs, minister responsible for prairies economic development canada, and minister responsible for the canadian northern economic development agency": "Crown-Indigenous Relations and Northern Affairs Canada",
    "leader of the government in the house of commons": "Privy Council Office",
    "minister of veterans affairs and associate minister of national defence": "Veterans Affairs Canada",
    "minister of veteran\'s affairs": "Veterans Affairs Canada", # Shorter variant with apostrophe
    "minister of sport and minister responsible for the economic development agency of canada for the regions of quebec": "Canadian Heritage",
    "minister of official languages and minister responsible for the atlantic canada opportunities agency": "Canadian Heritage",
    "minister of seniors": "Employment and Social Development Canada",
    "minister responsible for the federal economic development agency for southern ontario": "Federal Economic Development Agency for Southern Ontario",
    "minister of tourism and associate minister of finance": "Innovation, Science and Economic Development Canada",
    "minister of rural economic development": "Innovation, Science and Economic Development Canada",

    # Adding common variants if not already effectively covered by longer titles or normalization
    "minister of finance": "Finance Canada",
    "minister of indigenous services": "Indigenous Services Canada",
    "ministre of foreign affairs": "Global Affairs Canada", # Typo, kept as is from original
    # Adding clearly malformed variants from logs as a temporary measure
    "president of the queen's privy council for canada and minister of emergency preparedness president of the treasury board": "Multiple Departments - Needs Review", # Concatenated
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario and minister responsible for the federal economic development agency for northern ontario": "Indigenous Services Canada", # Duplicated phrase
    "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario canada": "Indigenous Services Canada" # Extra suffix
}

def standardize_department_name(name_str):
    original_name_str = str(name_str).strip()
    
    # Normalize apostrophes and spaces, and convert to lowercase
    normalized_name = (original_name_str.lower()
                       .replace("’", "'")  # U+2019 RIGHT SINGLE QUOTATION MARK
                       .replace("‘", "'")  # U+2018 LEFT SINGLE QUOTATION MARK
                       .replace("`", "'")  # U+0060 GRAVE ACCENT (backtick)
                       .replace("´", "'")  # U+00B4 ACUTE ACCENT
                       .replace('\xa0', ' ')) # U+00A0 NO-BREAK SPACE to regular space

    if not normalized_name or normalized_name == 'nan':
         return None

    standardized = DEPARTMENT_MAP.get(normalized_name)
    if standardized:
        return standardized

    # Fallback substring search
    for key, value in DEPARTMENT_MAP.items():
        if key in normalized_name:
            # print(f"DEBUG: Fallback match on key '{key}' for '{original_name_str}'") # Optional debug for fallback
            return value
    
    print(f"Warning: Could not standardize department: '{original_name_str}' (Normalized: '{normalized_name}')")
    return original_name_str # Return original if no mapping found, as per existing logic 