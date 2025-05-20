import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai
import os
import argparse
import json
from dotenv import load_dotenv
import time
import logging # Added
import re # Ensure re is imported

# Load environment variables
load_dotenv()

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__) # Use __name__ for logger
# --- End Logger Setup ---

# --- Configuration ---
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
TENETS_PATH = os.path.join(PROMPTS_DIR, "build_canada_tenets.txt")
DETAILED_INSTRUCTIONS_PATH = os.path.join(PROMPTS_DIR, "detailed_rating_instructions.md")
ECONOMIC_CONTEXTS_BASE_PATH = os.path.join(PROMPTS_DIR, "economic_contexts")

# Source type mapping to economic context file and Firestore query value
SOURCE_TYPE_CONFIG = {
    "2021": {
        "economic_context_file": "2021_mandate.txt",
        "firestore_query_value": "2021 LPC Mandate Letters",
        "context_name_for_prompt": "2021 Federal Election"
    },
    "2025": {
        "economic_context_file": "2025_platform.txt", # Ensure this file exists or is created
        "firestore_query_value": "2025 LPC Platform",
        "context_name_for_prompt": "2025 Federal Election"
    }
}

#LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-pro-preview-05-06") 
LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-2.5-flash-preview-04-17") 

GENERATION_CONFIG = {
    "temperature": 0.5, 
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 65536, 
    "response_mime_type": "application/json",
}
SYSTEM_INSTRUCTION = "You are the Build-Canada Mandate Scorer. You are an expert in Canadian policy and economics."

