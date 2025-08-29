import os
import sys
from datetime import datetime
from pymongo import MongoClient
from azure.storage.blob import BlobServiceClient
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

# ----------------------
# Load environment
# ----------------------
MONGO_URI = os.getenv("MONGO_URI")
AZURE_BLOB_CONN = os.getenv("AZURE_BLOB_CONN")
AZURE_CONTAINER = os.getenv("AZURE_CONTAINER")
PUSHGATEWAY_URL = os.getenv("PUSHGATEWAY_URL", "http://pushgateway:9091")

if not all([MONGO_URI, AZURE_BLOB_CONN, AZURE_CONTAINER]):
    print("❌ Missing required environment variables.", flush=True)
    sys.exit(1)

# ----------------------
# Setup Mongo & Blob
# ----------------------
client = MongoClient(MONGO_URI)
db = client["filesure"]
jobs_collection = db["jobs"]
docs_collection = db["documents"]

blob_service_client = BlobServiceClient.from_connection_string(AZURE_BLOB_CONN)
container_client = blob_service_client.get_container_client(AZURE_CONTAINER)

# Ensure container exists
try:
    container_client.create_container()
except Exception:
    pass  # already exists

# ----------------------
# Prometheus Metrics
# ----------------------
registry = CollectorRegistry()
g_completed = Gauge("completed_jobs", "Number of successfully completed jobs", registry=registry)
g_failed = Gauge("failed_jobs", "Number of failed jobs", registry=registry)
g_docs_uploaded = Gauge("documents_uploaded_total", "Number of documents uploaded to Azure Blob", registry=registry)
g_blob_failures = Gauge("blob_upload_failures_total", "Number of blob upload failures", registry=registry)

def push_metrics(completed=0, failed=0, uploaded=0, blob_failed=0):
    g_completed.set(completed)
    g_failed.set(failed)
    g_docs_uploaded.set(uploaded)
    g_blob_failures.set(blob_failed)
    push_to_gateway(PUSHGATEWAY_URL, job="filesure-worker", registry=registry)

# ----------------------
# Job Processing
# ----------------------
def process_job(job):
    job_id = str(job["_id"])
    print(f"⚙️ Processing job {job_id} for {job.get('companyName')}", flush=True)

    uploaded_count = 0
    failed_count = 0

    try:
        # Simulated list of "documents" (in reality you’d fetch from external API or disk)
        documents = [
            {"filename": f"{job_id}_doc1.txt", "content": f"Dummy content for job {job_id} - doc1"},
            {"filename": f"{job_id}_doc2.txt", "content": f"Dummy content for job {job_id} - doc2"}
        ]

        for doc in documents:
            try:
                # Upload to Azure Blob under path documents/<jobId>/<filename>
                blob_name = f"documents/{job_id}/{doc['filename']}"
                blob_client = container_client.get_blob_client(blob_name)
                blob_client.upload_blob(doc["content"], overwrite=True)

                # Insert into Mongo "documents" collection
                docs_collection.insert_one({
                    "jobId": job["_id"],
                    "filename": doc["filename"],
                    "blobPath": blob_name,
                    "uploadStatus": "success",
                    "uploadedAt": datetime.utcnow()
                })

                uploaded_count += 1
                print(f"✅ Uploaded {doc['filename']} to {blob_name}", flush=True)

            except Exception as e:
                failed_count += 1
                print(f"❌ Failed to upload {doc['filename']}: {e}", flush=True)

                docs_collection.insert_one({
                    "jobId": job["_id"],
                    "filename": doc["filename"],
                    "blobPath": None,
                    "uploadStatus": "failed",
                    "error": str(e),
                    "uploadedAt": datetime.utcnow()
                })

        # Update job status
        job_status = "completed" if failed_count == 0 else "partial_failed"
        jobs_collection.update_one(
            {"_id": job["_id"]},
            {"$set": {
                "jobStatus": job_status,
                "updatedAt": datetime.utcnow(),
                "progress": 100,
                "totalDocuments": len(documents),
                "uploadedDocuments": uploaded_count,
                "failedDocuments": failed_count
            }}
        )

        # Push metrics
        push_metrics(completed=(1 if failed_count == 0 else 0),
                     failed=(1 if failed_count > 0 else 0),
                     uploaded=uploaded_count,
                     blob_failed=failed_count)

    except Exception as e:
        print(f"❌ Job {job_id} failed entirely: {e}", flush=True)
        jobs_collection.update_one(
            {"_id": job["_id"]},
            {"$set": {"jobStatus": "failed", "updatedAt": datetime.utcnow()}}
        )
        push_metrics(failed=1, blob_failed=1)

# ----------------------
# Main Worker Logic
# ----------------------
if __name__ == "__main__":
    job = jobs_collection.find_one_and_update(
        {"jobStatus": "pending"},
        {"$set": {"jobStatus": "in_progress", "updatedAt": datetime.utcnow()}}
    )

    if not job:
        print("ℹ️ No pending jobs found, exiting.", flush=True)
        sys.exit(0)

    process_job(job)
    sys.exit(0)
