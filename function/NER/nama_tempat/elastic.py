from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Retrieve Elasticsearch credentials from environment variables
ELASTICSEARCH_URL = os.getenv("ELASTICSEARCH_URL")
ELASTICSEARCH_USERNAME = os.getenv("ELASTICSEARCH_USERNAME")
ELASTICSEARCH_PASSWORD = os.getenv("ELASTICSEARCH_PASSWORD")

# Connect to Elasticsearch using credentials from .env
es = Elasticsearch(
    ELASTICSEARCH_URL,
    basic_auth=(ELASTICSEARCH_USERNAME, ELASTICSEARCH_PASSWORD)
)

# Define the index and target date range (1 Nov 2025 to now)
index_name = "socmed-instagram-comments"
start_date = datetime(2025, 11, 1)

# Function to read the location data from text files
def read_location_data(folder, files):
    locations = set()
    for file_name in files:
        file_path = os.path.join(folder, file_name)
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                locations.update([line.strip().lower() for line in file.readlines()])
    return locations

# Function to check if the text contains location keywords
def extract_locations_from_text(text, locations):
    found_locations = []
    for location in locations:
        if location in text.lower():  # Case insensitive matching
            found_locations.append(location)
    return found_locations

# Read location data from files
files = [
    "daerah.txt",
    "provinsi.txt",
    "kecamatan.txt",
    "kelurahan.txt"
]
folder = "/path/to/your/files"
locations_from_files = read_location_data(folder, files)

# Perform a search to find documents with created_at before 1 November 2025
search_query = {
    "query": {
        "range": {
            "created_at": {
                "lt": start_date.strftime("%Y-%m-%dT%H:%M:%S%z")
            }
        }
    }
}

# Search for documents that match the date condition
search_results = es.search(index=index_name, body=search_query, size=1000)

# Loop through the search results and update the matching documents
for hit in search_results['hits']['hits']:
    doc_id = hit["_id"]
    doc_text = hit["_source"].get("text", "")
    
    # Extract locations from the 'text' field
    found_locations = extract_locations_from_text(doc_text, locations_from_files)
    
    # Prepare the update document
    doc_update = {
        "doc": {
            "ner_custom": {
                "person": [],  # You can add data for 'person' if needed
                "location": found_locations  # Update location based on text match
            },
            "created_at": start_date.strftime("%Y-%m-%dT%H:%M:%S%z")  # Set the date to 1 November 2025
        }
    }
    
    # Perform the update
    update_response = es.update(index=index_name, id=doc_id, body=doc_update)
    
    if update_response["result"] == "updated":
        print(f"[INFO] Document {doc_id} updated successfully with new location and date.")
    else:
        print(f"[ERROR] Failed to update document {doc_id}.")
