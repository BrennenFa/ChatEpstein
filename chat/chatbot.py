import os
import sys
import gc
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.callbacks import get_openai_callback
from langchain_classic.retrievers.document_compressors import LLMChainExtractor
from sentence_transformers import CrossEncoder
import spacy
import boto3
from botocore.config import Config
# Add VectorStore directory to path
vectorstore_path = Path(__file__).parent.parent / "VectorStore"
sys.path.insert(0, str(vectorstore_path))

from pinecone_connect import pinecone_connect

load_dotenv()

# load spaCy model with fallback download
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading en_core_web_sm model...")
    os.system("python -m spacy download en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# cross encoder for reranking
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

# Suppress tokenizer parallelism warning
os.environ["TOKENIZERS_PARALLELISM"] = "false"

api_key = os.getenv("GROQ_KEY")
model_name = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

if not api_key:
    raise ValueError("GROQ_KEY not found in environment")

# Initialize S3 client
bucket_name = os.getenv("AWS_BUCKET_NAME")
region = os.getenv("AWS_REGION")
s3_client = boto3.client(
    's3',
    region_name=region,
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
    config=Config(
        signature_version='s3v4',
        s3={'addressing_style': 'virtual'}
    )
) if bucket_name else None

llm =  ChatGroq(
    model=model_name,
    groq_api_key=api_key,
    temperature=0.2
)

def extract_entities_from_query(query: str) -> list[str]:
    """Extract named entities from user query"""
    doc = nlp(query)
    ALLOWED_LABELS = {"PERSON", "ORG", "GPE"}
    entities = []
    for ent in doc.ents:
        if ent.label_ in ALLOWED_LABELS and len(ent.text.strip()) > 2:
            entities.append(ent.text.strip().lower())
    return entities


def generate_presigned_url(s3_key: str, expiration: int = 3600) -> str:
    """
    Generate a presigned URL for an S3 object.

    Args:
        s3_key: S3 object key
        expiration: URL expiration time in seconds (default: 1 hour)

    Returns:
        Presigned URL string or "N/A" if generation fails
    """
    if not s3_client or not bucket_name or not s3_key:
        return "N/A"

    try:
        url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': s3_key},
            ExpiresIn=expiration
        )
        print(s3_key)
        return url
    except Exception as e:
        print(f"Error generating presigned URL for {s3_key}: {e}")
        return "N/A"



