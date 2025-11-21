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

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

def clean_filename(text):
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
        signature += options[0].get('text', '') # Add first option to uniqueness check
    
    # Create MD5 hash
    hash_object = hashlib.md5(signature.encode('utf-8'))
    # Return first 8 characters of hex digest (enough for uniqueness in this context)
    return hash_object.hexdigest()[:8]

def extract_from_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Skipping {filepath}: {e}")
        return []

    soup = BeautifulSoup(content, 'html.parser')
    
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
            json_match = re.search(r'questions\s*=\s*(\[\{.*\}\]);', srcdoc, re.DOTALL)
            
            if json_match:
                json_str = json_match.group(1)
                try:
                    questions_data = json.loads(json_str)
                    
                    # --- SERIALIZATION STEP ---
                    for q in questions_data:
                        # Inject Unique ID
                        q['uid'] = generate_question_id(q.get('text', ''), q.get('options', []))
                    
                    safe_title = clean_filename(title)
                    out_filename = f"{safe_title}.json"
                    
                    counter = 1
                    while os.path.exists(os.path.join(OUTPUT_DIR, out_filename)):
                         out_filename = f"{safe_title}_{counter}.json"
                         counter += 1

                    final_data = {
                        "meta": {
                            "id": container_id,
                            "title": title,
                            "total_questions": len(questions_data),
                            "source": filepath
                        },
                        "questions": questions_data
                    }
                    
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
    print("Starting serialization process...")

    for root, dirs, files in os.walk(ROOT_DIR):
        if OUTPUT_DIR in root: continue

        for file in files:
            if file.endswith(".html") and file not in EXCLUDE_FILES:
                full_path = os.path.join(root, file)
                tests = extract_from_file(full_path)
                if tests:
                    print(f"Processed: {full_path}")
                    all_quizzes.extend(tests)

    with open(MANIFEST_FILE, "w", encoding='utf-8') as f:
        json.dump(all_quizzes, f, indent=2)

    print(f"\nSuccessfully serialized {len(all_quizzes)} tests into '{OUTPUT_DIR}/'")

if __name__ == "__main__":
    main()