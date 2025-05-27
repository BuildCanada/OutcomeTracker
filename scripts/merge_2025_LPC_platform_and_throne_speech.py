import os
import json
import pandas as pd
from google import genai
from google.genai import types
import time
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
PLATFORM_CSV_PATH = "../raw-data/2025-LPC-platform.csv"
SFT_TEXT_PATH = "../raw-data/2025-SFT-speech.txt"
OUTPUT_CSV_PATH = "consolidated_2025_LPC_promises_final.csv"
GEMINI_MODEL_NAME = "gemini-2.5-pro-preview-05-06" 

# --- Gemini API Setup ---
try:
    GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GOOGLE_API_KEY:
        raise ValueError("Gemini API key not found in environment variables. Please set 'GEMINI_API_KEY'.")
    
    # Create client with the new SDK
    client = genai.Client(api_key=GOOGLE_API_KEY)
    print(f"Successfully configured Gemini client with model: {GEMINI_MODEL_NAME}")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")
    exit()

# --- Helper Functions ---
def call_gemini(prompt_text, is_json_output=True, max_retries=5, delay_seconds=10):
    """Calls the Gemini API with retry logic and optional JSON parsing."""
    for attempt in range(max_retries):
        try:
            print(f"\n--- Calling Gemini (Attempt {attempt + 1}/{max_retries}) ---")
            # print(f"Prompt (first 500 chars):\n{prompt_text[:500]}...")
            
            # Use the new SDK API
            response = client.models.generate_content(
                model=GEMINI_MODEL_NAME,
                contents=prompt_text,
                config=types.GenerateContentConfig(
                    temperature=0.2,  # Slightly higher for better JSON generation
                    max_output_tokens=65536,
                    safety_settings=[
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                        types.SafetySetting(
                            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                            threshold=types.HarmBlockThreshold.BLOCK_NONE
                        ),
                    ]
                )
            )
            
            response_text = response.text
            # print(f"Raw Gemini Response Text (first 500 chars):\n{response_text[:500]}...")

            if is_json_output:
                cleaned_response_text = response_text.strip()
                if cleaned_response_text.startswith("```json"):
                    cleaned_response_text = cleaned_response_text[7:]
                if cleaned_response_text.endswith("```"):
                    cleaned_response_text = cleaned_response_text[:-3]
                cleaned_response_text = cleaned_response_text.strip()
                
                # print(f"Cleaned Gemini Response for JSON parsing (first 500 chars):\n{cleaned_response_text[:500]}...")
                parsed_json = json.loads(cleaned_response_text)
                # print("JSON parsing successful.")
                return parsed_json
            else:
                return response_text
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e} on attempt {attempt + 1}. Response was not valid JSON.")
            print(f"First 1000 chars of response: {response_text[:1000]}")
            print(f"Last 500 chars of response: {response_text[-500:]}")
            if attempt == max_retries - 1:
                print("Max retries reached for JSON decoding. Returning error.")
                return {"error": "JSONDecodeError", "raw_text": response_text, "message": str(e)}
            else:
                print(f"Retrying with a longer delay...")
                time.sleep(delay_seconds * 2)  # Longer delay for JSON errors
        except Exception as e:
            print(f"Error calling Gemini API: {e} on attempt {attempt + 1}")
            # More specific error handling for common issues
            if "API key not valid" in str(e):
                print("Invalid API Key. Please check your GEMINI_API_KEY environment variable.")
                return {"error": "Invalid API Key", "message": str(e)}
            if "rate limit" in str(e).lower() or "429" in str(e):
                wait_time = delay_seconds * (2 ** attempt) # Exponential backoff
                print(f"Rate limit likely hit. Waiting for {wait_time} seconds before retrying.")
                time.sleep(wait_time)
            elif attempt == max_retries - 1:
                print("Max retries reached for API call.")
                return {"error": f"API Error after max retries: {e}", "message": str(e)}
            else:
                time.sleep(delay_seconds) # Wait before retrying for other errors
    return {"error": "Max retries exceeded without success"}


def get_sft_extraction_prompt(sft_full_text):
    """Generates the prompt for extracting promises from the SFT."""
    return f"""
Analyze the following Speech from the Throne text and extract all political promises, commitments, and pledges made by "The Government".
For each promise you identify, please provide:
1. A unique `sft_promise_id` (e.g., "SFT_001", "SFT_002").
2. The `text` of the promise/commitment as accurately as possible, focusing on future actions.
3. A `confidence` score (0.0 to 1.0) indicating how certain you are this is a promise (only include if >= 0.85).
4. A brief `rationale` explaining why this constitutes a promise by "The Government".

Return your response as a valid JSON array of objects. Ensure the JSON is well-formed.

Guidelines for identifying promises:
- Look for commitments using phrases like "The Government will...", "It will..." (where 'It' clearly refers to the Government), "The Government is responding by [future action]...", "The Government is determined to...".
- Focus on specific, actionable future commitments.
- Exclude statements of past accomplishments, general values, descriptions of current situations unless tied to a future action, or what other entities (e.g., "Canadians", "Premiers") are doing.
- If a sentence describes multiple distinct government actions, try to break them into separate promises.

Speech from the Throne Text:
--- START OF SPEECH ---
{sft_full_text}
--- END OF SPEECH ---

JSON Output Example:
[
  {{
    "sft_promise_id": "SFT_001",
    "text": "The Government will introduce legislation to enhance security at Canada's borders.",
    "confidence": 1.0,
    "rationale": "Uses 'The Government will introduce legislation' indicating a clear future action by the government."
  }}
]
"""

