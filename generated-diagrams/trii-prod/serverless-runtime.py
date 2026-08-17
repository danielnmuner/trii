from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import APIGateway
from diagrams.aws.storage import S3
from diagrams.custom import Custom


OUTPUT_DIR = Path("generated-diagrams/trii-prod")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STREAMLIT_ICON = Path("generated-diagrams/streamlit.png").resolve().as_posix()

graph_attr = {
    "fontsize": "18",
    "labelloc": "t",
    "pad": "0.4",
    "ranksep": "1.0",
    "nodesep": "0.8",
    "splines": "spline",
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
    streamlit_operator = Custom("Streamlit\noperator", STREAMLIT_ICON)

    with Cluster("AWS prod"):
        http_api = APIGateway("HTTP API")
        with Cluster("Synchronous API handling"):
            api_handler = Lambda("api_handler\nLambda")

        with Cluster("AI orchestration"):
            ai_handler = Lambda("ai_handler\nLambda")
            bedrock_nova = Bedrock("Bedrock\nNova Pro")

        with Cluster("Core data stores"):
            current_snapshots_table = Dynamodb("trii-prod-current-snapshots")
            stock_orders_table = Dynamodb("trii-prod-stock-orders")
            parsed_invoices_table = Dynamodb("trii-prod-parsed-invoices")
            source_documents_bucket = S3("trii-prod-source-documents")

    streamlit_operator >> Edge(label="send request / prompt") >> http_api >> api_handler

    api_handler >> Edge(label="save snapshot", color="firebrick") >> current_snapshots_table
    api_handler >> Edge(label="save orders", color="firebrick") >> stock_orders_table
    api_handler >> Edge(label="save invoice", color="firebrick") >> parsed_invoices_table
    api_handler >> Edge(label="save document", color="firebrick") >> source_documents_bucket

    api_handler >> Edge(label="call AI Lambda", color="steelblue") >> ai_handler
    ai_handler >> Edge(label="read snapshots", color="darkgreen", style="dashed") >> current_snapshots_table
    ai_handler >> Edge(label="read orders", color="darkgreen", style="dashed") >> stock_orders_table
    ai_handler >> Edge(label="read invoices", color="darkgreen", style="dashed") >> parsed_invoices_table
    ai_handler >> Edge(label="read docs", color="darkgreen", style="dashed") >> source_documents_bucket
    ai_handler >> Edge(label="invoke model", color="steelblue") >> bedrock_nova
    bedrock_nova >> Edge(label="model output", color="steelblue") >> ai_handler
    ai_handler >> Edge() >> api_handler
    api_handler >> Edge(label="return response") >> http_api >> streamlit_operator
