"""
Comprehensive test suite for hyperparameter tuning.

Tests cover:
- Parameter space definition
- Cross-validation strategies
- Grid Search
- Random Search
- Tuning orchestration
"""

import pytest
from typing import List
import math

from src.training.hyperparameter_tuning.parameter_space import (
    ParameterSpace, ParameterConfig, ParameterType, SearchSpace
)
from src.training.hyperparameter_tuning.cross_validation import (
    CrossValidator, CVStrategy, CVFold
)
from src.training.hyperparameter_tuning.grid_search import (
    GridSearchTuner, GridSearchConfig
)
from src.training.hyperparameter_tuning.random_search import (
    RandomSearchTuner, RandomSearchConfig
)
from src.training.hyperparameter_tuning.tuner import (
    HyperparameterTuner, TuningConfig, TuningStrategy
)


# ========== Fixtures ==========

@pytest.fixture
def sample_training_data() -> List[List[float]]:
    """Generate sample training data."""
    data = []
    for i in range(100):
        sample = [8.0 + i * 0.01, 25.0 + i * 0.05, 0.01 * (i % 5)]
        data.append(sample)
    return data


@pytest.fixture
def param_space() -> ParameterSpace:
    """Create parameter space."""
    space = ParameterSpace()
    space.add_int_parameter("n_estimators", 10, 100, default=50)
    space.add_float_parameter("contamination", 0.01, 0.2, default=0.1)
    space.add_categorical_parameter("metric", ["euclidean", "manhattan"], default="euclidean")
    return space


# ========== Parameter Space Tests ==========

class TestParameterSpace:
    """Tests for parameter space management."""
    
    def test_parameter_space_creation(self):
        """Test creating parameter space."""
        space = ParameterSpace()
        assert space.get_all_parameters() == {}
    
    def test_add_int_parameter(self):
        """Test adding integer parameter."""
        space = ParameterSpace()
        space.add_int_parameter("n_estimators", 10, 100)
        
        param = space.get_parameter("n_estimators")
        assert param is not None
        assert param.param_type == ParameterType.INT
    
    def test_add_float_parameter(self):
        """Test adding float parameter."""
        space = ParameterSpace()
        space.add_float_parameter("learning_rate", 0.001, 0.1)
        
        param = space.get_parameter("learning_rate")
        assert param is not None
        assert param.param_type == ParameterType.FLOAT
    
    def test_add_categorical_parameter(self):
        """Test adding categorical parameter."""
        space = ParameterSpace()
        space.add_categorical_parameter("metric", ["euclidean", "manhattan"])
        
        param = space.get_parameter("metric")
        assert param is not None
        assert param.param_type == ParameterType.CATEGORICAL
    
    def test_validate_config_success(self, param_space):
        """Test successful config validation."""
        config = {
            "n_estimators": 50,
            "contamination": 0.1,
            "metric": "euclidean"
        }
        assert param_space.validate_config(config)
    
    def test_validate_config_missing_param(self, param_space):
        """Test validation with missing parameter."""
        config = {
            "n_estimators": 50,
            "contamination": 0.1
        }
        with pytest.raises(ValueError):
            param_space.validate_config(config)
    
    def test_validate_config_out_of_range(self, param_space):
        """Test validation with out-of-range value."""
        config = {
            "n_estimators": 200,  # Out of range
            "contamination": 0.1,
            "metric": "euclidean"
        }
        with pytest.raises(ValueError):
            param_space.validate_config(config)
    
    def test_isolation_forest_space(self):
        """Test predefined Isolation Forest search space."""
        space = SearchSpace.isolation_forest_space()
        assert space.get_parameter("n_estimators") is not None
        assert space.get_parameter("contamination") is not None
    
    def test_one_class_svm_space(self):
        """Test predefined One-Class SVM search space."""
        space = SearchSpace.one_class_svm_space()
        assert space.get_parameter("nu") is not None
        assert space.get_parameter("kernel") is not None
    
    def test_lof_space(self):
        """Test predefined LOF search space."""
        space = SearchSpace.local_outlier_factor_space()
        assert space.get_parameter("n_neighbors") is not None
        assert space.get_parameter("metric") is not None


