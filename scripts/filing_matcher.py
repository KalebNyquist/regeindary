"""Filing Matcher - Optimized entity-filing relationship matching.

This module provides a class-based approach to matching filings with their
corresponding organizations, using either bulk write operations or MongoDB
aggregation pipelines for improved performance.

Usage:
    from filing_matcher import FilingMatcher
    from utils import mongo_regeindary, collections_map

    matcher = FilingMatcher(mongo_regeindary, collections_map)
    stats = matcher.match_all(method="bulk")  # or method="aggregation"
    print(stats)

Refactored by Claude Opus 4.5 from Kaleb Nyquist's utils.py match_filing() and run_all_match_filings()
    Claude: https://claude.ai/share/8eefb902-602c-4369-a1d4-49ad16a5b8cf
    Kaleb Nyquist: contact@kalebnyquist.me
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal
import logging
import pymongo
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError
from bson import ObjectId

from utils import ensure_indexes

logger = logging.getLogger(__name__)


# =========================================================================
# Data Classes for Type Safety and Clean Return Values
# =========================================================================

@dataclass
class RegistryConfig:
    """
    Configuration for registry-specific matching behavior.

    Different registries have different quirks:
    - US: If EIN was imported as an integer (older version of code), needs zero-padding to 9 digits to restore leading 0's
    - England/Wales: Subsidiaries
    - Others: Standard entityId matcging
    """
    name: str
    matching_field: str = "entityId"                    # 🡨 Field to match on
    transform_id: Optional[callable] = None             # 🡨 Optional ID transformation
    subsidiary_filter: Optional[dict] = None            # 🡨 Extra filter for subsidiaries


@dataclass
class MatchingStats:
    """Statistics from a matching operation. Using a dataclass gives us clean string representation for logging."""
    total_processed: int = 0
    matched: int = 0
    orphans_created: int = 0
    orphans_skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    method: str = ""

    def __str__(self) -> str:
        """Human-readable summary for console output."""
        return (
            f"Matching Progress ({self.method} method)\n"
            f"  ✔ Processed: {self.total_processed:,}\n"
            f"  ✔ Matched: {self.matched:,}\n"
            f"  ⚠ Orphans created: {self.orphans_created:,}\n"
            f"  ⚠ Orphans skipped: {self.orphans_skipped:,}\n"
            f"  ✖ Errors: {self.errors:,}\n"
            f"  ⏱ Duration: {self.duration_seconds:.2f}s"
        )


@dataclass
class BatchResult:
    """Result of processing a single batch of filings."""
    filings_updated: int = 0
    orgs_updated: int = 0
    orphans_created: int = 0
    orphans_skipped: int = 0
    errors: int = 0


# =========================================================================
# Registry Configuration
# =========================================================================

# TODO: move this to the UnitedStates retrieve.py script / plugin
def _us_ein_transform(entity_id) -> str:
    """Transform US EIN to 9-digit zero-padded string.

    The IRS uses 9-digit EINs, but some sources store them without leading zeroes.
    - Example: "12345" versus "000012345"
    - This can be caused by storing as an integer instead of as a string
    """
    return str(entity_id).rjust(9, '0')


REGISTRY_CONFIGS = {
    "United States - Internal Revenue Service - Exempt Organizations Business Master File Extract":
        RegistryConfig(
            name="United States",
            matching_field="entityId",
            transform_id=_us_ein_transform
        ),
    "England and Wales - Charity Commission Register of Charities":
        RegistryConfig(
            name="England and Wales",
            matching_field="entityId",
            subsidiary_filter={
                "$or": [
                     {"subsidiaryIndex": {"$exists": False}},
                     {"subsidiaryIndex": 0}
                 ]
            }
        )
}

DEFAULT_CONFIG = RegistryConfig(name="default", matching_field="entityId")


# =========================================================================
# Main FilingMatcher Class
# =========================================================================

class FilingMatcher:
    """Matches filings to organizations using optimized batch operations.

    Attributes:
        db: MongoDB database instance
        collections: Dictionary mapping collection names to actual names
        batch_size: Number of filings to process per batch
        create_orphans: Whether to create (unlisted but presumed to exist) organizations from unmatched filings

    Example:
        matcher = FilingMatcher(db, collections)
        stats = matcher.match_all(method="bulk")
    """

    def __init__(
            self,
            db,
            collections: dict,
            batch_size: int = 1000,
            create_orphans: bool = False
    ):
        """Initialize the FilingMatcher.

        Args:
            db: MongoDB database instance
            collections: Dict with keys 'organizations', 'filings', and 'registries'
            batch_size: Number of filings to process per batch (default 1000)
            create_orphans: If True, create orgs from orphan filings
        """
        self.db = db
        self.collections = collections
        self.batch_size = batch_size
        self.create_orphans = create_orphans

        # Cache for org lookups - reduces repeated queries
        #   Key: (registry_id, entity_id, [...other identifying datapoints]) tuple
        #   Value: ObjectId of matching org
        self._cache: dict[tuple, ObjectId] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Collection shortcuts
        self._filings = self.db[collections['filings']]
        self._orgs = self.db[collections['organizations']]
        self._registries = self.db[collections['registries']]

    # =========================================================================
    # Public API
    # =========================================================================

    def match_all(
            self,
            method: Literal["bulk", "aggregation"] = "bulk",
            limit: Optional[int] = None
    ) -> MatchingStats:
        """
        Match all unmatched filings to their organizations.

        Args:
            method: "bulk" for bulk_write operations, "aggregation" for pipeline
            limit: Optional limit on number of filings to process

        Returns:
            MatchingStats with counts and timing information
        """
        logger.info(f"Starting matching operation: method={method}, limit={limit}")
        start_time = datetime.now()

        # Ensure indexes exist for performance
        ensure_indexes(collections=['organizations', 'filings'], verbose=False)

        if method == "aggregation":
            stats = self._match_via_aggregation(limit)
        elif method == "bulk":
            stats = self._match_via_bulk(limit)
        else:
            raise ValueError(f"Invalid matching method: {method}")

        stats.duration_seconds = (datetime.now() - start_time).total_seconds()
        stats.method = method

        logger.info(f"Matching progress: {stats.matched:,} matched in {stats.duration_seconds:.2f}s")
        logger.info(f"Cache stats: {self._cache_hits:,} hits, {self._cache_misses:,} misses")

        return stats

    def match_batch(self, filings: list[dict]) -> BatchResult:
        """"Match a specific batch of filings.

        Useful for testing or custom batch processing.

        Args:
             filings: List of filing documents to match

        Returns:
            BatchResult with counts for this batch
        """
        return self._process_batch(filings)

    # =========================================================================
    # Bulk Write Implementation
    # =========================================================================

    def _match_via_bulk(self, limit: Optional[int]) -> MatchingStats:
        """Match filings using batched bulk_write operations.

        This is the fastest method, but requires a lot of memory.

        Algorithm:
        1. Fetch batch of unmatched filings
        2. Resolve org matches for all filings in batch
        3. Build bulk update operations
        4. Execute bulk_write for filings
        5. Execute bulk_write for orgs
        6. Repeat until done
        """
        stats = MatchingStats(method="bulk")

        # Count unmatched filings
        unmatched_filter = {"entityId_mongo": {"$exists": False}}
        total_unmatched = self._filings.count_documents(unmatched_filter)

        if limit:
            total_to_process = min(limit, total_unmatched)
        else:
            total_to_process = total_unmatched

        logger.info(f"Found {total_unmatched:,} unmatched filings, will process {total_to_process:,}")
        logger.info(f"Processing {total_to_process:,} filings in batches of {self.batch_size:,}")

        processed = 0
        skip_count = 0

        # Progress Tracking
        last_progress_time = datetime.now()
        last_progress_count = 0

        while processed < total_to_process:
            # Fetch next batch
            batch = list(
                self._filings.find(unmatched_filter)
                .skip(skip_count)
                .limit(self.batch_size)
                .sort("_id", pymongo.ASCENDING)                # Consistent ordering
            )

            if not batch:
                logger.info("No more unmatched filings found")
                break

            # Process this batch
            result = self._process_batch(batch)

            # Update stats
            stats.matched += result.filings_updated
            stats.orphans_created += result.orphans_created
            stats.orphans_skipped += result.orphans_skipped
            stats.errors += result.errors

            processed += len(batch)
            skip_count += result.orphans_skipped
            stats.total_processed = processed

            # Progress output
            pct = 100 * processed / total_to_process
            progress_message = f"Processed {processed:,}/{total_to_process:,} ({pct:.1f}%)"
            logger.debug(progress_message)
            print(f"\r  {progress_message}", end="")

            # Periodic detailed progress
            update_frequency = 30  # in seconds
            elapsed = (datetime.now() - last_progress_time).total_seconds()
            if elapsed > update_frequency:
                rate = (processed - last_progress_count) / elapsed
                remaining = (total_to_process - processed) / rate if rate > 0 else 0
                rate_message = f"Rate: {rate:.0f} filings/sec, ETA: {remaining/60:.1f} min"
                # TODO: add a few more stats
                logger.debug(rate_message)
                print(f"\n  {rate_message}")
                print(stats)
                last_progress_time = datetime.now()
                last_progress_count = processed

        print()  # Newline after progress
        return stats

    def _process_batch(self, filings: list[dict]) -> BatchResult:
        """Process a single batch of filings.

        This is the core matching logic, separated for testability.
        """
        result = BatchResult()

        if not filings:
            return result

        # Step 1: Resolve org matches for all filings
        # Returns: {filing_id: org_id} for successful matches
        matches, orphan_filings = self._resolve_org_matches(filings)

        # Step 2: Handle orphas
        for filing in orphan_filings:
            if self.create_orphans:
                org_id = self._create_org_from_filing(filing)
                if org_id:
                    matches[filing['_id']] = org_id
                    result.orphans_created += 1
                else:
                    result.orphans_skipped += 1
            else:
                result.orphans_skipped += 1

        if not matches:
            return result

        # Step 3: Build bulk update operations for filings
        filing_updates = [
            UpdateOne(
                {"_id": filing_id},
                {"$set": {"entityId_mongo": org_id}}
            )
            for filing_id, org_id in matches.items()
        ]

        # Step 4: Build bulk update operations for orgs
        # Group filings by org to build $addToSet operations
        org_to_filings: dict[ObjectId, list[ObjectId]] = {}
        for filing_id, org_id in matches.items():
            if org_id not in org_to_filings:
                org_to_filings[org_id] = []
            org_to_filings[org_id].append(filing_id)

        org_updates = [
            UpdateOne(
                {"_id": org_id},
                {"$addToSet": {"filings": {"$each": filing_ids}}}
            )
            for org_id, filing_ids in org_to_filings.items()
        ]

        # Step 5: Execute bulk writes
        try:
            if filing_updates:
                filing_result = self._filings.bulk_write(filing_updates, ordered=False)
                result.filings_updated = filing_result.modified_count
        except BulkWriteError as e:
            logger.error(f"Bulk write error (filings): {e.details}")
            result.errors += len(e.details.get('writeErrors', []))
            result.filings_updated = e.details.get('nModified', 0)

        try:
            if org_updates:
                org_result = self._orgs.bulk_write(org_updates, ordered=False)
                result.orgs_updated = org_result.modified_count
        except BulkWriteError as e:
            logger.error(f"Bulk write error (orgs): {e.details}")
            result.errors += len(e.details.get('writeErrors', []))

        return result

    def _resolve_org_matches(
            self,
            filings: list[dict]
    ) -> tuple[dict[ObjectId, ObjectId], list[dict]]:
        """Resolve organization matches for a batch of filings.

        Uses caching to avoid repeated lookups for the same entity ID.

        Args:
            filings: List of filing documents

        Returns:
            Tuple of:
            - matches: {filing_id: org_id} for successful matches
            - orphans: List of filings with no matching org
        """
        matches: dict[ObjectId, ObjectId] = {}
        orphans: list[dict] = []

        # Group filings by registry for batch lookup
        by_registry: dict[ObjectId, list[dict]] = {}
        for filing in filings:
            reg_id = filing.get('registryID')
            if reg_id not in by_registry:
                by_registry[reg_id] = []
            by_registry[reg_id].append(filing)

        # Process each registry group
        for registry_id, registry_filings in by_registry.items():
            # Get registry config
            registry_name = registry_filings[0].get('registryName', '')
            config = REGISTRY_CONFIGS.get(registry_name, DEFAULT_CONFIG)

            # Collect entity IDs that need lookup (not in cache)
            ids_to_lookup: dict[str, list[dict]] = {}  # entity_id -> [filings]

            for filing in registry_filings:
                entity_id = filing.get(config.matching_field)
                if entity_id is None:
                    orphans.append(filing)
                    continue

                # Apply transformation if needed (e.g., US EIN padding)
                if config.transform_id:
                    entity_id = config.transform_id(entity_id)

                # Check cache first
                cache_key = (registry_id, str(entity_id))
                if cache_key in self._cache:
                    matches[filing['_id']] = self._cache[cache_key]
                    self._cache_hits += 1
                else:
                    self._cache_misses += 1
                    if entity_id not in ids_to_lookup:
                        ids_to_lookup[entity_id] = []
                    ids_to_lookup[entity_id].append(filing)

            if not ids_to_lookup:
                continue

            # Batch query for all uncached entity IDs
            entity_ids_values = list(ids_to_lookup.keys())
            query = {
                "registryID": registry_id,
                "$or": [
                    {config.matching_field: {"$in": entity_ids_values}},
                    {config.matching_field: {"$in": [str(v) for v in entity_ids_values]}}
            ]
            }

            # Add subsidiary filter if configured
            if config.subsidiary_filter:
                query.update(config.subsidiary_filter)

            # Execute batch lookup
            cursor = self._orgs.find(
                query,
                {"_id": 1, config.matching_field: 1}
            )

            # Process results
            found_ids = set()
            for org in cursor:
                org_entity_id = str(org[config.matching_field])
                found_ids.add(org_entity_id)

                # Cache the result
                cache_key = (registry_id, str(org_entity_id))
                self._cache[cache_key] = org['_id']

                # Limit cache size to prevent memory issues
                # self._cache_max_size = 10000000
                # if len(self._cache) > self._cache_max_size:
                #     # Clear oldest half
                #     keys_to_remove = list(self._cache.keys())[:self._cache_max_size // 2]
                #     for k in keys_to_remove:
                #         del self._cache[k]
                #     logger.info(f"Organization matching cache: size exceeded, cleared oldest {len(keys_to_remove)} entries")

                # Match all filings with this entity ID
                for filing in ids_to_lookup.get(org_entity_id, []):
                    matches[filing['_id']] = org['_id']

            # Identify orphans (entity IDs not found)
            for entity_id, id_filings in ids_to_lookup.items():
                if entity_id not in found_ids:
                    orphans.extend(id_filings)

        return matches, orphans

    # =========================================================================
    # Aggregation Pipeline Implementation
    # =========================================================================

    def _match_via_aggregation(self, limit: Optional[int]) -> MatchingStats:
        """Match filings using MongoDB aggregation pipeline.

        This approach pushes the join logic to the database, which can be
        faster for simple matching scenarios but has limitations:
        - Cannot easily handle ID transformations (e.g., US EIN padding)
        - Orphan handling requires separate pass
        - Less control over batch processing

        Best for: Registries with clean 1:1 entity ID matching
        TODO: create a two-step executing function where aggregation pipeline does first pass, and then bulk process sweeps the rest
        """
        stats = MatchingStats(method="aggregation")

        logger.info("Using aggregation pipeline for matching")
        print("\nUsing aggregation pipeline")
        print("Note: This method works best for simple 1:1 matches")
        print("      Complex cases require 'bulk' fallback")

        # Get registries that can use pure aggregation
        # (those without ID transformation)
        # TODO: United States doesn't always need ID transformation if data is already clean, how to reflect in this process?
        simple_registries = []
        complex_registries = []

        for name, config in REGISTRY_CONFIGS.items():
            if config.transform_id is None:
                simple_registries.append(name)
            else:
                complex_registries.append(name)

        # Add default registries (not in REGISTRY_CONFIGS) to simple list
        all_registry_names = set(
            doc['_id']
            for doc in self._filings.aggregate([
                {"$match": {"entityId_mongo": {"$exists": False}}},
                {"$group": {"_id": "$registryName"}}
            ])
        )

        for name in all_registry_names:
            if name not in REGISTRY_CONFIGS:
                simple_registries.append(name)

        # 🡨 Process simple registries with aggregation
        for registry_name in simple_registries:
            config = REGISTRY_CONFIGS.get(registry_name, DEFAULT_CONFIG)
            reg_stats = self._aggregate_for_registry(registry_name, config, limit)

            stats.matched += reg_stats.matched
            stats.orphans_skipped += reg_stats.orphans_skipped
            stats.total_processed += reg_stats.total_processed

        # 🡨 Fall back to bulk for complex registries
        if complex_registries:
            print(f"\nFalling back to bulk for: {', '.join(complex_registries)}")

            # Filter to only unmatched filings from complex registries
            complex_filter = {
                "entityId_mongo": {"$exists": False},
                "registryName": {"$in": complex_registries}
            }

            complex_filings = list(self._filings.find(complex_filter))
            if complex_filings:
                bulk_result = self._process_batch(complex_filings)
                stats.matched += bulk_result.filings_updated
                stats.orphans_created += bulk_result.orphans_created
                stats.orphans_skipped += bulk_result.orphans_skipped
                stats.total_processed += len(complex_filings)

        return stats

    def _aggregate_for_registry(
            self,
            registry_name: str,
            config: RegistryConfig,
            limit: Optional[int]
    ) -> MatchingStats:
        """Run aggregation pipelne for a single registry.

        Pipeline stages:
        1. $match -  Filter to unmatched filings for this registry
        2. $lookup - Join with organizations
        3. $unwind - Flatten the joined array (only if match found)
        4. $set -    Add the entityId_mongo field
        5. $merge -  Write back to filings collection
        """
        stats = MatchingStats(method="aggregation")

        # Stage 1: Begin the aggregation pipeline with a filter
        pipeline = [
            # Filter to unmatched filings for this registry.
            # Interpretation note:
            #  - $match is a MongoDB command
            #  - "unmatched" in Regeindary jargon for filings without entityId_mongo
            #  - and so, we are "$match"-ing on filings that are "unmatched" (i.e. no entityId_mongo)
            {
                "$match": {
                    "entityId_mongo": {"$exists": False},
                    "registryName": registry_name
                }
            }
        ]

        # Optional limit
        if limit:
            pipeline.append({"$limit": limit})

        # Stage 2: Lookup organizations
        lookup_pipeline = [
            {
                "$match": {
                    "$expr" : {
                        "$and" : [
                            {"$eq" : ["$registryID", "$$filing_registry_id"]},
                            {"$eq" : [
                                {"$toString": f"${config.matching_field}"},
                                "$$filing_entity_id"
                            ]}
                        ]
                    }
                }
            }
        ]

        # Add subsidiary filter if configured
        if config.subsidiary_filter:
            lookup_pipeline.append({"$match": config.subsidiary_filter})

        pipeline.append(
            {"$lookup":
                 {"from": self.collections['organizations'],
                  "let": {
                      "filing_entity_id": {"$toString": f"${config.matching_field}"},
                      "filing_registry_id": "$registryID"
                  },
                  "pipeline": lookup_pipeline,
                  "as": "matched_org"
                  }
             })

        # Stage 3: Filter to only filings with exactly one match
        pipeline.append({
            "$match": {
                "matched_org": {"$size": 1}
            }
        })

        # Stage 4: Extract the org ID
        pipeline.append({
            "$set": {
                "entityId_mongo": {"$arrayElemAt": ["$matched_org._id", 0]}
            }
        })

        # Stage 5: Remove the temporary matched_org field
        pipeline.append({"$unset": "matched_org"})

        # Stage 6: Merge back to filings collection
        pipeline.append({
            "$merge": {
                "into": self.collections['filings'],
                "on": "_id",
                "whenMatched": "replace",
                "whenNotMatched": "discard"
            }
        })

        # Execute the pipeline
        stage_names = [list(stage.keys())[0] for stage in pipeline]
        summary = " 🡪 ".join(stage_names)
        logger.info(f"Running aggregation pipeline for {registry_name}: {summary}…")
        print(f"  Processing {registry_name}...", end="")

        try:
            # $merge doesn't return results, so we need to count before to compare with after
            before_count = self._filings.count_documents({"entityId_mongo": {"$exists": False}, "registryName": registry_name})

            # Run aggregation
            list(self._filings.aggregate(pipeline, allowDiskUse=True))

            # After count
            after_count = self._filings.count_documents({"entityId_mongo": {"$exists": False}, "registryName": registry_name})

            matched = before_count - after_count
            stats.matched += matched
            stats.total_processed = before_count if not limit else min(limit, before_count)
            stats.orphans_skipped = after_count             # Remaining unmatched  # TODO: examine if this is named correctly

            print(f" ✔ {matched:,} filings updated")

        except Exception as e:
            logger.error(f"Aggregation pipeline error for {registry_name}: {e}")
            print(f" ✖ Error: {e}")
            stats.errors += 1

        # TODO: Aggregation doesn't update the org's filings array, this would require a separate pass to be implemented

        return stats

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _create_org_from_filing(self, filing: dict) -> Optional[ObjectId]:
        """Create an organization record from an orphan filing.

        This preserves the original behavior from utils.py but is cleaner.
        """
        fields_to_clone = [
            'registryName',
            'registryID',
            'entityId',
            'entityName',
            'establishedDate',
            'websiteUrl'
        ]

        org_dict = {k: v for k, v in filing.items() if k in fields_to_clone}

        # Add breadcrumb for traceability
        org_dict['Original Data'] = {
            "created_from": "orphan_filing",
            "source_filing_id": filing['_id'],
            "created_at": datetime.now().isoformat()
        }

        try:
            result = self._orgs.insert_one(org_dict)
            logger.info(f"Created org from orphan filing: {result.inserted_id}")
            return result.inserted_id
        except Exception as e:
            logger.error(f"Failed to create org from filing: {e}")
            return None

    def get_config_for_registry(self, registry_name: str) -> RegistryConfig:
        """Get the configuration for a specific registry.

        Useful for debugging or customizing behavior.
        """
        return REGISTRY_CONFIGS.get(registry_name, DEFAULT_CONFIG)

    def clear_cache(self):
        """Clear the internal org lookup cache.

        Call this between test runs or if you suspect stale data.
        """
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Cache cleared")


# ============================================================================
# Standalone Usage / Testing
# ============================================================================

if __name__ == "__main__":
    """Example standalone usage for testing."""

    # This allows running: python filing_matcher.py
    # Useful for quick tests without going through interface.py

    import sys
    sys.path.insert(0, '.')

    from utils import mongo_regeindary, collections_map

    print("FilingMatcher Test Run")
    print("=" * 50)

    matcher = FilingMatcher(
        mongo_regeindary,
        collections_map,
        batch_size=500,  # Smaller batches for testing
        create_orphans=False  # Don't create orgs in test
    )

    # Test with small batch
    print("\nTesting bulk method with 100000 filings...")
    stats = matcher.match_all(method="bulk", limit=100000)
    print(stats)

    # Test with small batch
    # print("\nTesting aggregation method with 1000 filings...")
    # stats = matcher.match_all(method="aggregation", limit=1000)
    # print(stats)

    # Test with large batch
    print("\nTesting bulk method with 1000000 filings...")
    stats = matcher.match_all(method="bulk", limit=1000000)
    print(stats)

    # Show cache efficiency
    print(f"\nCache efficiency: {matcher._cache_hits}/{matcher._cache_hits + matcher._cache_misses} hits")