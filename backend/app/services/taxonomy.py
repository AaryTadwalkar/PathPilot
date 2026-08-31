import re

TAXONOMY_MAP = {
    "react": "React", "reactjs": "React", "react.js": "React",
    "vue": "Vue.js", "vuejs": "Vue.js", "vue.js": "Vue.js",
    "angular": "Angular", "angularjs": "Angular",
    "js": "JavaScript", "javascript": "JavaScript",
    "ts": "TypeScript", "typescript": "TypeScript",
    "html": "HTML", "html5": "HTML",
    "css": "CSS", "css3": "CSS",
    "tailwind": "Tailwind CSS", "tailwindcss": "Tailwind CSS",
    "node": "Node.js", "nodejs": "Node.js", "node.js": "Node.js",
    "express": "Express.js", "expressjs": "Express.js", "express.js": "Express.js",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "spring": "Spring Boot", "springboot": "Spring Boot",
    "java": "Java",
    "c++": "C++", "cpp": "C++",
    "c": "C",
    "c#": "C#", "csharp": "C#",
    "golang": "Go", "go": "Go",
    "python": "Python",
    "ml": "Machine Learning", "machine learning": "Machine Learning",
    "dl": "Deep Learning", "deep learning": "Deep Learning",
    "ai": "Artificial Intelligence", "artificial intelligence": "Artificial Intelligence",
    "nlp": "Natural Language Processing", "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision", "computer vision": "Computer Vision",
    "genai": "Generative AI", "generative ai": "Generative AI",
    "llm": "Large Language Models", "large language models": "Large Language Models", "llms": "Large Language Models",
    "rag": "Retrieval Augmented Generation", "retrieval augmented generation": "Retrieval Augmented Generation",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "keras": "Keras",
    "scikit learn": "Scikit Learn", "sklearn": "Scikit Learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "sql": "SQL",
    "mysql": "MySQL",
    "postgres": "PostgreSQL", "postgresql": "PostgreSQL",
    "mongo": "MongoDB", "mongodb": "MongoDB",
    "redis": "Redis",
    "spark": "Apache Spark", "apache spark": "Apache Spark",
    "kafka": "Apache Kafka", "apache kafka": "Apache Kafka",
    "hadoop": "Apache Hadoop",
    "aws": "AWS", "amazon web services": "AWS",
    "gcp": "Google Cloud", "google cloud platform": "Google Cloud",
    "azure": "Microsoft Azure", "microsoft azure": "Microsoft Azure",
    "docker": "Docker",
    "k8s": "Kubernetes", "kubernetes": "Kubernetes",
    "ci cd": "CI/CD", "cicd": "CI/CD",
    "git": "Git",
    "github": "GitHub",
    "linux": "Linux",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "llamaindex": "LlamaIndex",
    "huggingface": "Hugging Face",
    "transformers": "Transformers",

    "faiss": "FAISS",
    "chromadb": "ChromaDB",
    "pinecone": "Pinecone",
    "weaviate": "Weaviate",

    "prompt engineering": "Prompt Engineering",

    "agentic ai": "Agentic AI",

    "rag": "Retrieval Augmented Generation",
    "retrieval augmented generation": "Retrieval Augmented Generation",
    "xgboost": "XGBoost",
    "lightgbm": "LightGBM",
    "catboost": "CatBoost",

    "matplotlib": "Matplotlib",
    "seaborn": "Seaborn",

    "opencv": "OpenCV",
    "rest api": "REST API",
    "graphql": "GraphQL",

    "jwt": "JWT",
    "oauth": "OAuth",

    "microservices": "Microservices",
    "terraform": "Terraform",
    "ansible": "Ansible",

    "github actions": "GitHub Actions",

    "jenkins": "Jenkins",

    "airflow": "Apache Airflow",
    "mlflow": "MLflow",

    "kubeflow": "Kubeflow",
}

RELATED_SKILLS = {

    "Artificial Intelligence": [
        "Machine Learning",
        "Deep Learning"
    ],

    "Machine Learning": [
        "Scikit Learn",
        "XGBoost",
        "LightGBM"
    ],

    "Deep Learning": [
        "PyTorch",
        "TensorFlow",
        "Keras"
    ],

    "Large Language Models": [
        "Transformers",
        "LangChain",
        "Retrieval Augmented Generation",
        "Prompt Engineering"
    ],

    "Generative AI": [
        "Large Language Models",
        "Prompt Engineering",
        "LangChain"
    ],

    "Computer Vision": [
        "OpenCV",
        "PyTorch",
        "TensorFlow"
    ]
}

def normalize_skill(raw_skill: str) -> str:
    """
    Checks a raw string against the taxonomy map. 
    Returns the standardized version if found.
    """
    clean_skill = str(raw_skill).lower().strip()

    return TAXONOMY_MAP.get(clean_skill, raw_skill.strip())


def extract_skills_from_text(text: str) -> list[str]:
    if not text:
        return []
        
    text_lower = text.lower()
    found_skills = set()
    
    for key, canonical_name in TAXONOMY_MAP.items():
        # FIX: Lookarounds allow matching of special characters like +, #, and .
        pattern = r'(?<!\w)' + re.escape(key) + r'(?!\w)'
        if re.search(pattern, text_lower):
            found_skills.add(canonical_name)
            
    return list(found_skills)