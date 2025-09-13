# services/prompts.py
from langchain_core.prompts import PromptTemplate

def prompt_enhancer():
    return PromptTemplate(
        template=(
            "You are a prompt enhancer. "
            "Enhance the following prompt: {prompt}. "
            "Make it more descriptive and add details, "
            "without changing the meaning. "
            "Also: fix grammar and spelling."
        ),
        input_variables=["prompt"],
    )

def generation_prompt():
    return PromptTemplate(
        template=(
            "You are a world-class AI model. "
            "Answer the question based only on the provided context. "
            "If you don’t know, say you don’t know. "
            "\n\nContext:\n{context}\n\nQuestion: {enhanced_prompt}"
        ),
        input_variables=["context", "enhanced_prompt"],
    )
