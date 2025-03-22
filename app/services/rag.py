import logging
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import CHROMA_DB_PATH, AI_MODEL, OPENROUTER_API_KEY

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  

llm = ChatOpenAI(
    openai_api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
    model_name=AI_MODEL,
    temperature=0.5,
    max_tokens=3000
)

def get_group_vectorstore(vk_group_id: int) -> Chroma:
    collection_name = f"group_{vk_group_id}"
    vectorstore = Chroma(
        persist_directory=CHROMA_DB_PATH,
        collection_name=collection_name,
        embedding_function=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    try:
        vectorstore.get()
    except ValueError:
        logger.warning(f"⚠️ Коллекция {collection_name} не найдена! Создаем новую...")
        vectorstore.reset_collection()
    return vectorstore

