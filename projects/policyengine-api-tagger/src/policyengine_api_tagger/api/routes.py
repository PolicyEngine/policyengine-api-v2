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
    async def cleanup_old_revisions(
        keep: int = 5, delete_revisions: bool = False
    ) -> CleanupResult:
        """
        Clean up old Cloud Run revisions and their associated tags.

        This endpoint removes traffic tags for old revisions and optionally
        deletes the revisions themselves. It maintains safeguards to ensure
        the most recent US and UK versions are never deleted.

        Args:
            keep: Number of recent deployments to keep (default: 5)
            delete_revisions: If true, also delete old Cloud Run revisions

        Returns:
            CleanupResult with details of what was cleaned up
        """
        if cleanup is None:
            raise HTTPException(
                status_code=503,
                detail="Cleanup functionality not configured. "
                "Ensure simulation_service_name, project_id, and region are set.",
            )

        if keep < 1:
            raise HTTPException(
                status_code=400, detail="keep parameter must be at least 1"
            )

        log.info(
            f"Starting cleanup: keep={keep}, delete_revisions={delete_revisions}"
        )
        result = await cleanup.cleanup(
            keep_count=keep, delete_revisions=delete_revisions
        )
        log.info(
            f"Cleanup complete: kept={len(result.revisions_kept)}, "
            f"tags_removed={len(result.tags_removed)}, "
            f"files_deleted={len(result.metadata_files_deleted)}, "
            f"revisions_removed={len(result.revisions_removed)}"
        )
        return result

    return router


def add_all_routes(
    api: FastAPI, tagger: RevisionTagger, cleanup: RevisionCleanup | None = None
):
    api.include_router(create_router(tagger, cleanup))