# ========== Cross-Validation Tests ==========

class TestCrossValidation:
    """Tests for cross-validation."""
    
    def test_cv_initialization(self):
        """Test CV initialization."""
        cv = CrossValidator(strategy=CVStrategy.KFOLD, n_splits=5)
        assert cv.n_splits == 5
        assert cv.strategy == CVStrategy.KFOLD
    
    def test_kfold_generation(self):
        """Test K-Fold fold generation."""
        cv = CrossValidator(strategy=CVStrategy.KFOLD, n_splits=5)
        folds = cv.generate_folds(100)
        
        assert len(folds) == 5
        for fold in folds:
            assert len(fold.train_indices) + len(fold.test_indices) == 100
    
    def test_stratified_kfold_generation(self):
        """Test Stratified K-Fold generation."""
        cv = CrossValidator(strategy=CVStrategy.STRATIFIED_KFOLD, n_splits=5)
        labels = [0]*50 + [1]*50
        folds = cv.generate_folds(100, labels)
        
        assert len(folds) == 5
    
    def test_train_test_split_generation(self):
        """Test train/test split generation."""
        cv = CrossValidator(strategy=CVStrategy.TRAIN_TEST_SPLIT, n_splits=1)
        folds = cv.generate_folds(100)
        
        assert len(folds) == 1
        fold = folds[0]
        assert len(fold.train_indices) + len(fold.test_indices) == 100
    
    def test_fold_access(self):
        """Test accessing specific fold."""
        cv = CrossValidator(strategy=CVStrategy.KFOLD, n_splits=3)
        cv.generate_folds(30)
        
        fold = cv.get_fold(0)
        assert fold is not None
        assert len(fold.train_indices) + len(fold.test_indices) == 30


# ========== Grid Search Tests ==========

class MockModel:
    """Simple mock model for testing."""
    
    def __init__(self, **kwargs):
        self.params = kwargs
    
    def fit(self, X):
        self.X = X
        return self
    
    def predict(self, X):
        return [1] * len(X)


def simple_scoring(model, X_test):
    """Simple scoring function."""
    return 0.8  # Fixed score for testing


class TestGridSearch:
    """Tests for Grid Search."""
    
    def test_grid_search_initialization(self, param_space):
        """Test Grid Search initialization."""
        tuner = GridSearchTuner(param_space)
        assert tuner.param_space == param_space
    
    def test_grid_generation(self, param_space):
        """Test grid generation."""
        tuner = GridSearchTuner(param_space)
        grid = tuner.generate_grid()
        
        assert len(grid) > 0
        for config in grid:
            assert "n_estimators" in config
            assert "contamination" in config
            assert "metric" in config
    
    def test_grid_search_execution(self, param_space, sample_training_data):
        """Test grid search execution."""
        tuner = GridSearchTuner(param_space, GridSearchConfig(verbose=False))
        cv = CrossValidator(n_splits=2)
        
        result = tuner.search(
            MockModel, sample_training_data, cv, simple_scoring
        )
        
        assert "config" in result
        assert "mean_score" in result
    
    def test_grid_search_results(self, param_space, sample_training_data):
        """Test getting grid search results."""
        tuner = GridSearchTuner(param_space, GridSearchConfig(verbose=False))
        cv = CrossValidator(n_splits=2)
        
        tuner.search(MockModel, sample_training_data, cv, simple_scoring)
        
        results = tuner.get_results()
        assert len(results) > 0
        assert results[0]["mean_score"] >= results[-1]["mean_score"]


# ========== Random Search Tests ==========

