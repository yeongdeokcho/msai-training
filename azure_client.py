from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import *
from azure.storage.blob import BlobServiceClient
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
import json
from typing import List, Dict, Any
from config import Config


class AzureClients:
    def __init__(self, config: Config):
        self.config = config
        # Search용 KeyCredential 준비
        self.search_key_credential = AzureKeyCredential(
            self.config.AZURE_SEARCH_ADMIN_KEY
        )
        self.credential = DefaultAzureCredential()
        self._setup_clients()
        self._setup_search_index()

    def _setup_clients(self):
        """Azure 클라이언트 초기화"""
        # Search 클라이언트(API Key 인증)
        self.search_client = SearchClient(
            endpoint=self.config.AZURE_SEARCH_ENDPOINT,
            index_name=self.config.AZURE_SEARCH_INDEX_NAME,
            credential=self.search_key_credential,
        )

        self.search_index_client = SearchIndexClient(
            endpoint=self.config.AZURE_SEARCH_ENDPOINT,
            credential=self.search_key_credential,
        )

        self.blob_client = BlobServiceClient.from_connection_string(
            self.config.AZURE_STORAGE_CONNECTION_STRING
        )

        # OpenAI 클라이언트
        self.openai_client = AzureOpenAI(
            azure_endpoint=self.config.AZURE_OPENAI_ENDPOINT,
            api_key=self.config.AZURE_OPENAI_API_KEY,
            api_version=self.config.AZURE_OPENAI_API_VERSION,
        )

    def _setup_search_index(self):
        """검색 인덱스 생성"""
        fields = [
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SearchableField(name="summary", type=SearchFieldDataType.String),
            SearchableField(name="incident_type", type=SearchFieldDataType.String),
            SearchableField(name="root_cause", type=SearchFieldDataType.String),
            SearchableField(name="emergency_actions", type=SearchFieldDataType.String),
            SearchField(
                name="content_vector",
                type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                searchable=True,
                vector_search_dimensions=1536,
                vector_search_profile_name="default-vector-profile",
            ),
            SimpleField(name="file_path", type=SearchFieldDataType.String),
            SimpleField(name="upload_date", type=SearchFieldDataType.DateTimeOffset),
        ]

        vector_search = VectorSearch(
            profiles=[
                VectorSearchProfile(
                    name="default-vector-profile",
                    algorithm_configuration_name="default-algorithm",
                )
            ],
            algorithms=[HnswAlgorithmConfiguration(name="default-algorithm")],
        )

        index = SearchIndex(
            name=self.config.AZURE_SEARCH_INDEX_NAME,
            fields=fields,
            vector_search=vector_search,
        )

        try:
            self.search_index_client.create_or_update_index(index)
        except Exception as e:
            print(f"인덱스 생성 중 오류: {e}")
