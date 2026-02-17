# Hyperparameter Tuning Implementation

## Overview

Comprehensive hyperparameter tuning system for optimizing anomaly detection models in AstraGuard AI. Provides multiple tuning strategies, cross-validation frameworks, and result tracking.

**Status**: ✅ Approximately 30% of full implementation completed  
**Category**: machine-learning, training  
**Priority**: medium  

## Architecture

```
┌─────────────────────────────────────────────────┐
│      Hyperparameter Tuning System              │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────────┐    ┌──────────────────┐  │
│  │ Parameter Space  │    │ Cross-Validation │  │
│  └──────────────────┘    └──────────────────┘  │
│         ▲                        ▲              │
│         │                        │              │
│  ┌──────┴────────────────────────┴──────┐     │
│  │  Grid Search │ Random Search        │     │
│  └──────────────────────────────────────┘     │
│              ▲                                 │
│              │                                 │
│  ┌───────────┴──────────────────────────┐    │
│  │  Hyperparameter Tuner (Orchestrator) │    │
│  └────────────────────────────────────────┘   │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Components

### 1. Parameter Space (`parameter_space.py`)

**Purpose**: Define and manage hyperparameter search space

**Key Features**:
- ✅ Parameter type support (INT, FLOAT, CATEGORICAL)
- ✅ Range/value specification
- ✅ Configuration validation
- ✅ Pre-built search spaces

**Usage**:
```python
from src.training.hyperparameter_tuning import ParameterSpace, SearchSpace

# Create custom space
space = ParameterSpace()
space.add_int_parameter("n_estimators", 50, 500)
space.add_float_parameter("contamination", 0.01, 0.5)

# Or use predefined space
space = SearchSpace.isolation_forest_space()

# Validate config matches space
config = {"n_estimators": 100, "contamination": 0.1}
space.validate_config(config)
```

**Pre-defined Spaces**:
- `isolation_forest_space()`: Isolation Forest parameters
- `one_class_svm_space()`: One-Class SVM parameters
- `local_outlier_factor_space()`: LOF parameters

### 2. Cross-Validation (`cross_validation.py`)

**Purpose**: Implement multiple cross-validation strategies

**Key Features**:
- ✅ K-Fold cross-validation
- ✅ Stratified K-Fold
- ✅ Train/test split
- ✅ Fold generation and tracking

**Usage**:
```python
from src.training.hyperparameter_tuning import CrossValidator, CVStrategy

# Create validator
cv = CrossValidator(
    strategy=CVStrategy.KFOLD,
    n_splits=5,
    random_seed=42
)

# Generate folds
folds = cv.generate_folds(n_samples=1000)

# Access fold data
for fold in folds:
    train_indices = fold.train_indices
    test_indices = fold.test_indices
```

**Strategies**:
- `KFOLD`: Standard K-Fold splitting
- `STRATIFIED_KFOLD`: Stratified splitting (maintains class distribution)
- `TRAIN_TEST_SPLIT`: Single train/test split

### 3. Grid Search (`grid_search.py`)

**Purpose**: Exhaustive hyperparameter search

**Key Features**:
- ✅ Complete parameter space exploration
- ✅ Automatic grid generation
- ✅ Cross-validation evaluation
- ✅ Result tracking and ranking

**Usage**:
```python
from src.training.hyperparameter_tuning import GridSearchTuner, SearchSpace

# Create tuner
space = SearchSpace.isolation_forest_space()
tuner = GridSearchTuner(space)

# Define scoring function
def score_model(model, X_test):
    predictions = model.predict(X_test)
    return calculate_accuracy(predictions)

# Run grid search
results = tuner.search(
    model_class=IsolationForest,
    X_train=X_train,
    cv_validator=cv,
    scoring_func=score_model
)

# Get best configuration
best_config = tuner.get_best_config()
best_score = tuner.get_best_score()
```

**Performance**:
- Best for: Small parameter spaces
- Time complexity: O(n_combinations × n_folds)
- Space complexity: O(n_results)

### 4. Random Search (`random_search.py`)

**Purpose**: Efficient random sampling tuning

**Key Features**:
- ✅ Random parameter sampling
- ✅ Configurable iteration count
- ✅ Early stopping support
- ✅ Result tracking

**Usage**:
```python
from src.training.hyperparameter_tuning import RandomSearchTuner, RandomSearchConfig

# Configure Random Search
config = RandomSearchConfig(
    n_iter=20,        # Number of iterations
    random_seed=42,
    enable_early_stopping=True,
    early_stopping_rounds=5
)

# Create tuner
space = SearchSpace.isolation_forest_space()
tuner = RandomSearchTuner(space, config)

