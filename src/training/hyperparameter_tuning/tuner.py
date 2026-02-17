"""
Hyperparameter tuning orchestrator.

Coordinates:
- Parameter space definition
- Cross-validation setup
- Tuning strategy selection
- Results tracking and reporting
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .parameter_space import ParameterSpace, SearchSpace
from .cross_validation import CrossValidator, CVStrategy
from .grid_search import GridSearchTuner, GridSearchConfig
from .random_search import RandomSearchTuner, RandomSearchConfig

logger = logging.getLogger(__name__)


class TuningStrategy(str, Enum):
    """Hyperparameter tuning strategies."""
    
    GRID_SEARCH = "grid_search"
    RANDOM_SEARCH = "random_search"


@dataclass
class TuningConfig:
    """Configuration for hyperparameter tuning."""
    
    # Strategy and parameters
    strategy: TuningStrategy = TuningStrategy.RANDOM_SEARCH
    param_space: Optional[ParameterSpace] = None
    
    # Cross-validation
    cv_strategy: CVStrategy = CVStrategy.KFOLD
    cv_splits: int = 5
    cv_random_seed: Optional[int] = 42
    
    # Grid Search specific
    grid_search_config: Optional[GridSearchConfig] = None
    
    # Random Search specific
    random_search_config: Optional[RandomSearchConfig] = None
    
    # General options
    verbose: bool = True
    random_seed: Optional[int] = 42
    
    def __post_init__(self):
        """Initialize default configs if needed."""
        if self.grid_search_config is None:
            self.grid_search_config = GridSearchConfig()
        if self.random_search_config is None:
            self.random_search_config = RandomSearchConfig()


@dataclass
class TuningResult:
    """Results from hyperparameter tuning."""
    
    status: str  # "success" or "failed"
    strategy: str
    best_config: Dict[str, Any]
    best_score: float
    all_results: List[Dict[str, Any]]
    
    # Metadata
    tuning_time_seconds: float
    n_iterations: int
    timestamp: str
    
    # Optional error info
    error: Optional[str] = None
    
    def get_top_configs(self, n: int = 5) -> List[Dict[str, Any]]:
        """Get top N configurations."""
        sorted_results = sorted(
            self.all_results,
            key=lambda x: x.get("mean_score", 0),
            reverse=True
        )
        return sorted_results[:n]


class HyperparameterTuner:
    """
    Main orchestrator for hyperparameter tuning.
    
    Manages:
    - Parameter space setup
    - Cross-validation
    - Tuning strategy execution
    - Results tracking
    """
    
    def __init__(self, config: Optional[TuningConfig] = None):
        """
        Initialize hyperparameter tuner.
        
        Args:
            config: Tuning configuration
        """
        self.config = config or TuningConfig()
        
        # Set default parameter space if not provided
        if self.config.param_space is None:
            self.config.param_space = SearchSpace.isolation_forest_space()
        
        self._param_space = self.config.param_space
        self._cv_validator = CrossValidator(
            strategy=self.config.cv_strategy,
            n_splits=self.config.cv_splits,
            random_seed=self.config.cv_random_seed
        )
        
        self._tuning_results: Optional[TuningResult] = None
    
    def tune(
        self,
        model_class: type,
        X_train: List[List[float]],
        scoring_func: Callable[[Any, List[List[float]]], float],
    ) -> TuningResult:
        """
        Execute hyperparameter tuning.
        
        Args:
            model_class: Model class to tune
            X_train: Training features
            scoring_func: Scoring function (returns float, higher is better)
            
        Returns:
            TuningResult with best configuration and results
        """
        logger.info(f"Starting hyperparameter tuning with {self.config.strategy}")
        start_time = datetime.now()
        
        try:
            # Select and execute tuning strategy
            if self.config.strategy == TuningStrategy.GRID_SEARCH:
                best_result = self._tune_grid_search(
                    model_class, X_train, scoring_func
                )
            elif self.config.strategy == TuningStrategy.RANDOM_SEARCH:
                best_result = self._tune_random_search(
                    model_class, X_train, scoring_func
                )
            else:
                raise ValueError(f"Unknown strategy: {self.config.strategy}")
            
            tuning_time = (datetime.now() - start_time).total_seconds()
            
            # Create result
            if self.config.strategy == TuningStrategy.GRID_SEARCH:
                tuner_obj = self._last_tuner
                n_iterations = len(tuner_obj.get_results())
            else:
                tuner_obj = self._last_tuner
                n_iterations = tuner_obj.get_iteration_count()
            
            result = TuningResult(
                status="success",
                strategy=self.config.strategy.value,
                best_config=best_result["config"],
                best_score=best_result["mean_score"],
                all_results=tuner_obj.get_results(),
                tuning_time_seconds=tuning_time,
                n_iterations=n_iterations,
                timestamp=start_time.isoformat(),
            )
            
            self._tuning_results = result
            
            if self.config.verbose:
                logger.info(
                    f"Tuning completed in {tuning_time:.2f}s. "
                    f"Best score: {result.best_score:.4f}"
                )
            
            return result
        
        except Exception as e:
            logger.error(f"Tuning failed: {e}", exc_info=True)
            
            result = TuningResult(
                status="failed",
                strategy=self.config.strategy.value,
                best_config={},
                best_score=float('-inf'),
                all_results=[],
                tuning_time_seconds=(datetime.now() - start_time).total_seconds(),
                n_iterations=0,
                timestamp=start_time.isoformat(),
                error=str(e),
            )
            
            self._tuning_results = result
            raise
    
    def _tune_grid_search(
        self,
        model_class: type,
        X_train: List[List[float]],
        scoring_func: Callable
    ) -> Dict[str, Any]:
        """Execute grid search tuning."""
        tuner = GridSearchTuner(
            self._param_space,
            self.config.grid_search_config
        )
        
        self._last_tuner = tuner
        
        return tuner.search(
            model_class, X_train, self._cv_validator, scoring_func
        )
    
    def _tune_random_search(
        self,
        model_class: type,
        X_train: List[List[float]],
        scoring_func: Callable
    ) -> Dict[str, Any]:
        """Execute random search tuning."""
        tuner = RandomSearchTuner(
            self._param_space,
            self.config.random_search_config
        )
        
        self._last_tuner = tuner
        
        return tuner.search(
            model_class, X_train, self._cv_validator, scoring_func
        )
    
    def get_results(self) -> Optional[TuningResult]:
        """Get tuning results."""
        return self._tuning_results
    
    def set_param_space(self, param_space: ParameterSpace) -> None:
        """Set parameter space."""
        self._param_space = param_space
        self.config.param_space = param_space
    
    def get_param_space(self) -> ParameterSpace:
        """Get parameter space."""
        return self._param_space
