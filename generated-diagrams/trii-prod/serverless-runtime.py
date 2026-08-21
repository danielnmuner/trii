from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Dynamodb
from diagrams.aws.integration import Eventbridge
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import APIGateway
from diagrams.aws.storage import S3
from diagrams.custom import Custom
from diagrams.onprem.ci import GithubActions


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
    historic_stats_backfill_workflow = GithubActions("historic-stats-backfill\nworkflow")

    with Cluster("AWS prod"):
        http_api = APIGateway("HTTP API")

        with Cluster("Synchronous API handling"):
            api_handler = Lambda("api_handler\nLambda")

        with Cluster("Background analytics"):
            historic_stats_updater = Lambda("historic_stats_updater\nLambda")
            historic_stats_backfill = Lambda("historic_stats_backfill\nLambda")
            daily_closing_snapshots_updater = Lambda("daily_closing_snapshots_updater\nLambda")
            market_ai_recommendation_handler = Lambda("market_ai_recommendation_handler\nLambda")
            daily_closing_schedule = Eventbridge("24h closing\nschedule")

        with Cluster("Bedrock inference"):
            bedrock_nova = Bedrock("Bedrock\nNova Pro")

        with Cluster("Operational data stores"):
            with Cluster("API persistence"):
                snapshot_ingestion_checksums = Dynamodb("trii-prod-snapshot-ingestion-checksums")
                snapshot_ingestion_raw = Dynamodb("trii-prod-snapshot-ingestion-raw")
                current_snapshots_table = Dynamodb("trii-prod-current-snapshots")
                stock_orders_table = Dynamodb("trii-prod-stock-orders")
                source_documents_bucket = S3("trii-prod-source-documents")

            with Cluster("Analytics persistence"):
                historic_stats_table = Dynamodb("trii-prod-historic-stats")
                processed_stats_events_table = Dynamodb("trii-prod-processed-stats-events")
                daily_closing_snapshots_table = Dynamodb("trii-prod-daily-closing-snapshots")
                zscore_opportunities_table = Dynamodb("trii-prod-zscore-opportunities")
                market_ai_recommendations_table = Dynamodb("trii-prod-market-ai-recommendations")

    streamlit_operator >> Edge(label="read analytics / upload docs") >> http_api >> api_handler
    chrome_extension >> Edge(label="send snapshots / orders") >> http_api

    api_handler >> Edge(label="write checksum", color="firebrick") >> snapshot_ingestion_checksums
    api_handler >> Edge(label="write raw snapshot", color="firebrick") >> snapshot_ingestion_raw
    api_handler >> Edge(label="write snapshot", color="firebrick") >> current_snapshots_table
    api_handler >> Edge(label="write orders", color="firebrick") >> stock_orders_table
    api_handler >> Edge(label="store files", color="firebrick") >> source_documents_bucket

    current_snapshots_table >> Edge(label="stream inserts", color="darkorange") >> historic_stats_updater
    historic_stats_updater >> Edge(label="update stats", color="darkorange") >> historic_stats_table
    historic_stats_updater >> Edge(label="write idempotency", color="darkorange") >> processed_stats_events_table
    historic_stats_updater >> Edge(label="read approved orders", color="darkorange", style="dashed") >> stock_orders_table
    historic_stats_updater >> Edge(label="store z-score events", color="darkorange") >> zscore_opportunities_table
    historic_stats_updater >> Edge(label="trigger AI rules", color="steelblue") >> market_ai_recommendation_handler

    historic_stats_backfill_workflow >> Edge(label="manual invoke", color="slateblue") >> historic_stats_backfill
    historic_stats_backfill >> Edge(label="query raw history", color="slateblue", style="dashed") >> current_snapshots_table
    historic_stats_backfill >> Edge(label="rebuild metrics", color="slateblue") >> historic_stats_table

    daily_closing_schedule >> Edge(label="run every 24h", color="mediumpurple") >> daily_closing_snapshots_updater
    daily_closing_snapshots_updater >> Edge(label="read daily snapshots", color="mediumpurple", style="dashed") >> current_snapshots_table
    daily_closing_snapshots_updater >> Edge(label="store daily closing", color="mediumpurple") >> daily_closing_snapshots_table

    market_ai_recommendation_handler >> Edge(label="read current + prev", color="darkgreen", style="dashed") >> current_snapshots_table
    market_ai_recommendation_handler >> Edge(label="read stats bucket", color="darkgreen", style="dashed") >> historic_stats_table
    market_ai_recommendation_handler >> Edge(label="invoke model", color="steelblue") >> bedrock_nova
    bedrock_nova >> Edge(color="steelblue") >> market_ai_recommendation_handler
    market_ai_recommendation_handler >> Edge(label="store AI recommendation", color="steelblue") >> market_ai_recommendations_table

    api_handler >> Edge(label="return response") >> http_api >> streamlit_operator
    http_api >> Edge(label="acknowledge ingest") >> chrome_extension
