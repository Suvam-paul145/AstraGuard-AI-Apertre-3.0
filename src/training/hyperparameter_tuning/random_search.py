"""
Random Search strategy for hyperparameter tuning.

Efficient search using random sampling of parameter space.
"""

import logging
import random
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from .parameter_space import ParameterSpace, ParameterType
from .cross_validation import CrossValidator

logger = logging.getLogger(__name__)


@dataclass
class RandomSearchConfig:
    """Configuration for Random Search."""
    
    # Search parameters
    n_iter: int = 20  # Number of iterations
    random_seed: Optional[int] = 42
    verbose: bool = True
    
    # Parallelization
    n_jobs: int = 1  # 1 = sequential
    
    # Early stopping
    enable_early_stopping: bool = False
    early_stopping_rounds: int = 5
    early_stopping_threshold: float = 0.001  # Min improvement


class RandomSearchTuner:
    """
    Random Search hyperparameter tuning.
    
    Samples random configurations from parameter space by:
    1. Randomly sampling parameters
    2. Training model with each sample
    3. Evaluating using cross-validation
    4. Selecting best sample
    
    More efficient than grid search for large parameter spaces.
    """
    
    def __init__(
        self,
        param_space: ParameterSpace,
        config: Optional[RandomSearchConfig] = None
    ):
        """
        Initialize Random Search tuner.
        
        Args:
            param_space: Parameter space to search
            config: Random Search config
        """
        self.param_space = param_space
        self.config = config or RandomSearchConfig()
        
        if self.config.random_seed is not None:
            random.seed(self.config.random_seed)
        
        self._results: List[Dict[str, Any]] = []
        self._best_config: Optional[Dict[str, Any]] = None
        self._best_score: float = float('-inf')
        self._iteration_count = 0
    
    def sample_parameters(self) -> Dict[str, Any]:
        """
        Sample random parameter configuration from space.
        
        Returns:
            Parameter configuration dictionary
        """
        params = self.param_space.get_all_parameters()
        config = {}
        
        for name, param_config in params.items():
            if param_config.param_type == ParameterType.INT:
                min_val, max_val = param_config.values
                config[name] = random.randint(min_val, max_val)
            
            elif param_config.param_type == ParameterType.FLOAT:
                min_val, max_val = param_config.values
                config[name] = random.uniform(min_val, max_val)
            
            elif param_config.param_type == ParameterType.CATEGORICAL:
                config[name] = random.choice(param_config.values)
        
        return config
    
    def search(
        self,
        model_class: type,
        X_train: List[List[float]],
        cv_validator: CrossValidator,
        scoring_func,
    ) -> Dict[str, Any]:
        """
        Execute random search.
        
        Args:
            model_class: Model class to instantiate
            X_train: Training features
            cv_validator: Cross-validator for evaluation
            scoring_func: Function to score model (higher is better)
            
        Returns:
            Best result dictionary
        """
        logger.info("Starting Random Search")
        start_time = datetime.now()
        
        if self.config.verbose:
            logger.info(f"Running {self.config.n_iter} iterations")
        
        # Generate folds
        n_samples = len(X_train)
        folds = cv_validator.generate_folds(n_samples)
        
        # Early stopping tracking
        no_improve_count = 0
        prev_best_score = float('-inf')
        
        # Sample and evaluate configurations
        for iteration in range(self.config.n_iter):
            # Sample random configuration
            config = self.sample_parameters()
            
            if self.config.verbose and (iteration + 1) % 5 == 0:
                logger.info(f"Iteration {iteration + 1}/{self.config.n_iter}")
            
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
                "iteration": iteration,
            }
            
            self._results.append(result)
            self._iteration_count += 1
            
            # Track best
            if mean_score > self._best_score:
                self._best_score = mean_score
                self._best_config = config
                no_improve_count = 0
            else:
                no_improve_count += 1
            
            # Early stopping check
            if self.config.enable_early_stopping:
                improvement = mean_score - prev_best_score
                if (improvement < self.config.early_stopping_threshold and
                    no_improve_count >= self.config.early_stopping_rounds):
                    if self.config.verbose:
                        logger.info(
                            f"Early stopping at iteration {iteration + 1} "
                            f"(no improvement for {no_improve_count} iterations)"
                        )
                    break
            
            prev_best_score = max(prev_best_score, mean_score)
        
        search_time = (datetime.now() - start_time).total_seconds()
        
        if self.config.verbose:
            logger.info(f"Random Search completed in {search_time:.2f}s")
            logger.info(f"Best score: {self._best_score:.4f}")
            logger.info(f"Best config: {self._best_config}")
        
        return self.get_best_result()
    
    def get_results(self) -> List[Dict[str, Any]]:
        """Get all tuning results, sorted by score."""
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
        """Get best score found."""
        return self._best_score
    
    def get_iteration_count(self) -> int:
        """Get number of iterations run."""
        return self._iteration_count