def get_full_consolidation_prompt(platform_promises_list, sft_promises_list):
    """Generates the prompt for comparing all platform promises with all SFT promises in one pass."""
    platform_json = json.dumps(platform_promises_list, indent=2)
    sft_json = json.dumps(sft_promises_list, indent=2)
    
    return f"""
CRITICAL: You must respond with ONLY CSV format data. Do not include any explanatory text, code, or commentary before or after the CSV data.

You are an expert political analyst. Compare ALL political promises from a party platform (LPC Platform) with ALL promises extracted from a Speech from the Throne (SFT), then create a comprehensive consolidated list.

PLATFORM PROMISES (JSON array, {len(platform_promises_list)} promises):
{platform_json}

SPEECH FROM THE THRONE PROMISES (JSON array, {len(sft_promises_list)} promises):
{sft_json}

Task:
1. For each platform promise, determine if it has a counterpart in the SFT promises
2. For each SFT promise, determine if it's already covered by platform promises or is SFT-only  
3. Create a consolidated CSV with ALL commitments

CSV Columns (in this exact order):
1. commitment_id - Use original platform ID (e.g., "LPC-001"). For SFT-only promises, create IDs like "SFT_ONLY_001"
2. canonical_commitment_text - Consolidated text (if matched: synthesize; if platform-only: use platform text; if SFT-only: use SFT text)
3. appears_in - "Both", "Platform Only", or "SFT Only"
4. reporting_lead_title - From platform data, or "N/A" for SFT-only
5. all_other_ministers_involved - From platform data, or "N/A" for SFT-only
6. notes_and_differences - Brief explanation of matching/differences

Matching Guidelines:
- Look for similar policy intent, not exact wording
- Consider if commitments address the same policy area or goal
- Focus on core actionable components

RESPOND WITH ONLY CSV DATA (header row + data rows). Properly escape commas and quotes in text fields. NO OTHER TEXT."""

