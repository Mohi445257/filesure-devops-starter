import os
import time
import random
import sys
import threading
from datetime import datetime, timedelta
from pymongo import MongoClient
from bson import ObjectId
import logging
from prometheus_client import Counter, Summary, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from azure.storage.blob import BlobServiceClient
from flask import Flask

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DocumentDownloader:
    def __init__(self):
        # Mongo setup
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.client = MongoClient(self.mongo_uri)
        self.db = self.client["filesure"]
        self.collection = self.db["jobs"]
        self.docs_collection = self.db["documents"]

        # Azure Blob setup
        self.blob_connection_string = os.environ.get("AZURE_BLOB_CONN")
        self.blob_container = os.environ.get("AZURE_CONTAINER", "documents")
        self.blob_service_client = None
        if self.blob_connection_string:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.blob_connection_string
                )
                logger.info("Azure Blob Storage initialized")
            except Exception as e:
                logger.warning(f"Azure not configured: {e}")

        # Prometheus metrics
        self.jobs_processed = Counter("jobs_processed_total", "Total jobs processed", ["status"])
        self.jobs_failed = Counter("jobs_failed_total", "Total jobs failed")
        self.documents_downloaded = Counter("documents_downloaded_total", "Docs downloaded")
        self.documents_uploaded = Counter("documents_uploaded_total", "Docs uploaded")
        self.active_jobs = Gauge("active_jobs", "Jobs currently processing")
        self.pending_jobs = Gauge("pending_jobs", "Pending jobs")
        self.completed_jobs = Gauge("completed_jobs", "Completed jobs")
        self.processing_time = Summary("job_processing_duration_seconds", "Job processing time")
        self.download_batch_size = Histogram("download_batch_size", "Docs per batch")

        logger.info("Downloader initialized")

    def claim_job(self):
        """Find a pending job and atomically claim it"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=10)
        job = self.collection.find_one_and_update(
            {
                "jobStatus": "pending",
                "$or": [{"lockedAt": {"$exists": False}}, {"lockedAt": {"$lt": cutoff_time}}],
            },
            {
                "$set": {
                    "jobStatus": "processing",
                    "processingStages.documentDownload.status": "processing",
                    "processingStages.documentDownload.lastUpdated": datetime.utcnow(),
                    "updatedAt": datetime.utcnow(),
                    "lockedBy": f"worker-{os.getpid()}-{int(time.time())}",
                    "lockedAt": datetime.utcnow(),
                }
            },
            return_document=True,
        )
        if job:
            logger.info(f"Claimed job {job['_id']} for {job.get('companyName', 'Unknown')}")
            self.active_jobs.inc()
        return job

    def _upload_document(self, job_id, doc_num, company_name, cin):
        """Simulate uploading document to Azure"""
        if not self.blob_service_client:
            return None
        try:
            content = f"Document {doc_num} for {company_name} ({cin})"
            blob_name = f"jobs/{job_id}/document_{doc_num}.txt"
            blob_client = self.blob_service_client.get_blob_client(self.blob_container, blob_name)
            blob_client.upload_blob(content, overwrite=True)
            self.documents_uploaded.inc()
            return blob_client.url
        except Exception as e:
            logger.error(f"Blob upload failed: {e}")
            return None

    def _save_document_metadata(self, job_id, doc_num, company_name, cin, blob_url):
        """Save doc metadata to Mongo"""
        self.docs_collection.insert_one(
            {
                "jobId": job_id,
                "documentNumber": doc_num,
                "companyName": company_name,
                "cin": cin,
                "fileName": f"document_{doc_num}.txt",
                "blobUrl": blob_url,
                "createdAt": datetime.utcnow(),
            }
        )

    def process_job(self, job):
        job_id = job["_id"]
        company = job.get("companyName", "Unknown")
        cin = job.get("cin", "Unknown")

        logger.info(f"Processing job {job_id} for {company}")
        start = time.time()
        try:
            total_documents = random.randint(10, 20)
            self.collection.update_one(
                {"_id": job_id},
                {"$set": {"processingStages.documentDownload.totalDocuments": total_documents}},
            )

            for i in range(total_documents):
                time.sleep(0.5)  # simulate download
                self.documents_downloaded.inc()
                blob_url = self._upload_document(job_id, i + 1, company, cin)
                self._save_document_metadata(job_id, i + 1, company, cin, blob_url)

            self.collection.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "jobStatus": "completed",
                        "processingStages.documentDownload.status": "completed",
                        "updatedAt": datetime.utcnow(),
                    },
                    "$unset": {"lockedBy": "", "lockedAt": ""},
                },
            )
            self.jobs_processed.labels(status="completed").inc()
            self.completed_jobs.inc()
            logger.info(f"Job {job_id} completed")
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            self.collection.update_one(
                {"_id": job_id},
                {
                    "$set": {
                        "jobStatus": "failed",
                        "processingStages.documentDownload.status": "failed",
                        "updatedAt": datetime.utcnow(),
                    },
                    "$unset": {"lockedBy": "", "lockedAt": ""},
                },
            )
            self.jobs_failed.inc()
        finally:
            self.active_jobs.dec()
            self.processing_time.observe(time.time() - start)

    def run(self):
        job = self.claim_job()
        if not job:
            logger.info("No pending jobs. Exiting.")
            sys.exit(0)
        self.process_job(job)


# Flask metrics server
app = Flask(__name__)


@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}


def start_metrics_server():
    app.run(host="0.0.0.0", port=9100)


if __name__ == "__main__":
    threading.Thread(target=start_metrics_server, daemon=True).start()
    downloader = DocumentDownloader()
    downloader.run()
