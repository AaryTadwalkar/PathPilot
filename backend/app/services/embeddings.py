from sentence_transformers import SentenceTransformer

# Load the BGE model into memory. 
# We declare this globally outside the function so it only loads once when the server starts,
# rather than slowing down every single API request.
model = SentenceTransformer("BAAI/bge-small-en-v1.5")

def generate_embedding(text: str) -> list[float]:
    """
    Takes a string of text (like a student's combined skills and projects) 
    and converts it into a 384-dimensional mathematical vector using the BGE model.
    normalize_embeddings=True ensures cosine similarity calculations work perfectly later.
    """
    if not text or not text.strip():
        return []
        
    try:
        # Encode the text into a vector
        vector = model.encode(text, normalize_embeddings=True)
        
        # Convert the numpy array into a standard Python list so PostgreSQL can save it
        return vector.tolist()
        
    except Exception as e:
        print(f"Embedding Generation Error: {e}")
        return []