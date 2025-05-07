# Entity Mappings

This document outlines key entity mappings used in the Build Canada Promise Tracker project.

## Department Mappings

For details on how raw department/ministerial titles are mapped to standardized department names, please refer to `/docs/data-model/department_mapping.md`. The Python dictionary `DEPARTMENT_MAP` and the `standardize_department_name()` function are maintained in `PromiseTracker/data_processing/common_utils.py`.

## Promise Category Mappings

Promises are categorized into thematic areas. This section will document the list of categories and any specific mapping logic used (e.g., keywords or rules used by the LLM for assignment if not purely based on text analysis).

*(This section is a placeholder and will be populated as the categorization strategy is finalized.)*

**Current Categories (Example/To be defined):**

*   Economy
*   Healthcare
*   Environment
*   Social Development
*   Indigenous Relations
*   Governance
*   Infrastructure
*   Foreign Affairs
*   National Defence
*   Justice & Public Safety
