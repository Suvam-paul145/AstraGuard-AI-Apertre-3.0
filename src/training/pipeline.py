"""
Training pipeline orchestrator for complete end-to-end model training.

This module coordinates:
- Data loading and validation
- Feature engineering
- Model training
- Model evaluation
- Model deployment
"""

import logging
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .data_loader import DataLoader, DataConfig
from .feature_engineering import FeatureEngineer, FeatureConfig
from .trainer import ModelTrainer, TrainingConfig

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the complete training pipeline."""
    
    # Component configurations
    data_config: DataConfig = None
    feature_config: FeatureConfig = None
    training_config: TrainingConfig = None
    
    # Pipeline options
    run_validation: bool = True
    save_artifacts: bool = True
    artifact_dir: str = "artifacts/training"
    
    def __post_init__(self):
        """Initialize default configs if not provided."""
        if self.data_config is None:
            self.data_config = DataConfig()
        if self.feature_config is None:
            self.feature_config = FeatureConfig()
        if self.training_config is None:
            self.training_config = TrainingConfig()


class TrainingPipeline:
    """
    End-to-end training pipeline for anomaly detection models.
    
    Pipeline stages:
    1. Data Loading - Load telemetry data from various sources
    2. Data Validation - Ensure data quality
    3. Feature Engineering - Extract and scale features
    4. Train/Test Split - Prepare training and evaluation sets
    5. Model Training - Train anomaly detection model
    6. Model Evaluation - Evaluate performance
    7. Model Persistence - Save trained model
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize training pipeline.
        
        Args:
            config: PipelineConfig instance
        """
        self.config = config or PipelineConfig()
        
        # Initialize pipeline components
        self.data_loader = DataLoader(self.config.data_config)
        self.feature_engineer = FeatureEngineer(self.config.feature_config)
        self.model_trainer = ModelTrainer(self.config.training_config)
        
        # Pipeline state
        self._raw_data: List[Dict[str, Any]] = []
        self._train_data: List[Dict[str, Any]] = []
        self._test_data: List[Dict[str, Any]] = []
        self._validation_data: List[Dict[str, Any]] = []
        
        self._train_features: List[List[float]] = []
        self._test_features: List[List[float]] = []
        self._validation_features: List[List[float]] = []
        
        self._pipeline_metadata: Dict[str, Any] = {}
    
    def load_data_from_json(self, filepath: str) -> None:
        """Load data from JSON file."""
        logger.info(f"Stage 1/7: Loading data from {filepath}")
        self._raw_data = self.data_loader.load_from_json(filepath)
        logger.info(f"Loaded {len(self._raw_data)} records")
    
    def load_data_from_csv(self, filepath: str) -> None:
        """Load data from CSV file."""
        logger.info(f"Stage 1/7: Loading data from {filepath}")
        self._raw_data = self.data_loader.load_from_csv(filepath)
        logger.info(f"Loaded {len(self._raw_data)} records")
    
    def load_data_from_list(self, data: List[Dict[str, Any]]) -> None:
        """Load data from list."""
        logger.info(f"Stage 1/7: Loading {len(data)} records from list")
        self._raw_data = self.data_loader.load_from_list(data)
    
    def validate_data(self) -> None:
        """
        Validate data quality.
        
        Stage 2/7
        """
        logger.info("Stage 2/7: Validating data")
        self.data_loader.validate_data(self._raw_data)
        logger.info("Data validation passed")
    
    def prepare_data(self) -> None:
        """
        Prepare data splits for training.
        
        Stage 3/7: Split into train/test/validation
        """
        logger.info("Stage 3/7: Preparing data splits")
        
        # Split into train and test
        train_data, test_data = self.data_loader.split_train_test(
            self._raw_data
        )
        
        # Further split train into actual train and validation
        actual_train, validation_data = self.data_loader.split_validation(
            train_data
        )
        
        self._train_data = actual_train
        self._test_data = test_data
        self._validation_data = validation_data
        
        logger.info(
            f"Data splits: {len(actual_train)} train, "
            f"{len(validation_data)} validation, {len(test_data)} test"
        )
    
    def engineer_features(self) -> None:
        """
        Extract and scale features.
        
        Stage 4/7: Feature engineering
        """
        logger.info("Stage 4/7: Engineering features")
        
        # Fit scaler on training data
        self.feature_engineer.fit(self._train_data)
        
        # Transform all datasets
        self._train_features = self.feature_engineer.transform_batch(
            self._train_data
        )
        self._validation_features = self.feature_engineer.transform_batch(
            self._validation_data
        )
        self._test_features = self.feature_engineer.transform_batch(
            self._test_data
        )
        
        logger.info(
            f"Features engineered: {len(self._train_features)} train, "
            f"{len(self._validation_features)} validation, "
            f"{len(self._test_features)} test"
        )
    
    def train_model(self) -> Dict[str, Any]:
        """
        Train the anomaly detection model.
        
        Stage 5/7: Model training
        """
        logger.info("Stage 5/7: Training model")
        
        metadata = self.model_trainer.train(self._train_features)
        
        logger.info(f"Model training completed: {metadata}")
        return metadata
    
    def evaluate_model(self) -> Dict[str, float]:
        """
        Evaluate model on test data.
        
        Stage 6/7: Model evaluation
        """
        logger.info("Stage 6/7: Evaluating model")
        
        metrics = self.model_trainer.evaluate(
            self._test_features,
            y_test=None  # Labels not available for anomaly detection
        )
        
        logger.info(f"Model evaluation metrics: {metrics}")
        
        # Check minimum accuracy requirement
        accuracy = metrics.get("accuracy", 0)
        if (accuracy > 0 and
            accuracy < self.config.training_config.min_accuracy):
            logger.warning(
                f"Model accuracy {accuracy:.2%} below minimum "
                f"{self.config.training_config.min_accuracy:.2%}"
            )
        
        return metrics
    
    def save_model(self) -> str:
        """
        Save trained model.
        
        Stage 7/7: Model persistence
        """
        logger.info("Stage 7/7: Saving model")
        
        model_path = self.model_trainer.save_model()
        logger.info(f"Model saved to {model_path}")
        
        return model_path
    
    def run_full_pipeline(
        self,
        data_source: str,
        data_type: str = "json",
    ) -> Dict[str, Any]:
        """
        Execute complete training pipeline.
        
        Args:
            data_source: Path to data file or data list
            data_type: Type of data source ("json", "csv", or "list")
            
        Returns:
            Pipeline results dictionary
        """
        logger.info("=" * 60)
        logger.info("Starting AstraGuard AI Training Pipeline")
        logger.info("=" * 60)
        
        start_time = datetime.now()
        
        try:
            # Stage 1: Load data
            if data_type == "json":
                self.load_data_from_json(data_source)
            elif data_type == "csv":
                self.load_data_from_csv(data_source)
            elif data_type == "list":
                self.load_data_from_list(data_source)
            else:
                raise ValueError(f"Unsupported data type: {data_type}")
            
            # Stage 2: Validate
            if self.config.run_validation:
                self.validate_data()
            
            # Stage 3: Prepare
            self.prepare_data()
            
            # Stage 4: Engineer features
            self.engineer_features()
            
            # Stage 5: Train
            train_metadata = self.train_model()
            
            # Stage 6: Evaluate
            eval_metrics = self.evaluate_model()
            
            # Stage 7: Save
            model_path = self.save_model()
            
            # Prepare results
            pipeline_time = (datetime.now() - start_time).total_seconds()
            
            results = {
                "status": "success",
                "pipeline_time_seconds": pipeline_time,
                "data_source": data_source,
                "data_type": data_type,
                "n_raw_samples": len(self._raw_data),
                "n_train_samples": len(self._train_features),
                "n_validation_samples": len(self._validation_features),
                "n_test_samples": len(self._test_features),
                "training_metadata": train_metadata,
                "evaluation_metrics": eval_metrics,
                "model_path": model_path,
                "timestamp": start_time.isoformat(),
            }
            
            logger.info("=" * 60)
            logger.info("Training Pipeline Completed Successfully!")
            logger.info(f"Total time: {pipeline_time:.2f}s")
            logger.info("=" * 60)
            
            self._pipeline_metadata = results
            return results
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            
            results = {
                "status": "failed",
                "error": str(e),
                "timestamp": start_time.isoformat(),
            }
            
            self._pipeline_metadata = results
            raise
    
    def get_model(self) -> Any:
        """Get trained model."""
        return self.model_trainer.get_model()
    
    def get_pipeline_metadata(self) -> Dict[str, Any]:
        """Get pipeline execution metadata."""
        return self._pipeline_metadata.copy()
