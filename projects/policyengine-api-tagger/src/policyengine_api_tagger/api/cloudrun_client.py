from google.cloud.run_v2 import (
    ServicesAsyncClient,
    TrafficTarget,
    TrafficTargetAllocationType,
    UpdateServiceRequest,
    GetServiceRequest,
)
import logging

log = logging.getLogger(__file__)


class CloudrunClient:
    async def tag_revision(
        self, cloudrun_service_name: str, revision_name: str, tag: str
    ) -> str:
        # Not clearly documented anywhere I could find. the creation of this
        # client __MUST__ be done in the same async threadpool as the one
        # that actually uses it.
        # Generally speaking this means you should always create the client
        # right where you use it.
        services_client = ServicesAsyncClient()
        log.info(f"Getting service information for service {cloudrun_service_name}")
        service = await services_client.get_service(
            GetServiceRequest(name=cloudrun_service_name)
        )
        log.info(f"Looking for revision {revision_name}")
        # If it exists, just return it.
        for traffic in service.traffic:
            if traffic.revision == revision_name:
                if traffic.tag == tag:
                    log.info(f"Revision {revision_name} is already tagged with {tag}")
                    return service.uri
        # If tagged elsewhere, remove the tag from the existing revision
        removed = [t for t in service.traffic if t.tag == tag]
        for traffic in removed:
            log.info(
                f"Tag {tag} already exists on revision {traffic.revision}, removing"
            )
        service.traffic = [t for t in service.traffic if t.tag != tag]

        # Doesnt exist, so create it
        new_traffic = self._create_new_traffic(revision_name=revision_name, tag=tag)
        service.traffic.append(new_traffic)

        log.info(f"Tagging revision {revision_name} with tag {tag}")
        # I have no direct documentation of this but
        # this _should_ fail if the record has already been updated because
        # the original request includes an "etag" which, when provided in this
        # update request _should_ ask the cloudrun service to only succeed
        # if the record has not changed between the original get and this update.
        # none of this is explicitly documented for cloudrun or this call though.
        await services_client.update_service(
            UpdateServiceRequest(service=service, update_mask={"paths": ["traffic"]})
        )
        return service.uri

    def _create_new_traffic(self, revision_name: str, tag: str) -> TrafficTarget:
        new_traffic = TrafficTarget()
        new_traffic.revision = revision_name
        new_traffic.percent = 0
        new_traffic.tag = tag
        new_traffic.type_ = (
            TrafficTargetAllocationType.TRAFFIC_TARGET_ALLOCATION_TYPE_REVISION
        )
        return new_traffic
