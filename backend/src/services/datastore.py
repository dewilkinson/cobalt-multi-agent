import logging
import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from langchain_core.tools import tool
from src.tools.shared_storage import history_cache, df_cache, analysis_cache, GLOBAL_CONTEXT
from src.services.heat_manager import HeatManager
from src.config.database import PersistentCache, get_session_local
import json
import os
from src.utils.temporal import get_cache_segment_suffix

logger = logging.getLogger(__name__)



class DatastoreManager:
    _eager_worker_task = None
    _fetch_callback = None

    @classmethod
    def register_fetcher(cls, fetch_func):
        """Register the financial data fetching function to avoid circular imports."""
        cls._fetch_callback = fetch_func

    @classmethod
    def _get_symbol_container(cls, cache: Any, ticker: str, create: bool = True) -> dict[str, Any]:
        """ Internal helper to get or create a nested symbol container. """
        suffix = get_cache_segment_suffix()
        t = ticker.upper() + suffix
        if t not in cache:
            if not create:
                return {}
            
            # LRU Enforcement: If adding a new ticker, check cap
            cls._enforce_capacity(cache)
            cache[t] = {
                "reference_price": 0.0,
                "last_accessed": datetime.now(),
                "timeframes": {}
            }
        else:
            # Update access time to maintain LRU order
            cache.move_to_end(t)
            cache[t]["last_accessed"] = datetime.now()
            
        return cache[t]

    @classmethod
    def _enforce_capacity(cls, cache: Any):
        """ Enforces the 1,000 symbol limit using LRU eviction. """
        from src.config.loader import get_config
        
        # Optimization: Fetch limit once
        limit = cls._get_cached_limit()
        if len(cache) < limit:
            return

        # Identification phase: Get list of protected symbols (Top 20 Heat)
        # Optimization: Only calculate protected once per operation
        protected = HeatManager.get_protected_symbols(20)
        
        # Eviction phase: Find the oldest (first) non-protected symbol
        evict_key = None
        for ticker in cache:
            if ticker not in protected:
                evict_key = ticker
                break
        
        if evict_key:
            logger.info(f"[CACHE_LRU] Evicting symbol container: {evict_key} (Capacity limit reached)")
            del cache[evict_key]
        else:
            # Edge case: All 1,000 symbols are hot? Evict the absolute oldest anyway
            evict_key = next(iter(cache))
            logger.warning(f"[CACHE_LRU] Absolute emergency eviction of hot symbol: {evict_key}")
            del cache[evict_key]

    @classmethod
    def get_history_cache(cls) -> dict[str, Any]:
        from src.config.loader import get_bool_env
        if get_bool_env("VLI_CACHE_DISABLED", False):
            return {}
        return history_cache

    @classmethod
    def get_df_cache(cls) -> dict[str, Any]:
        from src.config.loader import get_bool_env
        if get_bool_env("VLI_CACHE_DISABLED", False):
            return {}
        return df_cache
    @classmethod
    def get_analysis_cache(cls) -> dict[str, Any]:
        from src.config.loader import get_bool_env
        if get_bool_env("VLI_CACHE_DISABLED", False):
            return {}
        return analysis_cache

    @classmethod
    def get_artifact(cls, ticker: str, resource_type: str, timeframe: str) -> dict[str, Any]:
        """ Retrieves an artifact with Read-Through support. """
        t = ticker.upper()
        cache_map = {
            'history': history_cache,
            'df': df_cache,
            'analysis': analysis_cache,
            'smc_analysis': analysis_cache,
            'news': analysis_cache,
            'news_raw': analysis_cache,
            'news_raw': analysis_cache,
            'search': analysis_cache
        }
        cache = cache_map.get(resource_type)

        if cache is None or t not in cache:
            # Phase 4: Read-Through to Database
            db_entry = cls._get_from_db(t, resource_type, timeframe)
            if db_entry:
                # Eagerly promote to RAM if found in DB
                cls.store_artifact(t, resource_type, timeframe, db_entry["data"], price=db_entry.get("reference_price"), persist=False)
                return db_entry
            return {}
            
        # Update heat on access
        HeatManager.increment_heat(t)
        
        # Update LRU pos
        cache.move_to_end(t)
        
        return cache[t]["timeframes"].get(timeframe, {})

    @classmethod
    def _get_from_db(cls, ticker: str, resource_type: str, timeframe: str) -> dict[str, Any]:
        """ Internal helper to fetch from PostgreSQL. """
        try:
            SessionLocal = get_session_local()
            with SessionLocal() as db:
                cache_obj = db.query(PersistentCache).filter(
                    PersistentCache.ticker == ticker,
                    PersistentCache.resource_type == resource_type,
                    PersistentCache.timeframe == timeframe
                ).first()
                
                if cache_obj:
                    if cache_obj.is_expired():
                        db.delete(cache_obj)
                        db.commit()
                        return {}
                    
                    # Update last accessed in DB
                    cache_obj.last_accessed = datetime.utcnow()
                    db.commit()
                    
                    try:
                        return {
                            "data": json.loads(cache_obj.data),
                            "updated_at": cache_obj.created_at,
                            "price": cache_obj.reference_price
                        }
                    except:
                        return {"data": cache_obj.data, "updated_at": cache_obj.created_at, "price": cache_obj.reference_price}
        except Exception as e:
            logger.warning(f"[DB_FALLBACK] PostgreSQL/SQLite query failed for {ticker}: {e}. Falling back to stateless mode.")
        return {}

    @classmethod
    def store_artifact(cls, ticker: str, resource_type: str, timeframe: str, data: Any, price: float = None, persist: bool = True, ttl: int = None):
        """ 
        Stores an artifact in the nested container. 
        Supported resource_type: 'history', 'df', 'analysis'
        """
        t = ticker.upper()
        cache_map = {
            'history': history_cache,
            'df': df_cache,
            'analysis': analysis_cache,
            'smc_analysis': analysis_cache,
            'news': analysis_cache,
            'news_raw': analysis_cache,
            'search': analysis_cache
        }
        
        cache = cache_map.get(resource_type)
        if cache is None:
            raise ValueError(f"Unknown resource type: {resource_type}")

        container = cls._get_symbol_container(cache, t)
        
        # Update metadata
        if price is not None:
            container["reference_price"] = price
            
        container["timeframes"][timeframe] = {
            "data": data,
            "updated_at": datetime.now()
        }
        
        # Increment heat on every store/access
        HeatManager.increment_heat(t)
        
        # Phase 3: Immediate Drift Check
        if price is not None:
            cls.validate_price_consistency(t, price)
            
        # Phase 4: Write-Through Persistence
        if persist:
            cls._save_to_db(t, resource_type, timeframe, data, price or container["reference_price"], ttl=ttl)

    @classmethod
    def _save_to_db(cls, ticker: str, resource_type: str, timeframe: str, data: Any, price: float, ttl: int = None):
        """ Internal helper to save to PostgreSQL. """
        from src.config.loader import get_config
        config = get_config()
        
        # Check if persistence is enabled for this type
        policy = config.get("CACHE_POLICIES", {}).get(resource_type, config.get("CACHE_POLICIES", {}).get("default", {}))
        if not policy.get("persist_offline", False) and resource_type != "smc_analysis":
             # Only persist if explicitly enabled OR if it's the high-value SMC type
             return

        # Determine TTL from config if not provided
        if ttl is None:
            ttl_sec = policy.get("ttl_sec", 3600)
        else:
            ttl_sec = ttl
            
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_sec)
        
        serialized_data = json.dumps(data) if not isinstance(data, str) else data
        
        try:
            SessionLocal = get_session_local()
            with SessionLocal() as db:
                # Upsert logic
                existing = db.query(PersistentCache).filter(
                    PersistentCache.ticker == ticker,
                    PersistentCache.resource_type == resource_type,
                    PersistentCache.timeframe == timeframe
                ).first()
                
                if existing:
                    existing.data = serialized_data
                    existing.reference_price = price
                    existing.expires_at = expires_at
                    existing.heat_score = HeatManager.get_heat_score(ticker)
                    existing.last_accessed = datetime.utcnow()
                else:
                    new_entry = PersistentCache(
                        ticker=ticker,
                        resource_type=resource_type,
                        timeframe=timeframe,
                        reference_price=price,
                        data=serialized_data,
                        expires_at=expires_at,
                        heat_score=HeatManager.get_heat_score(ticker)
                    )
                    db.add(new_entry)
                
                db.commit()
        except Exception as e:
            logger.error(f"[DB_FALLBACK] Failed to save {ticker} to persistent store: {e}")

    @classmethod
    def validate_price_consistency(cls, ticker: str, current_price: float):
        """ Checks if the current price has drifted significantly from the cached reference price. """
        t = ticker.upper()
        caches = [history_cache, df_cache, analysis_cache]
        
        # Optimization: Use class-level cached limit to avoid disk I/O in hot loops
        threshold = cls._get_cached_drift_threshold()
        
        for cache in caches:
            if t not in cache:
                continue
                
            container = cache[t]
            ref_price = container.get("reference_price", 0.0)
            
            if ref_price <= 0:
                container["reference_price"] = current_price
                continue
                
            drift = abs((current_price - ref_price) / ref_price)
            if drift > threshold:
                logger.warning(f"[CACHE_DRIFT] {t} price drifted {drift*100:.2f}% (Threshold: {threshold*100}%). Triggering Atomic Purge.")
                cls.invalidate_cache(t)
                break 

    @classmethod
    def invalidate_cache(cls, ticker: str = "") -> str:
        """Invalidate the cache for a specific ticker or clear all."""
        caches = [history_cache, df_cache, analysis_cache]

        if not ticker:
            for c in caches:
                c.clear()
            
            # Phase 4: Also flush DB
            try:
                SessionLocal = get_session_local()
                with SessionLocal() as db:
                    db.query(PersistentCache).delete()
                    db.commit()
            except Exception as e:
                logger.warning(f"[DB_FALLBACK] Global cache flush failed in DB: {e}. RAM context only.")
                
            # Phase 5: Clear secondary state
            HeatManager.clear_heat()
            GLOBAL_CONTEXT.get("cached_tickers", set()).clear()
            if "ticker_metadata" in GLOBAL_CONTEXT:
                GLOBAL_CONTEXT["ticker_metadata"].clear()
            if "vli_cache_diag" in GLOBAL_CONTEXT:
                GLOBAL_CONTEXT["vli_cache_diag"] = {"cache": {}, "history": []}
                
            # Phase 6: Delete all physical analysis report files
            try:
                import glob
                reports_dir = os.path.join(os.getcwd(), 'data', 'reports')
                if os.path.exists(reports_dir):
                    for f in glob.glob(os.path.join(reports_dir, 'analyze_*.md')):
                        os.remove(f)
                    logger.info("[CACHE] Deleted all physical report files")
                    
                # Also delete from Obsidian Vault
                vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
                if vault_path:
                    vault_reports_dir = os.path.join(vault_path, "_cobalt", "04_Analysis")
                    if os.path.exists(vault_reports_dir):
                        for f in glob.glob(os.path.join(vault_reports_dir, '*_Institutional_Brief.md')):
                            os.remove(f)
                        logger.info("[CACHE] Deleted all vault report files")
            except Exception as e:
                logger.warning(f"[CACHE] Failed to delete all physical reports: {e}")
                
            return "Datastore cache completely flushed (RAM + DB + Context + Files)."

        t = ticker.upper()
        for cache in caches:
            if t in cache:
                del cache[t]
                
        # Phase 4: Atomic DB Purge
        try:
            SessionLocal = get_session_local()
            with SessionLocal() as db:
                db.query(PersistentCache).filter(PersistentCache.ticker == t).delete()
                db.commit()
        except Exception as e:
            logger.warning(f"[DB_FALLBACK] Cache invalidation failed for {t} in DB: {e}. RAM context only.")

        # Phase 5: Clear secondary state for this ticker
        HeatManager.clear_heat(t)
        cached_set = GLOBAL_CONTEXT.get("cached_tickers", set())
        if t in cached_set:
            cached_set.remove(t)
        if "ticker_metadata" in GLOBAL_CONTEXT and t in GLOBAL_CONTEXT["ticker_metadata"]:
            del GLOBAL_CONTEXT["ticker_metadata"][t]
        if "vli_cache_diag" in GLOBAL_CONTEXT and t in GLOBAL_CONTEXT["vli_cache_diag"].get("cache", {}):
            del GLOBAL_CONTEXT["vli_cache_diag"]["cache"][t]

        # Phase 6: Delete physical analysis report file to immediately gray out the UI
        try:
            report_path = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{t.lower()}.md')
            if os.path.exists(report_path):
                os.remove(report_path)
                logger.info(f"[CACHE] Deleted physical report file: {report_path}")
                
            # Also delete from Obsidian Vault
            vault_path = os.environ.get("OBSIDIAN_VAULT_PATH")
            if vault_path:
                vault_report_path = os.path.join(vault_path, "_cobalt", "04_Analysis", f"{t.upper()}_Institutional_Brief.md")
                if os.path.exists(vault_report_path):
                    os.remove(vault_report_path)
                    logger.info(f"[CACHE] Deleted vault report file: {vault_report_path}")
        except Exception as e:
            logger.warning(f"[CACHE] Failed to delete physical report for {t}: {e}")

        return f"Cache invalidated for {t} (RAM + DB + Context + Files)."

    @classmethod
    def simulate_volatility(cls, force_invalid: bool = False):
        """Simulate market volatility by tweaking cache freshness or invalidating it."""
        caches = [history_cache, df_cache, analysis_cache]

        for cache in caches:
            for ticker in cache:
                container = cache[ticker]
                for tf in container.get("timeframes", {}):
                    container["timeframes"][tf]["updated_at"] = datetime.min
            if force_invalid:
                cache.clear()

    @classmethod
    def ensure_worker_started(cls):
        """Register background workers with the central Cobalt Heartbeat Scheduler."""
        if cls._eager_worker_task is None:
            try:
                # Also start the heat decay worker
                HeatManager.start_decay_worker()
                
                from src.services.scheduler import cobalt_scheduler
                cobalt_scheduler.add_timer(
                    task_id="EAGER_CACHE_SYNC",
                    name="Datastore Eager Cache Worker",
                    type="REPEAT",
                    schedule=60,
                    period_unit="seconds",
                    priority="LOW",
                    callback=cls._eager_cache_tick
                )
                
                cls._eager_worker_task = True # Marker instead of asyncio.Task
                logger.info("DatastoreManager Background Workers (Eager + Heat) registered with Heartbeat engine.")
            except Exception as e:
                logger.error(f"Failed to register Datastore workers: {e}")

    @classmethod
    def _eager_cache_tick(cls):
        """Heartbeat-triggered tick to perform eager refreshes."""
        from src.config.loader import get_int_env
        from datetime import timedelta

        try:
            expiry_minutes = get_int_env("CACHE_EXPIRY_MINUTES", 15)
            eager_limit = get_int_env("EAGER_CACHE_LIMIT", 5)

            if cls._fetch_callback is None:
                return

            # Use HeatManager to prioritize eager refreshes
            top_eager = HeatManager.get_protected_symbols(eager_limit)
            now = datetime.now()
            refresh_threshold = timedelta(minutes=expiry_minutes * 0.8)

            cache = history_cache

            for sym in top_eager:
                if sym not in cache:
                    continue
                    
                container = cache[sym]
                for tf_key, entry in list(container["timeframes"].items()):
                    last_up = entry.get("updated_at")
                    if last_up and (now - last_up) >= refresh_threshold:
                        logger.info(f"[CACHE_SYNC] Eager background refresh triggered for hot ticker {sym} ({tf_key})")
                        # Callback logic remains same (needs refinement in Phase 3/4)
                        pass

        except Exception as e:
            logger.error(f"DatastoreManager Eager tick error: {e}")

    @classmethod
    def _get_cached_limit(cls) -> int:
        """ Returns the capacity limit from config (cached for performance). """
        from src.config.loader import get_config
        return get_config().get("CACHE_POLICIES", {}).get("default", {}).get("capacity_limit", 1000)

    @classmethod
    def _get_cached_drift_threshold(cls) -> float:
        """ Returns the drift threshold from config (cached for performance). """
        from src.config.loader import get_config
        return get_config().get("CACHE_POLICIES", {}).get("default", {}).get("drift_pct", 1.0) / 100.0


@tool
def invalidate_market_cache(ticker: str = "") -> str:
    """Invalidate the cache for a specific ticker or clear all cache if none provided."""
    return DatastoreManager.invalidate_cache(ticker)


@tool
def simulate_cache_volatility(force_invalid: bool = False) -> str:
    """Simulate market volatility by tweaking cache freshness or invalidating it."""
    DatastoreManager.simulate_volatility(force_invalid)
    return "Simulated cache volatility applied."
