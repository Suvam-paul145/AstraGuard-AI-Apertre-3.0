"""
Comprehensive test suite for training pipeline.

Tests cover:
- Data loading from multiple formats
- Data validation
- Feature engineering
- Model training
- Pipeline orchestration
"""

import pytest
import json
import tempfile
import os
from typing import List, Dict, Any

# Import training modules
from src.training.data_loader import DataLoader, DataConfig, DataValidationError
from src.training.feature_engineering import FeatureEngineer, FeatureConfig
from src.training.trainer import ModelTrainer, TrainingConfig
from src.training.pipeline import TrainingPipeline, PipelineConfig


# ========== Fixtures ==========

@pytest.fixture
def sample_telemetry_data() -> List[Dict[str, Any]]:
    """Generate sample telemetry data."""
    data = []
    for i in range(200):
        record = {
            "voltage": 8.0 + (0.5 if i % 10 == 0 else 0),  # Some anomalies
            "temperature": 25.0 + (15 if i % 8 == 0 else 0),
            "gyro": 0.01 * (i % 3),
            "current": 1.0 + (0.3 if i % 15 == 0 else 0),
            "wheel_speed": 5.0,
        }
        data.append(record)
    return data


@pytest.fixture
def sample_anomaly_data() -> List[Dict[str, Any]]:
    """Generate data with labeled anomalies."""
    data = []
    for i in range(150):
        if i < 100:
            # Normal data
            record = {
                "voltage": 8.0,
                "temperature": 25.0,
                "gyro": 0.01,
                "label": 0,  # Normal
            }
        else:
            # Anomalous data
            record = {
                "voltage": 7.0,  # Low voltage
                "temperature": 45.0,  # High temperature
                "gyro": 0.5,  # High gyro
                "label": 1,  # Anomaly
            }
        data.append(record)
    return data


