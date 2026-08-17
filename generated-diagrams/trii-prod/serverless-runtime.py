from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import SimpleQueueServiceSqs
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import APIGateway
from diagrams.aws.storage import S3
from diagrams.onprem.client import User


OUTPUT_DIR = Path("generated-diagrams/trii-prod")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

graph_attr = {
    "fontsize": "18",
    "labelloc": "t",
    "pad": "0.4",
    "ranksep": "1.0",
    "nodesep": "0.8",
    "splines": "ortho",
}

node_attr = {
    "fontsize": "12",
}


with Diagram(
    "Trii prod serverless runtime",
    filename=str(OUTPUT_DIR / "serverless-runtime"),
    outformat="png",
    direction="LR",
    show=False,
    graph_attr=graph_attr,
    node_attr=node_attr,
):
    streamlit_operator = User("Streamlit\noperator")

    with Cluster("AWS prod"):
        http_api = APIGateway("HTTP API")

        with Cluster("Synchronous API handling"):
            api_handler = Lambda("api_handler\nLambda")

        with Cluster("Core data stores"):
            current_snapshots_table = Dynamodb("trii-prod-current-snapshots")
            stock_orders_table = Dynamodb("trii-prod-stock-orders")
            parsed_invoices_table = Dynamodb("trii-prod-parsed-invoices")
            source_documents_bucket = S3("trii-prod-source-documents")

        with Cluster("AI orchestration"):
            ai_jobs_queue = SimpleQueueServiceSqs("trii-prod-ai-jobs")
            process_ai_job = Lambda("process_ai_job\nLambda")
            bedrock_nova = Bedrock("Bedrock\nNova Pro")

    streamlit_operator >> Edge(label="POST /snapshots\nPOST /orders\nPOST /invoices\nGET /snapshots/{id}") >> http_api
    http_api >> api_handler

    api_handler >> Edge(label="write snapshot") >> current_snapshots_table
    api_handler >> Edge(label="read snapshot status") >> current_snapshots_table
    api_handler >> Edge(label="write orders") >> stock_orders_table
    api_handler >> Edge(label="write parsed invoice") >> parsed_invoices_table
    api_handler >> Edge(label="store source files") >> source_documents_bucket
    api_handler >> Edge(label="enqueue AI job") >> ai_jobs_queue

    ai_jobs_queue >> process_ai_job
    process_ai_job >> Edge(label="read snapshot") >> current_snapshots_table
    process_ai_job >> Edge(label="invoke model") >> bedrock_nova
    process_ai_job >> Edge(label="update snapshot") >> current_snapshots_table
