from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
import spacy
import os


class DocumentChunker:
    def __init__(self, chunk_size: int = 1024, chunk_overlap: int = 200):
        """
        Initialize the document chunker.

        Args:
            chunk_size: Maximum characters per chunk (default 1024)
            chunk_overlap: Characters to overlap between chunks (default 200)
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        # Get absolute path to spaCy model relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_path = os.path.join(current_dir, "..", "models", "en_core_web_sm", "en_core_web_sm-3.8.0")
        self.nlp = spacy.load(model_path) 


    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract named entities from text using spaCy NER"""
        if not text:
            return {}

        doc = self.nlp(text)

        entities = []
        for ent in doc.ents:
            cleaned_entity = ent.text.strip()
            entities.append(cleaned_entity)

        return entities

    def chunk_text(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        Split text into chunks with metadata.

        Args:
            text: Text to chunk
            metadata: Base metadata to attach to all chunks

        Returns:
            List of dicts with 'text' and 'metadata' keys
        """
        if not text or not text.strip():
            return []

        chunks = self.splitter.split_text(text)

        chunked_docs = []
        for idx, chunk in enumerate(chunks):
            # Extract entities
            entities_list = self.extract_entities(chunk)
            entities_str = ", ".join(entities_list) if entities_list else ""

            # add entities as comma separated string
            chunk_metadata = metadata.copy() if metadata else {}
            chunk_metadata.update({
                "chunk_index": idx,
                "text_length": len(chunk),
                "total_chunks": len(chunks),
                "entities": [e.lower() for e in entities_list]
            })

            # add entities at the end of text ---- way to much token usage
            # enhanced_text = chunk
            # if entities_str:
            #     enhanced_text = f"{chunk}\n\nEntities mentioned: {entities_str}"

            chunked_docs.append({
                "text": chunk,
                "metadata": chunk_metadata
            })

        return chunked_docs

    def chunk_page(self, page_text: str, page_number: int, base_metadata: Dict = None) -> List[Dict]:
        """
        Chunk a single page of a document.

        For single-page documents (images, text files with total_pages=1),
        stores the entire page as one chunk to avoid unnecessary overlap.

        Args:
            page_text: Text from the page
            page_number: Page number (1-indexed)
            base_metadata: Base metadata for the document

        Returns:
            List of chunks with metadata
        """
        metadata = base_metadata.copy() if base_metadata else {}
        metadata["page_number"] = page_number

        # For single-page documents (images, single-page text files),
        # store entire page as one chunk to save tokens and preserve context
        total_pages = base_metadata.get("total_pages", 1) if base_metadata else 1
        if total_pages == 1 and len(page_text) <= self.chunk_size * 2:
            # Extract entities for the entire page
            entities_list = self.extract_entities(page_text)

            metadata.update({
                "chunk_index": 0,
                "text_length": len(page_text),
                "total_chunks": 1,
                "entities": [e.lower() for e in entities_list]
            })

            return [{
                "text": page_text,
                "metadata": metadata
            }]

        # For multi-page documents or very large single pages, chunk normally
        return self.chunk_text(page_text, metadata)


# if __name__ == "__main__":
#     chunker = DocumentChunker(chunk_size=200, chunk_overlap=20)

#     sample_text = """
#     This is a sample document about Jeffrey Epstein's flight logs.
#     The logs contain detailed information about passengers and destinations.

#     In 1997, multiple flights were recorded to various international locations.
#     The manifests include names, dates, and flight routes.
#     """

#     metadata = {
#         "document_id": "TEST-001",
#         "source": "DOJ"
#     }

#     chunks = chunker.chunk_text(sample_text, metadata)
#     print(f"Generated {len(chunks)} chunks:")
#     for i, chunk in enumerate(chunks):
#         print(f"\nChunk {i}:")
#         print(f"Text: {chunk['text'][:100]}...")
#         print(f"Metadata: {chunk['metadata']}")
