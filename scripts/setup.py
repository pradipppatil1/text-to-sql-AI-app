from app.database.mysql_client import MySQLClient
from app.vector.qdrant_client import QdrantManager
from app.utils.data_gen import generate_wealth_data
from datasets import load_dataset
import os

def setup():
    db = MySQLClient()
    vector_db = QdrantManager()
    
    # 0. Check and Generate Data
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    if user_count == 0:
        generate_wealth_data(db)
    else:
        print(f"Skipping Data Gen: Found {user_count} users already in database.")
    
    # 1. Index Metadata
    print("Checking database metadata indexing...")
    vector_db.ensure_collection("table_metadata")
    existing_meta = vector_db.client.count("table_metadata").count
    if existing_meta == 0:
        meta = db.get_schema_metadata()
        vector_db.upsert_points("table_metadata", [{"table_name": k, "summary": v['summary']} for k,v in meta.items()])
        print(f"Indexed {len(meta)} tables.")
    else:
        print(f"Skipping Metadata Index: Found {existing_meta} points.")
    
    # 2. Seed Golden Queries from SQaLe (Subset)
    print("Checking golden queries indexing...")
    vector_db.ensure_collection("golden_queries")
    existing_queries = vector_db.client.count("golden_queries").count
    if existing_queries == 0:
        print("Seeding golden queries from SQaLe (Streaming)...")
        ds = load_dataset("trl-lab/SQaLe-text-to-SQL-dataset", split="train", streaming=True)
        samples = ds.take(50)
        queries = []
        for item in samples:
            queries.append({
                "question": item.get('question', item.get('input', '')),
                "sql": item.get('query', item.get('output', ''))
            })
        vector_db.upsert_points("golden_queries", queries, text_key="question")
        print(f"Indexed {len(queries)} golden queries.")
    else:
        print(f"Skipping Golden Queries: Found {existing_queries} points.")
    
    print("Setup complete!")

if __name__ == "__main__":
    setup()
