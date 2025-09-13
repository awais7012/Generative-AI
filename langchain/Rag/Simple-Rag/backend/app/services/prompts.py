from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence, RunnableParallel, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from pydantic import BaseModel, EmailStr


def prompt_enhancer(propmt):
    enhanced_prompt = PromptTemplate(
        template = "you are a propmt enhancer, enhance the following propmt: {prompt} ." \
                   "Make it more descriptive and add more details to it, make it more specific" \
                   "make sure by enhancing  you dont channge the menaing of prompt .Also do teh following steps:" \
                   "Remove all the gramatiacal errors, Correct all the spelling mistakes ",
        input_variables = ["prompt"]          
    )
    return enhanced_prompt



def generation_prompt(enhanced_prompt,context):
    generated_Answer = PromptTemplate(
        template = "You are a world class AI model, you have to anser the following question based on the context given" \
                   "If you dont know the answer, just say that you dont know, dont try to make up an answer" \
                   "Use the following context to answer the question: {context} \n\n Question: {enhanced_prompt}",
        input_variables = ["context","enhanced_prompt"]
    )
    return generated_Answer
