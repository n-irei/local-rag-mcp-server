import os
import hashlib
from pathlib import Path

import chromadb
from chromadb.config import Settings
import ollama
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

try:
    import fitz  # PyMuPDF
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

# --- 設定 ---
CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./chroma_db")
EMBED_MODEL    = os.getenv("EMBED_MODEL", "nomic-embed-text")
LLM_MODEL      = os.getenv("LLM_MODEL", "qwen3.5:9b")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")
OLLAMA_HOST    = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# --- ChromaDB 初期化 ---
chroma_client = chromadb.PersistentClient(
    path=CHROMA_DB_PATH,
    settings=Settings(anonymized_telemetry=False),
)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

# --- Ollama クライアント ---
ollama_client = ollama.Client(host=OLLAMA_HOST)

mcp = FastMCP("local-rag-mcp-server")


# =====================
# ユーティリティ関数
# =====================

def get_embedding(text: str) -> list[float]:
    response = ollama_client.embeddings(model=EMBED_MODEL, prompt=text)
    return response["embedding"]


def extract_text(file_path: str) -> str:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        if not PDF_SUPPORT:
            raise ValueError("PyMuPDF がインストールされていません。PDF の処理ができません。")
        doc = fitz.open(file_path)
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text
    elif suffix in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"未対応のファイル形式です: {suffix}（対応: .pdf / .txt / .md）")


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c for c in chunks if c.strip()]


# =====================
# MCPツール定義
# =====================

@mcp.tool()
def add_document(file_path: str) -> str:
    """ファイル（PDF / txt / md）を RAG インデックスに追加します。"""
    path = Path(file_path)
    if not path.exists():
        return f"エラー: ファイルが見つかりません: {file_path}"

    try:
        text = extract_text(file_path)
    except ValueError as e:
        return f"エラー: {e}"

    chunks = chunk_text(text)
    if not chunks:
        return "エラー: テキストを抽出できませんでした。ファイルの内容を確認してください。"

    file_hash = hashlib.md5(path.read_bytes()).hexdigest()
    doc_name = path.name

    ids, embeddings, documents, metadatas = [], [], [], []
    for i, chunk in enumerate(chunks):
        ids.append(f"{file_hash}_{i}")
        embeddings.append(get_embedding(chunk))
        documents.append(chunk)
        metadatas.append({
            "source": doc_name,
            "file_path": str(path.resolve()),
            "chunk_index": i,
            "file_hash": file_hash,
        })

    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    return f"登録完了: {doc_name}（{len(chunks)} チャンク）"


@mcp.tool()
def search_documents(query: str) -> str:
    """質問に対して RAG 検索を行い、qwen3.5:9b で回答を生成します。"""
    count = collection.count()
    if count == 0:
        return "ドキュメントが登録されていません。先に add_document でファイルを追加してください。"

    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(5, count),
        include=["documents", "metadatas"],
    )

    contexts = results["documents"][0]
    sources = list({m["source"] for m in results["metadatas"][0]})
    context_text = "\n\n---\n\n".join(contexts)

    prompt = f"""以下のコンテキストを参照して、質問に日本語で回答してください。
コンテキストに答えが含まれない場合は「コンテキストに情報がありません」と答えてください。

コンテキスト:
{context_text}

質問: {query}

回答:"""

    response = ollama_client.generate(
        model=LLM_MODEL,
        prompt=prompt,
        think=False,
        options={"temperature": 0.1},
    )

    answer = response["response"]
    sources_str = "、".join(sources)
    return f"{answer}\n\n---\n参照ソース: {sources_str}"


@mcp.tool()
def list_documents() -> str:
    """登録済みドキュメントの一覧を返します。"""
    count = collection.count()
    if count == 0:
        return "登録済みドキュメントはありません。"

    results = collection.get(include=["metadatas"])

    seen: dict[str, dict] = {}
    for meta in results["metadatas"]:
        fh = meta["file_hash"]
        if fh not in seen:
            seen[fh] = {"source": meta["source"], "file_path": meta["file_path"], "chunks": 0}
        seen[fh]["chunks"] += 1

    lines = [f"登録済みドキュメント一覧（{len(seen)} 件）:\n"]
    for i, info in enumerate(seen.values(), 1):
        lines.append(f"{i}. {info['source']}（{info['chunks']} チャンク）")
        lines.append(f"   パス: {info['file_path']}")

    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
