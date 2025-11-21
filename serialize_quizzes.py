import os
import json
import re
import hashlib
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
ROOT_DIR = "."  
OUTPUT_DIR = "quiz_data"
MANIFEST_FILE = "manifest.json"
EXCLUDE_FILES = ["qbanks.html", "index.html"]

# Create output directory if it doesn't exist
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def clean_filename(text):
    """Removes special characters to make safe filenames."""
    safe_text = re.sub(r'[^\w\s-]', '', text)
    return safe_text.strip().replace(" ", "_")

def generate_question_id(text, options):
    """
    Generates a deterministic 8-char unique ID based on the question content.
    This ensures the ID stays the same even if you re-run the script.
    """
    # Create a string signature of the question
    signature = text.strip()
    if options and len(options) > 0:
        signature += options[0].get('text', '') # Add first option to ensure uniqueness
    
    # Create MD5 hash
    hash_object = hashlib.md5(signature.encode('utf-8'))
    # Return first 8 characters (e.g., "a1b2c3d4")
    return hash_object.hexdigest()[:8]

def extract_and_serialize(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    
    # Map IDs to Titles
    titles_map = {}
    buttons = soup.select('.nav-buttons button')
    for btn in buttons:
        onclick = btn.get('onclick', '')
        match = re.search(r"showTest\('([^']+)'\)", onclick)
        if match:
            test_id = match.group(1)
            titles_map[test_id] = btn.text.strip()

    extracted_entries = []
    containers = soup.select('.iframe-container')
    
    if not containers:
        return []

    for container in containers:
        container_id = container.get('id')
        title = titles_map.get(container_id)
        if not title:
            h2 = container.find('h2')
            title = h2.text.strip() if h2 else f"Test {container_id}"

        iframe = container.find('iframe')
        if iframe and iframe.get('srcdoc'):
            srcdoc = iframe['srcdoc']
            
            # Extract JSON from JS
            json_match = re.search(r'questions\s*=\s*(\[\{.*\}\]);', srcdoc, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                try:
                    questions_data = json.loads(json_str)
                    
                    # --- IMPORTANT: GENERATE IDs HERE ---
                    for q in questions_data:
                        q['uid'] = generate_question_id(q.get('text', ''), q.get('options', []))
                    # ------------------------------------

                    safe_title = clean_filename(title)
                    out_filename = f"{safe_title}.json"
                    
                    # Handle duplicates
                    counter = 1
                    while os.path.exists(os.path.join(OUTPUT_DIR, out_filename)):
                         # Check if it's actually the same file we are rewriting (optional optimization)
                         # For safety, we just increment to avoid overwriting distinct tests with same name
                         out_filename = f"{safe_title}_{counter}.json"
                         counter += 1

                    final_data = {
                        "id": container_id,
                        "title": title,
                        "source_file": filepath,
                        "questions": questions_data
                    }
                    
                    # Save the JSON file
                    with open(os.path.join(OUTPUT_DIR, out_filename), 'w', encoding='utf-8') as outfile:
                        json.dump(final_data, outfile, indent=2)
                    
                    extracted_entries.append({
                        "title": title,
                        "file": out_filename,
                        "questions": len(questions_data)
                    })
                    
                except json.JSONDecodeError:
                    print(f"Error parsing JSON in {title}")
    
    return extracted_entries

def main():
    all_quizzes = []
    print("Starting serialization...")

    # Walk through directories
    for root, dirs, files in os.walk(ROOT_DIR):
        if OUTPUT_DIR in root: continue # Skip the output folder

        for file in files:
            if file.endswith(".html") and file not in EXCLUDE_FILES:
                full_path = os.path.join(root, file)
                tests = extract_and_serialize(full_path)
                if tests:
                    print(f"Serialized: {file} -> {len(tests)} tests")
                    all_quizzes.extend(tests)

    # Save Manifest
    with open(MANIFEST_FILE, "w", encoding='utf-8') as f:
        json.dump(all_quizzes, f, indent=2)

    print("\n" + "="*40)
    print(f"DONE! Processed {len(all_quizzes)} tests.")
    print(f"IDs generated in folder: {OUTPUT_DIR}/")
    print("="*40)

if __name__ == "__main__":
    main()