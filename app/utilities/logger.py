import logging
import os
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any


class SyncLogger:
    """
    Logger for Shopify inventory sync operations.
    Creates store-specific log directories and files for tracking sync operations.
    """
    
    def __init__(self, store_name: str, base_log_dir: str = "logs"):
        """
        Initialize the sync logger.
        
        Args:
            store_name: Name of the store (e.g., "refrigiwear", "murphynye")
            base_log_dir: Base directory for all logs (default: "logs")
        """
        self.store_name = store_name
        self.base_log_dir = Path(base_log_dir)
        self.store_log_dir = self.base_log_dir / store_name
        self.timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        
        # Create store-specific log directory if it doesn't exist
        self.store_log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        self.logger = self._setup_logger()
        
    def _setup_logger(self) -> logging.Logger:
        """
        Setup and configure the logger with file handler.
        
        Returns:
            Configured logger instance
        """
        log_filename = self.store_log_dir / f"sync_{self.timestamp}.log"
        
        # Create logger
        logger = logging.getLogger(f"sync_{self.store_name}_{self.timestamp}")
        logger.setLevel(logging.DEBUG)
        
        # Avoid adding handlers if they already exist
        if not logger.handlers:
            # Create file handler
            file_handler = logging.FileHandler(log_filename, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler to logger
            logger.addHandler(file_handler)
        
        return logger
    
    def info(self, message: str):
        """Log info message."""
        self.logger.info(message)
    
    def success(self, message: str):
        """Log success message (as INFO level with SUCCESS prefix)."""
        self.logger.info(f"SUCCESS: {message}")
    
    def warning(self, message: str):
        """Log warning message."""
        self.logger.warning(message)
    
    def error(self, message: str, exc_info: bool = False):
        """Log error message."""
        self.logger.error(message, exc_info=exc_info)
    
    def debug(self, message: str):
        """Log debug message."""
        self.logger.debug(message)
    
    def log_sync_start(self, total_rows: int, sync_mode: str):
        """Log the start of a sync operation."""
        self.info(f"Starting sync operation for store: {self.store_name}")
        self.info(f"Sync mode: {sync_mode}")
        self.info(f"Total rows to process: {total_rows}")
    
    def log_sync_summary(self, 
                        total_processed: int,
                        missing_count: int,
                        duplicate_count: int,
                        changes_count: int):
        """Log summary of sync operation."""
        self.info("=" * 50)
        self.info("SYNC SUMMARY")
        self.info(f"Total rows processed: {total_processed}")
        self.info(f"Missing items: {missing_count}")
        self.info(f"Duplicate items: {duplicate_count}")
        self.info(f"Quantity changes applied: {changes_count}")
        self.info("=" * 50)
    
    def log_missing_items(self, missing_items: List[str]):
        """Log missing items."""
        if missing_items:
            self.warning(f"Found {len(missing_items)} missing items:")
            for item in missing_items[:20]:  # Log first 20
                self.warning(f"  - {item}")
            if len(missing_items) > 20:
                self.warning(f"  ... and {len(missing_items) - 20} more")
    
    def log_duplicate_items(self, duplicate_items: List[str]):
        """Log duplicate items."""
        if duplicate_items:
            self.warning(f"Found {len(duplicate_items)} duplicate items:")
            for item in duplicate_items[:20]:  # Log first 20
                self.warning(f"  - {item}")
            if len(duplicate_items) > 20:
                self.warning(f"  ... and {len(duplicate_items) - 20} more")
    
    def parse_and_save_changes(self, result: Optional[Dict], sync_mode: str) -> Optional[str]:
        """
        Parse Shopify adjustment result and save changes to CSV file.
        
        Args:
            result: Result from Shopify adjustment operation
            sync_mode: The sync mode used (adjust, replace, tabula_rasa)
            
        Returns:
            Path to the saved CSV file or None if no changes
        """
        if not result:
            self.warning("No result data to parse")
            return None
        
        # Handle error in result
        if "error" in result:
            self.error(f"Result contains error: {result['error']}")
            return None
        
        # Extract changes from the result structure
        changes = None
        if "inventoryAdjustQuantities" in result:
            adjustment_group = result["inventoryAdjustQuantities"].get("inventoryAdjustmentGroup", {})
            changes = adjustment_group.get("changes", [])
        elif "changes" in result:
            changes = result["changes"]
        
        if not changes:
            self.warning("No changes found in result")
            return None
        
        self.info(f"Parsing {len(changes)} quantity changes")
        
        # Parse changes into a list of dictionaries for DataFrame
        parsed_changes = []
        for change in changes:
            try:
                # Extract variant information
                item = change.get("item", {})
                variant = item.get("variant", {})
                product = variant.get("product", {})
                location = change.get("location", {})
                
                # Extract location name and ID
                location_name = location.get("name", "Unknown")
                location_id = location.get("id", "").replace("gid://shopify/Location/", "")
                
                # Extract product info
                product_handle = product.get("handle", "Unknown")
                product_id = product.get("id", "").replace("gid://shopify/Product/", "")
                variant_display = variant.get("displayName", "Unknown")
                
                # Extract quantity change
                delta = change.get("delta")
                quantity = change.get("quantity")
                
                # Get final quantity from inventory levels
                inventory_levels = item.get("inventoryLevels", {}).get("nodes", [])
                final_quantity = None
                for level in inventory_levels:
                    if level.get("location", {}).get("id") == location.get("id"):
                        quantities = level.get("quantities", [])
                        for q in quantities:
                            if q.get("name") == "available":
                                final_quantity = q.get("quantity")
                                break
                
                parsed_changes.append({
                    "timestamp": self.timestamp,
                    "sync_mode": sync_mode,
                    "product_id": product_id,
                    "product_handle": product_handle,
                    "variant_display": variant_display,
                    "location_id": location_id,
                    "location_name": location_name,
                    "delta": delta if delta is not None else quantity,
                    "final_quantity": final_quantity,
                    "available_for_sale": variant.get("availableForSale", None)
                })
                
            except Exception as e:
                self.error(f"Error parsing change: {str(e)}", exc_info=True)
                continue
        
        if not parsed_changes:
            self.warning("No changes could be parsed")
            return None
        
        # Create DataFrame
        df = pd.DataFrame(parsed_changes)
        
        # Save to CSV with date-based filename
        csv_filename = self.store_log_dir / f"quantity_changes_{self.timestamp}.csv"
        df.to_csv(csv_filename, index=False, encoding='utf-8')
        
        self.success(f"Saved {len(parsed_changes)} quantity changes to: {csv_filename}")
        
        # Log some statistics
        total_delta = df["delta"].sum() if "delta" in df.columns else 0
        self.info(f"Total quantity change: {total_delta}")
        self.info(f"Unique products affected: {df['product_id'].nunique()}")
        self.info(f"Unique locations affected: {df['location_id'].nunique()}")
        
        return str(csv_filename)
    
    def log_exception(self, exception: Exception, context: str = ""):
        """
        Log an exception with context.
        
        Args:
            exception: The exception to log
            context: Additional context about where the exception occurred
        """
        error_msg = f"Exception occurred"
        if context:
            error_msg += f" during {context}"
        error_msg += f": {type(exception).__name__}: {str(exception)}"
        self.error(error_msg, exc_info=True)


def create_sync_logger(store_name: str, base_log_dir: str = "logs") -> SyncLogger:
    """
    Factory function to create a SyncLogger instance.
    
    Args:
        store_name: Name of the store
        base_log_dir: Base directory for logs
        
    Returns:
        SyncLogger instance
    """
    return SyncLogger(store_name=store_name, base_log_dir=base_log_dir)
