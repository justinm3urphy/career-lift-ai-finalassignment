import firebase_admin
from firebase_admin import credentials, storage
import pdfplumber # New heavy-duty library
import io
import json
from tqdm import tqdm

# 1. SETUP
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'resume-booster-cbd24.firebasestorage.app'
})

def generate_industry_twin(folder_name):
    bucket = storage.bucket()
    prefix = f"{folder_name}/"
    
    print(f"🚀 Scanning Firebase folder: {prefix}")
    blobs = list(bucket.list_blobs(prefix=prefix))
    
    # Filter for PDFs
    pdf_blobs = [b for b in blobs if b.name.lower().endswith('.pdf') and b.size > 0]
    
    if not pdf_blobs:
        print(f"❌ ERROR: No PDFs found in {prefix}.")
        return

    all_texts = []
    print(f"📄 Found {len(pdf_blobs)} files. Extracting with Heavy-Duty Engine...")

    for blob in tqdm(pdf_blobs):
        try:
            content = blob.download_as_bytes()
            # Open PDF with pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                full_text = ""
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        full_text += page_text + " "
                
                if full_text.strip():
                    all_texts.append(full_text.strip())
                    # Debug: print a tiny snippet of the first file found
                    if len(all_texts) == 1:
                        print(f"\n🔍 Sample text from first file: {full_text[:100]}...")
        except Exception as e:
            print(f"Skipping {blob.name}: {e}")

    # 2. CREATE DATA STRUCTURE
    if len(all_texts) > 0:
        twin_data = {
            "industry": folder_name,
            "count": len(all_texts),
            "knowledge_base": "\n\n---NEXT---\n\n".join(all_texts)
        }

        filename = f"{folder_name}_twin.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(twin_data, f, ensure_ascii=False, indent=4)
        print(f"\n✅ SUCCESS! Created {filename} with {len(all_texts)} resumes.")
    else:
        print("\n❌ FAILED: Still couldn't extract text. Your PDFs might be images (scans).")

if __name__ == "__main__":
    generate_industry_twin("ElectricalEngineer")