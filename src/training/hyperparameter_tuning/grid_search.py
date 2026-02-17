"""
Grid Search strategy for hyperparameter tuning.

Exhaustive search over specified parameter grid.
"""

import logging
import itertools
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from .parameter_space import ParameterSpace, ParameterType, ParameterConfig
from .cross_validation import CrossValidator, CVFold

logger = logging.getLogger(__name__)


@dataclass
class GridSearchConfig:
    """Configuration for Grid Search."""
    
    # Tuning parameters
    random_seed: Optional[int] = 42
    verbose: bool = True
    
    # Parallelization (not implemented in basic version)
    n_jobs: int = 1  # 1 = sequential
    
    # Early stopping
    enable_early_stopping: bool = False
    early_stopping_rounds: int = 5


class GridSearchTuner:
    """
    Grid Search hyperparameter tuning.
    
    Exhaustively searches over parameter grid by:
    1. Generating all parameter combinations
    2. Training model with each combination
    3. Evaluating using cross-validation
    4. Selecting best combination
    """
    
    def __init__(
        self,
        param_space: ParameterSpace,
        config: Optional[GridSearchConfig] = None
    ):
        """
        Initialize Grid Search tuner.
        
        Args:
            param_space: Parameter space to search
            config: Grid Search config
        """
        self.param_space = param_space
        self.config = config or GridSearchConfig()
        
        self._results: List[Dict[str, Any]] = []
        self._best_config: Optional[Dict[str, Any]] = None
        self._best_score: float = float('-inf')
    
    def generate_grid(self) -> List[Dict[str, Any]]:
        """
        Generate all parameter combinations for grid.
        
        Returns:
            List of parameter config dictionaries
        """
        params = self.param_space.get_all_parameters()
        
        # Generate value lists for each parameter
        param_values = {}
        for name, config in params.items():
            if config.param_type == ParameterType.INT:
                min_val, max_val = config.values
                param_values[name] = list(range(min_val, max_val + 1))
            
            elif config.param_type == ParameterType.FLOAT:
                min_val, max_val = config.values
                # Generate approximately 5 values in range
                step = (max_val - min_val) / 5
                values = [min_val + i * step for i in range(6)]
                param_values[name] = values
            
            elif config.param_type == ParameterType.CATEGORICAL:
                param_values[name] = config.values
        
        # Generate all combinations
        grid = []
        param_names = list(param_values.keys())
        param_lists = [param_values[name] for name in param_names]
        
        for combination in itertools.product(*param_lists):
            config = dict(zip(param_names, combination))
            grid.append(config)
        
        logger.info(f"Generated grid with {len(grid)} parameter combinations")
        return grid
    
    def search(
        self,
        model_class: type,
        X_train: List[List[float]],
        cv_validator: CrossValidator,
        scoring_func,
    ) -> Dict[str, Any]:
        """
        Execute grid search.
        
        Args:
            model_class: Model class to instantiate
            X_train: Training features
            cv_validator: Cross-validator for evaluation
            scoring_func: Function to score model (higher is better)
            
        Returns:
            Best result dictionary
        """
        logger.info("Starting Grid Search")
        start_time = datetime.now()
        
        # Generate grid
        grid = self.generate_grid()
        
        if self.config.verbose:
            logger.info(f"Grid size: {len(grid)} combinations")
        
        # Generate folds
        n_samples = len(X_train)
        folds = cv_validator.generate_folds(n_samples)
        
        # Try each configuration
        for grid_idx, config in enumerate(grid):
            if self.config.verbose and (grid_idx + 1) % 5 == 0:
                logger.info(f"Evaluating configuration {grid_idx + 1}/{len(grid)}")
            
            # Cross-validate configuration
            fold_scores = []
            
            for fold in folds:
                try:
                    # Get fold data
                    X_fold_train = [X_train[i] for i in fold.train_indices]
                    X_fold_test = [X_train[i] for i in fold.test_indices]
                    
                    # Train model with this config
                    model = model_class(**config)
                    model.fit(X_fold_train)
                    
                    # Score
                    score = scoring_func(model, X_fold_test)
                    fold_scores.append(score)
                
                except Exception as e:
                    logger.warning(f"Error evaluating config {config}: {e}")
                    fold_scores.append(float('-inf'))
            
            # Record result
            mean_score = sum(fold_scores) / len(fold_scores) if fold_scores else 0
            
            result = {
                "config": config,
                "mean_score": mean_score,
                "fold_scores": fold_scores,
                "n_folds": len(fold_scores),
            }
            
            self._results.append(result)
            
            # Track best
            if mean_score > self._best_score:
                self._best_score = mean_score
                self._best_config = config
        
        search_time = (datetime.now() - start_time).total_seconds()
        
        if self.config.verbose:
            logger.info(f"Grid Search completed in {search_time:.2f}s")
            logger.info(f"Best score: {self._best_score:.4f}")
            logger.info(f"Best config: {self._best_config}")
        
        return self.get_best_result()
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all tuning results."""
        return sorted(
            self._results,
            key=lambda x: x["mean_score"],
            reverse=True
        )
    
    def get_best_result(self) -> Dict[str, Any]:
        """Get best result."""
        if not self._results:
            raise ValueError("No results available")
        
        return sorted(
            self._results,
            key=lambda x: x["mean_score"],
            reverse=True
        )[0]
    
    def get_best_config(self) -> Optional[Dict[str, Any]]:
        """Get best hyperparameter configuration."""
        return self._best_config
    
    def get_best_score(self) -> float:
        """Get best score."""
        return self._best_score
