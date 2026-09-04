from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import Eventbridge
from diagrams.aws.network import APIGateway
from diagrams.aws.storage import S3
from diagrams.custom import Custom


OUTPUT_DIR = Path("generated-diagrams/trii-prod")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
STREAMLIT_ICON = Path("generated-diagrams/streamlit.png").resolve().as_posix()
CHROME_EXTENSION_ICON = Path("streamlit_app/chrome-ext.png").resolve().as_posix()

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
    chrome_extension = Custom("Chrome\nextension", CHROME_EXTENSION_ICON)

    with Cluster("AWS prod"):
        http_api = APIGateway("HTTP API")

        with Cluster("Synchronous API handling"):
            api_handler = Lambda("api_handler\nLambda")

        with Cluster("Background analytics"):
            historic_stats_updater = Lambda("historic_stats_updater\nLambda")
            daily_closing_snapshots_updater = Lambda("daily_closing_snapshots_updater\nLambda")
            analytics_catalog_updater = Lambda("analytics_catalog_updater\nLambda")
            session_vectors_updater = Lambda("session_vectors_updater\nLambda")
            current_snapshots_pruner = Lambda("current_snapshots_pruner\nLambda\n(stream + manual)")
            daily_closing_schedule = Eventbridge("24h closing\nschedule")

        with Cluster("Operational data stores"):
            with Cluster("API persistence"):
                current_snapshots_table = Dynamodb("trii-prod-current-snapshots")
                stock_orders_table = Dynamodb("trii-prod-stock-orders")
                source_documents_bucket = S3("trii-prod-source-documents")

            with Cluster("Analytics persistence"):
                historic_stats_table = Dynamodb("trii-prod-historic-stats")
                daily_closing_snapshots_table = Dynamodb("trii-prod-daily-closing-snapshots")
                analytics_catalog_table = Dynamodb("trii-prod-analytics-catalog")
                session_vectors_table = Dynamodb("trii-prod-session-vectors\n(120h TTL)")

    streamlit_operator >> Edge(label="read analytics / upload docs") >> http_api >> api_handler
    chrome_extension >> Edge(label="send snapshots / orders") >> http_api

    api_handler >> Edge(label="write snapshot", color="firebrick") >> current_snapshots_table
    api_handler >> Edge(label="write orders", color="firebrick") >> stock_orders_table
    api_handler >> Edge(label="store files", color="firebrick") >> source_documents_bucket

    current_snapshots_table >> Edge(label="stream INSERTs", color="darkorange") >> historic_stats_updater
    current_snapshots_table >> Edge(label="stream INSERTs", color="royalblue") >> analytics_catalog_updater
    current_snapshots_table >> Edge(label="stream INSERTs", color="deepskyblue4") >> session_vectors_updater
    current_snapshots_table >> Edge(label="stream INSERTs", color="firebrick4") >> current_snapshots_pruner
    historic_stats_updater >> Edge(label="update stats", color="darkorange") >> historic_stats_table
    daily_closing_schedule >> Edge(label="run every 24h", color="mediumpurple") >> daily_closing_snapshots_updater
    daily_closing_snapshots_updater >> Edge(label="read daily snapshots", color="mediumpurple", style="dashed") >> current_snapshots_table
    daily_closing_snapshots_updater >> Edge(label="store daily closing", color="mediumpurple") >> daily_closing_snapshots_table
    session_vectors_updater >> Edge(label="maintain manifest + segments", color="deepskyblue4") >> session_vectors_table
    current_snapshots_pruner >> Edge(label="delete stale\nsnapshots > 2", color="firebrick4") >> current_snapshots_table

    analytics_catalog_updater >> Edge(
        label="overwrite latest\nrecord per symbol",
        color="royalblue",
    ) >> analytics_catalog_table

    api_handler >> Edge(label="return response") >> http_api >> streamlit_operator
    http_api >> Edge(label="acknowledge ingest") >> chrome_extension
    analytics_catalog_table >> Edge(
        label="GetItem catalog\nprojection",
        color="royalblue",
        style="dashed",
    ) >> api_handler
    session_vectors_table >> Edge(
        label="query session vector\ndays + head + segments",
        color="deepskyblue4",
        style="dashed",
    ) >> api_handler