# Run search
results = tuner.search(
    model_class=IsolationForest,
    X_train=X_train,
    cv_validator=cv,
    scoring_func=score_model
)
```

**Performance**:
- Best for: Large parameter spaces
- Time complexity: O(n_iter × n_folds)
- Space complexity: O(n_iter × n_folds)
- Often better than Grid Search in practice

### 5. Hyperparameter Tuner (`tuner.py`)

**Purpose**: Orchestrate complete tuning workflow

**Key Features**:
- ✅ Strategy abstraction
- ✅ Automatic result tracking
- ✅ Unified interface
- ✅ Metadata reporting

**Usage**:
```python
from src.training.hyperparameter_tuning import (
    HyperparameterTuner, TuningConfig, TuningStrategy, SearchSpace
)

# Configure tuning
config = TuningConfig(
    strategy=TuningStrategy.RANDOM_SEARCH,
    param_space=SearchSpace.isolation_forest_space(),
    cv_splits=5,
    verbose=True
)

# Create tuner
tuner = HyperparameterTuner(config)

# Execute tuning
result = tuner.tune(
    model_class=IsolationForest,
    X_train=X_train,
    scoring_func=score_model
)

# Access results
print(f"Best config: {result.best_config}")
print(f"Best score: {result.best_score:.4f}")
print(f"Time taken: {result.tuning_time_seconds:.2f}s")
top_5 = result.get_top_configs(n=5)
```

## File Structure

```
src/training/hyperparameter_tuning/
├── __init__.py                      # Package exports
├── parameter_space.py               # Parameter space (280 lines)
├── cross_validation.py              # CV framework (320 lines)
├── grid_search.py                   # Grid Search (200 lines)
├── random_search.py                 # Random Search (240 lines)
└── tuner.py                         # Orchestrator (280 lines)

tests/training/
└── test_hyperparameter_tuning.py    # Tests (500+ lines)
```

## Example: Complete Tuning Workflow

```python
from src.training.hyperparameter_tuning import (
    HyperparameterTuner, 
    TuningConfig,
    TuningStrategy,
    SearchSpace,
    RandomSearchConfig
)
from sklearn.ensemble import IsolationForest

# 1. Load and prepare data
X_train = load_training_features()  # (1000, 3) array

# 2. Define data split scoring function
def evaluate_anomaly_detection(model, X_test):
    """Score based on anomaly detection consistency."""
    predictions = model.predict(X_test)
    anomaly_count = sum(1 for p in predictions if p == -1)
    # Prefer anomaly rates between 5-15%
    target_rate = 0.1
    actual_rate = anomaly_count / len(predictions)
    score = 1 - abs(actual_rate - target_rate)
    return score

# 3. Configure tuning
config = TuningConfig(
    strategy=TuningStrategy.RANDOM_SEARCH,
    param_space=SearchSpace.isolation_forest_space(),
    cv_splits=5,
    random_search_config=RandomSearchConfig(
        n_iter=30,
        enable_early_stopping=True,
        early_stopping_rounds=5
    ),
    verbose=True
)

# 4. Create and execute tuner
tuner = HyperparameterTuner(config)
result = tuner.tune(
    model_class=IsolationForest,
    X_train=X_train,
    scoring_func=evaluate_anomaly_detection
)

# 5. Process results
if result.status == "success":
    print(f"✅ Tuning completed in {result.tuning_time_seconds:.2f}s")
    print(f"📊 Best score: {result.best_score:.4f}")
    print(f"🎯 Best config: {result.best_config}")
    
    # Get top configurations
    top_5 = result.get_top_configs(n=5)
    for i, config_result in enumerate(top_5, 1):
        print(f"{i}. Score: {config_result['mean_score']:.4f}, Config: {config_result['config']}")
    
    # Train final model with best config
    final_model = IsolationForest(**result.best_config)
    final_model.fit(X_train)
    
    # Save for deployment
    save_model(final_model, "best_anomaly_detector.pkl")
