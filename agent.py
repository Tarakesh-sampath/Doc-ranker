import os
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain.chains import RetrievalQA

# ---- Configuration ----
INDEX_DIR = "index_store"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"

LLM_BASE_URL = "http://localhost:1234/v1"
LLM_MODEL = "local-model"

SYSTEM_PROMPT = """
You are an expert research assistant for the project:
"Interference Quantum Classifier (IQC)".

Your task is to reason strictly within the IQC framework.
You must:
- respect the canonical algorithm and definitions,
- avoid variational or fidelity-based quantum ML,
- prioritize interference-based reasoning,
- maintain NISQ-aware, hardware-feasible explanations,
- avoid introducing unstated assumptions.

When uncertain, ask for clarification rather than guessing.
Do not invent new mechanisms unless explicitly requested.
Treat this as a serious research environment.
"""

# ---- Load components ----
print("Loading embeddings...")
embeddings = HuggingFaceEmbeddings(model_name=EMBED_MODEL)

print("Loading FAISS index...")
vectorstore = FAISS.load_local(INDEX_DIR, embeddings, allow_dangerous_deserialization=True)

retriever = vectorstore.as_retriever(search_kwargs={"k": 6})

print("Connecting to local LLM...")
llm = ChatOpenAI(
    base_url=LLM_BASE_URL,
    api_key="not-needed",
    model=LLM_MODEL,
    temperature=0.2,
)

qa = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    chain_type="stuff",
    chain_type_kwargs={
        "prompt": None  # LangChain will insert context automatically
    },
)

# ---- Interactive loop ----
print("\nLocal Research Agent ready.")
print("Ask questions grounded in your PDFs. Type 'exit' to quit.\n")

while True:
    q = input(">> ")
    if q.strip().lower() in {"exit", "quit"}:
        break

    prompt = SYSTEM_PROMPT + "\n\nUser question:\n" + q
    result = qa.run(prompt)

    print("\n--- Answer ---\n")
    print(result)
    print("\n---------------\n")
