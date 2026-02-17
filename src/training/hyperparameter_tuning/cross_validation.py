"""
Cross-validation framework for hyperparameter tuning.

Provides:
- K-Fold cross-validation
- Stratified K-Fold
- Train/test split validation
- Fold generation and tracking
"""

import logging
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import random

logger = logging.getLogger(__name__)


class CVStrategy(str, Enum):
    """Cross-validation strategies."""
    
    KFOLD = "kfold"
    STRATIFIED_KFOLD = "stratified_kfold"
    TRAIN_TEST_SPLIT = "train_test_split"


@dataclass
class CVFold:
    """A single cross-validation fold."""
    
    fold_id: int
    train_indices: List[int]
    test_indices: List[int]
    
    def __len__(self) -> int:
        """Total samples in fold."""
        return len(self.train_indices) + len(self.test_indices)


@dataclass
class CVResult:
    """Results from cross-validation."""
    
    fold_id: int
    train_score: float
    test_score: float
    config: Dict[str, Any]
    metrics: Dict[str, float]
    
    def mean_score(self) -> float:
        """Average of train and test scores."""
        return (self.train_score + self.test_score) / 2


class CrossValidator:
    """
    Manages cross-validation splitting and evaluation.
    
    Supports:
    - K-Fold cross-validation
    - Stratified K-Fold (for imbalanced data)
    - Train/test split
    """
    
    def __init__(
        self,
        strategy: CVStrategy = CVStrategy.KFOLD,
        n_splits: int = 5,
        random_seed: Optional[int] = None
    ):
        """
        Initialize cross-validator.
        
        Args:
            strategy: CV strategy to use
            n_splits: Number of folds/splits
            random_seed: Random seed for reproducibility
        """
        self.strategy = strategy
        self.n_splits = n_splits
        self.random_seed = random_seed
        
        if random_seed is not None:
            random.seed(random_seed)
        
        self._folds: List[CVFold] = []
    
    def generate_folds(
        self,
        n_samples: int,
        labels: Optional[List[int]] = None
    ) -> List[CVFold]:
        """
        Generate cross-validation folds.
        
        Args:
            n_samples: Number of samples
            labels: Sample labels (for stratified split)
            
        Returns:
            List of CVFold instances
        """
        if self.strategy == CVStrategy.KFOLD:
            folds = self._generate_kfold(n_samples)
        elif self.strategy == CVStrategy.STRATIFIED_KFOLD:
            folds = self._generate_stratified_kfold(n_samples, labels)
        elif self.strategy == CVStrategy.TRAIN_TEST_SPLIT:
            folds = self._generate_train_test_split(n_samples)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
        
        self._folds = folds
        logger.info(f"Generated {len(folds)} folds using {self.strategy}")
        
        return folds
    
    def _generate_kfold(self, n_samples: int) -> List[CVFold]:
        """Generate K-Fold splits."""
        indices = list(range(n_samples))
        random.shuffle(indices)
        
        fold_size = n_samples // self.n_splits
        folds = []
        
        for fold_id in range(self.n_splits):
            start = fold_id * fold_size
            if fold_id == self.n_splits - 1:
                # Last fold gets remaining samples
                end = n_samples
            else:
                end = (fold_id + 1) * fold_size
            
            test_indices = sorted(indices[start:end])
            train_indices = sorted(indices[:start] + indices[end:])
            
            folds.append(CVFold(
                fold_id=fold_id,
                train_indices=train_indices,
                test_indices=test_indices
            ))
        
        return folds
    
    def _generate_stratified_kfold(
        self,
        n_samples: int,
        labels: Optional[List[int]] = None
    ) -> List[CVFold]:
        """Generate Stratified K-Fold splits."""
        if labels is None:
            # Fall back to regular K-Fold if no labels provided
            return self._generate_kfold(n_samples)
        
        # Group indices by label
        class_indices = {}
        for idx, label in enumerate(labels):
            if label not in class_indices:
                class_indices[label] = []
            class_indices[label].append(idx)
        
        # Shuffle within each class
        for label in class_indices:
            random.shuffle(class_indices[label])
        
        folds = [[] for _ in range(self.n_splits)]
        
        # Distribute class samples across folds
        for label, indices in class_indices.items():
            fold_size = len(indices) // self.n_splits
            for fold_id in range(self.n_splits):
                start = fold_id * fold_size
                if fold_id == self.n_splits - 1:
                    end = len(indices)
                else:
                    end = (fold_id + 1) * fold_size
                
                folds[fold_id].extend(indices[start:end])
        
        # Create CVFold objects
        cv_folds = []
        all_indices = list(range(n_samples))
        
        for fold_id in range(self.n_splits):
            test_indices = sorted(folds[fold_id])
            train_indices = sorted(
                [idx for idx in all_indices if idx not in test_indices]
            )
            
            cv_folds.append(CVFold(
                fold_id=fold_id,
                train_indices=train_indices,
                test_indices=test_indices
            ))
        
        return cv_folds
    
    def _generate_train_test_split(
        self,
        n_samples: int,
        train_ratio: float = 0.8
    ) -> List[CVFold]:
        """Generate single train/test split."""
        indices = list(range(n_samples))
        random.shuffle(indices)
        
        split_point = int(n_samples * train_ratio)
        train_indices = sorted(indices[:split_point])
        test_indices = sorted(indices[split_point:])
        
        return [CVFold(
            fold_id=0,
            train_indices=train_indices,
            test_indices=test_indices
        )]
    
    def get_fold(self, fold_id: int) -> Optional[CVFold]:
        """Get a specific fold."""
        if fold_id < len(self._folds):
            return self._folds[fold_id]
        return None
    
    def get_all_folds(self) -> List[CVFold]:
        """Get all folds."""
        return self._folds.copy()
    
    def get_fold_count(self) -> int:
        """Get number of folds."""
        return len(self._folds)
