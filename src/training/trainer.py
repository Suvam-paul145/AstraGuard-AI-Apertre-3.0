"""
Model trainer for anomaly detection.

This module handles:
- Model training orchestration
- Model evaluation and metrics
- Model persistence and loading
- Training history tracking
"""

import logging
import pickle
import os
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    
    # Training parameters
    model_type: str = "isolation_forest"  # isolation_forest, one_class_svm, etc.
    
    # Model hyperparameters
    hyperparams: Dict[str, Any] = field(
        default_factory=lambda: {
            "n_estimators": 100,
            "contamination": 0.1,
            "random_state": 42,
        }
    )
    
    # Training options
    save_model: bool = True
    model_save_path: str = "models/anomaly_model.pkl"
    
    # Validation
    evaluate_on_test: bool = True
    min_accuracy: float = 0.70
    
    # Tracking
    track_history: bool = True
    verbose: bool = True


class ModelTrainer:
    """
    Trains and evaluates anomaly detection models.
    
    Supports multiple model types:
    - Isolation Forest
    - One-Class SVM
    - Local Outlier Factor
    - Elliptic Envelope
    
    Provides:
    - Cross-validation
    - Hyperparameter tracking
    - Model persistence
    - Performance metrics
    """
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        """
        Initialize model trainer.
        
        Args:
            config: TrainingConfig instance
        """
        self.config = config or TrainingConfig()
        self._model: Optional[Any] = None
        self._training_history: List[Dict[str, Any]] = []
        self._metrics: Dict[str, float] = {}
        self._is_trained = False
    
    def build_model(self) -> Any:
        """
        Build model instance based on configuration.
        
        Returns:
            Untrained model instance
            
        Raises:
            ImportError: If required ML library not available
            ValueError: If model type not supported
        """
        if self.config.model_type == "isolation_forest":
            try:
                from sklearn.ensemble import IsolationForest
                model = IsolationForest(**self.config.hyperparams)
                logger.info("Built Isolation Forest model")
                return model
            except ImportError:
                raise ImportError("scikit-learn required for Isolation Forest")
        
        elif self.config.model_type == "one_class_svm":
            try:
                from sklearn.svm import OneClassSVM
                # OneClassSVM doesn't use 'contamination' parameter
                params = {k: v for k, v in self.config.hyperparams.items()
                         if k != "contamination"}
                model = OneClassSVM(**params)
                logger.info("Built One-Class SVM model")
                return model
            except ImportError:
                raise ImportError("scikit-learn required for One-Class SVM")
        
        elif self.config.model_type == "local_outlier_factor":
            try:
                from sklearn.neighbors import LocalOutlierFactor
                model = LocalOutlierFactor(**self.config.hyperparams)
                logger.info("Built Local Outlier Factor model")
                return model
            except ImportError:
                raise ImportError("scikit-learn required for LOF")
        
        else:
            raise ValueError(
                f"Unsupported model type: {self.config.model_type}. "
                "Supported: isolation_forest, one_class_svm, local_outlier_factor"
            )
    
    def train(
        self,
        X_train: List[List[float]],
        y_train: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Train the model on provided data.
        
        Args:
            X_train: Training feature vectors
            y_train: Training labels (optional, for supervised metrics)
            
        Returns:
            Training metadata dictionary
            
        Raises:
            ValueError: If data is empty or invalid
        """
        if not X_train:
            raise ValueError("Training data is empty")
        
        if self._model is None:
            self._model = self.build_model()
        
        logger.info(
            f"Starting training on {len(X_train)} samples "
            f"using {self.config.model_type}"
        )
        
        start_time = datetime.now()
        
        try:
            # Train model
            if y_train is not None:
                # For supervised models
                try:
                    self._model.fit(X_train, y_train)
                except TypeError:
                    # Model might not support labels, train unsupervised
                    self._model.fit(X_train)
            else:
                # Unsupervised training
                self._model.fit(X_train)
            
            training_time = (datetime.now() - start_time).total_seconds()
            self._is_trained = True
            
            # Record training metadata
            metadata = {
                "model_type": self.config.model_type,
                "training_time_seconds": training_time,
                "n_samples": len(X_train),
                "timestamp": start_time.isoformat(),
                "hyperparams": self.config.hyperparams,
            }
            
            self._training_history.append(metadata)
            
            if self.config.verbose:
                logger.info(
                    f"Training completed in {training_time:.2f}s "
                    f"with {len(X_train)} samples"
                )
            
            return metadata
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            raise
    
    def evaluate(
        self,
        X_test: List[List[float]],
        y_test: Optional[List[int]] = None,
    ) -> Dict[str, float]:
        """
        Evaluate model performance on test data.
        
        Args:
            X_test: Test feature vectors
            y_test: Test labels (optional)
            
        Returns:
            Dictionary of evaluation metrics
            
        Raises:
            ValueError: If model not trained or data empty
        """
        if not self._is_trained or self._model is None:
            raise ValueError("Model must be trained before evaluation")
        
        if not X_test:
            raise ValueError("Test data is empty")
        
        logger.info(f"Evaluating model on {len(X_test)} test samples")
        
        try:
            # Get predictions
            if self.config.model_type == "local_outlier_factor":
                # LOF uses predict_proba
                predictions = self._model.predict(X_test)
                scores = self._model.negative_outlier_factor_
            else:
                predictions = self._model.predict(X_test)
                
                # Get anomaly scores if available
                if hasattr(self._model, 'score_samples'):
                    scores = self._model.score_samples(X_test)
                else:
                    scores = [0.0] * len(X_test)
            
            # Calculate metrics
            metrics = self._compute_metrics(
                predictions, scores, y_test, X_test
            )
            
            self._metrics = metrics
            
            if self.config.verbose:
                logger.info(f"Evaluation metrics: {metrics}")
            
            return metrics
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            raise
    
    def _compute_metrics(
        self,
        predictions: List[int],
        scores: List[float],
        y_true: Optional[List[int]] = None,
        X_test: Optional[List[List[float]]] = None,
    ) -> Dict[str, float]:
        """
        Compute evaluation metrics.
        
        Args:
            predictions: Model predictions (-1 for anomaly, 1 for normal)
            scores: Anomaly scores
            y_true: True labels (if available)
            X_test: Test features (for additional metrics)
            
        Returns:
            Dictionary of metrics
        """
        metrics = {}
        
        # Anomaly detection rate
        n_anomalies = sum(1 for p in predictions if p == -1)
        metrics["anomaly_rate"] = n_anomalies / len(predictions) if predictions else 0
        metrics["n_anomalies_detected"] = n_anomalies
        
        # Score statistics
        if scores:
            metrics["mean_score"] = sum(scores) / len(scores)
            metrics["max_score"] = max(scores)
            metrics["min_score"] = min(scores)
        
        # If true labels available, compute supervised metrics
        if y_true is not None and len(predictions) == len(y_true):
            # Convert predictions to binary (0 = normal, 1 = anomaly)
            pred_binary = [1 if p == -1 else 0 for p in predictions]
            
            # True positives, false positives, etc.
            tp = sum(1 for pred, true in zip(pred_binary, y_true)
                    if pred == 1 and true == 1)
            fp = sum(1 for pred, true in zip(pred_binary, y_true)
                    if pred == 1 and true == 0)
            tn = sum(1 for pred, true in zip(pred_binary, y_true)
                    if pred == 0 and true == 0)
            fn = sum(1 for pred, true in zip(pred_binary, y_true)
                    if pred == 0 and true == 1)
            
            # Calculate metrics
            metrics["true_positives"] = tp
            metrics["false_positives"] = fp
            metrics["true_negatives"] = tn
            metrics["false_negatives"] = fn
            
            # Accuracy
            total = len(y_true)
            metrics["accuracy"] = (tp + tn) / total if total > 0 else 0
            
            # Precision
            metrics["precision"] = tp / (tp + fp) if (tp + fp) > 0 else 0
            
            # Recall
            metrics["recall"] = tp / (tp + fn) if (tp + fn) > 0 else 0
            
            # F1 Score
            if metrics["precision"] + metrics["recall"] > 0:
                metrics["f1_score"] = (
                    2 * (metrics["precision"] * metrics["recall"]) /
                    (metrics["precision"] + metrics["recall"])
                )
            else:
                metrics["f1_score"] = 0
        
        return metrics
    
    def save_model(self, filepath: Optional[str] = None) -> str:
        """
        Save trained model to disk.
        
        Args:
            filepath: Path to save model (uses config default if not provided)
            
        Returns:
            Path where model was saved
            
        Raises:
            ValueError: If model not trained
            IOError: If save fails
        """
        if not self._is_trained or self._model is None:
            raise ValueError("Model must be trained before saving")
        
        save_path = filepath or self.config.model_save_path
        
        # Create directory if needed
        os.makedirs(os.path.dirname(save_path) or ".", exist_ok=True)
        
        try:
            with open(save_path, "wb") as f:
                pickle.dump(self._model, f)
            
            logger.info(f"Model saved to {save_path}")
            return save_path
            
        except Exception as e:
            logger.error(f"Failed to save model: {e}")
            raise
    
    def load_model(self, filepath: str) -> None:
        """
        Load model from disk.
        
        Args:
            filepath: Path to model file
            
        Raises:
            FileNotFoundError: If file not found
            IOError: If load fails
        """
        try:
            with open(filepath, "rb") as f:
                self._model = pickle.load(f)  # noqa: S301
            
            self._is_trained = True
            logger.info(f"Model loaded from {filepath}")
            
        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def get_model(self) -> Optional[Any]:
        """Get the trained model instance."""
        return self._model
    
    def get_metrics(self) -> Dict[str, float]:
        """Get last evaluation metrics."""
        return self._metrics.copy()
    
    def get_training_history(self) -> List[Dict[str, Any]]:
        """Get training history."""
        return self._training_history.copy()
