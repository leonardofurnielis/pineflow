import uuid
from logging import getLogger
from typing import List, Literal

from pineflow.core.document import Document, DocumentWithScore
from pineflow.core.embeddings import BaseEmbedding

logger = getLogger(__name__)


class ChromaVectorStore:
    """Chroma is the AI-native open-source vector database. Embeddings are stored within a ChromaDB collection.

    Args:
        embed_model (BaseEmbedding):
        collection_name (str, optional): Name of the ChromaDB collection.
        distance_strategy (str, optional): Distance strategy for similarity search. Currently supports "cosine", "ip" and "l2". Defaults to ``cosine``.

    **Example**

    .. code-block:: python

        from pineflow.embeddings import HuggingFaceEmbedding
        from pineflow.vector_stores import ChromaVectorStore

        embedding = HuggingFaceEmbedding()
        vector_db = ChromaVectorStore(embed_model=embedding)
    """

    def __init__(self, embed_model: BaseEmbedding,
                 collection_name: str = None,
                 distance_strategy: Literal["cosine", "ip", "l2"] = "cosine") -> None:
        try:
            import chromadb
            import chromadb.config

        except ImportError:
            raise ImportError("chromadb package not found, please install it with `pip install chromadb`")

        self._embed_model = embed_model
        self._client_settings = chromadb.config.Settings()
        self._client = chromadb.Client(self._client_settings)

        if collection_name is None:
            collection_name = "auto-generated-" + str(uuid.uuid4())[:8]
            logger.info(f"collection_name: {collection_name}")

        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=None,
            metadata={"hnsw:space": distance_strategy}
        )

    def add_documents(self, documents: List[Document]) -> List:
        """Add documents to the ChromaDB collection.

        Args:
            documents (List[Document]): List of `Document` objects to add to the collection.
        """
        embeddings = []
        metadatas = []
        ids = []
        chroma_documents = []

        for doc in documents:
            embeddings.append(self._embed_model.get_query_embedding(doc.get_content()))
            metadatas.append(doc.get_metadata() if doc.get_metadata() else None)
            ids.append(doc.doc_id if doc.doc_id else str(uuid.uuid4()))
            chroma_documents.append(doc.get_content())

        self._collection.add(embeddings=embeddings,
                             ids=ids,
                             metadatas=metadatas,
                             documents=chroma_documents)

        return ids

    def query(self, query: str, top_k: int = 4) -> List[DocumentWithScore]:
        """Performs a similarity search for top-k most similar documents.

        Args:
            query (str): Query text.
            top_k (int, optional): Number of top results to return. Defaults to ``4``.
        """
        query_embedding = self._embed_model.get_query_embedding(query)

        results = self._collection.query(
            query_embeddings=query_embedding,
            n_results=top_k
        )

        return [
            DocumentWithScore(document=Document(
                doc_id=result[0],
                text=result[1],
                metadata=result[2]
            ), score=result[3])
            for result in zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def delete_documents(self, ids: List[str] = None) -> None:
        """Delete documents from the ChromaDB collection.

        Args:
            ids (List[str]): List of `Document` IDs to delete. Defaults to ``None``.
        """
        if not ids:
            raise ValueError("No ids provided to delete.")

        self._collection.delete(ids=ids)