# --- Main Script Logic ---
def main():
    # 1. Load Platform Data
    try:
        platform_df = pd.read_csv(PLATFORM_CSV_PATH)
        # Ensure all columns are treated as strings to avoid issues with NaN becoming float
        for col in ['Reporting Lead', 'Reporting Lead Name', 'All ministers']:
            if col in platform_df.columns:
                platform_df[col] = platform_df[col].astype(str).fillna('') 
        platform_promises_list = platform_df.to_dict('records')
        print(f"Loaded {len(platform_promises_list)} promises from {PLATFORM_CSV_PATH}")
    except FileNotFoundError:
        print(f"Error: Platform CSV file not found at {PLATFORM_CSV_PATH}")
        return
    except Exception as e:
        print(f"Error loading platform CSV: {e}")
        return

    # 2. Load SFT Text
    try:
        with open(SFT_TEXT_PATH, 'r', encoding='utf-8') as f:
            sft_full_text = f.read()
        print(f"Loaded Speech from the Throne text from {SFT_TEXT_PATH}")
    except FileNotFoundError:
        print(f"Error: SFT text file not found at {SFT_TEXT_PATH}. Please create this file first using Part 2 of the assistant's response.")
        return
    except Exception as e:
        print(f"Error loading SFT text file: {e}")
        return

    # 3. Extract Promises from SFT using Gemini
    print("Extracting promises from Speech from the Throne...")
    sft_extraction_prompt = get_sft_extraction_prompt(sft_full_text)
    sft_extracted_data = call_gemini(sft_extraction_prompt, is_json_output=True)

    sft_promises_from_llm = []
    if isinstance(sft_extracted_data, list):
        sft_promises_from_llm = sft_extracted_data
        print(f"Successfully extracted {len(sft_promises_from_llm)} promises from SFT via LLM.")
    elif isinstance(sft_extracted_data, dict) and 'error' in sft_extracted_data:
        print(f"Failed to extract SFT promises: {sft_extracted_data['error']} - {sft_extracted_data.get('message')}")
        if 'raw_text' in sft_extracted_data:
             print(f"Raw text from SFT extraction attempt: {sft_extracted_data['raw_text'][:1000]}")
    else:
        print(f"Unexpected data type from SFT extraction: {type(sft_extracted_data)}. Content: {str(sft_extracted_data)[:500]}")



    # 4. Consolidate All Promises in Single API Call
    print(f"\n--- Starting Full Consolidation: {len(platform_promises_list)} Platform Promises + {len(sft_promises_from_llm)} SFT Promises ---")
    
    consolidation_prompt = get_full_consolidation_prompt(platform_promises_list, sft_promises_from_llm)
    
    print("Calling Gemini for full consolidation...")
    consolidated_data = call_gemini(consolidation_prompt, is_json_output=False)

    if isinstance(consolidated_data, str) and 'commitment_id' in consolidated_data[:500]:
        # Parse CSV data
        import csv
        import io
        
        try:
            # Clean up any markdown formatting that might be present
            csv_text = consolidated_data.strip()
            if csv_text.startswith("```csv"):
                csv_text = csv_text[6:]
            if csv_text.startswith("```"):
                csv_text = csv_text[3:]
            if csv_text.endswith("```"):
                csv_text = csv_text[:-3]
            csv_text = csv_text.strip()
            
            csv_reader = csv.DictReader(io.StringIO(csv_text))
            consolidated_promises = list(csv_reader)
            print(f"Successfully consolidated {len(consolidated_promises)} total commitments from CSV")
        except Exception as csv_error:
            print(f"Error parsing CSV: {csv_error}")
            print("First 1000 chars of CSV data:")
            print(consolidated_data[:1000])
            print("Saving raw response for manual inspection...")
            with open("raw_gemini_csv_response.txt", 'w', encoding='utf-8') as f:
                f.write(consolidated_data)
            # Fall back to manual consolidation
            consolidated_promises = []
    elif isinstance(consolidated_data, dict) and 'error' in consolidated_data:
        print(f"Error during full consolidation: {consolidated_data['error']} - {consolidated_data.get('message')}")
        # Fallback: create basic consolidation without comparison
        print("Creating fallback consolidation without comparison...")
        consolidated_promises = []
        
        # Add all platform promises as "Platform Only"
        for platform_promise in platform_promises_list:
            consolidated_promises.append({
                "commitment_id": platform_promise.get('ID', 'N/A'),
                "canonical_commitment_text": platform_promise.get('Commitment', ''),
                "appears_in": "Platform Only",
                "reporting_lead_title": platform_promise.get('Reporting Lead', ''),
                "all_other_ministers_involved": platform_promise.get('All ministers', ''),
                "notes_and_differences": "Fallback mode: No SFT comparison performed due to API error"
            })
        
        # Add all SFT promises as "SFT Only"
        for i, sft_promise in enumerate(sft_promises_from_llm):
            consolidated_promises.append({
                "commitment_id": f"SFT_ONLY_{sft_promise.get('sft_promise_id', f'SFT_{i+1:03d}')}",
                "canonical_commitment_text": sft_promise.get("text", "N/A"),
                "appears_in": "SFT Only",
                "reporting_lead_title": "N/A (SFT Specific)",
                "all_other_ministers_involved": "N/A (SFT Specific)",
                "notes_and_differences": f"Fallback mode: {sft_promise.get('rationale', 'N/A')}"
            })
    else:
        print(f"Unexpected response format from consolidation: {type(consolidated_data)}")
        print("Creating fallback consolidation...")
        # Same fallback as above
        consolidated_promises = []
        for platform_promise in platform_promises_list:
            consolidated_promises.append({
                "commitment_id": platform_promise.get('ID', 'N/A'),
                "canonical_commitment_text": platform_promise.get('Commitment', ''),
                "appears_in": "Platform Only",
                "reporting_lead_title": platform_promise.get('Reporting Lead', ''),
                "all_other_ministers_involved": platform_promise.get('All ministers', ''),
                "notes_and_differences": "Fallback mode: Unexpected response format"
            })
        for i, sft_promise in enumerate(sft_promises_from_llm):
            consolidated_promises.append({
                "commitment_id": f"SFT_ONLY_{sft_promise.get('sft_promise_id', f'SFT_{i+1:03d}')}",
                "canonical_commitment_text": sft_promise.get("text", "N/A"),
                "appears_in": "SFT Only",
                "reporting_lead_title": "N/A (SFT Specific)",
                "all_other_ministers_involved": "N/A (SFT Specific)",
                "notes_and_differences": f"Fallback mode: {sft_promise.get('rationale', 'N/A')}"
            })

    # 6. Save Consolidated Data
    try:
        # Save as CSV
        if consolidated_promises and len(consolidated_promises) > 0:
            import csv
            with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8', newline='') as f:
                if isinstance(consolidated_promises[0], dict):
                    fieldnames = consolidated_promises[0].keys()
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(consolidated_promises)
                else:
                    # If it's raw CSV text, just write it
                    f.write(consolidated_data)
            print(f"\nConsolidated promises saved to {OUTPUT_CSV_PATH}")
            print(f"Total consolidated entries: {len(consolidated_promises)}")
        else:
            # Fallback: save raw response as CSV
            with open(OUTPUT_CSV_PATH, 'w', encoding='utf-8') as f:
                f.write(consolidated_data)
            print(f"\nRaw consolidated data saved to {OUTPUT_CSV_PATH}")
    except Exception as e:
        print(f"Error saving consolidated CSV: {e}")

if __name__ == "__main__":
    main()