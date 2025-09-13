from dotebv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain.schema.runnable import RunnableSequence, RunnableParallel, RunnableLambda


load_dotenv()

model = "llama-3.3-70b-versatile"
temperature = 0.7
llm = ChatGroq(model=model, temperature=temperature)

