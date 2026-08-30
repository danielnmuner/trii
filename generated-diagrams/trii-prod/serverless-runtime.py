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
    analytics_catalog_backfill_workflow = GithubActions("analytics-catalog-backfill\nworkflow")

    with Cluster("AWS prod"):
        http_api = APIGateway("HTTP API")

        with Cluster("Synchronous API handling"):
            api_handler = Lambda("api_handler\nLambda")

        with Cluster("Background analytics"):
            historic_stats_updater = Lambda("historic_stats_updater\nLambda")
            historic_stats_backfill = Lambda("historic_stats_backfill\nLambda")
            daily_closing_snapshots_updater = Lambda("daily_closing_snapshots_updater\nLambda")
            zscore_opportunities_sampler = Lambda("zscore_opportunities_sampler\nLambda")
            analytics_catalog_updater = Lambda("analytics_catalog_updater\nLambda")
            analytics_catalog_backfill = Lambda("analytics_catalog_backfill\nLambda")
            session_vectors_updater = Lambda("session_vectors_updater\nLambda\n(stream + manual)")
            market_ai_recommendation_handler = Lambda("market_ai_recommendation_handler\nLambda")
            daily_closing_schedule = Eventbridge("24h closing\nschedule")
            zscore_sampling_schedule = Eventbridge("10 min z-score\nschedule")

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
                analytics_catalog_table = Dynamodb("trii-prod-analytics-catalog")
                zscore_opportunities_table = Dynamodb("trii-prod-zscore-opportunities")
                session_vectors_table = Dynamodb("trii-prod-session-vectors")
                market_ai_recommendations_table = Dynamodb("trii-prod-market-ai-recommendations")

    streamlit_operator >> Edge(label="read analytics / upload docs") >> http_api >> api_handler
    chrome_extension >> Edge(label="send snapshots / orders") >> http_api

    api_handler >> Edge(label="write checksum", color="firebrick") >> snapshot_ingestion_checksums
    api_handler >> Edge(label="write raw snapshot", color="firebrick") >> snapshot_ingestion_raw
    api_handler >> Edge(label="write snapshot", color="firebrick") >> current_snapshots_table
    api_handler >> Edge(label="write orders", color="firebrick") >> stock_orders_table
    api_handler >> Edge(label="store files", color="firebrick") >> source_documents_bucket

    current_snapshots_table >> Edge(label="stream INSERTs", color="darkorange") >> historic_stats_updater
    current_snapshots_table >> Edge(label="stream INSERTs", color="royalblue") >> analytics_catalog_updater
    current_snapshots_table >> Edge(label="stream INSERTs", color="deepskyblue4") >> session_vectors_updater
    historic_stats_updater >> Edge(label="update stats", color="darkorange") >> historic_stats_table
    historic_stats_updater >> Edge(label="write idempotency", color="darkorange") >> processed_stats_events_table
    historic_stats_updater >> Edge(label="trigger AI rules", color="steelblue") >> market_ai_recommendation_handler

    historic_stats_backfill_workflow >> Edge(label="manual invoke", color="slateblue") >> historic_stats_backfill
    historic_stats_backfill >> Edge(label="query raw history", color="slateblue", style="dashed") >> current_snapshots_table
    historic_stats_backfill >> Edge(label="rebuild metrics", color="slateblue") >> historic_stats_table
    analytics_catalog_backfill_workflow >> Edge(label="manual invoke", color="dodgerblue4") >> analytics_catalog_backfill
    analytics_catalog_backfill >> Edge(label="query latest trading date", color="dodgerblue4", style="dashed") >> current_snapshots_table
    analytics_catalog_backfill >> Edge(label="overwrite catalog", color="dodgerblue4") >> analytics_catalog_table

    daily_closing_schedule >> Edge(label="run every 24h", color="mediumpurple") >> daily_closing_snapshots_updater
    daily_closing_snapshots_updater >> Edge(label="read daily snapshots", color="mediumpurple", style="dashed") >> current_snapshots_table
    daily_closing_snapshots_updater >> Edge(label="store daily closing", color="mediumpurple") >> daily_closing_snapshots_table
    zscore_sampling_schedule >> Edge(label="run every 10m", color="darkgoldenrod4") >> zscore_opportunities_sampler
    zscore_opportunities_sampler >> Edge(label="read latest day snapshots", color="darkgoldenrod4", style="dashed") >> current_snapshots_table
    zscore_opportunities_sampler >> Edge(label="read z-score stats", color="darkgoldenrod4", style="dashed") >> historic_stats_table
    zscore_opportunities_sampler >> Edge(label="read approved orders", color="darkgoldenrod4", style="dashed") >> stock_orders_table
    zscore_opportunities_sampler >> Edge(label="upsert sampled records", color="darkgoldenrod4") >> zscore_opportunities_table
    session_vectors_updater >> Edge(label="maintain manifest + segments", color="deepskyblue4") >> session_vectors_table
    analytics_catalog_table >> Edge(
        label="manual rebuild:\nresolve latest trading date",
        color="deepskyblue4",
        style="dashed",
    ) >> session_vectors_updater
    session_vectors_updater >> Edge(
        label="manual rebuild:\nquery latest day snapshots",
        color="deepskyblue4",
        style="dashed",
    ) >> current_snapshots_table

    analytics_catalog_updater >> Edge(
        label="overwrite latest\nrecord per symbol",
        color="royalblue",
    ) >> analytics_catalog_table

    market_ai_recommendation_handler >> Edge(label="read current + prev", color="darkgreen", style="dashed") >> current_snapshots_table
    market_ai_recommendation_handler >> Edge(label="read stats bucket", color="darkgreen", style="dashed") >> historic_stats_table
    market_ai_recommendation_handler >> Edge(label="invoke model", color="steelblue") >> bedrock_nova
    bedrock_nova >> Edge(color="steelblue") >> market_ai_recommendation_handler
    market_ai_recommendation_handler >> Edge(label="store AI recommendation", color="steelblue") >> market_ai_recommendations_table

    api_handler >> Edge(label="return response") >> http_api >> streamlit_operator
    http_api >> Edge(label="acknowledge ingest") >> chrome_extension
    analytics_catalog_table >> Edge(
        label="GetItem catalog\nprojection",
        color="royalblue",
        style="dashed",
    ) >> api_handler
    session_vectors_table >> Edge(
        label="query session vector\nhead + segments",
        color="deepskyblue4",
        style="dashed",
    ) >> api_handler