class TestRandomSearch:
    """Tests for Random Search."""
    
    def test_random_search_initialization(self, param_space):
        """Test Random Search initialization."""
        tuner = RandomSearchTuner(param_space)
        assert tuner.param_space == param_space
    
    def test_sample_parameters(self, param_space):
        """Test parameter sampling."""
        tuner = RandomSearchTuner(param_space)
        
        for _ in range(10):
            config = tuner.sample_parameters()
            assert "n_estimators" in config
            assert "contamination" in config
            assert "metric" in config
    
    def test_random_search_execution(self, param_space, sample_training_data):
        """Test random search execution."""
        tuner = RandomSearchTuner(
            param_space,
            RandomSearchConfig(n_iter=5, verbose=False)
        )
        cv = CrossValidator(n_splits=2)
        
        result = tuner.search(
            MockModel, sample_training_data, cv, simple_scoring
        )
        
        assert "config" in result
        assert "mean_score" in result
    
    def test_random_search_iteration_count(self, param_space, sample_training_data):
        """Test iteration count tracking."""
        config = RandomSearchConfig(n_iter=10, verbose=False)
        tuner = RandomSearchTuner(param_space, config)
        cv = CrossValidator(n_splits=2)
        
        tuner.search(MockModel, sample_training_data, cv, simple_scoring)
        
        assert tuner.get_iteration_count() == 10


# ========== Hyperparameter Tuner Tests ==========

class TestHyperparameterTuner:
    """Tests for main tuning orchestrator."""
    
    def test_tuner_initialization(self):
        """Test tuner initialization."""
        config = TuningConfig(strategy=TuningStrategy.RANDOM_SEARCH)
        tuner = HyperparameterTuner(config)
        assert tuner.config.strategy == TuningStrategy.RANDOM_SEARCH
    
    def test_tuner_with_custom_space(self, param_space):
        """Test tuner with custom parameter space."""
        config = TuningConfig(
            strategy=TuningStrategy.RANDOM_SEARCH,
            param_space=param_space
        )
        tuner = HyperparameterTuner(config)
        assert tuner.get_param_space() == param_space
    
    def test_tune_random_search(self, sample_training_data):
        """Test tuning with Random Search."""
        config = TuningConfig(
            strategy=TuningStrategy.RANDOM_SEARCH,
            param_space=SearchSpace.isolation_forest_space(),
            random_search_config=RandomSearchConfig(n_iter=3, verbose=False)
        )
        tuner = HyperparameterTuner(config)
        
        result = tuner.tune(MockModel, sample_training_data, simple_scoring)
        
        assert result.status == "success"
        assert result.strategy == "random_search"
        assert result.best_score >= 0
    
    def test_tune_grid_search(self, sample_training_data):
        """Test tuning with Grid Search."""
        space = ParameterSpace()
        space.add_int_parameter("n_estimators", 10, 20)
        space.add_float_parameter("contamination", 0.05, 0.15)
        
        config = TuningConfig(
            strategy=TuningStrategy.GRID_SEARCH,
            param_space=space,
            grid_search_config=GridSearchConfig(verbose=False)
        )
        tuner = HyperparameterTuner(config)
        
        result = tuner.tune(MockModel, sample_training_data, simple_scoring)
        
        assert result.status == "success"
        assert result.strategy == "grid_search"
    
    def test_get_results(self, sample_training_data):
        """Test retrieving tuning results."""
        config = TuningConfig(
            strategy=TuningStrategy.RANDOM_SEARCH,
            param_space=SearchSpace.isolation_forest_space(),
            random_search_config=RandomSearchConfig(n_iter=2, verbose=False)
        )
        tuner = HyperparameterTuner(config)
        
        result = tuner.tune(MockModel, sample_training_data, simple_scoring)
        
        retrieved = tuner.get_results()
        assert retrieved is not None
        assert retrieved.status == "success"
    
    def test_top_configs(self, sample_training_data):
        """Test getting top configurations."""
        config = TuningConfig(
            strategy=TuningStrategy.RANDOM_SEARCH,
            param_space=SearchSpace.isolation_forest_space(),
            random_search_config=RandomSearchConfig(n_iter=5, verbose=False)
        )
        tuner = HyperparameterTuner(config)
        
        result = tuner.tune(MockModel, sample_training_data, simple_scoring)
        top_configs = result.get_top_configs(n=3)
        
        assert len(top_configs) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
