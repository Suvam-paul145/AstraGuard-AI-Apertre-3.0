"""
Data loading and preprocessing for training anomaly detection models.

This module handles:
- Loading telemetry data from various sources (JSON, CSV, database)
- Data validation and cleaning
- Train/test split operations
- Data augmentation for imbalanced datasets
"""

import json
import csv
import logging
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
import random

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


@dataclass
class DataConfig:
    """Configuration for data loading operations."""
    
    train_test_split: float = 0.8
    validation_split: float = 0.1
    random_seed: Optional[int] = 42
    
    # Data validation thresholds
    min_samples: int = 100
    max_missing_ratio: float = 0.1
    
    # Data augmentation
    enable_augmentation: bool = False
    augmentation_factor: float = 1.5
    
    # Imbalanced data handling
    handle_imbalance: bool = True
    anomaly_ratio_target: float = 0.3


class DataLoader:
    """
    Loads and preprocesses telemetry data for model training.
    
    Supports multiple data sources and formats:
    - JSON files with telemetry records
    - CSV files with time-series data
    - In-memory lists of telemetry dictionaries
    """
    
    def __init__(self, config: Optional[DataConfig] = None):
        """
        Initialize data loader.
        
        Args:
            config: DataConfig instance with loading parameters
        """
        self.config = config or DataConfig()
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
        
        self._train_data: List[Dict[str, Any]] = []
        self._test_data: List[Dict[str, Any]] = []
        self._validation_data: List[Dict[str, Any]] = []
    
    def load_from_json(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Load telemetry data from JSON file.
        
        Expected format: List of dictionaries or JSONL format
        
        Args:
            filepath: Path to JSON file
            
        Returns:
            List of data records
            
        Raises:
            DataValidationError: If file format is invalid
            FileNotFoundError: If file doesn't exist
        """
        logger.info(f"Loading data from JSON: {filepath}")
        
        try:
            data = []
            with open(filepath, 'r') as f:
                content = f.read().strip()
                
                # Try parsing as JSON array first
                if content.startswith('['):
                    data = json.loads(content)
                else:
                    # Try JSONL format (one JSON per line)
                    for line in content.split('\n'):
                        if line.strip():
                            data.append(json.loads(line))
            
            logger.info(f"Loaded {len(data)} records from JSON")
            return data
            
        except json.JSONDecodeError as e:
            raise DataValidationError(f"Invalid JSON format: {e}")
        except FileNotFoundError:
            raise
        except Exception as e:
            raise DataValidationError(f"Error loading JSON file: {e}")
    
    def load_from_csv(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Load telemetry data from CSV file.
        
        Args:
            filepath: Path to CSV file
            
        Returns:
            List of data records
            
        Raises:
            DataValidationError: If file format is invalid
        """
        logger.info(f"Loading data from CSV: {filepath}")
        
        try:
            data = []
            with open(filepath, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert numeric strings to floats
                    converted_row = {}
                    for key, value in row.items():
                        try:
                            converted_row[key] = float(value)
                        except (ValueError, TypeError):
                            converted_row[key] = value
                    data.append(converted_row)
            
            logger.info(f"Loaded {len(data)} records from CSV")
            return data
            
        except FileNotFoundError:
            raise
        except Exception as e:
            raise DataValidationError(f"Error loading CSV file: {e}")
    
    def load_from_list(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Load data from in-memory list.
        
        Args:
            data: List of telemetry dictionaries
            
        Returns:
            Validated data list
            
        Raises:
            DataValidationError: If data format is invalid
        """
        logger.info(f"Loading {len(data)} records from list")
        
        if not isinstance(data, list):
            raise DataValidationError("Data must be a list of dictionaries")
        
        if not data:
            raise DataValidationError("Data list is empty")
        
        return data
    
    def validate_data(self, data: List[Dict[str, Any]]) -> None:
        """
        Validate data quality and format.
        
        Checks:
        - Minimum number of samples
        - Missing value ratio
        - Required fields presence
        
        Args:
            data: Data to validate
            
        Raises:
            DataValidationError: If validation fails
        """
        if len(data) < self.config.min_samples:
            raise DataValidationError(
                f"Insufficient samples: {len(data)} < {self.config.min_samples}"
            )
        
        # Check for required fields
        required_fields = {"voltage", "temperature", "gyro"}
        
        missing_counts = {field: 0 for field in required_fields}
        
        for record in data:
            for field in required_fields:
                if field not in record or record[field] is None:
                    missing_counts[field] += 1
        
        # Check missing ratio
        for field, count in missing_counts.items():
            ratio = count / len(data)
            if ratio > self.config.max_missing_ratio:
                raise DataValidationError(
                    f"Field '{field}' missing in {ratio:.1%} of samples "
                    f"(max allowed: {self.config.max_missing_ratio:.1%})"
                )
        
        logger.info("Data validation passed")
    
    def split_train_test(
        self, data: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Split data into training and testing sets.
        
        Args:
            data: Full dataset
            
        Returns:
            Tuple of (train_data, test_data)
        """
        self.validate_data(data)
        
        # Shuffle data
        shuffled = data.copy()
        random.shuffle(shuffled)
        
        split_idx = int(len(shuffled) * self.config.train_test_split)
        train_data = shuffled[:split_idx]
        test_data = shuffled[split_idx:]
        
        self._train_data = train_data
        self._test_data = test_data
        
        logger.info(
            f"Split data: {len(train_data)} training, {len(test_data)} testing"
        )
        
        return train_data, test_data
    
    def split_validation(
        self, train_data: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Split training data into training and validation sets.
        
        Args:
            train_data: Training dataset
            
        Returns:
            Tuple of (train_subset, validation_data)
        """
        shuffled = train_data.copy()
        random.shuffle(shuffled)
        
        split_idx = int(len(shuffled) * (1 - self.config.validation_split))
        actual_train = shuffled[:split_idx]
        validation = shuffled[split_idx:]
        
        self._validation_data = validation
        
        logger.info(
            f"Split training data: {len(actual_train)} training, "
            f"{len(validation)} validation"
        )
        
        return actual_train, validation
    
    def get_train_data(self) -> List[Dict[str, Any]]:
        """Get loaded training data."""
        return self._train_data
    
    def get_test_data(self) -> List[Dict[str, Any]]:
        """Get loaded test data."""
        return self._test_data
    
    def get_validation_data(self) -> List[Dict[str, Any]]:
        """Get loaded validation data."""
        return self._validation_data
