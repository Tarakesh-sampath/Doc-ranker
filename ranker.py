import os
import re
import json
from collections import defaultdict

import numpy as np
from tqdm import tqdm
from pypdf import PdfReader
import nltk
from nltk.tokenize import sent_tokenize
import shutil

import faiss
from sentence_transformers import SentenceTransformer

# ----------------- Config -----------------
LIBRARY_DIR = "library_pdfs"
QUERY_DIR = "query_pdfs"
INDEX_DIR = "index_store"
OUTPUT_DIR = "ranked_output"
MODEL_NAME = "BAAI/bge-base-en-v1.5"

CHUNK_WORDS = 500
CHUNK_OVERLAP = 80
TOP_K = 50

os.makedirs(INDEX_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LIBRARY_DIR, exist_ok=True)
os.makedirs(QUERY_DIR, exist_ok=True)

# --------------- Utilities ----------------
def clean_text(t):
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def pdf_to_text(path):
    try:
        reader = PdfReader(path, strict=False)
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                pass
        return clean_text(" ".join(pages))
    except Exception as e:
        print(f"[WARN] Skipping broken PDF: {os.path.basename(path)} ({e})")
        return ""

def chunk_text(text, chunk_words=500, overlap=80):
    sents = sent_tokenize(text)
    chunks = []
    buf = []
    buf_words = 0

    for s in sents:
        w = len(s.split())
        if buf_words + w <= chunk_words:
            buf.append(s)
            buf_words += w
        else:
            chunks.append(" ".join(buf))
            # overlap
            tail = " ".join(buf).split()[-overlap:]
            buf = [" ".join(tail), s]
            buf_words = len(buf[0].split()) + w

    if buf:
        chunks.append(" ".join(buf))

    return [c for c in chunks if len(c.split()) > 40]

# --------------- Index Build --------------
def build_index(model):
    all_chunks = []
    meta = []

    pdfs = [p for p in os.listdir(LIBRARY_DIR) if p.lower().endswith(".pdf")]
    for pdf in tqdm(pdfs, desc="Reading library PDFs"):
        path = os.path.join(LIBRARY_DIR, pdf)
        text = pdf_to_text(path)
        if not text.strip():
            continue
        chunks = chunk_text(text, CHUNK_WORDS, CHUNK_OVERLAP)
        for c in chunks:
            all_chunks.append(c)
            meta.append({"pdf": pdf})

    print(f"Total chunks: {len(all_chunks)}")

    embs = model.encode(
        all_chunks,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    ).astype("float32")

    dim = embs.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embs)

    faiss.write_index(index, os.path.join(INDEX_DIR, "index.faiss"))
    with open(os.path.join(INDEX_DIR, "meta.json"), "w") as f:
        json.dump(meta, f)

    print("Index built and saved.")

# --------------- Query --------------------
def rank_with_queries(model):
    index = faiss.read_index(os.path.join(INDEX_DIR, "index.faiss"))
    with open(os.path.join(INDEX_DIR, "meta.json")) as f:
        meta = json.load(f)

    q_pdfs = [p for p in os.listdir(QUERY_DIR) if p.lower().endswith(".pdf")]
    assert q_pdfs, "No PDFs in query_pdfs/"

    q_chunks = []
    for pdf in q_pdfs:
        path = os.path.join(QUERY_DIR, pdf)
        text = pdf_to_text(path)
        q_chunks.extend(chunk_text(text, CHUNK_WORDS, CHUNK_OVERLAP))

    q_embs = model.encode(
        q_chunks,
        batch_size=32,
        show_progress_bar=True,
        normalize_embeddings=True
    ).astype("float32")

    # pooled intent vector (Option 1)
    q_vec = np.mean(q_embs, axis=0, keepdims=True)

    scores, ids = index.search(q_vec, TOP_K)

    per_pdf = defaultdict(list)
    for s, i in zip(scores[0], ids[0]):
        per_pdf[meta[i]["pdf"]].append(float(s))

    ranked = sorted(
        ((pdf, float(np.mean(v))) for pdf, v in per_pdf.items()),
        key=lambda x: x[1],
        reverse=True
    )

    print("\n=== Ranked Library PDFs ===")
    for i, (pdf, score) in enumerate(ranked, 1):
        print(f"{i:02d}. {pdf:40s}  {score:.4f}")
    
    # ---- Save top results ----
    TOP_COPY = min(30, len(ranked))  # copy top 10 (change if you want)

    for rank, (pdf, score) in enumerate(ranked[:TOP_COPY], 1):
        src = os.path.join(LIBRARY_DIR, pdf)
        dst_name = f"{rank:02d}_{pdf}"
        dst = os.path.join(OUTPUT_DIR, dst_name)

        try:
            shutil.copy2(src, dst)
        except Exception as e:
            print(f"[WARN] Could not copy {pdf}: {e}")

    print(f"\nCopied top {TOP_COPY} PDFs to: {OUTPUT_DIR}/")

# ----------------- Main -------------------
if __name__ == "__main__":
    nltk.download("punkt", quiet=True)

    print("Loading model on GPU...")
    model = SentenceTransformer(MODEL_NAME, device="cuda")

    if not os.path.exists(os.path.join(INDEX_DIR, "index.faiss")):
        build_index(model)

    rank_with_queries(model)
