from langchain_community.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from app.db.pinecone_db import get_pinecone
from services.embeddings import generate_embedding_docs
from services.search import train_bm25_for_user
import uuid
from datetime import datetime

def docs_loader(file_path: str):
    if file_path.endswith('.txt'):
        loader = TextLoader(file_path)
    elif file_path.endswith('.pdf'):
        loader = PyPDFLoader(file_path)
    else:
        raise ValueError("❌ File format not supported (only .txt or .pdf)")
    return loader.load()

def split_docs(documents, chunk_size=1000, chunk_overlap=200):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return splitter.split_documents(documents)

def store_docs_in_pinecone(user_id: str, file_path: str):
    """Store documents with user isolation and BM25 training"""
    try:
        pc = get_pinecone()
        index = pc.Index(settings.pinecone_index_name)
        
        docs = docs_loader(file_path)
        chunks = split_docs(docs)
        
        texts = [chunk.page_content for chunk in chunks]
        embeddings = generate_embedding_docs(texts)
        
        # Train BM25 for this user with new texts
        train_bm25_for_user(user_id, texts)
        
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
        
        # Store in user's namespace
        index.upsert(vectors=vectors, namespace=user_id)
        
        # Update document count in MongoDB
        from app.models import Document
        from app.db.mongodb import connection
        
        db = connection()
        doc_record = Document(
            doc_id=str(uuid.uuid4()),
            user_id=user_id,
            filename=file_path.split("/")[-1],
            file_path=file_path,
            chunks_count=len(chunks)
        )
        db.documents.insert_one(doc_record.dict())
        
        return {"message": f"✅ Stored {len(chunks)} chunks for {file_path}"}
        
    except Exception as e:
        return {"error": f"❌ Failed to store documents: {str(e)}"}