def setup_rag_chain():
    """Setup RAG chain with vector DB and LLM"""
    # Connect to vector database
    vector_db = pinecone_connect()

    # Store document metadata for citation lookup
    doc_metadata = {}

    # Prompt context basedon chat history
    context_prompt = """Reformulate the follow-up question as a standalone question using chat history context. If already standalone, return as-is. Don't answer it."""

    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system", context_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])

    # Create prompt template for answers
    qa_system_prompt = """You are a meticulous document analyst. Your goal is to extract facts from Epstein-related records with 100% accuracy.

### Instructions
1. DOCUMENT ANALYSIS: ALL questions about people, events, or information in the documents must ONLY use the provided context. NEVER use your training data or general knowledge for document-related questions.
2. GENERAL KNOWLEDGE: ONLY answer without the context for completely unrelated general knowledge questions (e.g., "Who created The Simpsons?", "What is 2+2?").
3. DEFAULT ASSUMPTION: Unless the question is clearly asking for general knowledge, assume it is about the documents.
4. The context contains documents with Document ID and Page information clearly marked.
5. For every claim about the DOCUMENTS, include the EXACT QUOTE from the document followed by a citation in this format: (Document_ID, Page X)
6. CRITICAL: Always include the specific quoted text before the citation when discussing documents.
7. If the context does not contain the answer to a document-related question, you MUST state: "I don't have information about that in the documents."
8. NEVER fabricate citations or use document IDs that are not in the provided context.
9. Attribution: Only attribute quotes to someone if named as the speaker OR subject.
   - Being mentioned in a document ≠ the document is about them
   - If unclear, use "according to the document" or "an unnamed person" - NEVER GUESS

### Citation Format
CRITICAL: Each document must have its OWN citation. NEVER combine multiple documents.

Format: (DOCUMENT_ID, Page X) - Use EXACT Document ID, NOT "Document 1" or numbers.

CORRECT: Epstein knew Prince Andrew (DOJ-OGR-00024825, Page 1.0) and Bill Clinton (DOJ-OGR-00024826, Page 2.0).
WRONG: ❌ (Documents 1, 2, DOJ-OGR-00024825, DOJ-OGR-00024826, Page 1.0)
WRONG: ❌ (Document 1, Page 1.0)

### Context
{context}"""

    # qa user prompt
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", qa_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])


    # Entity-aware retrieval with reranking and compression
    def entity_aware_retrieval(query: str):
        """
        Three-stage retrieval:
        1. Entity-based filtering + semantic search
        2. Cross-encoder reranking
        3. Contextual compression (removes irrelevant sentences)
        """
        
        query_entities = extract_entities_from_query(query)

        # retrieval of entities
        if query_entities:
            entity_clean = [entity.lower() for entity in query_entities]
            

            entity_docs_max = 8
            # query for entity-matched docs
            entity_matched_docs = vector_db.similarity_search(
                query,
                k=entity_docs_max,
                filter={"entities": {"$in": entity_clean}}
            )

            # calcuate remaining docs needed for 12 total
            num_entity_matched = len(entity_matched_docs)
            num_to_total = 8 + (entity_docs_max - num_entity_matched)

            normal_docs = vector_db.similarity_search(
                query,
                k=num_to_total
            )

            # combine entities
            candidates_docs = entity_matched_docs + normal_docs


        else:
            # no entities in query
            candidates_docs = vector_db.similarity_search(
                query,
                k=16,
            )

        # Cross-encoder reranking

        # collect query and doc object from db
        query_content = [(query, doc.page_content) for doc in candidates_docs]
        rerank_scores = reranker.predict(query_content)

        # sort docs with reranked scores
        reranked = sorted(
            zip(candidates_docs, rerank_scores),
            key=lambda x: x[1],
            reverse=True  # Higher scores are better for cross-encoder
        )

        # take top 6 docs
        final_docs = [doc for doc, score in reranked[:8]]


        # Contextual compression (filter irrelevant sentences) -- kinda expensive
        # DISABLED: Uses extra LLM call, too expensive (~2-3k tokens per query)
        # compressor = LLMChainExtractor.from_llm(llm)
        # compressed_docs = compressor.compress_documents(top_docs, query)
        # final_docs = compressed_docs[:6]

        return final_docs

    # get documents for resonse with chat history
    def get_docs(x):
        # clear metadata to prevent excess memory usage
        doc_metadata.clear()
        citations_metadata.clear()
        gc.collect()

        # Contextualize question with chat history if available
        if x.get("chat_history"):
            contextualized_prompt = (contextualize_prompt | llm | StrOutputParser()).invoke(x)
        else:
            contextualized_prompt = x["input"]

        # Retrieve relevant docs for prompt using entity based retrieval
        docs = entity_aware_retrieval(contextualized_prompt)

        # query docs grouped by id
        doc_groups = defaultdict(list)
        for doc in docs:
            doc_id = doc.metadata.get('document_id', 'Unknown')
            page_num = doc.metadata.get('page_number', 'N/A')
            doc_page_id = f"{doc_id}_{page_num}"
            doc_groups[doc_page_id].append(doc)

        # Format each unique document while merging chunks w same id
        doc_data = []
        doc_number = 1

        # combine chunks of same document page
        for doc_page_key, chunks in doc_groups.items():

            # Combine content chunks of this document
            combined_content = "\n\n---\n\n".join([chunk.page_content for chunk in chunks])

            # use metadata from first chunk
            first_chunk = chunks[0]
            doc_id = first_chunk.metadata.get('document_id', 'Unknown')
            page = first_chunk.metadata.get('page_number', 'N/A')
            s3_key = first_chunk.metadata.get('s3_key')
            source_url = generate_presigned_url(s3_key) if s3_key else "N/A"

            # Store metadata for citation lookup
            citation_key = f"{doc_id}, Page {page}"
            doc_metadata[citation_key] = {
                'source': first_chunk.metadata.get('source', 'Unknown'),
                'document_id': doc_id,
                'page': page,
                's3_key': s3_key,
                'url': source_url
            }

            doc_text = (
                f"=== DOCUMENT {doc_number} ===\n"
                f"Source: {first_chunk.metadata.get('source', 'Unknown')}\n"
                f"Document ID: {doc_id}\n"
                f"Page: {page}\n"
                f"Date: {first_chunk.metadata.get('publication_date', 'Unknown')}\n"
                f"Link: {source_url}\n\n"
                f"{combined_content}\n"
                f"=== END DOCUMENT {doc_number} ==="
            )

            doc_data.append(doc_text)
            doc_number += 1

        context = "\n\n".join(doc_data)
        return context

    # Store citations metadata for API response
    citations_metadata = {}

    # Function to append sources based on citations in LLM answer
    def append_sources(llm_answer: str) -> str:
        """Parse citations from answer and append formatted sources"""
        import re

        # Clear previous citations
        citations_metadata.clear()

        # Extract all citations in format (DOC-ID, Page X)
        citation_pattern = r'\(([A-Z0-9\-_]+),\s*Page\s+([^\)]+)\)'
        citations = re.findall(citation_pattern, llm_answer)

        if not citations:
            return llm_answer

        # Get unique citations preserving order of first appearance
        seen = set()
        unique_citations = []
        for doc_id, page in citations:
            citation_key = f"{doc_id}, Page {page}"
            if citation_key not in seen:
                seen.add(citation_key)
                unique_citations.append(citation_key)

        # Build sources section and populate citations metadata
        sources_text = "\n\n---\n\n**Sources:**\n\n"

        for citation_key in unique_citations:
            if citation_key in doc_metadata:
                meta = doc_metadata[citation_key]
                page_text = f", Page {meta['page']}" if meta['page'] != "N/A" else ""
                sources_text += f"- **{meta['document_id']}{page_text} - {meta['source']}**"

                # Add link if available
                if meta['url'] and meta['url'] != "N/A":
                    sources_text += f" - [View Document]({meta['url']})"

                # Store citation metadata for frontend (even if URL is N/A)
                citations_metadata[citation_key] = meta['url']

                sources_text += "\n"

        return llm_answer + sources_text

    # chain with doc retrieval
    retrieval_chain = RunnablePassthrough.assign(context=get_docs)

    # Chain: retrieve docs → generate answer → append sources
    rag_chain = retrieval_chain | qa_prompt | llm | StrOutputParser() | RunnableLambda(append_sources)

    message_store = {}
    MAX_SESSIONS = 50

    # manage session history (limited to last 2 exchanges)
    def get_session_history(session_id: str) -> BaseChatMessageHistory:

        # remove excess sessions to avoid memory overload
        sessions_deleted = 0
        while session_id not in message_store and len(message_store) >= MAX_SESSIONS:
            oldest_session = next(iter(message_store))
            del message_store[oldest_session]
            sessions_deleted += 1

        # Force garbage collection after deleting sessions
        if sessions_deleted > 0:
            gc.collect()
            print(f"[Memory] Removed {sessions_deleted} old session(s), forced GC (current: {len(message_store)} sessions)")

        if session_id not in message_store:
            message_store[session_id] = ChatMessageHistory()

        history = message_store[session_id]

        # Limit to last 2 exchanges (4 messages: 2 user + 2 assistant)
        old_message_count = len(history.messages)
        history.messages = history.messages[-4:]

        # Force GC if we deleted old messages
        if old_message_count > 4:
            gc.collect()

        return history

    # Wrap with message history
    conversational_rag_chain = RunnableWithMessageHistory(
        rag_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    # Return both the chain and the citations metadata dict
    return conversational_rag_chain, citations_metadata


def track_tokens(qa_chain, user_input, total_tokens):
    """Track Tokens bc im broke :("""
    with get_openai_callback() as cb:
        answer = qa_chain.invoke(
            {"input": user_input},
            config={"configurable": {"session_id": "default"}}
        )

        print(f"\nAnswer: {answer}\n")

        # Display token usage
        print(f"{'='*50}")
        print(f"Tokens used: {cb.total_tokens} (Prompt: {cb.prompt_tokens}, Completion: {cb.completion_tokens})")
        total_tokens += cb.total_tokens
        print(f"Session total: {total_tokens} / 100,000 daily limit ({(total_tokens/100000)*100:.1f}%)")
        print(f"{'='*50}\n")

        return answer, total_tokens


def chat_session():
    """Run an interactive RAG chat session."""
    print("\n" + "="*50)
    print("Epstein Documents RAG Chatbot")
    print("="*50)
    print("Loading vector database and LLM...")

    rag_chain, citations_metadata = setup_rag_chain()

    model = os.getenv("MODEL_NAME")
    db_dir = os.getenv("DB_DIR")

    print(f"Model: {model}")
    print(f"Database: {db_dir}")
    print("\nType 'quit' to exit")
    print("="*50 + "\n")

    total_tokens = 0
    
    # Set to False to disable tracking
    ENABLE_TOKEN_TRACKING = True

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue
        try:
            if ENABLE_TOKEN_TRACKING:
                answer, total_tokens = track_tokens(rag_chain, user_input, total_tokens)
            else:
                answer = rag_chain.invoke(
                    {"input": user_input},
                    config={"configurable": {"session_id": "default"}} # establish sessions w chat his
                )
                print(f"\nAnswer: {answer}\n")


        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    chat_session()
