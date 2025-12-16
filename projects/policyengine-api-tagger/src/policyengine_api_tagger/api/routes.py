from fastapi import FastAPI, HTTPException
from fastapi.routing import APIRouter

from policyengine_api_tagger.api.revision_tagger import RevisionTagger
from policyengine_api_tagger.api.revision_cleanup import RevisionCleanup, CleanupResult
import logging

log = logging.getLogger(__file__)


def create_router(
    tagger: RevisionTagger, cleanup: RevisionCleanup | None = None
) -> APIRouter:
    router = APIRouter()

    @router.get("/tag")
    async def get_tag_uri(country: str, model_version: str) -> str:
        uri = await tagger.tag(country, model_version)
        if uri is None:
            log.info(f"No tag url for country {country}, model_version {model_version}")
            raise HTTPException(status_code=404, detail="Item not found")
        log.info(f"Got URI {uri} for country {country} model_version {model_version}")
        return uri

    @router.post("/cleanup")
    async def cleanup_old_revisions(keep: int = 40) -> CleanupResult:
        """
        Clean up old traffic tags, keeping the specified number.

        This endpoint:
        1. Gets all existing traffic tags from Cloud Run
        2. Identifies the newest US and UK tags (always kept as safeguards)
        3. Keeps the top `keep` tags total (including safeguards)
        4. Updates the traffic configuration in one atomic operation

        Metadata files are NOT touched - they enable on-demand tag recreation.

        Args:
            keep: Number of tags to keep (default: 40, minimum: 2)

        Returns:
            CleanupResult with details of what was cleaned up
        """
        if cleanup is None:
            raise HTTPException(
                status_code=503,
                detail="Cleanup functionality not configured. "
                "Ensure simulation_service_name, project_id, and region are set.",
            )

        if keep < 2:
            raise HTTPException(
                status_code=400,
                detail="keep parameter must be at least 2 (for US + UK safeguards)",
            )

        log.info(f"Starting cleanup with keep={keep}")
        result = await cleanup.cleanup(keep_count=keep)
        log.info(
            f"Cleanup complete: total_tags={result.total_tags_found}, "
            f"kept={len(result.tags_kept)}, removed={len(result.tags_removed)}"
        )
        return result

    return router


def add_all_routes(
    api: FastAPI, tagger: RevisionTagger, cleanup: RevisionCleanup | None = None
):
    api.include_router(create_router(tagger, cleanup))