# --- Firestore Initialization (mimicking enrich_tag_new_promise.py) ---
def initialize_firestore():
    db_client = None
    try:
        if not firebase_admin._apps:
            firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Attempting Firestore connection (Project: {project_id}) using default credentials.")
        db_client = firestore.client()
        logger.info(f"Successfully connected to Firestore using default credentials.")
        return db_client
    except Exception as e_default:
        logger.warning(f"Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv("FIREBASE_ADMIN_SDK_PATH") # Ensure this ENV var is set
        if not cred_path:
            logger.critical("FIREBASE_ADMIN_SDK_PATH environment variable not set and default creds failed.")
            raise ValueError("FIREBASE_ADMIN_SDK_PATH environment variable not set and default creds failed.")
        if not os.path.exists(cred_path):
            logger.critical(f"Firebase Admin SDK file not found at {cred_path}")
            raise FileNotFoundError(f"Firebase Admin SDK file not found at {cred_path}")
        try:
            logger.info(f"Attempting Firebase init with service account key from: {cred_path}")
            cred = credentials.Certificate(cred_path)
            app_name = 'rank_promise_priority_app' # Unique app name for this script
            if firebase_admin.DEFAULT_APP_NAME not in firebase_admin._apps:
                 firebase_admin.initialize_app(cred) 
            elif not any(app.name == app_name for app in firebase_admin._apps.values()):
                 firebase_admin.initialize_app(cred, name=app_name)
            current_app = firebase_admin.get_app(name=app_name if any(app.name == app_name for app in firebase_admin._apps.values()) else firebase_admin.DEFAULT_APP_NAME)
            project_id_sa = current_app.project_id or os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
            logger.info(f"Connected to Firestore (Project: {project_id_sa}) via service account using app: {current_app.name}.")
            db_client = firestore.client(app=current_app)
            return db_client
        except Exception as e_sa:
            logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
            raise

# --- Generative AI Initialization (mimicking enrich_tag_new_promise.py) ---
def initialize_genai():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel(
            model_name=LLM_MODEL_NAME,
            generation_config=GENERATION_CONFIG, 
            system_instruction=SYSTEM_INSTRUCTION
        )
        logger.info(f"Initialized Gemini model: {LLM_MODEL_NAME} with system instructions.")
        return model
    except Exception as e:
        logger.critical(f"Failed to initialize Gemini model '{LLM_MODEL_NAME}': {e}", exc_info=True)
        raise

# --- Helper Functions ---
def load_file_content(path, description):
    if not os.path.exists(path):
        logger.error(f"{description} file not found at: {path}")
        raise FileNotFoundError(f"{description} file not found at: {path}")
    with open(path, 'r') as f:
        return f.read()

def get_llm_evaluation(model, promise_text, tenets_text, economic_context_text, detailed_instructions_text, election_context_name):
    # Construct the full prompt by combining all parts
    # The detailed_instructions.md already contains placeholders for where it expects other info, 
    # but here we make it explicit by structuring the combined input to the LLM.
    
    # The user prompt will be a combination of the static instructions and the dynamic parts
    # The SYSTEM_INSTRUCTION is handled by the model initialization.
    user_prompt = f"You will be provided with a government commitment, Build Canada Core Tenets, the Election Economic Context, and detailed scoring instructions.\n\n"
    user_prompt += f"== Build Canada Core Tenets ==\n{tenets_text}\n\n"
    user_prompt += f"== Election Economic Context: {election_context_name} ==\n{economic_context_text}\n\n"
    user_prompt += f"== Government Commitment to Evaluate ==\n```text\n{promise_text}\n```\n\n"
    user_prompt += f"== Detailed Scoring Instructions (Task, Scoring Criteria, Method, Guidance, Examples) ==\n{detailed_instructions_text}"

    max_retries = 3
    delay_seconds = 5 
    for attempt in range(max_retries):
        try:
            logger.debug(f"Attempt {attempt + 1} to get LLM evaluation for promise: {promise_text[:70]}...")
            # logger.debug(f"Full prompt for LLM:\n{user_prompt}") # Uncomment for debugging full prompt
            response = model.generate_content(user_prompt) 
            
            # response_mime_type="application/json" should ensure response.text is parseable JSON.
            # However, LLMs can sometimes still wrap it or add conversational fluff.
            raw_response_text = response.text
            logger.debug(f"Raw LLM response text: {raw_response_text}")
            
            # Try to find JSON within ```json ... ``` if present, otherwise assume raw_response_text is the JSON string.
            match = re.search(r"```json\n(.*\n)```", raw_response_text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()
            else:
                # If no markdown block, assume the text is the JSON itself or needs cleaning.
                # A common pattern is for the LLM to return *only* the JSON string when response_mime_type is set.
                # However, if it's not perfectly clean, json.loads will fail.
                json_text = raw_response_text.strip() # Basic strip
                # Further cleaning might be needed if LLM adds leading/trailing text outside markdown
                if not json_text.startswith("{") or not json_text.endswith("}"):
                    # Attempt to extract the first valid JSON object from the string
                    first_brace = json_text.find('{')
                    last_brace = json_text.rfind('}')
                    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                        json_text = json_text[first_brace:last_brace+1]
                    else:
                        logger.warning("Could not reliably extract JSON object from raw response.")
                        raise ValueError("Response does not appear to be a clean JSON object or markdown block.")

            logger.debug(f"Extracted JSON text for parsing: {json_text}")
            parsed_json = json.loads(json_text)
            return parsed_json

        except (json.JSONDecodeError, AttributeError, ValueError, Exception) as e: 
            logger.error(f"Error processing LLM response (attempt {attempt + 1}/{max_retries}): {e}. Promise: {promise_text[:70]}")
            logger.error(f"Raw response on error: {getattr(response, 'text', 'N/A')}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {delay_seconds} seconds...")
                time.sleep(delay_seconds)
                delay_seconds *= 2 
            else:
                logger.error("Max retries reached. Skipping this promise evaluation.")
                return None
    return None

# --- Main Logic ---
def rank_promises(db, model, source_arg, limit, force_reprocess):
    # Determine the base collection path.
    # FIXME: This is hardcoded for LPC in Canada. Make dynamic if other parties/regions needed.
    # Example: derive party from context_info["firestore_query_value"] or add to SOURCE_TYPE_CONFIG
    default_region = "Canada"
    default_party_for_config = "LPC" # Assuming current configs are for LPC
    base_collection_path = f"promises/{default_region}/{default_party_for_config}"
    
    try:
        target_collection_ref = db.collection(base_collection_path)
        logger.info(f"Targeting Firestore collection: {base_collection_path}")
    except Exception as e_col:
        logger.critical(f"Failed to get reference to collection '{base_collection_path}': {e_col}")
        return

    # Load static prompt components once
    try:
        tenets_text = load_file_content(TENETS_PATH, "Build Canada Tenets")
        detailed_instructions_text = load_file_content(DETAILED_INSTRUCTIONS_PATH, "Detailed Rating Instructions")
    except FileNotFoundError:
        logger.critical("Core prompt files (tenets or instructions) not found. Aborting.")
        return

    contexts_to_process = []
    if source_arg == "all":
        for key in SOURCE_TYPE_CONFIG.keys():
            config = SOURCE_TYPE_CONFIG[key]
            contexts_to_process.append({
                "firestore_query_value": config["firestore_query_value"],
                "economic_context_file": config["economic_context_file"],
                "context_name_for_prompt": config["context_name_for_prompt"]
            })
    elif source_arg in SOURCE_TYPE_CONFIG:
        config = SOURCE_TYPE_CONFIG[source_arg]
        contexts_to_process.append({
            "firestore_query_value": config["firestore_query_value"],
            "economic_context_file": config["economic_context_file"],
            "context_name_for_prompt": config["context_name_for_prompt"]
        })
    else:
        logger.error(f"Invalid source_type argument: {source_arg}. Choices are: {list(SOURCE_TYPE_CONFIG.keys()) + ['all']}")
        return

    processed_total_overall = 0 # Renamed for clarity
    updated_total_overall = 0   # Renamed for clarity
    firestore_page_size = 100 # Number of documents to fetch from Firestore at a time for pagination

    for context_info in contexts_to_process:
        logger.info(f"--- Processing for context: {context_info['context_name_for_prompt']} (Source Type: {context_info['firestore_query_value']}) ---")
        logger.info(f"Force reprocess for this context: {force_reprocess}")
        try:
            economic_context_text = load_file_content(
                os.path.join(ECONOMIC_CONTEXTS_BASE_PATH, context_info["economic_context_file"]),
                f"Economic Context for {context_info['context_name_for_prompt']}"
            )
        except FileNotFoundError:
            logger.error(f"Economic context file {context_info['economic_context_file']} not found. Skipping this context.")
            continue

        base_query = target_collection_ref.where(
            filter=firestore.FieldFilter('source_type', '==', context_info["firestore_query_value"])
        )

        if not force_reprocess:
            # Query for promises where bc_promise_rank is explicitly null (None in Python)
            base_query = base_query.where(filter=firestore.FieldFilter('bc_promise_rank', '==', None))
            logger.info("Querying for promises where bc_promise_rank is null (force_reprocess is False).")
        else:
            logger.info("Querying for all promises matching source_type (force_reprocess is True).")

        # Debug: Count documents matching the full query criteria for this context
        try:
            count_query = base_query.select([]) # Only fetch IDs for counting
            all_matching_docs_for_context = list(count_query.stream()) # Materialize for count
            total_docs_to_consider_for_context = len(all_matching_docs_for_context)
            logger.info(f"Found {total_docs_to_consider_for_context} documents matching full criteria for context '{context_info['context_name_for_prompt']}'.")
            if total_docs_to_consider_for_context == 0:
                logger.info(f"No documents to process for this context based on criteria. Skipping.")
                continue # Skip to next context if no docs found for this one
        except Exception as e_count:
            logger.error(f"Error counting documents for context: {e_count}. Proceeding without exact pre-count.")
            total_docs_to_consider_for_context = -1 # Indicate count failed or wasn't fully performed

        last_doc_snapshot = None
        processed_this_context = 0
        updated_this_context = 0
        # Loop for pagination within this context
        while True:
            if limit is not None and processed_total_overall >= limit:
                logger.info(f"Overall processing limit ({limit}) reached. Stopping further processing for this context.")
                break # Break from pagination loop for this context

            current_page_query = base_query
            if last_doc_snapshot:
                current_page_query = current_page_query.start_after(last_doc_snapshot)
            
            # Determine how many to fetch in this page vs how many are left for the overall limit
            num_to_fetch_this_page = firestore_page_size
            if limit is not None:
                remaining_for_overall_limit = limit - processed_total_overall
                if remaining_for_overall_limit <= 0:
                    break # Overall limit reached
                num_to_fetch_this_page = min(firestore_page_size, remaining_for_overall_limit)
            
            if num_to_fetch_this_page <= 0: # Should be caught by outer check, but defensive
                break

            logger.info(f"Fetching next page of up to {num_to_fetch_this_page} documents for context '{context_info['context_name_for_prompt']}'...")
            docs_this_page = list(current_page_query.limit(num_to_fetch_this_page).stream())

            if not docs_this_page:
                logger.info("No more documents found in this context for this page. Moving to next context or finishing.")
                break # No more documents in this context
            
            batch = db.batch()
            operations_in_batch = 0
            batch_commit_size = 5 # LLM calls are slow, commit in smaller Firestore batches

            for promise_doc in docs_this_page:
                if limit is not None and processed_total_overall >= limit:
                    logger.info("Overall processing limit ({}) reached mid-page.".format(limit))
                    break # Break from processing documents in this page

                processed_total_overall += 1
                processed_this_context += 1
                promise_data = promise_doc.to_dict()
                promise_text = promise_data.get('text')

                if not promise_text:
                    logger.warning(f"Skipping promise {promise_doc.id} due to missing text.")
                    continue

                logger.info(f"Processing promise ID: {promise_doc.id} ({processed_total_overall} total, {processed_this_context} for this context)...")
                evaluation = get_llm_evaluation(
                    model, promise_text, tenets_text, economic_context_text, 
                    detailed_instructions_text, context_info['context_name_for_prompt']
                )
                if evaluation and all(k in evaluation for k in ['bc_promise_rank', 'bc_promise_direction', 'bc_promise_rank_rationale']):
                    rank_val = evaluation['bc_promise_rank']
                    direction_val = evaluation['bc_promise_direction']
                    if rank_val not in ['strong', 'medium', 'weak'] or direction_val not in ['positive', 'negative', 'neutral']:
                        logger.warning(f"Invalid rank/direction from LLM for {promise_doc.id}: {rank_val}, {direction_val}. Skipping update.")
                        continue
                    update_data = {
                        'bc_promise_rank': rank_val,
                        'bc_promise_direction': direction_val,
                        'bc_promise_rank_rationale': evaluation['bc_promise_rank_rationale'],
                        'last_updated_at': firestore.SERVER_TIMESTAMP
                    }
                    batch.update(target_collection_ref.document(promise_doc.id), update_data)
                    operations_in_batch +=1
                    updated_total_overall +=1
                    updated_this_context +=1
                    logger.info(f"  -> Evaluated: Rank '{evaluation['bc_promise_rank']}', Direction '{evaluation['bc_promise_direction']}'")
                else:
                    logger.warning(f"  -> Failed to evaluate or parse response for promise {promise_doc.id}.")

                if operations_in_batch >= batch_commit_size:
                    logger.info(f"Committing Firestore batch of {operations_in_batch} updates...")
                    batch.commit()
                    logger.info(f"Firestore batch committed.")
                    batch = db.batch() # Reset batch
                    operations_in_batch = 0
            # After processing all docs in the current page
            if operations_in_batch > 0: # Commit any remaining operations in the batch for this page
                logger.info(f"Committing final Firestore batch of {operations_in_batch} updates for this page...")
                batch.commit()
                logger.info(f"Final Firestore batch for page committed.")
            
            last_doc_snapshot = docs_this_page[-1] if docs_this_page else None
            if len(docs_this_page) < num_to_fetch_this_page : # If we fetched less than requested, it's the last page for this context
                logger.info("Reached end of documents for this context (fetched less than page size).")
                break # End of documents for this context
            if not last_doc_snapshot: # Defensive break if something went wrong
                break

        logger.info(f"--- Context {context_info['context_name_for_prompt']} processing complete. Updated {updated_this_context} of {processed_this_context} considered in this context. ---")
        if limit is not None and processed_total_overall >= limit:
            logger.info("Overall processing limit reached after processing a context. Halting.")
            break # Break from outer loop over contexts

    logger.info(f"==== Total Ranking complete. {updated_total_overall} promises updated out of {processed_total_overall} processed across all contexts. ====")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rank promises based on Build Canada tenets using an LLM.")
    parser.add_argument(
        "source_type", 
        choices=list(SOURCE_TYPE_CONFIG.keys()) + ["all"], 
        help="The source type of promises to rank (e.g., '2021', '2025', or 'all' to process all configured types)"
    )
    parser.add_argument("--limit", type=int, help="Limit the total number of promises to process across all specified source types.")
    parser.add_argument("--force-reprocess", action="store_true", help="Force reprocessing of all promises, even if they already have a rank.")

    args = parser.parse_args()

    db_client = None
    llm_model = None
    try:
        logger.info(f"Starting promise ranking script with source_type: {args.source_type}, limit: {args.limit}, force_reprocess: {args.force_reprocess}")
        db_client = initialize_firestore()
        llm_model = initialize_genai()
        
        if db_client and llm_model:
            rank_promises(db_client, llm_model, args.source_type, args.limit, args.force_reprocess)
        else:
            logger.critical("Failed to initialize Firestore client or Generative AI model. Aborting script.")
            
    except FileNotFoundError as fnf_error:
        logger.critical(f"Essential file not found: {fnf_error}. Please ensure all prompt and context files exist.")
    except ValueError as val_error:
        logger.critical(f"Configuration or value error: {val_error}")
    except Exception as e:
        logger.critical(f"An unexpected critical error occurred in main execution: {e}", exc_info=True)
    finally:
        logger.info("Promise ranking script finished.") 