@pytest.fixture
def temp_json_file(sample_telemetry_data):
    """Create temporary JSON file with test data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(sample_telemetry_data, f)
        filepath = f.name
    yield filepath
    os.unlink(filepath)


@pytest.fixture
def temp_csv_file(sample_telemetry_data):
    """Create temporary CSV file with test data."""
    import csv
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='') as f:
        writer = csv.DictWriter(f, fieldnames=sample_telemetry_data[0].keys())
        writer.writeheader()
        writer.writerows(sample_telemetry_data)
        filepath = f.name
    yield filepath
    os.unlink(filepath)


# ========== DataLoader Tests ==========

class TestDataLoader:
    """Tests for DataLoader component."""
    
    def test_data_loader_initialization(self):
        """Test DataLoader initialization."""
        config = DataConfig(train_test_split=0.75, random_seed=123)
        loader = DataLoader(config)
        assert loader.config.train_test_split == 0.75
        assert loader.config.random_seed == 123
    
    def test_load_from_list(self, sample_telemetry_data):
        """Test loading data from list."""
        loader = DataLoader()
        data = loader.load_from_list(sample_telemetry_data)
        assert len(data) == len(sample_telemetry_data)
        assert data[0]["voltage"] is not None
    
    def test_load_from_json(self, temp_json_file):
        """Test loading data from JSON file."""
        loader = DataLoader()
        data = loader.load_from_json(temp_json_file)
        assert len(data) > 0
        assert "voltage" in data[0]
    
    def test_load_from_csv(self, temp_csv_file):
        """Test loading data from CSV file."""
        loader = DataLoader()
        data = loader.load_from_csv(temp_csv_file)
        assert len(data) > 0
        assert "voltage" in data[0]
    
    def test_validate_data_success(self, sample_telemetry_data):
        """Test successful data validation."""
        loader = DataLoader()
        loader.validate_data(sample_telemetry_data)  # Should not raise
    
    def test_validate_data_insufficient_samples(self):
        """Test validation with insufficient samples."""
        loader = DataLoader(DataConfig(min_samples=1000))
        data = [{"voltage": 8.0, "temperature": 25.0, "gyro": 0.0}] * 100
        
        with pytest.raises(DataValidationError):
            loader.validate_data(data)
    
    def test_validate_data_missing_fields(self):
        """Test validation with missing required fields."""
        loader = DataLoader()
        data = [{"voltage": 8.0}] * 100  # Missing temperature and gyro
        
        with pytest.raises(DataValidationError):
            loader.validate_data(data)
    
    def test_split_train_test(self, sample_telemetry_data):
        """Test train/test split."""
        loader = DataLoader(DataConfig(train_test_split=0.8))
        train, test = loader.split_train_test(sample_telemetry_data)
        
        assert len(train) + len(test) == len(sample_telemetry_data)
        assert len(train) / len(sample_telemetry_data) == pytest.approx(0.8, abs=0.05)
    
    def test_split_validation(self, sample_telemetry_data):
        """Test validation split."""
        loader = DataLoader(DataConfig(validation_split=0.1))
        train, _ = loader.split_train_test(sample_telemetry_data)
        
        actual_train, validation = loader.split_validation(train)
        
        assert len(actual_train) + len(validation) == len(train)
        assert len(validation) / len(train) == pytest.approx(0.1, abs=0.05)


# ========== FeatureEngineer Tests ==========

class TestFeatureEngineer:
    """Tests for FeatureEngineer component."""
    
    def test_feature_engineer_initialization(self):
        """Test FeatureEngineer initialization."""
        config = FeatureConfig(scaling_method="zscore")
        engineer = FeatureEngineer(config)
        assert engineer.config.scaling_method == "zscore"
    
    def test_fit_scaler(self, sample_telemetry_data):
        """Test fitting scaling parameters."""
        engineer = FeatureEngineer()
        engineer.fit(sample_telemetry_data)
        
        assert engineer._is_fitted
        assert "voltage" in engineer._feature_min
    
    def test_extract_features(self, sample_telemetry_data):
        """Test feature extraction."""
        engineer = FeatureEngineer()
        features = engineer.extract_features(sample_telemetry_data[0])
        
        assert "voltage" in features
        assert "temperature" in features
        assert "gyro" in features
    
    def test_extract_features_missing_field(self):
        """Test feature extraction with missing field."""
        engineer = FeatureEngineer()
        record = {"voltage": 8.0}  # Missing temperature and gyro
        
        with pytest.raises(ValueError):
            engineer.extract_features(record)
    
    def test_scale_minmax(self, sample_telemetry_data):
        """Test min-max scaling."""
        engineer = FeatureEngineer(FeatureConfig(scaling_method="minmax"))
        engineer.fit(sample_telemetry_data)
        
        features = engineer.extract_features(sample_telemetry_data[0])
        scaled = engineer.scale_features(features)
        
        # Scaled values should be in [0, 1]
        assert all(0 <= v <= 1 for v in scaled.values())
    
    def test_scale_zscore(self, sample_telemetry_data):
        """Test z-score scaling."""
        engineer = FeatureEngineer(FeatureConfig(scaling_method="zscore"))
        engineer.fit(sample_telemetry_data)
        
        features = engineer.extract_features(sample_telemetry_data[0])
        scaled = engineer.scale_features(features)
        
        # Z-score scaled values should vary around 0
        assert "voltage" in scaled
    
    def test_transform_batch(self, sample_telemetry_data):
        """Test batch transformation."""
        engineer = FeatureEngineer()
        engineer.fit(sample_telemetry_data)
        
        vectors = engineer.transform_batch(sample_telemetry_data)
        
        assert len(vectors) == len(sample_telemetry_data)
        assert all(len(v) == 3 for v in vectors)  # 3 base features
    
    def test_derived_features(self, sample_telemetry_data):
        """Test derived feature computation."""
        config = FeatureConfig(compute_derivatives=True)
        engineer = FeatureEngineer(config)
        features = engineer.extract_features(sample_telemetry_data[0])
        
        # Should include derived features
        assert "voltage_temp_ratio" in features
        assert "gyro_intensity" in features
        assert "composite_score" in features


# ========== ModelTrainer Tests ==========

class TestModelTrainer:
    """Tests for ModelTrainer component."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_trainer_initialization(self):
        """Test ModelTrainer initialization."""
        config = TrainingConfig(model_type="isolation_forest")
        trainer = ModelTrainer(config)
        assert trainer.config.model_type == "isolation_forest"
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_build_isolation_forest(self):
        """Test building Isolation Forest model."""
        trainer = ModelTrainer(
            TrainingConfig(model_type="isolation_forest")
        )
        model = trainer.build_model()
        assert model is not None
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_train_model(self, sample_telemetry_data):
        """Test model training."""
        # Prepare features
        engineer = FeatureEngineer()
        engineer.fit(sample_telemetry_data)
        X_train = engineer.transform_batch(sample_telemetry_data)
        
        # Train model
        trainer = ModelTrainer(
            TrainingConfig(model_type="isolation_forest")
        )
        metadata = trainer.train(X_train)
        
        assert "model_type" in metadata
        assert "training_time_seconds" in metadata
        assert trainer._is_trained
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_evaluate_model(self, sample_anomaly_data):
        """Test model evaluation."""
        # Prepare features
        engineer = FeatureEngineer()
        engineer.fit(sample_anomaly_data)
        X_data = engineer.transform_batch(sample_anomaly_data)
        y_data = [r.get("label", 0) for r in sample_anomaly_data]
        
        # Train and evaluate
        trainer = ModelTrainer(
            TrainingConfig(model_type="isolation_forest")
        )
        trainer.train(X_data)
        metrics = trainer.evaluate(X_data, y_data)
        
        assert "anomaly_rate" in metrics
        assert "accuracy" in metrics or "n_anomalies_detected" in metrics
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_save_load_model(self, sample_telemetry_data, tmp_path):
        """Test model persistence."""
        # Train model
        engineer = FeatureEngineer()
        engineer.fit(sample_telemetry_data)
        X_train = engineer.transform_batch(sample_telemetry_data)
        
        trainer = ModelTrainer(
            TrainingConfig(model_type="isolation_forest")
        )
        trainer.train(X_train)
        
        # Save and load
        model_path = os.path.join(tmp_path, "test_model.pkl")
        trainer.save_model(model_path)
        
        assert os.path.exists(model_path)
        
        # Load into new trainer
        trainer2 = ModelTrainer()
        trainer2.load_model(model_path)
        assert trainer2._is_trained