```

## Test Coverage

**Total Tests**: 30+  
**Categories**:
- Parameter Space Tests: 10
- Cross-Validation Tests: 7
- Grid Search Tests: 4
- Random Search Tests: 4
- Tuner Tests: 7

**Test Scenarios**:
✅ Parameter space creation and validation  
✅ Multi-type parameter support (INT, FLOAT, CATEGORICAL)  
✅ K-Fold, Stratified K-Fold, Train/Test splitting  
✅ Grid generation and exhaustive search  
✅ Random parameter sampling  
✅ Early stopping in Random Search  
✅ Cross-validation evaluation  
✅ Result tracking and ranking  
✅ Strategy abstraction in orchestrator  

## Performance Characteristics

| Strategy | Time Complexity | Best For | Pros | Cons |
|----------|-----------------|----------|------|------|
| **Grid Search** | O(n_params^n_dims) | Small spaces | Exhaustive, simple | Exponential growth |
| **Random Search** | O(n_iter) | Large spaces | Efficient, can be better | May miss optima |
| **K-Fold CV** | O(k) | All | Robust | More computation |
| **Stratified K-Fold** | O(k) | Imbalanced | Balanced folds | Complex setup |

**Example Timings**:
- Random Search (20 iter, 5-fold CV): ~30-60 seconds on 1000 samples
- Grid Search (100 combos, 5-fold CV): ~2-5 minutes
- Early stopping: 20-30% time savings

## Configuration Reference

### TuningConfig
```python
TuningConfig(
    strategy=TuningStrategy.RANDOM_SEARCH,  # or GRID_SEARCH
    param_space=SearchSpace.isolation_forest_space(),
    cv_strategy=CVStrategy.KFOLD,
    cv_splits=5,
    cv_random_seed=42,
    random_search_config=RandomSearchConfig(n_iter=20),
    verbose=True,
    random_seed=42
)
```

### RandomSearchConfig
```python
RandomSearchConfig(
    n_iter=20,
    random_seed=42,
    verbose=True,
    enable_early_stopping=False,
    early_stopping_rounds=5,
    early_stopping_threshold=0.001
)
```

### GridSearchConfig
```python
GridSearchConfig(
    random_seed=42,
    verbose=True,
    n_jobs=1,  # Future: multi-process support
    enable_early_stopping=False
)
```

## Integration with Training Pipeline

Seamlessly integrates with the training pipeline:

```python
from src.training import TrainingPipeline, PipelineConfig
from src.training.hyperparameter_tuning import HyperparameterTuner, TuningConfig

# 1. Load data
pipeline = TrainingPipeline()
pipeline.load_data_from_json("telemetry.json")
pipeline.prepare_data()
pipeline.engineer_features()

# 2. Tune hyperparameters
tuning_config = TuningConfig()
tuner = HyperparameterTuner(tuning_config)
result = tuner.tune(
    IsolationForest,
    pipeline._train_features,
    scoring_func
)

# 3. Train with best config
trainer = pipeline.model_trainer
trainer.config.hyperparams = result.best_config
trainer.train(pipeline._train_features)
```

## Future Enhancements (70% remaining)

### Phase 2: Advanced Strategies
- [ ] Bayesian Optimization (scikit-optimize)
- [ ] Particle Swarm Optimization
- [ ] Differential Evolution
- [ ] Genetic Algorithms

### Phase 3: Advanced Features
- [ ] Warm starting
- [ ] Parallelization support
- [ ] Distributed tuning
- [ ] Remote hyperparameter tracking

### Phase 4: Analysis Tools
- [ ] Parameter importance analysis
- [ ] Visualization (contour plots, heatmaps)
- [ ] Tuning history exploration
- [ ] Comparative analysis utilities

### Phase 5: Production Features
- [ ] Model selection from tuning results
- [ ] Automatic config export
- [ ] Integration with model registry
- [ ] Automated retuning triggers

## Running Tests

```bash
# All tuning tests
pytest tests/training/test_hyperparameter_tuning.py -v

# Specific component
pytest tests/training/test_hyperparameter_tuning.py::TestGridSearch -v

# With coverage
pytest tests/training/ --cov=src.training.hyperparameter_tuning --cov-report=html

# Specific test
pytest tests/training/test_hyperparameter_tuning.py::TestHyperparameterTuner::test_tune_random_search -v
```

## Code Quality

- **Lines of Code**: 1,320+ (implementation) + 500+ (tests)
- **Test Coverage**: 30+ test cases
- **Type Hints**: Complete throughout
- **Documentation**: Comprehensive with examples
- **Error Handling**: Robust exception handling
- **Logging**: Detailed logging and progress tracking

## Dependencies

**Required**:
- Python 3.9+
- (From training pipeline)

**Optional**:
- scikit-learn (for actual model training)
- numpy (for numerical operations)

## References

- [Training Pipeline](TRAINING_PIPELINE.md)
- [Anomaly Detector](../../src/anomaly/anomaly_detector.py)
- [Contributing Guidelines](../../docs/CONTRIBUTING.md)

## Contributors

- Issue #584: Hyperparameter Tuning Implementation
- Category: machine-learning, training
- Status: In Progress (30% complete, core features done)
