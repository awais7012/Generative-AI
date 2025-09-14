from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain.schema.runnable import RunnableSequence, RunnableParallel, RunnableLambda
from services.search import hybrid_search
from services.prompts import prompt_enhancer, generation_prompt
from app.models import get_chat_context, update_chat_context, update_user_tokens, update_chat_tokens
from app.config.settings import settings
import tiktoken

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile", 
    temperature=0.7,
    groq_api_key=settings.groq_api_key
)
parser = StrOutputParser()

# Token counter
def count_tokens(text: str) -> int:
    """Count tokens in text"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except:
        return len(text.split()) * 1.3  

def create_rag_pipeline():
    """Create multi-user RAG pipeline"""
    
    def enhance_prompt(data):
        prompt = data["prompt"]
        enhanced = prompt_enhancer() | llm | parser
        return enhanced.invoke({"prompt": prompt})
    
    def get_context(data):
        user_id = data["user_id"]
        chat_id = data["chat_id"]
        enhanced_prompt = data["enhanced_prompt"]
        
        # Get chat history from Redis
        chat_context = get_chat_context(user_id, chat_id)
        
        # Get documents via hybrid search
        documents = hybrid_search(user_id, enhanced_prompt)
        doc_context = "\n".join(documents)
        
        # Combine contexts
        full_context = f"Chat History:\n{chat_context}\n\nDocuments:\n{doc_context}"
        
        return {
            "enhanced_prompt": enhanced_prompt,
            "context": full_context,
            "user_id": user_id,
            "chat_id": chat_id
        }
    
    def generate_answer(data):
        # Generate answer
        generation_chain = generation_prompt() | llm | parser
        answer = generation_chain.invoke({
            "context": data["context"],
            "enhanced_prompt": data["enhanced_prompt"]
        })
        
        # Count tokens
        prompt_tokens = count_tokens(data["enhanced_prompt"] + data["context"])
        answer_tokens = count_tokens(answer)
        total_tokens = prompt_tokens + answer_tokens
        
        # Update token usage
        update_user_tokens(data["user_id"], total_tokens)
        update_chat_tokens(data["user_id"], data["chat_id"], total_tokens)
        
        # Save to chat history
        update_chat_context(data["user_id"], data["chat_id"], "user", data["enhanced_prompt"])
        update_chat_context(data["user_id"], data["chat_id"], "assistant", answer)
        
        return {
            "answer": answer,
            "tokens_used": total_tokens
        }
    
    # Creatingggggggg pipeline
    pipeline = (
        RunnableLambda(enhance_prompt) |
        RunnableLambda(lambda enhanced: {
            "enhanced_prompt": enhanced,
            "user_id": None,  
            "chat_id": None   #
        }) |
        RunnableLambda(get_context) |
        RunnableLambda(generate_answer)
    )
    
    return pipeline


def query_rag_system(user_id: str, chat_id: str, prompt: str):
    """Main function to query RAG system"""
    try:
        pipeline = create_rag_pipeline()
        
        
        input_data = {
            "prompt": prompt,
            "user_id": user_id,
            "chat_id": chat_id
        }
        
        result = pipeline.invoke(input_data)
        return {
            "success": True,
            "answer": result["answer"],
            "tokens_used": result["tokens_used"]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"❌ RAG error: {str(e)}",
            "answer": "Sorry, I couldn't process your request."
        }