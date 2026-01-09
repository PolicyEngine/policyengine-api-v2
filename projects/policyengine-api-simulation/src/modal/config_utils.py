"""
Configuration utilities for Modal image building.
"""

import logging


def snapshot_models():
    """Pre-load models at image build time for fast cold starts."""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    logger.info("Pre-loading US tax-benefit system...")
    from policyengine_us import CountryTaxBenefitSystem as USSystem

    USSystem()

    logger.info("Pre-loading UK tax-benefit system...")
    from policyengine_uk import CountryTaxBenefitSystem as UKSystem

    UKSystem()

    logger.info("Models pre-loaded into image snapshot")
