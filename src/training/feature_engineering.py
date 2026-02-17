"""
Feature engineering for anomaly detection model training.

This module provides:
- Feature extraction from telemetry data
- Feature scaling and normalization
- Feature validation
- Feature importance analysis
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
import math

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature engineering."""
    
    # Required telemetry fields
    required_fields: List[str] = field(
        default_factory=lambda: ["voltage", "temperature", "gyro"]
    )
    
    # Feature scaling method: "minmax", "zscore", or "none"
    scaling_method: str = "minmax"
    
    # Feature range expectations for validation
    voltage_range: Tuple[float, float] = (6.0, 10.0)
    temperature_range: Tuple[float, float] = (0.0, 60.0)
    gyro_range: Tuple[float, float] = (-1.0, 1.0)
    
    # Additional derived features
    compute_derivatives: bool = True
    compute_stats: bool = True
    
    # Outlier handling
    remove_outliers: bool = False
    outlier_threshold: float = 3.0  # Standard deviations


class FeatureEngineer:
    """
    Performs feature engineering for anomaly detection models.
    
    Supports:
    - Feature extraction and validation
    - Scaling and normalization
    - Derived feature computation
    - Outlier detection
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        """
        Initialize feature engineer.
        
        Args:
            config: FeatureConfig instance
        """
        self.config = config or FeatureConfig()
        
        # Scaling parameters (computed during fit)
        self._feature_min: Dict[str, float] = {}
        self._feature_max: Dict[str, float] = {}
        self._feature_mean: Dict[str, float] = {}
        self._feature_std: Dict[str, float] = {}
        
        self._is_fitted = False
    
    def fit(self, data: List[Dict[str, Any]]) -> None:
        """
        Fit scaling parameters using training data.
        
        Args:
            data: List of training records
        """
        if not data:
            raise ValueError("Cannot fit on empty data")
        
        # Extract feature values
        features_by_key = {field: [] for field in self.config.required_fields}
        
        for record in data:
            for field in self.config.required_fields:
                if field in record and record[field] is not None:
                    features_by_key[field].append(float(record[field]))
        
        # Compute statistics
        for field, values in features_by_key.items():
            if not values:
                logger.warning(f"No values for field '{field}' during fitting")
                continue
            
            self._feature_min[field] = min(values)
            self._feature_max[field] = max(values)
            
            mean = sum(values) / len(values)
            self._feature_mean[field] = mean
            
            # Standard deviation
            variance = sum((x - mean) ** 2 for x in values) / len(values)
            self._feature_std[field] = math.sqrt(variance)
        
        self._is_fitted = True
        logger.info("Feature scaling parameters fitted")
    
    def extract_features(
        self, record: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Extract and validate features from a single record.
        
        Args:
            record: Telemetry record
            
        Returns:
            Dictionary of extracted features
            
        Raises:
            ValueError: If required fields are missing
        """
        features = {}
        
        # Extract required fields
        for field in self.config.required_fields:
            if field not in record:
                raise ValueError(f"Required field '{field}' not found in record")
            
            value = float(record[field])
            
            # Validate ranges
            if not self._validate_field_range(field, value):
                logger.warning(
                    f"Field '{field}' value {value} out of expected range"
                )
            
            features[field] = value
        
        # Add derived features if enabled
        if self.config.compute_derivatives:
            derived = self._compute_derived_features(features)
            features.update(derived)
        
        return features
    
    def _validate_field_range(self, field: str, value: float) -> bool:
        """Check if field value is within expected range."""
        ranges = {
            "voltage": self.config.voltage_range,
            "temperature": self.config.temperature_range,
            "gyro": self.config.gyro_range,
        }
        
        if field not in ranges:
            return True
        
        min_val, max_val = ranges[field]
        return min_val <= value <= max_val
    
    def _compute_derived_features(
        self, features: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Compute derived features from base features.
        
        Args:
            features: Base features
            
        Returns:
            Dictionary of derived features
        """
        derived = {}
        
        # Compute ratios and combinations
        voltage = features.get("voltage", 0)
        temperature = features.get("temperature", 0)
        gyro = abs(features.get("gyro", 0))
        
        # Voltage-temperature coupling (indicator of power stress)
        if voltage > 0:
            derived["voltage_temp_ratio"] = temperature / voltage
        else:
            derived["voltage_temp_ratio"] = 0.0
        
        # Gyro intensity (absolute rotation)
        derived["gyro_intensity"] = gyro
        
        # Composite anomaly score (simple combination)
        derived["composite_score"] = (
            (voltage / 8.0) * 0.3 +
            (temperature / 30.0) * 0.3 +
            (gyro * 10.0) * 0.4
        )
        
        return derived
    
    def scale_features(
        self, features: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Scale features using fitted parameters.
        
        Args:
            features: Features to scale
            
        Returns:
            Scaled features
        """
        if not self._is_fitted:
            logger.warning("Scaler not fitted. Returning unscaled features.")
            return features.copy()
        
        scaled = {}
        
        for field, value in features.items():
            if self.config.scaling_method == "minmax":
                scaled[field] = self._scale_minmax(field, value)
            elif self.config.scaling_method == "zscore":
                scaled[field] = self._scale_zscore(field, value)
            else:
                scaled[field] = value
        
        return scaled
    
    def _scale_minmax(self, field: str, value: float) -> float:
        """Min-max normalization to [0, 1]."""
        if field not in self._feature_min:
            return value
        
        min_val = self._feature_min.get(field, 0)
        max_val = self._feature_max.get(field, 1)
        
        if max_val == min_val:
            return 0.5
        
        return (value - min_val) / (max_val - min_val)
    
    def _scale_zscore(self, field: str, value: float) -> float:
        """Z-score (standardization) normalization."""
        if field not in self._feature_mean:
            return value
        
        mean = self._feature_mean.get(field, 0)
        std = self._feature_std.get(field, 1)
        
        if std == 0:
            return 0.0
        
        return (value - mean) / std
    
    def transform_batch(
        self, records: List[Dict[str, Any]]
    ) -> List[List[float]]:
        """
        Transform multiple records into feature vectors.
        
        Args:
            records: List of telemetry records
            
        Returns:
            List of feature vectors
        """
        feature_vectors = []
        
        for record in records:
            try:
                # Extract features
                features = self.extract_features(record)
                
                # Scale features
                scaled = self.scale_features(features)
                
                # Create feature vector (consistent order)
                vector = [
                    scaled.get("voltage", 0),
                    scaled.get("temperature", 0),
                    scaled.get("gyro", 0),
                ]
                
                feature_vectors.append(vector)
                
            except ValueError as e:
                logger.warning(f"Failed to transform record: {e}")
                continue
        
        return feature_vectors
    
    def get_feature_names(self) -> List[str]:
        """Get list of feature names in transformation order."""
        names = ["voltage", "temperature", "gyro"]
        
        if self.config.compute_derivatives:
            names.extend([
                "voltage_temp_ratio",
                "gyro_intensity",
                "composite_score"
            ])
        
        return names
