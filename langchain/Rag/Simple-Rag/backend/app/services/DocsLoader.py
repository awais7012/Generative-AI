# services/docsLoader.py
from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.db.pinecone_db import get_pinecone
from services.embeddings import generate_embedding_docs
import uuid
from datetime import datetime


# --- Step 1: Load Documents ---
def docs_loader(file_path: str):
    if file_path.endswith('.txt'):
        loader = TextLoader(file_path)
    elif file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    else:
        raise ValueError("❌ File format not supported (only .txt or .pdf)")
    return loader.load()


# --- Step 2: Split Docs ---
def split_docs(documents, chunk_size=1000, chunk_overlap=200):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(documents)


# --- Step 3: Store in Pinecone ---
def store_docs_in_pinecone(user_id: str, file_path: str):
    pc = get_pinecone()
    index = pc.Index("my-index")  

    docs = docs_loader(file_path)
    chunks = split_docs(docs)

    texts = [chunk.page_content for chunk in chunks]
    embeddings = generate_embedding_docs(texts)

    vectors = []
    for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_id = str(uuid.uuid4())
        vectors.append((
            chunk_id,
            embedding,
            {
                "user_id": user_id,
                "filename": file_path.split("/")[-1],
                "chunk_index": i,
                "text": chunk.page_content,
                "created_at": datetime.utcnow().isoformat()
            }
        ))

    index.upsert(vectors=vectors, namespace=user_id)

    return {"message": f"✅ Stored {len(chunks)} chunks for {file_path}"}