# ========== TrainingPipeline Tests ==========

class TestTrainingPipeline:
    """Tests for TrainingPipeline orchestrator."""
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        config = PipelineConfig()
        pipeline = TrainingPipeline(config)
        assert pipeline._raw_data == []
    
    def test_pipeline_data_loading_from_list(self, sample_telemetry_data):
        """Test pipeline data loading."""
        pipeline = TrainingPipeline()
        pipeline.load_data_from_list(sample_telemetry_data)
        
        assert len(pipeline._raw_data) == len(sample_telemetry_data)
    
    def test_pipeline_validation(self, sample_telemetry_data):
        """Test pipeline validation stage."""
        pipeline = TrainingPipeline()
        pipeline.load_data_from_list(sample_telemetry_data)
        pipeline.validate_data()  # Should not raise
    
    def test_pipeline_data_preparation(self, sample_telemetry_data):
        """Test pipeline data preparation."""
        pipeline = TrainingPipeline()
        pipeline.load_data_from_list(sample_telemetry_data)
        pipeline.prepare_data()
        
        assert len(pipeline._train_data) > 0
        assert len(pipeline._test_data) > 0
    
    def test_pipeline_feature_engineering(self, sample_telemetry_data):
        """Test pipeline feature engineering."""
        pipeline = TrainingPipeline()
        pipeline.load_data_from_list(sample_telemetry_data)
        pipeline.prepare_data()
        pipeline.engineer_features()
        
        assert len(pipeline._train_features) > 0
        assert all(len(v) >= 3 for v in pipeline._train_features)
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_pipeline_training(self, sample_telemetry_data):
        """Test pipeline training."""
        pipeline = TrainingPipeline(
            PipelineConfig(
                training_config=TrainingConfig(
                    model_type="isolation_forest"
                )
            )
        )
        pipeline.load_data_from_list(sample_telemetry_data)
        pipeline.prepare_data()
        pipeline.engineer_features()
        
        metadata = pipeline.train_model()
        
        assert "model_type" in metadata
        assert pipeline.model_trainer._is_trained
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_full_pipeline_execution(self, sample_telemetry_data, tmp_path):
        """Test complete pipeline execution."""
        # Create temporary JSON file
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', dir=tmp_path, delete=False
        ) as f:
            json.dump(sample_telemetry_data, f)
            filepath = f.name
        
        # Run pipeline
        config = PipelineConfig(
            training_config=TrainingConfig(
                model_type="isolation_forest",
                model_save_path=os.path.join(tmp_path, "model.pkl")
            )
        )
        pipeline = TrainingPipeline(config)
        
        results = pipeline.run_full_pipeline(filepath, data_type="json")
        
        assert results["status"] == "success"
        assert results["n_raw_samples"] == len(sample_telemetry_data)
        assert os.path.exists(results["model_path"])


# ========== Integration Tests ==========

class TestTrainingIntegration:
    """Integration tests for complete training workflow."""
    
    @pytest.mark.skipif(
        not pytest.importorskip("sklearn", minversion=None),
        reason="scikit-learn not installed"
    )
    def test_end_to_end_training(self, sample_telemetry_data, tmp_path):
        """Test complete end-to-end training workflow."""
        # Create config
        config = PipelineConfig(
            data_config=DataConfig(train_test_split=0.8),
            feature_config=FeatureConfig(scaling_method="minmax"),
            training_config=TrainingConfig(
                model_type="isolation_forest",
                model_save_path=os.path.join(tmp_path, "trained_model.pkl")
            ),
        )
        
        # Run pipeline
        pipeline = TrainingPipeline(config)
        results = pipeline.run_full_pipeline(
            sample_telemetry_data, data_type="list"
        )
        
        # Verify results
        assert results["status"] == "success"
        assert "training_metadata" in results
        assert "evaluation_metrics" in results
        assert os.path.exists(results["model_path"])
        
        # Verify model can be used for predictions
        model = pipeline.get_model()
        assert model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
