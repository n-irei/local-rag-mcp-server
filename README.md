# local-rag-mcp-server

完全オフラインで動作するローカル RAG MCP サーバーです。
ChromaDB + Ollama（nomic-embed-text / qwen3.5:9b）を使い、PDF・txt・md ファイルを登録して質問に回答します。

## 構成

| コンポーネント | 役割 |
|---|---|
| FastMCP | MCP サーバーフレームワーク |
| ChromaDB | ベクトル DB（ローカル永続化） |
| nomic-embed-text | Embedding モデル（Ollama） |
| qwen3.5:9b | LLM（Ollama、think=False） |
| PyMuPDF | PDF テキスト抽出 |

## 前提条件

- Python 3.10 以上
- [Ollama](https://ollama.ai/) がローカルで起動していること
- 以下のモデルが pull 済みであること

```bash
ollama pull nomic-embed-text
ollama pull qwen3.5:9b
```

## セットアップ

```bash
# 1. リポジトリのルートに移動
cd C:\Users\pcuser\Documents\project\local-rag-mcp-server

# 2. .env ファイルを作成
cp .env.example .env

# 3. 仮想環境を有効化（作成済み）
.venv\Scripts\activate

# 4. サーバーを起動（動作確認）
python server.py
```

## MCPツール

### `add_document(file_path: str)`
ファイルを RAG インデックスに追加します。

```
対応形式: .pdf / .txt / .md
```

### `search_documents(query: str)`
質問に対して RAG 検索を行い、qwen3.5:9b で回答を生成します。

### `list_documents()`
登録済みドキュメントの一覧（ファイル名・チャンク数・パス）を返します。

## ディレクトリ構成

```
local-rag-mcp-server/
├── server.py           # MCP サーバー本体
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数テンプレート
├── .env                # 環境変数（自分で作成）
├── .venv/              # 仮想環境
├── chroma_db/          # ChromaDB データ（自動生成）
├── docs/               # ドキュメント格納フォルダ
└── README.md
```

## Claude Desktop への設定

`claude_desktop_config.json` に以下を追加してください。

**場所:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "local-rag": {
      "command": "C:\\Users\\pcuser\\Documents\\project\\local-rag-mcp-server\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\Users\\pcuser\\Documents\\project\\local-rag-mcp-server\\server.py"
      ],
      "env": {
        "CHROMA_DB_PATH": "C:\\Users\\pcuser\\Documents\\project\\local-rag-mcp-server\\chroma_db",
        "EMBED_MODEL": "nomic-embed-text",
        "LLM_MODEL": "qwen3.5:9b",
        "OLLAMA_HOST": "http://localhost:11434"
      }
    }
  }
}
```

設定後、Claude Desktop を再起動すると `local-rag` サーバーが認識されます。

## 使用例

```
# ドキュメントを登録
add_document("C:/Users/pcuser/Documents/project/local-rag-mcp-server/docs/manual.pdf")

# 質問して回答を得る
search_documents("有給休暇の申請方法を教えてください")

# 登録済みドキュメントを確認
list_documents()
```

## 環境変数

| 変数名 | デフォルト値 | 説明 |
|---|---|---|
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB の保存先 |
| `EMBED_MODEL` | `nomic-embed-text` | Embedding モデル名 |
| `LLM_MODEL` | `qwen3.5:9b` | LLM モデル名 |
| `COLLECTION_NAME` | `documents` | ChromaDB コレクション名 |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama エンドポイント |
